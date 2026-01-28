"""
ICC Pattern Detection Utilities

This module provides utilities for detecting ICC (Indication, Correction, Continuation) patterns
in stock price data. ICC patterns are commonly used in trading to identify potential entry points.
"""

from typing import Dict, List, Optional
import pandas as pd
import numpy as np
from datetime import datetime

def calculate_support_resistance(data: pd.DataFrame, window: int = 20) -> Dict[str, float]:
    """
    Calculate support and resistance levels from price data
    
    Args:
        data: DataFrame with OHLCV data
        window: Rolling window size for calculation
        
    Returns:
        Dictionary with support and resistance levels
    """
    if len(data) < window:
        current_price = data['Close'].iloc[-1]
        return {
            "support": current_price * 0.95,
            "resistance": current_price * 1.05
        }
    
    recent_data = data.tail(window)
    
    # Support: lowest low in the window
    support = recent_data['Low'].min()
    
    # Resistance: highest high in the window
    resistance = recent_data['High'].max()
    
    return {
        "support": float(support),
        "resistance": float(resistance)
    }

def detect_volume_spike(data: pd.DataFrame, threshold: float = 1.5) -> bool:
    """
    Detect if current volume is significantly higher than average
    
    Args:
        data: DataFrame with Volume column
        threshold: Multiplier for average volume to consider a spike
        
    Returns:
        True if volume spike detected
    """
    if 'Volume' not in data.columns or len(data) < 10:
        return False
    
    avg_volume = data['Volume'].tail(20).mean()
    current_volume = data['Volume'].iloc[-1]
    
    return current_volume > (avg_volume * threshold)

def calculate_momentum(data: pd.DataFrame, periods: int = 5) -> float:
    """
    Calculate price momentum
    
    Args:
        data: DataFrame with Close prices
        periods: Number of periods to look back
        
    Returns:
        Momentum value (positive = bullish, negative = bearish)
    """
    if len(data) < periods + 1:
        return 0.0
    
    current_price = data['Close'].iloc[-1]
    past_price = data['Close'].iloc[-(periods + 1)]
    
    return float((current_price - past_price) / past_price)

def identify_swing_points(data: pd.DataFrame, window: int = 5) -> Dict[str, List]:
    """
    Identify swing highs and lows in price data
    
    Args:
        data: DataFrame with OHLCV data
        window: Window size for swing detection
        
    Returns:
        Dictionary with lists of swing highs and lows
    """
    if len(data) < window * 2:
        return {"highs": [], "lows": []}
    
    highs = []
    lows = []
    
    for i in range(window, len(data) - window):
        # Check for swing high
        if data['High'].iloc[i] == data['High'].iloc[i-window:i+window+1].max():
            highs.append({
                "index": i,
                "price": float(data['High'].iloc[i]),
                "timestamp": data.index[i]
            })
        
        # Check for swing low
        if data['Low'].iloc[i] == data['Low'].iloc[i-window:i+window+1].min():
            lows.append({
                "index": i,
                "price": float(data['Low'].iloc[i]),
                "timestamp": data.index[i]
            })
    
    return {"highs": highs, "lows": lows}

def calculate_fibonacci_levels(high: float, low: float) -> Dict[str, float]:
    """
    Calculate Fibonacci retracement levels
    
    Args:
        high: High price
        low: Low price
        
    Returns:
        Dictionary with Fibonacci levels
    """
    diff = high - low
    
    return {
        "0.0": high,
        "0.236": high - (diff * 0.236),
        "0.382": high - (diff * 0.382),
        "0.5": high - (diff * 0.5),
        "0.618": high - (diff * 0.618),
        "0.786": high - (diff * 0.786),
        "1.0": low
    }

def validate_pattern_completeness(indication: Dict, correction: Dict, continuation: Dict) -> bool:
    """
    Validate if all phases of ICC pattern are detected
    
    Args:
        indication: Indication phase detection result
        correction: Correction phase detection result
        continuation: Continuation phase detection result
        
    Returns:
        True if pattern is complete
    """
    return (
        indication.get("detected", False) and
        correction.get("detected", False) and
        continuation.get("detected", False)
    )
