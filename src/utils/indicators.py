"""
Technical Indicators Module for Stock ICC Tracker

Provides technical analysis indicators to enhance ML-based pattern detection.
All indicators are designed to work with pandas DataFrames from yfinance.
"""

import pandas as pd
import numpy as np
from typing import Dict, Optional, Tuple
from dataclasses import dataclass


# Beginner-friendly indicator definitions
INDICATOR_DEFINITIONS = {
    "rsi": {
        "name": "Relative Strength Index (RSI)",
        "what_it_is": "A momentum indicator that measures the speed and magnitude of recent price changes to evaluate overbought or oversold conditions.",
        "how_to_read": "RSI ranges from 0 to 100. Above 70 suggests the stock may be overbought (potentially overvalued). Below 30 suggests it may be oversold (potentially undervalued).",
        "signals": {
            "overbought": "RSI > 70: Stock may be overvalued. Consider waiting for a pullback before buying.",
            "oversold": "RSI < 30: Stock may be undervalued. Could be a buying opportunity.",
            "bullish_momentum": "RSI 50-70: Upward momentum. Buyers are in control.",
            "bearish_momentum": "RSI 30-50: Downward momentum. Sellers are in control."
        }
    },
    "macd": {
        "name": "Moving Average Convergence Divergence (MACD)",
        "what_it_is": "A trend-following momentum indicator that shows the relationship between two moving averages of a stock's price.",
        "how_to_read": "MACD consists of the MACD line, signal line, and histogram. When MACD crosses above the signal line, it's bullish. When it crosses below, it's bearish.",
        "signals": {
            "bullish_crossover": "MACD crossed above signal line: Potential uptrend starting. Consider buying.",
            "bearish_crossover": "MACD crossed below signal line: Potential downtrend starting. Consider selling.",
            "bullish": "MACD above signal line: Uptrend in progress.",
            "bearish": "MACD below signal line: Downtrend in progress."
        }
    },
    "bollinger": {
        "name": "Bollinger Bands",
        "what_it_is": "A volatility indicator consisting of a middle band (20-day average) and upper/lower bands that are 2 standard deviations away.",
        "how_to_read": "Price near the upper band may indicate overbought conditions. Price near the lower band may indicate oversold conditions. Narrow bands (squeeze) often precede big moves.",
        "signals": {
            "at_upper_band": "Price at upper band: Stock may be overbought. Watch for potential reversal.",
            "at_lower_band": "Price at lower band: Stock may be oversold. Watch for potential bounce.",
            "within_bands": "Price within bands: Normal trading range.",
            "squeeze_active": "Bands are narrow (squeeze): Low volatility period. A breakout may be coming."
        }
    },
    "stochastic": {
        "name": "Stochastic Oscillator",
        "what_it_is": "A momentum indicator comparing a stock's closing price to its price range over a given period.",
        "how_to_read": "Ranges from 0 to 100. Above 80 is overbought, below 20 is oversold. %K crossing above %D is bullish, crossing below is bearish.",
        "signals": {
            "overbought": "%K > 80: Stock may be overbought. Watch for reversal signals.",
            "oversold": "%K < 20: Stock may be oversold. Watch for bounce signals.",
            "bullish_momentum": "%K above %D: Bullish momentum building.",
            "bearish_momentum": "%K below %D: Bearish momentum building."
        }
    },
    "volume": {
        "name": "Volume Ratio",
        "what_it_is": "Compares current trading volume to the 20-day average volume.",
        "how_to_read": "High volume confirms price moves. Low volume suggests weak conviction. Volume spikes often accompany breakouts.",
        "signals": {
            "very_high": "Volume > 2x average: Very strong interest. Confirms the current move.",
            "high": "Volume > 1.5x average: Above average interest. Adds conviction to price action.",
            "normal": "Volume near average: Typical trading activity.",
            "low": "Volume < 0.75x average: Below average interest. Move may lack conviction.",
            "very_low": "Volume < 0.5x average: Very weak interest. Be cautious of price moves."
        }
    },
    "atr": {
        "name": "Average True Range (ATR)",
        "what_it_is": "A volatility indicator that shows how much a stock typically moves in a day.",
        "how_to_read": "Higher ATR means more volatility (bigger daily swings). Use ATR to set stop-losses: typically 1.5-2x ATR below entry for long positions.",
        "signals": {
            "high_volatility": "ATR is elevated: Expect larger price swings. Use wider stop-losses.",
            "low_volatility": "ATR is low: Smaller price movements expected. Tighter stops may work.",
            "increasing": "ATR rising: Volatility is increasing. Be prepared for bigger moves.",
            "decreasing": "ATR falling: Volatility is calming down."
        }
    },
    "moving_averages": {
        "name": "Moving Averages (SMA/EMA)",
        "what_it_is": "Smoothed price lines that help identify trends. SMA gives equal weight to all prices; EMA gives more weight to recent prices.",
        "how_to_read": "Price above moving averages = uptrend. Price below = downtrend. Common periods: 20 (short-term), 50 (medium-term), 200 (long-term).",
        "signals": {
            "golden_cross": "50-day crosses above 200-day: Major bullish signal. Long-term uptrend may be starting.",
            "death_cross": "50-day crosses below 200-day: Major bearish signal. Long-term downtrend may be starting.",
            "above_all": "Price above all MAs: Strong uptrend. Look for buying opportunities on pullbacks.",
            "below_all": "Price below all MAs: Strong downtrend. Be cautious with long positions."
        }
    }
}


