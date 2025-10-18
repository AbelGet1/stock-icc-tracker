variable "app_name" {
  description = "Application name used for resource naming"
  type        = string
  default     = "stock-icc-tracker"
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
  default     = true
}

variable "default_watchlist" {
  description = "Default stocks to analyze"
  type        = list(string)
  default     = ["AAPL", "TSLA", "NVDA", "AMD", "MSFT", "GOOGL", "AMZN", "META"]
}

variable "default_timeframes" {
  description = "Default timeframes for analysis"
  type        = list(string)
  default     = ["1d", "4h"]
}

variable "alert_email" {
  description = "Email address for alerts (must be verified in SES)"
  type        = string
  default     = ""
}