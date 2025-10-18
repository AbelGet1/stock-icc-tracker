output "lambda_function_name" {
  description = "Name of the Lambda function"
  value       = aws_lambda_function.stock_analyzer.function_name
}

output "s3_bucket_name" {
  description = "Name of the S3 storage bucket"
  value       = aws_s3_bucket.app_storage.bucket
}

output "dynamodb_patterns_table" {
  description = "Name of the patterns DynamoDB table"
  value       = aws_dynamodb_table.stock_patterns.name
}

output "dynamodb_subscriptions_table" {
  description = "Name of the subscriptions DynamoDB table"
  value       = aws_dynamodb_table.subscriptions.name
}

output "aws_region" {
  description = "AWS region"
  value       = var.aws_region
}