def get_indicator_definition(indicator: str) -> Dict:
    """
    Get the beginner-friendly definition for an indicator

    Args:
        indicator: Indicator name (rsi, macd, bollinger, etc.)

    Returns:
        Dict with name, what_it_is, how_to_read, and signals
    """
    return INDICATOR_DEFINITIONS.get(indicator.lower(), {})


def get_all_definitions() -> Dict:
    """Return all indicator definitions"""
    return INDICATOR_DEFINITIONS


@dataclass
class IndicatorResult:
    """Container for indicator calculation results"""
    value: float
    signal: str  # 'bullish', 'bearish', 'neutral'
    strength: str  # 'strong', 'moderate', 'weak'


def calculate_rsi(data: pd.DataFrame, period: int = 14) -> pd.Series:
    """
    Calculate Relative Strength Index (RSI)

    RSI measures momentum by comparing recent gains to recent losses.
    - RSI > 70: Overbought (potential sell signal)
    - RSI < 30: Oversold (potential buy signal)

    Args:
        data: DataFrame with 'Close' column
        period: Lookback period (default 14)

    Returns:
        Series of RSI values (0-100)
    """
    if len(data) < period + 1:
        return pd.Series([np.nan] * len(data), index=data.index)

    delta = data['Close'].diff()

    gain = delta.where(delta > 0, 0.0)
    loss = (-delta).where(delta < 0, 0.0)

    avg_gain = gain.rolling(window=period, min_periods=period).mean()
    avg_loss = loss.rolling(window=period, min_periods=period).mean()

    # Use Wilder's smoothing for subsequent values
    for i in range(period, len(data)):
        avg_gain.iloc[i] = (avg_gain.iloc[i-1] * (period - 1) + gain.iloc[i]) / period
        avg_loss.iloc[i] = (avg_loss.iloc[i-1] * (period - 1) + loss.iloc[i]) / period

    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))

    return rsi


def calculate_macd(
    data: pd.DataFrame,
    fast_period: int = 12,
    slow_period: int = 26,
    signal_period: int = 9
) -> Dict[str, pd.Series]:
    """
    Calculate Moving Average Convergence Divergence (MACD)

    MACD shows the relationship between two EMAs.
    - MACD crossing above signal: Bullish
    - MACD crossing below signal: Bearish
    - Histogram shows momentum strength

    Args:
        data: DataFrame with 'Close' column
        fast_period: Fast EMA period (default 12)
        slow_period: Slow EMA period (default 26)
        signal_period: Signal line period (default 9)

    Returns:
        Dict with 'macd', 'signal', and 'histogram' Series
    """
    close = data['Close']

    ema_fast = close.ewm(span=fast_period, adjust=False).mean()
    ema_slow = close.ewm(span=slow_period, adjust=False).mean()

    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal_period, adjust=False).mean()
    histogram = macd_line - signal_line

    return {
        'macd': macd_line,
        'signal': signal_line,
        'histogram': histogram
    }


