# StockScout - Project Context for Claude

This document serves as the comprehensive project brain for Claude interactions. It contains all context needed for future development sessions.

## Project Identity

**Name**: StockScout (formerly stock-icc-tracker)
**Purpose**: Daily stock tracker with ML-powered insights for informed decision-making
**Philosophy**: Educational tool to help users understand market signals - NOT a trading signal generator

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                         StockScout Architecture                      │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌──────────────┐     ┌──────────────┐     ┌──────────────┐        │
│  │   GitHub     │     │   AWS S3     │     │  DynamoDB    │        │
│  │   Actions    │────▶│   (Models)   │     │  (Results)   │        │
│  │  (Training)  │     └──────────────┘     └──────────────┘        │
│  └──────────────┘            │                    ▲                 │
│         │                    ▼                    │                 │
│         │              ┌──────────────┐           │                 │
│         └─────────────▶│   Lambda     │───────────┘                 │
│                        │  (Inference) │                             │
│                        └──────────────┘                             │
│                              ▲                                      │
│                              │                                      │
│                        ┌──────────────┐                             │
│                        │   FastAPI    │◀──── User Requests          │
│                        │   (API)      │                             │
│                        └──────────────┘                             │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

## Key Constraints

### Cost Target: <$2/month
This is the **#1 priority**. All architectural decisions must respect this constraint:
- Lambda over EC2 (pay per execution)
- DynamoDB on-demand billing
- No always-on infrastructure
- Rate limiting and daily caps
- Maximum 5 symbols per request

### Security Requirements
- API key authentication (optional but recommended)
- Rate limiting: 100 requests/hour per IP
- Daily limit: 500 requests total
- Input validation and sanitization
- CORS restrictions
- Security headers on all responses
- No public access to tokens/secrets

## Directory Structure

```
stockscout/
├── .github/
│   ├── workflows/
│   │   ├── deploy.yml          # Infrastructure deployment
│   │   ├── train_model.yml     # Weekly model training
│   │   └── test.yml            # CI tests
│   └── DEPLOYMENT.md           # Deployment guide
├── docs/
│   └── RISK_FRAMEWORK.md       # Risk management philosophy
├── models/                      # Trained models (gitignored)
│   ├── current_model.joblib    # ~46MB Random Forest model
│   └── current_metadata.json   # Model version, metrics, features
├── scripts/
│   └── train_model.py          # ML training script
├── src/
│   ├── api/
│   │   └── main.py             # FastAPI application (700+ lines)
│   ├── config/
│   │   └── sp500_top50.py      # Stock watchlist
│   ├── lambda/
│   │   └── stock_analyzer/
│   │       └── handler.py      # Lambda function
│   └── utils/
│       └── indicators.py       # Technical indicators (15+)
├── terraform/
│   ├── main.tf                 # AWS infrastructure
│   └── variables.tf            # Terraform variables
├── tests/
│   └── test_indicators.py      # Unit tests
├── .env.example                # Environment template
├── CLAUDE.md                   # This file
├── README.md                   # User documentation
└── requirements.txt            # Python dependencies
```

## ML Model Details

### Current Model (v1.2.0)
- **Type**: Random Forest Classifier
- **Trees**: 500, Max Depth: 12
- **Target**: Binary classification - "Will stock gain >1% in 5 trading days?"
- **Training Data**: 2+ years of S&P 500 top 50 stocks (~47,000 samples)

### Features (15 total)
| Feature | Description | Importance |
|---------|-------------|------------|
| `spy_vs_sma20` | S&P 500 vs its 20-day SMA | ~15% (highest) |
| `spy_rsi` | S&P 500 RSI | ~12% |
| `spy_volatility` | S&P 500 20-day volatility | ~10% |
| `price_vs_sma_20` | Stock price vs 20-day SMA | ~8% |
| `rsi` | Stock RSI (14-day) | ~7% |
| `macd_histogram` | MACD histogram value | ~6% |
| `bb_position` | Bollinger Band position | ~6% |
| `volume_ratio` | Volume vs 20-day average | ~5% |
| `atr_pct` | ATR as % of price | ~5% |
| `stoch_k` | Stochastic %K | ~4% |
| ... | (5 more features) | ~22% combined |

**Key Insight**: Market-wide features (SPY indicators) account for ~40% of predictive power.

### Performance Metrics
| Threshold | Precision | Recall | F1 | Use Case |
|-----------|-----------|--------|----|----|
| 0.45 | 64% | 88% | 74% | Aggressive mode |
| 0.50 | 74% | 74% | 74% | Moderate mode |
| 0.55 | 83% | 55% | 66% | Balanced mode (default) |
| 0.60 | 90% | 37% | 52% | Beginner mode |

### Training Schedule
- **Frequency**: Weekly (Sunday night via GitHub Actions)
- **Validation**: Time-series cross-validation (no future data leakage)
- **Output**: Model saved to S3, metadata includes threshold analysis

## API Endpoints

### Core Endpoints
| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/` | GET | Health check |
| `/modes` | GET | List user modes and thresholds |
| `/model/info` | GET | Model metadata and version |
| `/predict` | POST | Get predictions for multiple stocks |
| `/predict/{symbol}` | GET | Single stock prediction |
| `/threshold-analysis` | GET | Precision/recall curves |

### Legacy Endpoints (ICC Pattern)
| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/analyze` | POST | Invoke Lambda for pattern analysis |
| `/subscribe` | POST | Email alert subscription |
| `/patterns` | GET | List recent patterns |
| `/patterns/{symbol}` | GET | Patterns for specific stock |

