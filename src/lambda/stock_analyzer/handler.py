import json
import boto3
import pandas as pd
from datetime import datetime, timedelta
import os
from typing import Dict, List, Optional
from decimal import Decimal
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# AWS clients
dynamodb = boto3.resource('dynamodb')
s3 = boto3.client('s3')
ses = boto3.client('ses')

# Environment variables
PATTERNS_TABLE = os.environ.get('PATTERNS_TABLE', 'stock-icc-tracker-patterns')
STORAGE_BUCKET = os.environ.get('STORAGE_BUCKET', 'stock-icc-tracker-storage')
SUBSCRIPTIONS_TABLE = os.environ.get('SUBSCRIPTIONS_TABLE', 'stock-icc-tracker-subscriptions')

class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return super(DecimalEncoder, self).default(obj)

class ICCDetector:
    def __init__(self):
        self.patterns_table = dynamodb.Table(PATTERNS_TABLE)
        self.subscriptions_table = dynamodb.Table(SUBSCRIPTIONS_TABLE)
    
    def get_stock_data(self, symbol: str, period: str = "3mo", interval: str = "1d") -> Optional[pd.DataFrame]:
        """Get stock data using yfinance"""
        try:
            import yfinance as yf
            ticker = yf.Ticker(symbol)
            data = ticker.history(period=period, interval=interval)
            
            if data.empty:
                logger.warning(f"No data found for symbol: {symbol}")
                return None
                
            return data
        except Exception as e:
            logger.error(f"Error fetching data for {symbol}: {e}")
            return None
    
    def analyze_stock(self, symbol: str, timeframe: str = "1d") -> Dict:
        """Main analysis function for ICC pattern detection"""
        try:
            logger.info(f"Analyzing {symbol} on {timeframe} timeframe")
            
            # Get stock data
            data = self.get_stock_data(symbol, interval=timeframe)
            
            if data is None or data.empty:
                return {
                    "symbol": symbol,
                    "error": f"No data available for {symbol}",
                    "timestamp": datetime.now().isoformat()
                }
            
            # Perform ICC analysis
            indication = self.detect_indication(data)
            correction = self.detect_correction(data, indication)
            continuation = self.detect_continuation(data, indication, correction)
            
            # Calculate overall confidence
            confidence_score = self.calculate_confidence(indication, correction, continuation)
            
            # Prepare result
            result = {
                "symbol": symbol.upper(),
                "timestamp": datetime.now().isoformat(),
                "timeframe": timeframe,
                "current_price": float(data['Close'].iloc[-1]),
                "volume": float(data['Volume'].iloc[-1]) if 'Volume' in data.columns else 0,
                "indication": indication,
                "correction": correction,
                "continuation": continuation,
                "confidence_score": confidence_score,
                "pattern_status": self.determine_pattern_status(indication, correction, continuation),
                "recommendation": self.generate_recommendation(confidence_score, indication)
            }
            
            # Store analysis result
            self.store_analysis(result)
            
            logger.info(f"Analysis complete for {symbol}: confidence={confidence_score:.2%}")
            return result
            
        except Exception as e:
            logger.error(f"Error analyzing {symbol}: {e}")
            return {
                "symbol": symbol,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
    
    def detect_indication(self, data: pd.DataFrame) -> Dict:
        """Detect Break of Structure (BOS) - the Indication phase"""
        try:
            if len(data) < 20:
                return {
                    "detected": False,
                    "reason": "Insufficient data for analysis",
                    "confidence": 0.0
                }
            
            # Calculate swing highs and lows
            swing_window = 5
            recent_periods = 15
            
            # Get recent swing points
            highs = data['High'].rolling(window=swing_window, center=True).max()
            lows = data['Low'].rolling(window=swing_window, center=True).min()
            
            recent_data = data.tail(recent_periods)
            current_price = data['Close'].iloc[-1]
            current_high = data['High'].iloc[-1]
            current_low = data['Low'].iloc[-1]
            
            # Detect resistance/support breaks
            resistance_level = recent_data['High'].max()
            support_level = recent_data['Low'].min()
            
            # Check for breakouts with volume confirmation
            avg_volume = data['Volume'].tail(20).mean() if 'Volume' in data.columns else 1
            current_volume = data['Volume'].iloc[-1] if 'Volume' in data.columns else 1
            volume_spike = current_volume > avg_volume * 1.5
            
            # Bullish indication (resistance break)
            resistance_break = current_high > resistance_level * 1.002  # 0.2% break
            bullish_momentum = current_price > data['Close'].tail(5).mean()
            
            # Bearish indication (support break)
            support_break = current_low < support_level * 0.998  # 0.2% break
            bearish_momentum = current_price < data['Close'].tail(5).mean()
            
            if resistance_break and bullish_momentum:
                direction = "bullish"
                detected = True
                strength = (current_price - resistance_level) / resistance_level
                key_level = float(resistance_level)
            elif support_break and bearish_momentum:
                direction = "bearish"
                detected = True
                strength = (support_level - current_price) / support_level
                key_level = float(support_level)
            else:
                direction = "neutral"
                detected = False
                strength = 0.0
                key_level = float(current_price)
            
            # Calculate confidence based on multiple factors
            confidence = 0.0
            if detected:
                confidence += min(abs(strength) * 50, 0.4)  # Breakout strength
                if volume_spike:
                    confidence += 0.3  # Volume confirmation
                
                # Add momentum confirmation
                if direction == "bullish" and bullish_momentum:
                    confidence += 0.2
                elif direction == "bearish" and bearish_momentum:
                    confidence += 0.2
            
            return {
                "detected": detected,
                "direction": direction,
                "strength": float(strength),
                "key_level": key_level,
                "volume_confirmed": volume_spike,
                "confidence": min(confidence, 1.0),
                "timestamp": data.index[-1].isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error in indication detection: {e}")
            return {"detected": False, "error": str(e), "confidence": 0.0}
    
    def detect_correction(self, data: pd.DataFrame, indication: Dict) -> Dict:
        """Detect pullback/retracement - the Correction phase"""
        try:
            if not indication.get("detected", False):
                return {"detected": False, "reason": "No indication detected"}
            
            # Look for retracement in recent periods
            lookback = min(10, len(data) // 2)
            recent_data = data.tail(lookback)
            
            indication_level = indication.get("key_level", data['Close'].iloc[-1])
            current_price = data['Close'].iloc[-1]
            direction = indication.get("direction", "neutral")
            
            if direction == "bullish":
                # Look for pullback from highs
                high_since_indication = recent_data['High'].max()
                low_since_indication = recent_data['Low'].min()
                
                # Calculate retracement
                move_size = high_since_indication - indication_level
                pullback_size = high_since_indication - low_since_indication
                
                if move_size > 0:
                    retracement_pct = pullback_size / move_size
                else:
                    retracement_pct = 0
                
                # Ideal retracement is 30-70%
                detected = 0.3 <= retracement_pct <= 0.7 and low_since_indication < current_price
                
            else:  # bearish
                # Look for bounce from lows
                low_since_indication = recent_data['Low'].min()
                high_since_indication = recent_data['High'].max()
                
                # Calculate retracement
                move_size = indication_level - low_since_indication
                bounce_size = high_since_indication - low_since_indication
                
                if move_size > 0:
                    retracement_pct = bounce_size / move_size
                else:
                    retracement_pct = 0
                
                # Ideal retracement is 30-70%
                detected = 0.3 <= retracement_pct <= 0.7 and high_since_indication > current_price
            
            # Classify correction depth
            if retracement_pct < 0.3:
                depth = "shallow"
            elif retracement_pct <= 0.7:
                depth = "ideal"
            else:
                depth = "deep"
            
            return {
                "detected": detected,
                "retracement_percentage": float(retracement_pct * 100),
                "correction_depth": depth,
                "is_ideal_retracement": 0.3 <= retracement_pct <= 0.7,
                "confidence": 0.8 if detected else 0.2
            }
            
        except Exception as e:
            logger.error(f"Error in correction detection: {e}")
            return {"detected": False, "error": str(e)}
    
    def detect_continuation(self, data: pd.DataFrame, indication: Dict, correction: Dict) -> Dict:
        """Detect trend continuation - the Continuation phase"""
        try:
            if not indication.get("detected") or not correction.get("detected"):
                return {"detected": False, "reason": "Prerequisites not met"}
            
            current_price = data['Close'].iloc[-1]
            indication_level = indication.get("key_level", current_price)
            direction = indication.get("direction", "neutral")
            
            # Check for continuation beyond indication level
            if direction == "bullish":
                continuation = current_price > indication_level * 1.005  # 0.5% above
                strength = (current_price - indication_level) / indication_level
            else:
                continuation = current_price < indication_level * 0.995  # 0.5% below
                strength = (indication_level - current_price) / indication_level
            
            # Volume confirmation
            avg_volume = data['Volume'].tail(10).mean() if 'Volume' in data.columns else 1
            current_volume = data['Volume'].iloc[-1] if 'Volume' in data.columns else 1
            volume_confirmed = current_volume > avg_volume * 1.2
            
            return {
                "detected": continuation,
                "strength": float(abs(strength)),
                "volume_confirmed": volume_confirmed,
                "confidence": 0.7 if continuation and volume_confirmed else 0.3 if continuation else 0.1
            }
            
        except Exception as e:
            logger.error(f"Error in continuation detection: {e}")
            return {"detected": False, "error": str(e)}
    
    def calculate_confidence(self, indication: Dict, correction: Dict, continuation: Dict) -> float:
        """Calculate overall pattern confidence score"""
        try:
            confidence = 0.0
            
            # Indication confidence (40% weight)
            if indication.get("detected", False):
                indication_conf = indication.get("confidence", 0) * 0.4
                confidence += indication_conf
            
            # Correction confidence (30% weight)
            if correction.get("detected", False):
                correction_conf = correction.get("confidence", 0) * 0.3
                confidence += correction_conf
            
            # Continuation confidence (30% weight)
            if continuation.get("detected", False):
                continuation_conf = continuation.get("confidence", 0) * 0.3
                confidence += continuation_conf
            
            return min(confidence, 1.0)
            
        except Exception as e:
            logger.error(f"Error calculating confidence: {e}")
            return 0.0
    
    def determine_pattern_status(self, indication: Dict, correction: Dict, continuation: Dict) -> str:
        """Determine current pattern status"""
        if continuation.get("detected", False):
            return "CONTINUATION"
        elif correction.get("detected", False):
            return "CORRECTION"
        elif indication.get("detected", False):
            return "INDICATION"
        else:
            return "NO_PATTERN"
    
    def generate_recommendation(self, confidence: float, indication: Dict) -> str:
        """Generate trading recommendation"""
        if confidence < 0.3:
            return "NO_ACTION"
        elif confidence < 0.6:
            return "WATCH"
        elif confidence < 0.8:
            direction = indication.get("direction", "neutral")
            return f"CONSIDER_{direction.upper()}"
        else:
            direction = indication.get("direction", "neutral")
            return f"STRONG_{direction.upper()}"
    
    def store_analysis(self, result: Dict):
        """Store analysis result in DynamoDB"""
        try:
            # Convert floats to Decimal for DynamoDB
            item = json.loads(json.dumps(result), parse_float=Decimal)
            
            self.patterns_table.put_item(Item=item)
            logger.info(f"Stored analysis for {result['symbol']}")
            
        except Exception as e:
            logger.error(f"Error storing analysis: {e}")

def send_alert(analysis: Dict):
    """Send email alert for high-confidence patterns"""
    try:
        symbol = analysis['symbol']
        confidence = analysis['confidence_score']
        pattern_status = analysis['pattern_status']
        recommendation = analysis['recommendation']
        
        if confidence < 0.7:  # Only send alerts for high confidence
            return
        
        subject = f"🚨 ICC Pattern Alert: {symbol} - {pattern_status}"
        
        indication = analysis.get('indication', {})
        direction = indication.get('direction', 'unknown').upper()
        
        body = f"""
High-confidence ICC pattern detected for {symbol}!

📊 PATTERN ANALYSIS
Symbol: {symbol}
Status: {pattern_status}
Direction: {direction}
Confidence: {confidence:.1%}
Recommendation: {recommendation}

💰 PRICE DATA
Current Price: ${analysis['current_price']:.2f}
Key Level: ${indication.get('key_level', 0):.2f}

🔍 PATTERN DETAILS
Indication: {"✅" if indication.get('detected') else "❌"} {direction} breakout
Correction: {"✅" if analysis.get('correction', {}).get('detected') else "❌"} Retracement detected  
Continuation: {"✅" if analysis.get('continuation', {}).get('detected') else "❌"} Trend continuation

⏰ Analysis Time: {analysis['timestamp']}
📈 Timeframe: {analysis['timeframe']}

This is an automated alert from Stock ICC Tracker.
"""
        
        # Note: You need to set up and verify an email in AWS SES
        # For now, this will log the alert
        logger.info(f"ALERT: {subject}")
        logger.info(body)
        
        # Uncomment below when SES is configured
        # ses.send_email(
        #     Source='your-verified-email@domain.com',
        #     Destination={'ToAddresses': ['your-email@domain.com']},
        #     Message={
        #         'Subject': {'Data': subject},
        #         'Body': {'Text': {'Data': body}}
        #     }
        # )
        
    except Exception as e:
        logger.error(f"Error sending alert: {e}")

def main(event, context):
    """Lambda handler function"""
    try:
        logger.info(f"Starting ICC analysis with event: {event}")
        
        detector = ICCDetector()
        
        # Get symbols and timeframes from event or use defaults
        symbols = event.get('symbols', ['AAPL', 'TSLA', 'NVDA', 'AMD', 'MSFT'])
        timeframes = event.get('timeframes', ['1d'])
        
        results = []
        alerts_sent = 0
        
        for symbol in symbols:
            for timeframe in timeframes:
                try:
                    result = detector.analyze_stock(symbol.upper(), timeframe)
                    results.append(result)
                    
                    # Send alert if high confidence pattern
                    if result.get('confidence_score', 0) >= 0.7:
                        send_alert(result)
                        alerts_sent += 1
                        
                except Exception as e:
                    logger.error(f"Error analyzing {symbol}: {e}")
                    results.append({
                        "symbol": symbol,
                        "error": str(e),
                        "timestamp": datetime.now().isoformat()
                    })
        
        response = {
            'statusCode': 200,
            'body': json.dumps({
                'message': f'Analysis complete',
                'symbols_analyzed': len(symbols),
                'timeframes': timeframes,
                'total_analyses': len(results),
                'alerts_sent': alerts_sent,
                'results': results
            }, cls=DecimalEncoder)
        }
        
        return response
        
    except Exception as e:
        logger.error(f"Lambda handler error: {e}")
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': str(e),
                'message': 'Analysis failed'
            })
        }