def calculate_bollinger_bands(
    data: pd.DataFrame,
    period: int = 20,
    std_dev: float = 2.0
) -> Dict[str, pd.Series]:
    """
    Calculate Bollinger Bands

    Bollinger Bands measure volatility and identify overbought/oversold conditions.
    - Price near upper band: Potentially overbought
    - Price near lower band: Potentially oversold
    - Band squeeze: Low volatility, potential breakout coming

    Args:
        data: DataFrame with 'Close' column
        period: Moving average period (default 20)
        std_dev: Number of standard deviations (default 2.0)

    Returns:
        Dict with 'upper', 'middle', 'lower', 'bandwidth', and 'squeeze' Series
    """
    close = data['Close']

    middle = close.rolling(window=period).mean()
    std = close.rolling(window=period).std()

    upper = middle + (std * std_dev)
    lower = middle - (std * std_dev)

    # Bandwidth: measures volatility
    bandwidth = ((upper - lower) / middle) * 100

    # Squeeze detection: low bandwidth indicates potential breakout
    bandwidth_avg = bandwidth.rolling(window=period).mean()
    squeeze = bandwidth < bandwidth_avg * 0.75  # True when in squeeze

    return {
        'upper': upper,
        'middle': middle,
        'lower': lower,
        'bandwidth': bandwidth,
        'squeeze': squeeze
    }


def calculate_sma(data: pd.DataFrame, period: int) -> pd.Series:
    """
    Calculate Simple Moving Average (SMA)

    Args:
        data: DataFrame with 'Close' column
        period: Lookback period

    Returns:
        Series of SMA values
    """
    return data['Close'].rolling(window=period).mean()


def calculate_ema(data: pd.DataFrame, period: int) -> pd.Series:
    """
    Calculate Exponential Moving Average (EMA)

    Args:
        data: DataFrame with 'Close' column
        period: Lookback period

    Returns:
        Series of EMA values
    """
    return data['Close'].ewm(span=period, adjust=False).mean()


def calculate_moving_averages(data: pd.DataFrame) -> Dict[str, pd.Series]:
    """
    Calculate common moving averages (SMA and EMA for 20, 50, 200 periods)

    Returns:
        Dict with all moving average Series
    """
    return {
        'sma_20': calculate_sma(data, 20),
        'sma_50': calculate_sma(data, 50),
        'sma_200': calculate_sma(data, 200),
        'ema_20': calculate_ema(data, 20),
        'ema_50': calculate_ema(data, 50),
        'ema_200': calculate_ema(data, 200)
    }


def calculate_atr(data: pd.DataFrame, period: int = 14) -> pd.Series:
    """
    Calculate Average True Range (ATR)

    ATR measures market volatility by calculating the average range of price movement.
    Higher ATR = higher volatility.

    Args:
        data: DataFrame with 'High', 'Low', 'Close' columns
        period: Lookback period (default 14)

    Returns:
        Series of ATR values
    """
    high = data['High']
    low = data['Low']
    close = data['Close']

    # True Range calculation
    tr1 = high - low
    tr2 = abs(high - close.shift(1))
    tr3 = abs(low - close.shift(1))

    true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

    # ATR is the smoothed average of True Range
    atr = true_range.rolling(window=period).mean()

    # Apply Wilder's smoothing for subsequent values
    for i in range(period, len(data)):
        atr.iloc[i] = (atr.iloc[i-1] * (period - 1) + true_range.iloc[i]) / period

    return atr


def calculate_volume_ratio(data: pd.DataFrame, period: int = 20) -> pd.Series:
    """
    Calculate Volume Ratio vs moving average

    Compares current volume to the average volume.
    - Ratio > 1.5: High volume (potential significant move)
    - Ratio < 0.5: Low volume (potential consolidation)

    Args:
        data: DataFrame with 'Volume' column
        period: Lookback period for average (default 20)

    Returns:
        Series of volume ratios
    """
    if 'Volume' not in data.columns:
        return pd.Series([np.nan] * len(data), index=data.index)

    avg_volume = data['Volume'].rolling(window=period).mean()
    volume_ratio = data['Volume'] / avg_volume

    return volume_ratio


