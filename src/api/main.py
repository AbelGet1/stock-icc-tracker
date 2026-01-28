from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import List, Optional
import boto3
import json
from datetime import datetime
import os

app = FastAPI(title="Stock ICC Tracker API", version="1.0.0")

# AWS clients
lambda_client = boto3.client('lambda')
dynamodb = boto3.resource('dynamodb')

# Environment variables
LAMBDA_FUNCTION_NAME = os.environ.get('LAMBDA_FUNCTION_NAME', 'stock-icc-tracker-analyzer')
PATTERNS_TABLE_NAME = os.environ.get('PATTERNS_TABLE_NAME', 'stock-icc-tracker-patterns')
SUBSCRIPTIONS_TABLE_NAME = os.environ.get('SUBSCRIPTIONS_TABLE_NAME', 'stock-icc-tracker-subscriptions')

class AnalysisRequest(BaseModel):
    symbols: List[str]
    timeframes: Optional[List[str]] = ["1d"]

class AlertSubscription(BaseModel):
    email: str
    symbols: List[str]
    min_confidence: Optional[float] = 0.7

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