"""
Tests for Technical Indicators Module
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import sys
import os

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from utils.indicators import (
    calculate_rsi,
    calculate_macd,
    calculate_bollinger_bands,
    calculate_sma,
    calculate_ema,
    calculate_moving_averages,
    calculate_atr,
    calculate_volume_ratio,
    calculate_stochastic,
    calculate_all_indicators,
    get_ml_features,
    generate_interpretations,
    generate_beginner_summary,
    get_indicator_definition,
    get_all_definitions,
    INDICATOR_DEFINITIONS
)


@pytest.fixture
def sample_data():
    """Create sample OHLCV data for testing"""
    np.random.seed(42)
    dates = pd.date_range(start='2024-01-01', periods=100, freq='D')

    # Generate realistic price data
    base_price = 100
    returns = np.random.randn(100) * 0.02  # 2% daily volatility
    close = base_price * np.cumprod(1 + returns)

    # Generate OHLC from close
    high = close * (1 + np.abs(np.random.randn(100) * 0.01))
    low = close * (1 - np.abs(np.random.randn(100) * 0.01))
    open_price = close * (1 + np.random.randn(100) * 0.005)

    # Ensure high >= close >= low and high >= open >= low
    high = np.maximum(high, np.maximum(close, open_price))
    low = np.minimum(low, np.minimum(close, open_price))

    volume = np.random.randint(1000000, 10000000, 100)

    df = pd.DataFrame({
        'Open': open_price,
        'High': high,
        'Low': low,
        'Close': close,
        'Volume': volume
    }, index=dates)

    return df


@pytest.fixture
def trending_up_data():
    """Create data with clear uptrend"""
    dates = pd.date_range(start='2024-01-01', periods=100, freq='D')

    # Clear uptrend
    close = 100 + np.arange(100) * 0.5 + np.random.randn(100) * 0.5
    high = close + np.abs(np.random.randn(100) * 0.3)
    low = close - np.abs(np.random.randn(100) * 0.3)
    open_price = close - np.random.randn(100) * 0.2
    volume = np.random.randint(1000000, 5000000, 100)

    return pd.DataFrame({
        'Open': open_price,
        'High': high,
        'Low': low,
        'Close': close,
        'Volume': volume
    }, index=dates)


@pytest.fixture
def trending_down_data():
    """Create data with clear downtrend"""
    dates = pd.date_range(start='2024-01-01', periods=100, freq='D')

    # Clear downtrend
    close = 150 - np.arange(100) * 0.5 + np.random.randn(100) * 0.5
    high = close + np.abs(np.random.randn(100) * 0.3)
    low = close - np.abs(np.random.randn(100) * 0.3)
    open_price = close + np.random.randn(100) * 0.2
    volume = np.random.randint(1000000, 5000000, 100)

    return pd.DataFrame({
        'Open': open_price,
        'High': high,
        'Low': low,
        'Close': close,
        'Volume': volume
    }, index=dates)


class TestRSI:
    """Tests for RSI calculation"""

    def test_rsi_returns_series(self, sample_data):
        """RSI should return a pandas Series"""
        rsi = calculate_rsi(sample_data)
        assert isinstance(rsi, pd.Series)
        assert len(rsi) == len(sample_data)

    def test_rsi_range(self, sample_data):
        """RSI values should be between 0 and 100"""
        rsi = calculate_rsi(sample_data)
        valid_rsi = rsi.dropna()
        assert (valid_rsi >= 0).all()
        assert (valid_rsi <= 100).all()

    def test_rsi_uptrend(self, trending_up_data):
        """RSI should be higher in uptrend"""
        rsi = calculate_rsi(trending_up_data)
        # Last RSI should be above 50 in uptrend
        assert rsi.iloc[-1] > 50

    def test_rsi_downtrend(self, trending_down_data):
        """RSI should be lower in downtrend"""
        rsi = calculate_rsi(trending_down_data)
        # Last RSI should be below 50 in downtrend
        assert rsi.iloc[-1] < 50

    def test_rsi_insufficient_data(self):
        """RSI should handle insufficient data"""
        small_data = pd.DataFrame({
            'Close': [100, 101, 102]
        })
        rsi = calculate_rsi(small_data)
        assert len(rsi) == 3
        assert pd.isna(rsi.iloc[-1])


class TestMACD:
    """Tests for MACD calculation"""

    def test_macd_returns_dict(self, sample_data):
        """MACD should return a dict with macd, signal, histogram"""
        macd = calculate_macd(sample_data)
        assert isinstance(macd, dict)
        assert 'macd' in macd
        assert 'signal' in macd
        assert 'histogram' in macd

    def test_macd_histogram_calculation(self, sample_data):
        """Histogram should equal MACD minus signal"""
        macd = calculate_macd(sample_data)
        # Check last valid values
        expected_hist = macd['macd'].iloc[-1] - macd['signal'].iloc[-1]
        assert np.isclose(macd['histogram'].iloc[-1], expected_hist, rtol=1e-5)

    def test_macd_uptrend(self, trending_up_data):
        """MACD should be positive in uptrend"""
        macd = calculate_macd(trending_up_data)
        assert macd['macd'].iloc[-1] > 0


class TestBollingerBands:
    """Tests for Bollinger Bands calculation"""

    def test_bollinger_returns_dict(self, sample_data):
        """Bollinger Bands should return dict with required keys"""
        bb = calculate_bollinger_bands(sample_data)
        assert isinstance(bb, dict)
        assert 'upper' in bb
        assert 'middle' in bb
        assert 'lower' in bb
        assert 'bandwidth' in bb
        assert 'squeeze' in bb

    def test_bollinger_band_order(self, sample_data):
        """Upper band should be >= middle >= lower"""
        bb = calculate_bollinger_bands(sample_data)
        valid_idx = bb['middle'].dropna().index

        assert (bb['upper'].loc[valid_idx] >= bb['middle'].loc[valid_idx]).all()
        assert (bb['middle'].loc[valid_idx] >= bb['lower'].loc[valid_idx]).all()

    def test_bollinger_squeeze_is_boolean(self, sample_data):
        """Squeeze should be boolean Series"""
        bb = calculate_bollinger_bands(sample_data)
        assert bb['squeeze'].dtype == bool


class TestMovingAverages:
    """Tests for SMA and EMA calculations"""

    def test_sma_calculation(self, sample_data):
        """SMA should be correct"""
        sma_20 = calculate_sma(sample_data, 20)
        # Manual check: SMA of last 20 closes
        expected = sample_data['Close'].tail(20).mean()
        assert np.isclose(sma_20.iloc[-1], expected, rtol=1e-5)

    def test_ema_returns_series(self, sample_data):
        """EMA should return a Series"""
        ema = calculate_ema(sample_data, 20)
        assert isinstance(ema, pd.Series)

    def test_moving_averages_all_periods(self, sample_data):
        """Should return all standard moving averages"""
        mas = calculate_moving_averages(sample_data)
        assert 'sma_20' in mas
        assert 'sma_50' in mas
        assert 'sma_200' in mas
        assert 'ema_20' in mas
        assert 'ema_50' in mas
        assert 'ema_200' in mas


class TestATR:
    """Tests for ATR calculation"""

    def test_atr_returns_series(self, sample_data):
        """ATR should return a pandas Series"""
        atr = calculate_atr(sample_data)
        assert isinstance(atr, pd.Series)

    def test_atr_positive(self, sample_data):
        """ATR should always be positive"""
        atr = calculate_atr(sample_data)
        valid_atr = atr.dropna()
        assert (valid_atr >= 0).all()


class TestVolumeRatio:
    """Tests for Volume Ratio calculation"""

    def test_volume_ratio_returns_series(self, sample_data):
        """Volume ratio should return a Series"""
        vr = calculate_volume_ratio(sample_data)
        assert isinstance(vr, pd.Series)

    def test_volume_ratio_handles_missing_volume(self):
        """Should handle missing Volume column"""
        data = pd.DataFrame({
            'Close': [100, 101, 102]
        })
        vr = calculate_volume_ratio(data)
        assert pd.isna(vr.iloc[-1])


class TestStochastic:
    """Tests for Stochastic Oscillator calculation"""

    def test_stochastic_returns_dict(self, sample_data):
        """Stochastic should return dict with k and d"""
        stoch = calculate_stochastic(sample_data)
        assert isinstance(stoch, dict)
        assert 'k' in stoch
        assert 'd' in stoch

    def test_stochastic_range(self, sample_data):
        """Stochastic values should be between 0 and 100"""
        stoch = calculate_stochastic(sample_data)
        valid_k = stoch['k'].dropna()
        valid_d = stoch['d'].dropna()

        assert (valid_k >= 0).all() and (valid_k <= 100).all()
        assert (valid_d >= 0).all() and (valid_d <= 100).all()


class TestAllIndicators:
    """Tests for calculate_all_indicators"""

    def test_returns_all_indicators(self, sample_data):
        """Should return all indicator values"""
        indicators = calculate_all_indicators(sample_data)

        assert 'rsi_14' in indicators
        assert 'macd' in indicators
        assert 'macd_signal' in indicators
        assert 'macd_histogram' in indicators
        assert 'bb_upper' in indicators
        assert 'bb_middle' in indicators
        assert 'bb_lower' in indicators
        assert 'sma_20' in indicators
        assert 'sma_50' in indicators
        assert 'ema_20' in indicators
        assert 'atr_14' in indicators
        assert 'volume_ratio' in indicators
        assert 'stochastic_k' in indicators
        assert 'stochastic_d' in indicators
        assert 'interpretations' in indicators

    def test_interpretations_included(self, sample_data):
        """Should include interpretations"""
        indicators = calculate_all_indicators(sample_data)
        assert isinstance(indicators['interpretations'], dict)


class TestMLFeatures:
    """Tests for ML feature extraction"""

    def test_returns_normalized_features(self, sample_data):
        """Should return normalized features"""
        features = get_ml_features(sample_data)
        assert isinstance(features, dict)

    def test_rsi_normalized(self, sample_data):
        """RSI should be normalized to 0-1"""
        features = get_ml_features(sample_data)
        if 'rsi_14_norm' in features:
            assert 0 <= features['rsi_14_norm'] <= 1

    def test_volume_ratio_capped(self, sample_data):
        """Volume ratio should be capped and normalized"""
        features = get_ml_features(sample_data)
        if 'volume_ratio' in features:
            assert 0 <= features['volume_ratio'] <= 1


class TestInterpretations:
    """Tests for indicator interpretations"""

    def test_rsi_overbought(self):
        """RSI > 70 should be overbought"""
        interp = generate_interpretations(
            rsi=75, macd=None, macd_signal=None, macd_hist=None,
            stoch_k=None, stoch_d=None, bb_upper=None, bb_lower=None,
            bb_squeeze=False, current_price=100, volume_ratio=None
        )
        assert interp['rsi'] == 'overbought'

    def test_rsi_oversold(self):
        """RSI < 30 should be oversold"""
        interp = generate_interpretations(
            rsi=25, macd=None, macd_signal=None, macd_hist=None,
            stoch_k=None, stoch_d=None, bb_upper=None, bb_lower=None,
            bb_squeeze=False, current_price=100, volume_ratio=None
        )
        assert interp['rsi'] == 'oversold'

    def test_macd_bullish(self):
        """MACD above signal should be bullish"""
        interp = generate_interpretations(
            rsi=None, macd=1.5, macd_signal=1.0, macd_hist=0.5,
            stoch_k=None, stoch_d=None, bb_upper=None, bb_lower=None,
            bb_squeeze=False, current_price=100, volume_ratio=None
        )
        assert 'bullish' in interp['macd']

    def test_high_volume(self):
        """Volume ratio > 1.5 should be high"""
        interp = generate_interpretations(
            rsi=None, macd=None, macd_signal=None, macd_hist=None,
            stoch_k=None, stoch_d=None, bb_upper=None, bb_lower=None,
            bb_squeeze=False, current_price=100, volume_ratio=1.8
        )
        assert interp['volume'] == 'high'


class TestBeginnerSummary:
    """Tests for beginner-friendly summary generation"""

    def test_beginner_summary_included(self, sample_data):
        """calculate_all_indicators should include for_beginners"""
        indicators = calculate_all_indicators(sample_data)
        assert 'for_beginners' in indicators

    def test_beginner_summary_has_required_keys(self, sample_data):
        """Beginner summary should have all required keys"""
        indicators = calculate_all_indicators(sample_data)
        summary = indicators['for_beginners']

        assert 'indicators_explained' in summary
        assert 'overall_sentiment' in summary
        assert 'action_summary' in summary
        assert 'risk_level' in summary
        assert 'definitions' in summary

    def test_indicators_explained_has_details(self, sample_data):
        """Each explained indicator should have required fields"""
        indicators = calculate_all_indicators(sample_data)
        explanations = indicators['for_beginners']['indicators_explained']

        assert len(explanations) > 0
        for exp in explanations:
            assert 'indicator' in exp
            assert 'value' in exp
            assert 'status' in exp
            assert 'definition' in exp

    def test_overall_sentiment_valid(self, sample_data):
        """Overall sentiment should be valid value"""
        indicators = calculate_all_indicators(sample_data)
        sentiment = indicators['for_beginners']['overall_sentiment']
        assert sentiment in ['bullish', 'bearish', 'mixed', 'neutral']

    def test_risk_level_valid(self, sample_data):
        """Risk level should be valid value"""
        indicators = calculate_all_indicators(sample_data)
        risk = indicators['for_beginners']['risk_level']
        assert risk in ['LOW', 'MODERATE', 'HIGH']


class TestIndicatorDefinitions:
    """Tests for indicator definitions"""

    def test_definitions_exist(self):
        """All expected indicators should have definitions"""
        expected = ['rsi', 'macd', 'bollinger', 'stochastic', 'volume', 'atr', 'moving_averages']
        for ind in expected:
            assert ind in INDICATOR_DEFINITIONS

    def test_definition_structure(self):
        """Each definition should have required fields"""
        for name, defn in INDICATOR_DEFINITIONS.items():
            assert 'name' in defn, f"{name} missing 'name'"
            assert 'what_it_is' in defn, f"{name} missing 'what_it_is'"
            assert 'how_to_read' in defn, f"{name} missing 'how_to_read'"
            assert 'signals' in defn, f"{name} missing 'signals'"

    def test_get_indicator_definition(self):
        """get_indicator_definition should return correct definition"""
        rsi_def = get_indicator_definition('rsi')
        assert rsi_def['name'] == 'Relative Strength Index (RSI)'
        assert 'overbought' in rsi_def['signals']

    def test_get_all_definitions(self):
        """get_all_definitions should return all definitions"""
        all_defs = get_all_definitions()
        assert len(all_defs) == len(INDICATOR_DEFINITIONS)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