def calculate_stochastic(
    data: pd.DataFrame,
    k_period: int = 14,
    d_period: int = 3
) -> Dict[str, pd.Series]:
    """
    Calculate Stochastic Oscillator

    Measures momentum by comparing closing price to price range.
    - %K > 80: Overbought
    - %K < 20: Oversold
    - %K crossing %D: Signal line crossover

    Args:
        data: DataFrame with 'High', 'Low', 'Close' columns
        k_period: %K lookback period (default 14)
        d_period: %D smoothing period (default 3)

    Returns:
        Dict with 'k' and 'd' Series
    """
    high = data['High']
    low = data['Low']
    close = data['Close']

    lowest_low = low.rolling(window=k_period).min()
    highest_high = high.rolling(window=k_period).max()

    # %K calculation
    k = 100 * ((close - lowest_low) / (highest_high - lowest_low))

    # %D is the SMA of %K
    d = k.rolling(window=d_period).mean()

    return {
        'k': k,
        'd': d
    }


def calculate_all_indicators(data: pd.DataFrame) -> Dict[str, any]:
    """
    Calculate all technical indicators for a stock

    Args:
        data: DataFrame with OHLCV columns from yfinance

    Returns:
        Dict containing all indicator values and interpretations
    """
    if len(data) < 200:
        # Need at least 200 periods for 200 SMA
        pass  # Will have NaN for longer-period indicators

    # Calculate all indicators
    rsi = calculate_rsi(data)
    macd = calculate_macd(data)
    bollinger = calculate_bollinger_bands(data)
    moving_averages = calculate_moving_averages(data)
    atr = calculate_atr(data)
    volume_ratio = calculate_volume_ratio(data)
    stochastic = calculate_stochastic(data)

    # Get latest values
    latest_rsi = rsi.iloc[-1] if not pd.isna(rsi.iloc[-1]) else None
    latest_macd = macd['macd'].iloc[-1] if not pd.isna(macd['macd'].iloc[-1]) else None
    latest_macd_signal = macd['signal'].iloc[-1] if not pd.isna(macd['signal'].iloc[-1]) else None
    latest_macd_hist = macd['histogram'].iloc[-1] if not pd.isna(macd['histogram'].iloc[-1]) else None
    latest_bb_upper = bollinger['upper'].iloc[-1] if not pd.isna(bollinger['upper'].iloc[-1]) else None
    latest_bb_lower = bollinger['lower'].iloc[-1] if not pd.isna(bollinger['lower'].iloc[-1]) else None
    latest_bb_squeeze = bollinger['squeeze'].iloc[-1] if not pd.isna(bollinger['squeeze'].iloc[-1]) else False
    latest_atr = atr.iloc[-1] if not pd.isna(atr.iloc[-1]) else None
    latest_volume_ratio = volume_ratio.iloc[-1] if not pd.isna(volume_ratio.iloc[-1]) else None
    latest_stoch_k = stochastic['k'].iloc[-1] if not pd.isna(stochastic['k'].iloc[-1]) else None
    latest_stoch_d = stochastic['d'].iloc[-1] if not pd.isna(stochastic['d'].iloc[-1]) else None

    current_price = data['Close'].iloc[-1]

    # Generate interpretations
    interpretations = generate_interpretations(
        rsi=latest_rsi,
        macd=latest_macd,
        macd_signal=latest_macd_signal,
        macd_hist=latest_macd_hist,
        stoch_k=latest_stoch_k,
        stoch_d=latest_stoch_d,
        bb_upper=latest_bb_upper,
        bb_lower=latest_bb_lower,
        bb_squeeze=latest_bb_squeeze,
        current_price=current_price,
        volume_ratio=latest_volume_ratio
    )

    result = {
        'rsi_14': latest_rsi,
        'macd': latest_macd,
        'macd_signal': latest_macd_signal,
        'macd_histogram': latest_macd_hist,
        'bb_upper': latest_bb_upper,
        'bb_middle': bollinger['middle'].iloc[-1] if not pd.isna(bollinger['middle'].iloc[-1]) else None,
        'bb_lower': latest_bb_lower,
        'bb_bandwidth': bollinger['bandwidth'].iloc[-1] if not pd.isna(bollinger['bandwidth'].iloc[-1]) else None,
        'bb_squeeze': latest_bb_squeeze,
        'sma_20': moving_averages['sma_20'].iloc[-1] if not pd.isna(moving_averages['sma_20'].iloc[-1]) else None,
        'sma_50': moving_averages['sma_50'].iloc[-1] if not pd.isna(moving_averages['sma_50'].iloc[-1]) else None,
        'sma_200': moving_averages['sma_200'].iloc[-1] if not pd.isna(moving_averages['sma_200'].iloc[-1]) else None,
        'ema_20': moving_averages['ema_20'].iloc[-1] if not pd.isna(moving_averages['ema_20'].iloc[-1]) else None,
        'ema_50': moving_averages['ema_50'].iloc[-1] if not pd.isna(moving_averages['ema_50'].iloc[-1]) else None,
        'ema_200': moving_averages['ema_200'].iloc[-1] if not pd.isna(moving_averages['ema_200'].iloc[-1]) else None,
        'atr_14': latest_atr,
        'volume_ratio': latest_volume_ratio,
        'stochastic_k': latest_stoch_k,
        'stochastic_d': latest_stoch_d,
        'interpretations': interpretations
    }

    # Add beginner-friendly summary
    result['for_beginners'] = generate_beginner_summary(result)

    return result


