# Stock ICC Tracker - Claude Instructions

## Project Overview
A stock analysis system that combines ICC (Inverted Cup and Handle) pattern detection with ML-based predictions, targeting S&P 500 top 50 stocks.

## Current Goal
Transform rule-based ICC pattern detection into a hybrid ML system using technical indicators as features for classification.

## Architecture
- **Training**: GitHub Actions (weekly) → S3 (model storage)
- **Inference**: Lambda loads pre-trained model from S3 → DynamoDB (results)
- **Model**: Random Forest Classifier - Binary classification for "Will stock gain >2% in 5 trading days?"

## Key Files
- `src/lambda/stock_analyzer/handler.py` - Main Lambda handler for stock analysis
- `src/api/main.py` - FastAPI endpoints
- `terraform/main.tf` - Infrastructure definitions

## Implementation Phases

### Phase 1: Technical Indicators (Current)
Create `src/utils/indicators.py` with: RSI, MACD, Bollinger Bands, SMA/EMA, ATR, Volume ratio, Stochastic Oscillator

### Phase 2: ML Training Infrastructure
- `src/config/sp500_top50.py` - Stock watchlist
- `scripts/train_model.py` - Training script
- `.github/workflows/train_model.yml` - Weekly automation

### Phase 3: Lambda ML Integration
- Model loading from S3
- Combine ICC pattern + ML prediction
- Confidence scores with beginner-friendly interpretation

### Phase 4: Email Alerts
- SES integration for high-confidence signals

## Preferences
<!-- Add your preferences here -->
-
-
-

## Notes
<!-- Add any additional context or constraints here -->
-
-
-
