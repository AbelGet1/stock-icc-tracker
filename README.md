# StockScout

**Daily stock tracker with ML-powered insights for informed decision-making.**

StockScout analyzes S&P 500 stocks using machine learning to identify favorable market conditions. It's designed as an educational tool to help you understand market signals - not as a trading signal generator.

## What It Does

- Analyzes stocks using 15+ technical indicators (RSI, MACD, Bollinger Bands, etc.)
- Predicts probability of 1%+ gain in the next 5 trading days
- Provides confidence-based signals with beginner-friendly explanations
- Runs on serverless AWS infrastructure for minimal cost (~$0.30/month)

## User Modes

| Mode | Precision | Best For |
|------|-----------|----------|
| **Beginner** | 90% | New investors - only high-confidence signals |
| **Balanced** | 83% | Most users - good balance of signals and accuracy |
| **Moderate** | 74% | Experienced - more signals, standard threshold |
| **Aggressive** | 64% | Active traders - catches more opportunities |

## Quick Start

```bash
# Clone and install
git clone https://github.com/your-username/stockscout.git
cd stockscout
pip install -r requirements.txt

# Run locally
uvicorn src.api.main:app --reload

# Access API at http://127.0.0.1:8000
```

## API Usage

### Get Prediction
```bash
curl -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -d '{"symbols": ["AAPL", "MSFT"], "mode": "balanced"}'
```

### Response
```json
{
  "predictions": [
    {
      "symbol": "AAPL",
      "probability": 0.72,
      "signal": true,
      "signal_strength": "strong",
      "interpretation": "Strong positive indicators - favorable market conditions"
    }
  ],
  "disclaimer": "This is not investment advice."
}
```

## Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /` | Health check |
| `GET /modes` | Available user modes and thresholds |
| `GET /model/info` | Current model version and metrics |
| `POST /predict` | Get ML predictions for stocks |
| `GET /predict/{symbol}` | Quick single-stock prediction |
| `GET /threshold-analysis` | Precision/recall at different thresholds |

## Deployment

### AWS (Serverless)
```bash
cd terraform
terraform init
terraform apply
```

### Environment Variables
Copy `.env.example` to `.env` and configure:
- `API_KEY` - Enable authentication (recommended for production)
- `RATE_LIMIT_REQUESTS` - Requests per hour (default: 100)
- `MAX_SYMBOLS_PER_REQUEST` - Symbols per request (default: 5)

## Cost Optimization

Designed for minimal AWS costs:
- Lambda: Pay only for execution time
- DynamoDB: On-demand pricing
- No always-on servers
- **Target: <$2/month**

## Model Performance

Current model (v1.2.0):
- Training data: 2+ years of S&P 500 top 50 stocks
- Cross-validation F1: ~56%
- At 0.55 threshold: 83% precision, 55% recall

## Important Disclaimer

This tool provides **educational market analysis, not investment advice**.
- Past performance does not predict future results
- All investments carry risk of loss
- Consult a licensed financial advisor before investing

## License

MIT License
