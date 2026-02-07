# Deployment Guide

This guide explains how to set up and deploy the StockScout application using GitHub Actions.

## Prerequisites

1. AWS Account with appropriate permissions
2. GitHub repository with Actions enabled
3. AWS credentials configured as GitHub Secrets

## Required GitHub Secrets

Configure the following secrets in your GitHub repository settings (Settings → Secrets and variables → Actions):

- `AWS_ACCESS_KEY_ID`: Your AWS access key ID
- `AWS_SECRET_ACCESS_KEY`: Your AWS secret access key
- `AWS_REGION`: AWS region (default: `us-east-1`)

## Terraform Configuration

### Backend Configuration

The current Terraform configuration uses **local state** by default. For production deployments, consider using an S3 backend:

1. Create an S3 bucket for Terraform state:
   ```bash
   aws s3 mb s3://your-terraform-state-bucket
   aws s3api put-bucket-versioning \
     --bucket your-terraform-state-bucket \
     --versioning-configuration Status=Enabled
   ```

2. Add backend configuration to `terraform/main.tf`:
   ```hcl
   terraform {
     backend "s3" {
       bucket         = "your-terraform-state-bucket"
       key            = "stockscout/terraform.tfstate"
       region         = "us-east-1"
       encrypt        = true
       dynamodb_table = "terraform-state-lock"  # Optional: for state locking
     }
   }
   ```

### Terraform Variables

Create a `terraform/terraform.tfvars` file (or use GitHub Secrets for sensitive values):

```hcl
app_name = "stockscout"
environment = "prod"
aws_region = "us-east-1"
enable_scheduled_analysis = true
default_watchlist = ["AAPL", "TSLA", "NVDA", "AMD", "MSFT"]
default_timeframes = ["1d", "4h"]
```

## Deployment Process

### Automatic Deployment

The deployment workflow (`deploy.yml`) automatically runs when you push to the `main` branch:

1. **Checkout code**: Retrieves the latest code
2. **Configure AWS credentials**: Sets up AWS CLI with GitHub Secrets
3. **Terraform operations**:
   - Format check
   - Initialize Terraform
   - Validate configuration
   - Plan changes
   - Apply infrastructure
4. **Package Lambda**: Creates deployment package
5. **Deploy Lambda**: Updates Lambda function code

### Manual Deployment

You can also trigger deployment manually:

1. Go to Actions tab in GitHub
2. Select "Deploy" workflow
3. Click "Run workflow"

### Local Deployment

For local testing:

```bash
# Set up AWS credentials
export AWS_ACCESS_KEY_ID=your-key
export AWS_SECRET_ACCESS_KEY=your-secret
export AWS_REGION=us-east-1

# Initialize Terraform
cd terraform
terraform init

# Review changes
terraform plan

# Apply infrastructure
terraform apply

# Deploy Lambda function
cd ..
zip -r stock_analyzer.zip src/lambda/stock_analyzer/
aws lambda update-function-code \
  --function-name stockscout-analyzer \
  --zip-file fileb://stock_analyzer.zip
```

## Troubleshooting

### Common Issues

1. **Terraform state lock**: If deployment fails due to state lock, wait a few minutes or manually unlock:
   ```bash
   terraform force-unlock <LOCK_ID>
   ```

2. **Lambda deployment fails**: Ensure the Lambda function exists (created by Terraform) before updating code.

3. **AWS credentials**: Verify GitHub Secrets are correctly configured and have necessary permissions.

4. **Terraform version mismatch**: The workflow uses Terraform 1.6.0. Ensure your local version matches or update the workflow.

### Required AWS Permissions

Your AWS credentials need permissions for:
- Lambda (create, update, invoke)
- DynamoDB (create tables, read/write)
- S3 (create buckets, read/write)
- CloudWatch Events (create rules)
- IAM (create roles and policies)
- CloudWatch Logs (create log groups)

### Monitoring

After deployment, monitor:
- CloudWatch Logs for Lambda execution logs
- DynamoDB tables for pattern storage
- S3 bucket for chart/data storage
- CloudWatch Metrics for Lambda performance

## Post-Deployment

1. **Verify Lambda function**: Check AWS Console that function exists and has correct environment variables
2. **Test API**: If using FastAPI, ensure it's deployed and accessible
3. **Configure SES**: Set up and verify email addresses in AWS SES for alerts
4. **Test scheduled analysis**: Verify EventBridge rule triggers Lambda correctly
