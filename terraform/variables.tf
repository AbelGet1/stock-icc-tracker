variable "app_name" {
  description = "Application name used for resource naming"
  type        = string
  default     = "stockscout"
}

variable "environment" {
  description = "Environment (dev, staging, prod)"
  type        = string
  default     = "dev"
}

variable "aws_region" {
  description = "AWS region for resources"
  type        = string
  default     = "us-east-1"
}

variable "analysis_schedule" {
  description = "CloudWatch Events schedule expression for analysis"
  type        = string
  default     = "cron(0 14,20 ? * MON-FRI *)"  # 9 AM and 3 PM EST on weekdays
}

variable "enable_scheduled_analysis" {
  description = "Enable/disable scheduled analysis"
  type        = bool
  # Cost-first default: keep schedule off unless explicitly enabled.
  default     = false
}

variable "default_watchlist" {
  description = "Default stocks to analyze"
  type        = list(string)
  # Cost-first default: keep the list small to reduce API calls / compute.
  default     = ["AAPL"]
}

variable "default_timeframes" {
  description = "Default timeframes for analysis"
  type        = list(string)
  # Cost-first default: fewer intervals = less compute.
  default     = ["1d"]
}

variable "alert_email" {
  description = "Email address for alerts (must be verified in SES)"
  type        = string
  default     = ""
}

# Cost optimization variables
variable "lambda_memory_size" {
  description = "Lambda function memory size in MB (128, 256, 512, etc.)"
  type        = number
  default     = 256  # Reduced from 512 for cost savings
}

variable "lambda_timeout" {
  description = "Lambda function timeout in seconds"
  type        = number
  default     = 120  # Reduced from 300 for cost savings
}

variable "cloudwatch_log_retention_days" {
  description = "CloudWatch log retention in days"
  type        = number
  default     = 3  # Reduced from 7 for cost savings
}

variable "enable_s3_versioning" {
  description = "Enable S3 bucket versioning (increases storage costs)"
  type        = bool
  default     = false  # Disabled for cost savings
}

variable "enable_dynamodb_pitr" {
  description = "Enable DynamoDB Point-in-Time Recovery (adds ~20% cost)"
  type        = bool
  default     = false  # Disabled for cost savings
}

variable "enable_dynamodb_gsi" {
  description = "Enable DynamoDB Global Secondary Index on patterns table"
  type        = bool
  default     = false  # Disabled for cost savings
}

# Security variables
variable "ses_sender_email" {
  description = "Verified SES email address for sending alerts (restricts Lambda to only send from this address)"
  type        = string
  default     = ""  # Must be set and verified in SES before use
}