## User Modes

```python
MODE_THRESHOLDS = {
    "beginner": {
        "threshold": 0.60,
        "expected_precision": 0.90,
        "expected_recall": 0.37,
        "description": "Conservative - only high-confidence signals"
    },
    "balanced": {
        "threshold": 0.55,
        "expected_precision": 0.83,
        "expected_recall": 0.55,
        "description": "Recommended default"
    },
    "moderate": {
        "threshold": 0.50,
        "expected_precision": 0.74,
        "expected_recall": 0.74,
        "description": "Standard threshold"
    },
    "aggressive": {
        "threshold": 0.45,
        "expected_precision": 0.64,
        "expected_recall": 0.88,
        "description": "Catches more opportunities"
    }
}
```

## Security Implementation

### Rate Limiting (src/api/main.py)
```python
RATE_LIMIT_REQUESTS = 100  # per window
RATE_LIMIT_WINDOW = 3600   # 1 hour
MAX_SYMBOLS_PER_REQUEST = 5
MAX_REQUESTS_PER_DAY = 500
```

### Input Validation
- Symbols: alphanumeric + dots/dashes only, max 10 chars
- Email: RFC 5321 compliant, max 254 chars
- All inputs sanitized before processing

### Security Headers
- X-Frame-Options: DENY
- X-Content-Type-Options: nosniff
- X-XSS-Protection: 1; mode=block
- Content-Security-Policy: default-src 'none'

## Risk Framework

### Signal Confidence Levels
| Probability | Display to User |
|-------------|-----------------|
| 0.0 - 0.35 | "Market conditions uncertain" |
| 0.35 - 0.50 | "Slightly bearish signals" |
| 0.50 - 0.60 | "Mixed signals - no clear direction" |
| 0.60 - 0.70 | "Some positive indicators" |
| 0.70 - 0.85 | "Favorable conditions detected" |
| 0.85 - 1.0 | "Strong positive signals" (rare) |

### Required Disclaimer
Every prediction response includes:
> "This is not investment advice. Past performance does not guarantee future results."

## AWS Resources (Terraform)

| Resource | Name Pattern | Purpose |
|----------|--------------|---------|
| S3 Bucket | stockscout-storage-{random} | Model storage, charts |
| DynamoDB | stockscout-patterns | Pattern analysis results |
| DynamoDB | stockscout-subscriptions | Email subscriptions |
| Lambda | stockscout-analyzer | Stock analysis |
| EventBridge | stockscout-analysis-schedule | Scheduled triggers |
| IAM Role | stockscout-lambda-role | Lambda permissions |

## Development Workflow

### Local Development
```bash
# Install dependencies
pip install -r requirements.txt
pip install -r requirements-training.txt  # For ML training

# Run API locally
uvicorn src.api.main:app --reload

# Train model locally
python scripts/train_model.py --optimize balanced
```

### Testing
```bash
pytest tests/ -v
```

### Deployment
```bash
cd terraform
terraform init
terraform plan
terraform apply
```

## Common Tasks

### Add New Technical Indicator
1. Add to `src/utils/indicators.py`
2. Include in `get_ml_features()` return dict
3. Retrain model: `python scripts/train_model.py`
4. Verify feature importance in metadata

### Change Classification Threshold
1. Update `MODE_THRESHOLDS` in `src/api/main.py`
2. Or use custom_threshold in API request

### Add New Stock to Watchlist
1. Edit `src/config/sp500_top50.py`
2. Stocks automatically included in next training run

## Known Issues & Limitations

1. **yfinance rate limiting**: May fail with too many concurrent requests
2. **Model staleness**: Needs weekly retraining to stay current
3. **In-memory rate limiting**: Resets on Lambda cold start (use Redis for production)
4. **Homebrew on M1/M2**: User has Intel Homebrew, may cause issues

## Future Enhancements (Backlog)

1. **Phase 2**: Risk scoring for individual stocks
2. **Phase 3**: Walk-forward backtesting + performance transparency
3. **Phase 4**: Market regime detection + adaptive behavior
4. **Redis rate limiting**: For production scalability
5. **Frontend dashboard**: React/Next.js visualization

## Environment Variables

```bash
# Security
API_KEY=                    # Optional API key for auth
ALLOWED_ORIGINS=            # CORS allowed origins
ENABLE_DOCS=false           # Disable OpenAPI docs in prod

# Rate Limiting
RATE_LIMIT_REQUESTS=100
RATE_LIMIT_WINDOW=3600
MAX_SYMBOLS_PER_REQUEST=5
MAX_REQUESTS_PER_DAY=500

# AWS
AWS_REGION=us-east-1
LAMBDA_FUNCTION_NAME=stockscout-analyzer
PATTERNS_TABLE_NAME=stockscout-patterns
SUBSCRIPTIONS_TABLE_NAME=stockscout-subscriptions

# Model
MODEL_PATH=models/current_model.joblib
METADATA_PATH=models/current_metadata.json
```

## Conversation History Notes

- User prioritizes cost (<$2/month) above all else
- User prefers beginner-friendly explanations
- User has M2 Mac but had Intel Homebrew installed
- Project started as ICC pattern detector, evolved to ML-based predictions
- Name "StockScout" chosen from RISK_FRAMEWORK.md suggestions

---

*Last updated: February 2026*
*Model version: 1.2.0*
