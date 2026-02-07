from fastapi import FastAPI, HTTPException, BackgroundTasks, Query, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from pydantic import BaseModel, Field, field_validator
from typing import List, Optional, Dict, Any
from enum import Enum
import boto3
import json
from datetime import datetime
import os
import joblib
import numpy as np
import pandas as pd
from collections import defaultdict
import time
import re


# =============================================================================
# SECURITY HEADERS MIDDLEWARE
# =============================================================================

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to all responses"""
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        # Prevent clickjacking
        response.headers["X-Frame-Options"] = "DENY"
        # Prevent MIME sniffing
        response.headers["X-Content-Type-Options"] = "nosniff"
        # XSS protection
        response.headers["X-XSS-Protection"] = "1; mode=block"
        # Referrer policy
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        # Content Security Policy
        response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
        return response

# =============================================================================
# COST PROTECTION CONFIGURATION (Target: <$2/month)
# =============================================================================

# Rate limiting - prevent API abuse
RATE_LIMIT_REQUESTS = int(os.environ.get("RATE_LIMIT_REQUESTS", "100"))  # per window
RATE_LIMIT_WINDOW = int(os.environ.get("RATE_LIMIT_WINDOW", "3600"))  # seconds (1 hour)

# Input limits - prevent expensive operations
MAX_SYMBOLS_PER_REQUEST = int(os.environ.get("MAX_SYMBOLS_PER_REQUEST", "5"))
MAX_REQUESTS_PER_DAY = int(os.environ.get("MAX_REQUESTS_PER_DAY", "500"))

# API key protection (optional - set in environment)
API_KEY = os.environ.get("API_KEY", None)  # If set, requires X-API-Key header

# Simple in-memory rate limiter (use Redis in production)
_rate_limit_store: Dict[str, list] = defaultdict(list)
_daily_request_count = {"count": 0, "date": datetime.now().date()}


def check_rate_limit(client_ip: str) -> bool:
    """Check if client has exceeded rate limit"""
    now = time.time()
    window_start = now - RATE_LIMIT_WINDOW

    # Clean old entries
    _rate_limit_store[client_ip] = [
        t for t in _rate_limit_store[client_ip] if t > window_start
    ]

    # Check limit
    if len(_rate_limit_store[client_ip]) >= RATE_LIMIT_REQUESTS:
        return False

    # Record request
    _rate_limit_store[client_ip].append(now)
    return True


def check_daily_limit() -> bool:
    """Check if daily request limit exceeded (cost protection)"""
    today = datetime.now().date()
    if _daily_request_count["date"] != today:
        _daily_request_count["count"] = 0
        _daily_request_count["date"] = today

    if _daily_request_count["count"] >= MAX_REQUESTS_PER_DAY:
        return False

    _daily_request_count["count"] += 1
    return True


async def rate_limit_dependency(request: Request):
    """FastAPI dependency for rate limiting"""
    client_ip = request.client.host if request.client else "unknown"

    # Check API key if configured
    if API_KEY:
        provided_key = request.headers.get("X-API-Key")
        if provided_key != API_KEY:
            raise HTTPException(
                status_code=401,
                detail="Invalid or missing API key. Set X-API-Key header."
            )

    # Check rate limit
    if not check_rate_limit(client_ip):
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded. Max {RATE_LIMIT_REQUESTS} requests per {RATE_LIMIT_WINDOW}s."
        )

    # Check daily limit (cost protection)
    if not check_daily_limit():
        raise HTTPException(
            status_code=429,
            detail=f"Daily limit exceeded ({MAX_REQUESTS_PER_DAY} requests). Try again tomorrow."
        )


# =============================================================================
# CORS CONFIGURATION (Security: Restrict origins)
# =============================================================================

# Allowed origins - restrict in production
ALLOWED_ORIGINS = os.environ.get("ALLOWED_ORIGINS", "").split(",") if os.environ.get("ALLOWED_ORIGINS") else []

app = FastAPI(
    title="Stock ICC Tracker API",
    version="2.0.0",
    description="ML-powered stock analysis with configurable risk modes",
    dependencies=[Depends(rate_limit_dependency)],  # Apply rate limiting globally
    docs_url="/docs" if os.environ.get("ENABLE_DOCS", "false").lower() == "true" else None,  # Disable docs in prod
    redoc_url=None,  # Disable redoc
    openapi_url="/openapi.json" if os.environ.get("ENABLE_DOCS", "false").lower() == "true" else None
)

# Add CORS middleware with restrictive settings
if ALLOWED_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=ALLOWED_ORIGINS,  # Only allow specified origins
        allow_credentials=False,
        allow_methods=["GET", "POST"],  # Only allow needed methods
        allow_headers=["X-API-Key", "Content-Type"],  # Only allow needed headers
        max_age=86400,  # Cache preflight for 24 hours
    )
else:
    # Development mode - still restrictive
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["X-API-Key", "Content-Type"],
    )

# Add security headers to all responses
app.add_middleware(SecurityHeadersMiddleware)


# =============================================================================
# USER MODE CONFIGURATION
# =============================================================================

class UserMode(str, Enum):
    """User experience modes with different risk tolerances"""
    BEGINNER = "beginner"      # High precision (0.60 threshold) - fewer but safer signals
    BALANCED = "balanced"      # Balanced (0.55 threshold) - recommended default
    MODERATE = "moderate"      # Standard (0.50 threshold) - more signals
    AGGRESSIVE = "aggressive"  # Lower threshold (0.45) - most signals, lower precision


# Threshold configurations per mode
MODE_THRESHOLDS = {
    UserMode.BEGINNER: {
        "threshold": 0.60,
        "expected_precision": 0.90,
        "expected_recall": 0.37,
        "description": "Conservative mode - only shows high-confidence signals"
    },
    UserMode.BALANCED: {
        "threshold": 0.55,
        "expected_precision": 0.83,
        "expected_recall": 0.55,
        "description": "Balanced mode - good precision with reasonable coverage"
    },
    UserMode.MODERATE: {
        "threshold": 0.50,
        "expected_precision": 0.74,
        "expected_recall": 0.74,
        "description": "Standard mode - equal precision and recall"
    },
    UserMode.AGGRESSIVE: {
        "threshold": 0.45,
        "expected_precision": 0.64,
        "expected_recall": 0.88,
        "description": "Aggressive mode - catches more opportunities but less precise"
    }
}


# =============================================================================
# MODEL LOADING
# =============================================================================

MODEL_PATH = os.environ.get('MODEL_PATH', os.path.join(
    os.path.dirname(__file__), '..', '..', 'models', 'current_model.joblib'
))
METADATA_PATH = os.environ.get('METADATA_PATH', os.path.join(
    os.path.dirname(__file__), '..', '..', 'models', 'current_metadata.json'
))

# Global model cache
_model_cache = None
_metadata_cache = None


def load_model():
    """Load the ML model (cached)"""
    global _model_cache, _metadata_cache

    if _model_cache is None:
        try:
            _model_cache = joblib.load(MODEL_PATH)
            with open(METADATA_PATH, 'r') as f:
                _metadata_cache = json.load(f)
        except FileNotFoundError:
            raise HTTPException(
                status_code=503,
                detail="Model not found. Please ensure the model is trained and deployed."
            )

    return _model_cache, _metadata_cache


def get_model_info() -> Dict[str, Any]:
    """Get model metadata"""
    _, metadata = load_model()
    return {
        "version": metadata.get("version"),
        "trained_at": metadata.get("timestamp"),
        "features_count": len(metadata.get("feature_names", [])),
        "training_samples": metadata.get("metrics", {}).get("n_samples"),
        "cv_f1_score": metadata.get("metrics", {}).get("cv_f1_mean"),
        "threshold_analysis": metadata.get("metrics", {}).get("threshold_analysis", [])
    }

# AWS clients
# NOTE: boto3 requires a region; in CI/tests we may not have AWS config.
AWS_REGION = os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION") or "us-east-1"
lambda_client = boto3.client("lambda", region_name=AWS_REGION)
dynamodb = boto3.resource("dynamodb", region_name=AWS_REGION)

# Environment variables
LAMBDA_FUNCTION_NAME = os.environ.get('LAMBDA_FUNCTION_NAME', 'stock-icc-tracker-analyzer')
PATTERNS_TABLE_NAME = os.environ.get('PATTERNS_TABLE_NAME', 'stock-icc-tracker-patterns')
SUBSCRIPTIONS_TABLE_NAME = os.environ.get('SUBSCRIPTIONS_TABLE_NAME', 'stock-icc-tracker-subscriptions')

class AnalysisRequest(BaseModel):
    symbols: List[str] = Field(..., max_length=MAX_SYMBOLS_PER_REQUEST)
    timeframes: Optional[List[str]] = Field(default=["1d"], max_length=3)

    @field_validator('symbols')
    @classmethod
    def validate_symbols(cls, v):
        if len(v) > MAX_SYMBOLS_PER_REQUEST:
            raise ValueError(f"Maximum {MAX_SYMBOLS_PER_REQUEST} symbols per request")
        return [s.upper()[:10] for s in v]  # Sanitize


class PredictionRequest(BaseModel):
    """Request for ML prediction on stocks"""
    symbols: List[str] = Field(..., description="List of stock symbols to analyze")
    mode: Optional[UserMode] = Field(
        default=UserMode.BALANCED,
        description="User mode determines signal threshold"
    )
    custom_threshold: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Override mode threshold with custom value (0.0-1.0)"
    )

    @field_validator('symbols')
    @classmethod
    def validate_symbols(cls, v):
        if len(v) > MAX_SYMBOLS_PER_REQUEST:
            raise ValueError(f"Maximum {MAX_SYMBOLS_PER_REQUEST} symbols per request (cost protection)")
        if len(v) == 0:
            raise ValueError("At least one symbol required")
        # Sanitize symbols - only allow alphanumeric and dots
        for symbol in v:
            if not symbol.replace('.', '').replace('-', '').isalnum():
                raise ValueError(f"Invalid symbol format: {symbol}")
            if len(symbol) > 10:
                raise ValueError(f"Symbol too long: {symbol}")
        return [s.upper() for s in v]


class AlertSubscription(BaseModel):
    email: str = Field(..., max_length=254)  # RFC 5321 max length
    symbols: List[str] = Field(..., max_length=MAX_SYMBOLS_PER_REQUEST)
    min_confidence: Optional[float] = Field(default=0.7, ge=0.0, le=1.0)
    mode: Optional[UserMode] = Field(
        default=UserMode.BALANCED,
        description="User mode for signal filtering"
    )

    @field_validator('email')
    @classmethod
    def validate_email(cls, v):
        # Basic email validation to prevent injection
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, v):
            raise ValueError("Invalid email format")
        if len(v) > 254:
            raise ValueError("Email too long")
        return v.lower()

    @field_validator('symbols')
    @classmethod
    def validate_symbols(cls, v):
        if len(v) > MAX_SYMBOLS_PER_REQUEST:
            raise ValueError(f"Maximum {MAX_SYMBOLS_PER_REQUEST} symbols")
        for symbol in v:
            if not symbol.replace('.', '').replace('-', '').isalnum():
                raise ValueError(f"Invalid symbol format: {symbol}")
        return [s.upper()[:10] for s in v]


class UserPreferences(BaseModel):
    """User preference settings"""
    user_id: str
    mode: UserMode = UserMode.BALANCED
    custom_threshold: Optional[float] = None
    show_educational_tips: bool = True
    risk_acknowledgment: bool = False  # Required for aggressive mode

@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "Stock ICC Tracker API",
        "version": "1.0.0"
    }

@app.post("/analyze")
async def analyze_stocks(request: AnalysisRequest, background_tasks: BackgroundTasks):
    """
    Analyze stocks for ICC patterns
    
    Triggers Lambda function to analyze the provided symbols
    """
    try:
        # Invoke Lambda function asynchronously
        response = lambda_client.invoke(
            FunctionName=LAMBDA_FUNCTION_NAME,
            InvocationType='RequestResponse',  # Synchronous for API response
            Payload=json.dumps({
                "symbols": request.symbols,
                "timeframes": request.timeframes
            })
        )
        
        # Parse Lambda response
        response_payload = json.loads(response['Payload'].read())
        
        if response_payload.get('statusCode') == 200:
            return response_payload.get('body', {})
        else:
            raise HTTPException(
                status_code=500,
                detail=response_payload.get('body', {}).get('error', 'Analysis failed')
            )
            
    except lambda_client.exceptions.ResourceNotFoundException:
        raise HTTPException(
            status_code=503,
            detail=f"Lambda function '{LAMBDA_FUNCTION_NAME}' not found. Please ensure it's deployed."
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/subscribe")
async def subscribe_alerts(subscription: AlertSubscription):
    """
    Subscribe to email alerts for specific stocks
    
    Stores subscription in DynamoDB
    """
    try:
        subscriptions_table = dynamodb.Table(SUBSCRIPTIONS_TABLE_NAME)
        
        item = {
            "email": subscription.email,
            "symbols": subscription.symbols,
            "min_confidence": subscription.min_confidence,
            "created_at": datetime.now().isoformat(),
            "active": True
        }
        
        subscriptions_table.put_item(Item=item)
        
        return {
            "message": "Subscription created successfully",
            "email": subscription.email,
            "symbols": subscription.symbols
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/patterns/{symbol}")
async def get_patterns(symbol: str, limit: Optional[int] = 10):
    """
    Get recent pattern analysis results for a symbol
    """
    try:
        patterns_table = dynamodb.Table(PATTERNS_TABLE_NAME)
        
        # Query patterns for the symbol
        response = patterns_table.query(
            KeyConditionExpression="symbol = :symbol",
            ExpressionAttributeValues={":symbol": symbol.upper()},
            Limit=limit,
            ScanIndexForward=False  # Most recent first
        )
        
        return {
            "symbol": symbol.upper(),
            "count": len(response.get('Items', [])),
            "patterns": response.get('Items', [])
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/patterns")
async def list_all_patterns(limit: Optional[int] = 20):
    """
    List recent pattern analyses across all symbols
    """
    try:
        patterns_table = dynamodb.Table(PATTERNS_TABLE_NAME)

        # Scan table (limited for cost)
        response = patterns_table.scan(Limit=limit)

        # Sort by timestamp if available
        items = response.get('Items', [])
        items.sort(key=lambda x: x.get('timestamp', ''), reverse=True)

        return {
            "count": len(items),
            "patterns": items[:limit]
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# ML PREDICTION ENDPOINTS
# =============================================================================

@app.get("/modes")
async def get_available_modes():
    """
    Get available user modes and their configurations

    Returns threshold settings and expected performance for each mode.
    """
    return {
        "modes": {
            mode.value: {
                **config,
                "threshold": config["threshold"],
                "expected_precision_pct": f"{config['expected_precision']:.0%}",
                "expected_recall_pct": f"{config['expected_recall']:.0%}"
            }
            for mode, config in MODE_THRESHOLDS.items()
        },
        "default_mode": UserMode.BALANCED.value,
        "recommendation": "Use 'beginner' mode if you're new to investing"
    }


@app.get("/model/info")
async def get_model_metadata():
    """
    Get information about the currently loaded ML model

    Returns training date, performance metrics, and feature count.
    """
    try:
        info = get_model_info()
        return {
            "model": info,
            "status": "loaded",
            "modes_available": list(MODE_THRESHOLDS.keys())
        }
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/predict")
async def predict_stocks(request: PredictionRequest):
    """
    Get ML predictions for stocks with configurable thresholds

    Uses the trained model to predict probability of 1%+ gain in 5 days.
    The mode parameter controls how conservative the signals are.

    - **beginner**: Only high-confidence signals (90% precision)
    - **balanced**: Good balance (83% precision, 55% recall)
    - **moderate**: Standard threshold (74% precision/recall)
    - **aggressive**: More signals (64% precision, 88% recall)
    """
    try:
        model, metadata = load_model()
        feature_names = metadata.get("feature_names", [])

        # Determine threshold
        if request.custom_threshold is not None:
            threshold = request.custom_threshold
            mode_info = {"custom": True, "threshold": threshold}
        else:
            mode_config = MODE_THRESHOLDS[request.mode]
            threshold = mode_config["threshold"]
            mode_info = {
                "mode": request.mode.value,
                "threshold": threshold,
                "expected_precision": mode_config["expected_precision"],
                "description": mode_config["description"]
            }

        # Import indicators for feature generation
        import sys
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
        from utils.indicators import get_ml_features

        import yfinance as yf

        results = []
        for symbol in request.symbols:
            try:
                # Fetch recent data
                ticker = yf.Ticker(symbol)
                data = ticker.history(period="1y", interval="1d")

                if data.empty or len(data) < 200:
                    results.append({
                        "symbol": symbol.upper(),
                        "error": "Insufficient data",
                        "signal": None
                    })
                    continue

                # Generate features
                features = get_ml_features(data)

                # Create feature vector (matching training order)
                feature_vector = []
                for fname in feature_names:
                    if fname in features:
                        feature_vector.append(features[fname])
                    else:
                        feature_vector.append(0.0)  # Default for missing

                # Get prediction probability
                X = np.array([feature_vector])
                probability = model.predict_proba(X)[0][1]

                # Apply threshold
                signal = probability >= threshold
                signal_strength = "strong" if probability >= 0.70 else \
                                  "moderate" if probability >= 0.55 else \
                                  "weak" if probability >= 0.45 else "none"

                result = {
                    "symbol": symbol.upper(),
                    "probability": round(float(probability), 4),
                    "signal": signal,
                    "signal_strength": signal_strength,
                    "threshold_used": threshold,
                    "interpretation": _interpret_signal(signal, probability, request.mode)
                }

                # Add educational content for beginners
                if request.mode == UserMode.BEGINNER:
                    result["educational_note"] = _get_educational_note(signal, probability)

                results.append(result)

            except Exception as e:
                results.append({
                    "symbol": symbol.upper(),
                    "error": str(e),
                    "signal": None
                })

        return {
            "predictions": results,
            "mode_info": mode_info,
            "timestamp": datetime.now().isoformat(),
            "disclaimer": "This is not investment advice. Past performance does not guarantee future results."
        }

    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def _interpret_signal(signal: bool, probability: float, mode: UserMode) -> str:
    """Generate human-readable interpretation of the signal"""
    if not signal:
        if probability >= 0.40:
            return "Mixed signals - conditions are uncertain"
        else:
            return "Unfavorable conditions detected"

    if probability >= 0.70:
        return "Strong positive indicators - favorable market conditions"
    elif probability >= 0.60:
        return "Good positive indicators - market conditions look favorable"
    elif probability >= 0.55:
        return "Moderate positive indicators - some favorable signals"
    else:
        return "Slight positive indicators - proceed with caution"


def _get_educational_note(signal: bool, probability: float) -> str:
    """Get educational content for beginner users"""
    if signal and probability >= 0.60:
        return (
            "This signal indicates the model found favorable patterns based on "
            "market-wide trends (S&P 500 momentum) and technical indicators. "
            "Remember: this is one data point among many you should consider. "
            "Never invest more than you can afford to lose."
        )
    elif signal:
        return (
            "This is a moderate signal. The model found some positive patterns, "
            "but confidence is not high. Consider researching the company's "
            "fundamentals before making any decisions."
        )
    else:
        return (
            "No positive signal was detected. This doesn't necessarily mean "
            "the stock will decline - it means the model didn't find strong "
            "enough positive patterns in current conditions."
        )


@app.get("/predict/{symbol}")
async def predict_single_stock(
    symbol: str,
    mode: UserMode = Query(default=UserMode.BALANCED, description="User mode")
):
    """
    Quick prediction for a single stock

    Convenience endpoint for single-stock lookups.
    """
    request = PredictionRequest(symbols=[symbol], mode=mode)
    result = await predict_stocks(request)
    return result["predictions"][0] if result["predictions"] else {"error": "No result"}


@app.get("/threshold-analysis")
async def get_threshold_analysis():
    """
    Get detailed threshold analysis from the trained model

    Shows precision/recall trade-offs at different thresholds.
    Useful for understanding how mode selection affects signal quality.
    """
    try:
        info = get_model_info()
        analysis = info.get("threshold_analysis", [])

        return {
            "analysis": analysis,
            "recommended_thresholds": {
                "high_precision_80": next(
                    (t for t in analysis if t.get("precision", 0) >= 0.80),
                    None
                ),
                "balanced_f1": max(analysis, key=lambda x: x.get("f1", 0)) if analysis else None,
                "high_recall_80": next(
                    (t for t in reversed(analysis) if t.get("recall", 0) >= 0.80),
                    None
                )
            },
            "note": "Higher thresholds = higher precision, lower recall (fewer but more accurate signals)"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))