# Stock ICC Tracker

Serverless Stock ICC Pattern Tracker - Reusable Trading Strategy Template

## Overview

The Stock ICC Tracker is a serverless application designed to analyze stock data and detect ICC (Indication, Correction, Continuation) patterns. It provides trading recommendations based on confidence scores and sends alerts for high-confidence patterns.

## Features

- **Stock Analysis**: Detects ICC patterns using historical stock data.
- **Serverless Architecture**: Built on AWS Lambda, DynamoDB, and S3.
- **Alerts**: Sends email alerts for high-confidence patterns via AWS SES.
- **Extensible**: Easily customizable for additional patterns or data sources.
- **Infrastructure as Code**: Managed using Terraform.

## Project Structure

```
.
├── .github/workflows/   # CI/CD workflows
├── docker/              # Docker configuration
├── scripts/             # Helper scripts for deployment and setup
├── src/                 # Source code
│   ├── api/             # FastAPI application
│   ├── lambda/          # AWS Lambda functions
│   └── utils/           # Utility modules
├── terraform/           # Terraform configuration for AWS resources
├── tests/               # Unit tests
├── Dockerfile           # Dockerfile for local development
├── requirements.txt     # Python dependencies
└── README.md            # Project documentation
```

## Getting Started

### Prerequisites

- Python 3.9+
- AWS CLI configured with appropriate permissions
- Terraform 1.3.0+
- Docker (optional for local development)

### Installation

1. Clone the repository:
   ```sh
   git clone https://github.com/your-username/stock-icc-tracker.git
   cd stock-icc-tracker

2. Install Dependencies 
    python -m pip install --upgrade pip
    pip install -r requirements.txt

3. Setup env variables 
    cp .env.example .env

4. Initialize Terraform
    cd terraform
    terraform init


###### Running Locally 
1. Start the FastAPI server: 
    uvicorn src.api.main:app --reload

2. Access the API at http://127.0.0.1:8000.


##### Deployment 
1. Deploy Infrastructure using Terraform 
    terraform apply -auto-approve

2. Deploy the Lambda function 
    zip -r stock_analyzer.zip src/lambda/stock_analyzer/
    aws lambda update-function-code \
        --function-name stock-icc-tracker-analyzer \
        --zip-file fileb://stock_analyzer.zip


##### Usage 

API Endpoints
- Analyze Stocks: /analyze
    Request: 
        {
            "symbols": ["AAPL", "TSLA"],
            "timeframes": ["1d", "4h"]
        }

    Response:
        {
        "results": [
            {
            "symbol": "AAPL",
            "confidence_score": 0.85,
            "recommendation": "STRONG_BUY"
            }
          ]
        }

Subscribe to Alerts: /subscribe
    Request:
        {
        "email": "user@example.com",
        "symbols": ["AAPL", "TSLA"]
        }

Scheduled Analysis
The analysis runs automatically based on the schedule defined in the Terraform configuration (cron(0 14,20 ? * MON-FRI *)).

##### Testing
Run unit tests using pytest: pytest tests/


#### CI/CD
- Testing Workflow: test.yml
- Deployment Workflow: deploy.yml

#### Contributing
Contributions are welcome! Please open an issue or submit a pull request.

#### License
This project is licensed under the MIT License.

