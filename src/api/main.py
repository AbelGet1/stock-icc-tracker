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

class AnalysisRequest(BaseModel):
    symbols: List[str]
    timeframes: Optional[List[str]] = ["1d"]

class AlertSubscription(BaseModel):
    email: str
    symbols: List[str]
    min_