def generate_interpretations(
    rsi: Optional[float],
    macd: Optional[float],
    macd_signal: Optional[float],
    macd_hist: Optional[float],
    stoch_k: Optional[float],
    stoch_d: Optional[float],
    bb_upper: Optional[float],
    bb_lower: Optional[float],
    bb_squeeze: bool,
    current_price: float,
    volume_ratio: Optional[float]
) -> Dict[str, str]:
    """
    Generate human-readable interpretations of indicator values

    Returns:
        Dict with interpretations for each indicator
    """
    interpretations = {}

    # RSI interpretation
    if rsi is not None:
        if rsi > 70:
            interpretations['rsi'] = 'overbought'
        elif rsi < 30:
            interpretations['rsi'] = 'oversold'
        elif rsi > 50:
            interpretations['rsi'] = 'bullish_momentum'
        else:
            interpretations['rsi'] = 'bearish_momentum'

    # MACD interpretation
    if macd is not None and macd_signal is not None:
        if macd > macd_signal:
            if macd_hist is not None and macd_hist > 0:
                interpretations['macd'] = 'bullish_crossover' if macd_hist > 0 else 'bullish'
            else:
                interpretations['macd'] = 'bullish'
        else:
            if macd_hist is not None and macd_hist < 0:
                interpretations['macd'] = 'bearish_crossover' if macd_hist < 0 else 'bearish'
            else:
                interpretations['macd'] = 'bearish'

    # Stochastic interpretation
    if stoch_k is not None:
        if stoch_k > 80:
            interpretations['stochastic'] = 'overbought'
        elif stoch_k < 20:
            interpretations['stochastic'] = 'oversold'
        elif stoch_k is not None and stoch_d is not None:
            if stoch_k > stoch_d:
                interpretations['stochastic'] = 'bullish_momentum'
            else:
                interpretations['stochastic'] = 'bearish_momentum'

    # Bollinger Bands interpretation
    if bb_upper is not None and bb_lower is not None:
        if current_price >= bb_upper:
            interpretations['bollinger'] = 'at_upper_band'
        elif current_price <= bb_lower:
            interpretations['bollinger'] = 'at_lower_band'
        else:
            interpretations['bollinger'] = 'within_bands'

        if bb_squeeze:
            interpretations['bollinger_squeeze'] = 'squeeze_active'

    # Volume interpretation
    if volume_ratio is not None:
        if volume_ratio > 2.0:
            interpretations['volume'] = 'very_high'
        elif volume_ratio > 1.5:
            interpretations['volume'] = 'high'
        elif volume_ratio < 0.5:
            interpretations['volume'] = 'very_low'
        elif volume_ratio < 0.75:
            interpretations['volume'] = 'low'
        else:
            interpretations['volume'] = 'normal'

    return interpretations


