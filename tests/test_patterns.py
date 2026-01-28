"""
Tests for ICC pattern detection utilities
"""
import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from src.utils.patterns import (
    calculate_support_resistance,
    detect_volume_spike,
    calculate_momentum,
    identify_swing_points,
    calculate_fibonacci_levels,
    validate_pattern_completeness
)


def create_sample_data(periods=50, trend='up'):
    """Create sample OHLCV data for testing"""
    dates = pd.date_range(start=datetime.now() - timedelta(days=periods), periods=periods, freq='D')
    
    if trend == 'up':
        base_prices = np.linspace(100, 150, periods)
    elif trend == 'down':
        base_prices = np.linspace(150, 100, periods)
    else:
        base_prices = np.full(periods, 125)
    
    # Add some noise
    noise = np.random.normal(0, 2, periods)
    prices = base_prices + noise
    
    data = pd.DataFrame({
        'Open': prices + np.random.normal(0, 0.5, periods),
        'High': prices + np.abs(np.random.normal(1, 0.5, periods)),
        'Low': prices - np.abs(np.random.normal(1, 0.5, periods)),
        'Close': prices,
        'Volume': np.random.randint(1000000, 5000000, periods)
    }, index=dates)
    
    return data


def test_calculate_support_resistance():
    """Test support and resistance calculation"""
    data = create_sample_data(periods=30)
    levels = calculate_support_resistance(data, window=20)
    
    assert 'support' in levels
    assert 'resistance' in levels
    assert levels['support'] < levels['resistance']
    assert isinstance(levels['support'], float)
    assert isinstance(levels['resistance'], float)


def test_detect_volume_spike():
    """Test volume spike detection"""
    data = create_sample_data(periods=30)
    
    # Normal volume
    assert isinstance(detect_volume_spike(data, threshold=1.5), bool)
    
    # Create volume spike
    data_with_spike = data.copy()
    data_with_spike.loc[data_with_spike.index[-1], 'Volume'] = data['Volume'].mean() * 2
    
    assert detect_volume_spike(data_with_spike, threshold=1.5) == True


def test_calculate_momentum():
    """Test momentum calculation"""
    data = create_sample_data(periods=20, trend='up')
    momentum = calculate_momentum(data, periods=5)
    
    assert isinstance(momentum, float)
    
    # Upward trend should have positive momentum
    up_data = create_sample_data(periods=20, trend='up')
    up_momentum = calculate_momentum(up_data, periods=5)
    assert up_momentum > 0
    
    # Downward trend should have negative momentum
    down_data = create_sample_data(periods=20, trend='down')
    down_momentum = calculate_momentum(down_data, periods=5)
    assert down_momentum < 0


def test_identify_swing_points():
    """Test swing point identification"""
    data = create_sample_data(periods=30)
    swings = identify_swing_points(data, window=5)
    
    assert 'highs' in swings
    assert 'lows' in swings
    assert isinstance(swings['highs'], list)
    assert isinstance(swings['lows'], list)


def test_calculate_fibonacci_levels():
    """Test Fibonacci retracement calculation"""
    levels = calculate_fibonacci_levels(high=150.0, low=100.0)
    
    assert '0.0' in levels
    assert '0.5' in levels
    assert '1.0' in levels
    assert levels['0.0'] == 150.0
    assert levels['1.0'] == 100.0
    assert levels['0.5'] == 125.0
    
    # Verify levels are in descending order
    level_values = [levels[k] for k in sorted(levels.keys(), key=float, reverse=True)]
    assert level_values == sorted(level_values, reverse=True)


def test_validate_pattern_completeness():
    """Test pattern completeness validation"""
    # Complete pattern
    complete_pattern = {
        "indication": {"detected": True},
        "correction": {"detected": True},
        "continuation": {"detected": True}
    }
    assert validate_pattern_completeness(
        complete_pattern["indication"],
        complete_pattern["correction"],
        complete_pattern["continuation"]
    ) == True
    
    # Incomplete pattern
    incomplete_pattern = {
        "indication": {"detected": True},
        "correction": {"detected": False},
        "continuation": {"detected": True}
    }
    assert validate_pattern_completeness(
        incomplete_pattern["indication"],
        incomplete_pattern["correction"],
        incomplete_pattern["continuation"]
    ) == False
