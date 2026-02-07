terraform {
  required_version = ">= 1.0"
  
  # Backend configuration - uncomment and configure for remote state
  # For local development, state is stored locally
  # For production, use S3 backend:
  # backend "s3" {
  #   bucket         = "your-terraform-state-bucket"
  #   key            = "stockscout/terraform.tfstate"
  #   region         = "us-east-1"
  #   encrypt        = true
  #   dynamodb_table = "terraform-state-lock"
  # }
  
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.1"
    }
    archive = {
      source  = "hashicorp/archive"
      version = "~> 2.2"
    }
  }
}

provider "aws" {
  region = var.aws_region
  
  default_tags {
    tags = {
      Project     = var.app_name
      Environment = var.environment
      ManagedBy   = "Terraform"
    }
  }
}

# Get current AWS account ID for IAM policies
data "aws_caller_identity" "current" {}

# Generate random suffix for unique resource names
resource "random_id" "suffix" {
  byte_length = 4
}

# S3 Bucket for charts and data storage
resource "aws_s3_bucket" "app_storage" {
  bucket = "${var.app_name}-storage-${random_id.suffix.hex}"
}

resource "aws_s3_bucket_versioning" "app_storage" {
  count  = var.enable_s3_versioning ? 1 : 0
  bucket = aws_s3_bucket.app_storage.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "app_storage" {
  bucket = aws_s3_bucket.app_storage.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "app_storage" {
  bucket = aws_s3_bucket.app_storage.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# DynamoDB Table for storing pattern analysis results
resource "aws_dynamodb_table" "stock_patterns" {
  name           = "${var.app_name}-patterns"
  billing_mode   = "PAY_PER_REQUEST"
  hash_key       = "symbol"
  range_key      = "timestamp"

  attribute {
    name = "symbol"
    type = "S"
  }

  attribute {
    name = "timestamp"
    type = "S"
  }

  attribute {
    name = "confidence_score"
    type = "N"
  }

  dynamic "global_secondary_index" {
    for_each = var.enable_dynamodb_gsi ? [1] : []
    content {
      name     = "ConfidenceIndex"
      hash_key = "confidence_score"
      projection_type = "ALL"
    }
  }

  point_in_time_recovery {
    enabled = var.enable_dynamodb_pitr
  }
}

# DynamoDB Table for alert subscriptions
resource "aws_dynamodb_table" "subscriptions" {
  name           = "${var.app_name}-subscriptions"
  billing_mode   = "PAY_PER_REQUEST"
  hash_key       = "email"

  attribute {
    name = "email"
    type = "S"
  }

  point_in_time_recovery {
    enabled = var.enable_dynamodb_pitr
  }
}

# IAM Role for Lambda functions
resource "aws_iam_role" "lambda_role" {
  name = "${var.app_name}-lambda-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })
}

# IAM Policy for Lambda functions
resource "aws_iam_role_policy" "lambda_policy" {
  name = "${var.app_name}-lambda-policy"
  role = aws_iam_role.lambda_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:${var.aws_region}:*:*"
      },
      {
        Effect = "Allow"
        Action = [
          "dynamodb:GetItem",
          "dynamodb:PutItem",
          "dynamodb:Query",
          "dynamodb:Scan",
          "dynamodb:UpdateItem",
          "dynamodb:DeleteItem"
        ]
        Resource = [
          aws_dynamodb_table.stock_patterns.arn,
          "${aws_dynamodb_table.stock_patterns.arn}/*",
          aws_dynamodb_table.subscriptions.arn,
          "${aws_dynamodb_table.subscriptions.arn}/*"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject"
        ]
        Resource = "${aws_s3_bucket.app_storage.arn}/*"
      },
      {
        Effect = "Allow"
        Action = [
          "ses:SendEmail",
          "ses:SendRawEmail"
        ]
        # Restrict SES to only verified identities in this region/account
        # This prevents sending from arbitrary email addresses
        Resource = "arn:aws:ses:${var.aws_region}:${data.aws_caller_identity.current.account_id}:identity/*"
        Condition = {
          StringEquals = {
            "ses:FromAddress" = var.ses_sender_email
          }
        }
      }
    ]
  })
}

# Lambda function zip
data "archive_file" "stock_analyzer" {
  type        = "zip"
  source_dir  = "${path.module}/../src/lambda/stock_analyzer"
  output_path = "${path.module}/stock_analyzer.zip"
}

# Main Lambda function for stock analysis
resource "aws_lambda_function" "stock_analyzer" {
  filename         = data.archive_file.stock_analyzer.output_path
  function_name    = "${var.app_name}-analyzer"
  role            = aws_iam_role.lambda_role.arn
  handler         = "handler.main"
  source_code_hash = data.archive_file.stock_analyzer.output_base64sha256
  runtime          = "python3.9"
  timeout          = var.lambda_timeout
  memory_size      = var.lambda_memory_size

  environment {
    variables = {
      PATTERNS_TABLE = aws_dynamodb_table.stock_patterns.name
      STORAGE_BUCKET = aws_s3_bucket.app_storage.bucket
      SUBSCRIPTIONS_TABLE = aws_dynamodb_table.subscriptions.name
    }
  }
}

# CloudWatch Log Group for Lambda
resource "aws_cloudwatch_log_group" "lambda_logs" {
  name              = "/aws/lambda/${aws_lambda_function.stock_analyzer.function_name}"
  retention_in_days = var.cloudwatch_log_retention_days
}

# EventBridge rule for scheduled analysis
resource "aws_cloudwatch_event_rule" "stock_analysis_schedule" {
  name                = "${var.app_name}-analysis-schedule"
  description         = "Trigger stock analysis during market hours"
  schedule_expression = var.analysis_schedule
  state               = var.enable_scheduled_analysis ? "ENABLED" : "DISABLED"
}

resource "aws_cloudwatch_event_target" "stock_analysis_target" {
  rule      = aws_cloudwatch_event_rule.stock_analysis_schedule.name
  target_id = "StockAnalysisTarget"
  arn       = aws_lambda_function.stock_analyzer.arn

  input = jsonencode({
    symbols = var.default_watchlist
    timeframes = var.default_timeframes
  })
}

resource "aws_lambda_permission" "allow_eventbridge" {
  statement_id  = "AllowExecutionFromEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.stock_analyzer.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.stock_analysis_schedule.arn
}