def generate_beginner_summary(indicators: Dict) -> Dict:
    """
    Generate a beginner-friendly summary of all indicators

    Args:
        indicators: Dict from calculate_all_indicators

    Returns:
        Dict with easy-to-understand explanations and recommendations
    """
    interpretations = indicators.get('interpretations', {})
    summary = {
        'indicators_explained': [],
        'overall_sentiment': 'neutral',
        'action_summary': '',
        'risk_level': 'MODERATE',
        'definitions': INDICATOR_DEFINITIONS
    }

    bullish_signals = 0
    bearish_signals = 0
    explanations = []

    # RSI explanation
    rsi = indicators.get('rsi_14')
    if rsi is not None:
        rsi_interp = interpretations.get('rsi', '')
        rsi_def = INDICATOR_DEFINITIONS['rsi']
        explanation = {
            'indicator': 'RSI',
            'value': round(rsi, 1),
            'status': rsi_interp,
            'explanation': rsi_def['signals'].get(rsi_interp, ''),
            'definition': rsi_def['what_it_is']
        }
        explanations.append(explanation)

        if rsi_interp in ['oversold', 'bullish_momentum']:
            bullish_signals += 1
        elif rsi_interp in ['overbought', 'bearish_momentum']:
            bearish_signals += 1

    # MACD explanation
    macd = indicators.get('macd')
    if macd is not None:
        macd_interp = interpretations.get('macd', '')
        macd_def = INDICATOR_DEFINITIONS['macd']
        explanation = {
            'indicator': 'MACD',
            'value': round(macd, 4),
            'status': macd_interp,
            'explanation': macd_def['signals'].get(macd_interp, ''),
            'definition': macd_def['what_it_is']
        }
        explanations.append(explanation)

        if 'bullish' in macd_interp:
            bullish_signals += 1
        elif 'bearish' in macd_interp:
            bearish_signals += 1

    # Bollinger Bands explanation
    bb_interp = interpretations.get('bollinger', '')
    bb_squeeze = interpretations.get('bollinger_squeeze', '')
    if bb_interp:
        bb_def = INDICATOR_DEFINITIONS['bollinger']
        explanation = {
            'indicator': 'Bollinger Bands',
            'value': f"Upper: {round(indicators.get('bb_upper', 0), 2)}, Lower: {round(indicators.get('bb_lower', 0), 2)}",
            'status': bb_interp + (', ' + bb_squeeze if bb_squeeze else ''),
            'explanation': bb_def['signals'].get(bb_interp, ''),
            'definition': bb_def['what_it_is']
        }
        if bb_squeeze:
            explanation['squeeze_note'] = bb_def['signals'].get('squeeze_active', '')
        explanations.append(explanation)

        if bb_interp == 'at_lower_band':
            bullish_signals += 1
        elif bb_interp == 'at_upper_band':
            bearish_signals += 1

    # Stochastic explanation
    stoch_k = indicators.get('stochastic_k')
    if stoch_k is not None:
        stoch_interp = interpretations.get('stochastic', '')
        stoch_def = INDICATOR_DEFINITIONS['stochastic']
        explanation = {
            'indicator': 'Stochastic',
            'value': round(stoch_k, 1),
            'status': stoch_interp,
            'explanation': stoch_def['signals'].get(stoch_interp, ''),
            'definition': stoch_def['what_it_is']
        }
        explanations.append(explanation)

        if stoch_interp in ['oversold', 'bullish_momentum']:
            bullish_signals += 1
        elif stoch_interp in ['overbought', 'bearish_momentum']:
            bearish_signals += 1

    # Volume explanation
    vol_ratio = indicators.get('volume_ratio')
    if vol_ratio is not None:
        vol_interp = interpretations.get('volume', '')
        vol_def = INDICATOR_DEFINITIONS['volume']
        explanation = {
            'indicator': 'Volume',
            'value': f"{round(vol_ratio, 2)}x average",
            'status': vol_interp,
            'explanation': vol_def['signals'].get(vol_interp, ''),
            'definition': vol_def['what_it_is']
        }
        explanations.append(explanation)

    # ATR explanation
    atr = indicators.get('atr_14')
    if atr is not None:
        atr_def = INDICATOR_DEFINITIONS['atr']
        current_price = indicators.get('bb_middle', 100)  # Use middle band as proxy
        atr_pct = (atr / current_price * 100) if current_price else 0
        volatility = 'high_volatility' if atr_pct > 3 else 'low_volatility'
        explanation = {
            'indicator': 'ATR (Volatility)',
            'value': round(atr, 2),
            'status': f"{round(atr_pct, 1)}% daily range",
            'explanation': atr_def['signals'].get(volatility, ''),
            'definition': atr_def['what_it_is']
        }
        explanations.append(explanation)

    summary['indicators_explained'] = explanations

    # Determine overall sentiment
    total_signals = bullish_signals + bearish_signals
    if total_signals > 0:
        if bullish_signals > bearish_signals + 1:
            summary['overall_sentiment'] = 'bullish'
            summary['action_summary'] = 'Multiple indicators suggest bullish momentum. Consider looking for entry points on pullbacks.'
            summary['risk_level'] = 'MODERATE'
        elif bearish_signals > bullish_signals + 1:
            summary['overall_sentiment'] = 'bearish'
            summary['action_summary'] = 'Multiple indicators suggest bearish pressure. Consider waiting for confirmation before buying.'
            summary['risk_level'] = 'HIGH'
        else:
            summary['overall_sentiment'] = 'mixed'
            summary['action_summary'] = 'Indicators show mixed signals. Wait for clearer direction before taking action.'
            summary['risk_level'] = 'MODERATE'
    else:
        summary['action_summary'] = 'Insufficient data to determine trend. Monitor for developing patterns.'

    return summary


def get_ml_features(data: pd.DataFrame) -> Dict[str, float]:
    """
    Extract ML-ready features from technical indicators

    Normalizes and prepares indicator values for ML model input.
    Enhanced with momentum, trend, and lag features.

    Args:
        data: DataFrame with OHLCV columns

    Returns:
        Dict of feature names to normalized values
    """
    indicators = calculate_all_indicators(data)
    current_price = data['Close'].iloc[-1]

    features = {}

    # === MOMENTUM INDICATORS ===

    # RSI (already 0-100 scale, normalize to 0-1)
    if indicators['rsi_14'] is not None:
        features['rsi_14_norm'] = indicators['rsi_14'] / 100
        # RSI zones (oversold/overbought signals)
        features['rsi_oversold'] = 1.0 if indicators['rsi_14'] < 30 else 0.0
        features['rsi_overbought'] = 1.0 if indicators['rsi_14'] > 70 else 0.0

    # MACD (normalize by price)
    if indicators['macd'] is not None:
        features['macd_norm'] = indicators['macd'] / current_price
    if indicators['macd_histogram'] is not None:
        features['macd_hist_norm'] = indicators['macd_histogram'] / current_price
        # MACD histogram direction
        features['macd_hist_positive'] = 1.0 if indicators['macd_histogram'] > 0 else 0.0

    # Stochastic (normalize to 0-1)
    if indicators['stochastic_k'] is not None:
        features['stoch_k_norm'] = indicators['stochastic_k'] / 100
        features['stoch_oversold'] = 1.0 if indicators['stochastic_k'] < 20 else 0.0
        features['stoch_overbought'] = 1.0 if indicators['stochastic_k'] > 80 else 0.0
    if indicators['stochastic_d'] is not None:
        features['stoch_d_norm'] = indicators['stochastic_d'] / 100
        # Stochastic crossover
        if indicators['stochastic_k'] is not None:
            features['stoch_k_above_d'] = 1.0 if indicators['stochastic_k'] > indicators['stochastic_d'] else 0.0

    # === VOLATILITY INDICATORS ===

    # Bollinger position (-1 to 1, where -1 is at lower, 1 is at upper)
    if indicators['bb_upper'] is not None and indicators['bb_lower'] is not None:
        bb_range = indicators['bb_upper'] - indicators['bb_lower']
        if bb_range > 0:
            bb_position = (current_price - indicators['bb_lower']) / bb_range
            features['bb_position'] = (bb_position * 2) - 1  # Scale to -1 to 1
            features['bb_at_lower'] = 1.0 if bb_position < 0.1 else 0.0
            features['bb_at_upper'] = 1.0 if bb_position > 0.9 else 0.0

    # Bollinger squeeze (binary)
    features['bb_squeeze'] = 1.0 if indicators['bb_squeeze'] else 0.0

    # Bollinger bandwidth (volatility measure)
    if indicators['bb_bandwidth'] is not None:
        features['bb_bandwidth_norm'] = min(indicators['bb_bandwidth'], 20) / 20  # Cap at 20%

    # ATR as percentage of price (volatility measure)
    if indicators['atr_14'] is not None:
        features['atr_pct'] = indicators['atr_14'] / current_price

    # === TREND INDICATORS ===

    # Price vs moving averages (percentage above/below)
    for ma in ['sma_20', 'sma_50', 'sma_200', 'ema_20', 'ema_50', 'ema_200']:
        if indicators[ma] is not None and indicators[ma] > 0:
            features[f'price_vs_{ma}'] = (current_price - indicators[ma]) / indicators[ma]

    # Moving average alignments (trend confirmation)
    if indicators['sma_20'] is not None and indicators['sma_50'] is not None:
        features['sma_20_above_50'] = 1.0 if indicators['sma_20'] > indicators['sma_50'] else 0.0
    if indicators['sma_50'] is not None and indicators['sma_200'] is not None:
        features['sma_50_above_200'] = 1.0 if indicators['sma_50'] > indicators['sma_200'] else 0.0
    if indicators['ema_20'] is not None and indicators['ema_50'] is not None:
        features['ema_20_above_50'] = 1.0 if indicators['ema_20'] > indicators['ema_50'] else 0.0

    # Price above all MAs (strong uptrend)
    if all(indicators[ma] is not None for ma in ['sma_20', 'sma_50', 'sma_200']):
        features['price_above_all_sma'] = 1.0 if (current_price > indicators['sma_20'] and
                                                   current_price > indicators['sma_50'] and
                                                   current_price > indicators['sma_200']) else 0.0

    # === VOLUME INDICATORS ===

    # Volume ratio (capped)
    if indicators['volume_ratio'] is not None:
        features['volume_ratio'] = min(indicators['volume_ratio'], 5.0) / 5.0
        features['volume_spike'] = 1.0 if indicators['volume_ratio'] > 1.5 else 0.0
        features['volume_dry'] = 1.0 if indicators['volume_ratio'] < 0.5 else 0.0

    # === PRICE ACTION FEATURES ===

    if len(data) >= 20:
        close = data['Close']
        high = data['High']
        low = data['Low']

        # Returns over different periods
        for period in [1, 3, 5, 10, 20]:
            if len(close) > period:
                ret = (close.iloc[-1] - close.iloc[-1-period]) / close.iloc[-1-period]
                features[f'return_{period}d'] = np.clip(ret, -0.5, 0.5)  # Clip extreme values

        # Volatility (rolling std of returns)
        if len(close) > 20:
            returns = close.pct_change().dropna()
            features['volatility_20d'] = returns.tail(20).std() * np.sqrt(252)  # Annualized

        # Price position in recent range
        if len(high) >= 20 and len(low) >= 20:
            high_20 = high.tail(20).max()
            low_20 = low.tail(20).min()
            range_20 = high_20 - low_20
            if range_20 > 0:
                features['price_position_20d'] = (current_price - low_20) / range_20

        # Trend strength (linear regression slope normalized)
        if len(close) >= 20:
            x = np.arange(20)
            y = close.tail(20).values
            slope = np.polyfit(x, y, 1)[0]
            features['trend_slope_20d'] = slope / current_price  # Normalize by price

        # Gap detection (overnight gaps)
        if len(data) >= 2:
            prev_close = close.iloc[-2]
            curr_open = data['Open'].iloc[-1]
            gap = (curr_open - prev_close) / prev_close
            features['overnight_gap'] = np.clip(gap, -0.1, 0.1)

        # Candle patterns
        body = close.iloc[-1] - data['Open'].iloc[-1]
        upper_shadow = high.iloc[-1] - max(close.iloc[-1], data['Open'].iloc[-1])
        lower_shadow = min(close.iloc[-1], data['Open'].iloc[-1]) - low.iloc[-1]
        candle_range = high.iloc[-1] - low.iloc[-1]

        if candle_range > 0:
            features['candle_body_ratio'] = body / candle_range
            features['upper_shadow_ratio'] = upper_shadow / candle_range
            features['lower_shadow_ratio'] = lower_shadow / candle_range

    return features
