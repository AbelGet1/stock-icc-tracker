#!/usr/bin/env python3
"""
ML Model Training Script for StockScout

This script:
1. Fetches historical stock data for S&P 500 top 50 stocks
2. Calculates technical indicators as features
3. Creates target variable (5-day forward return > 2%)
4. Trains a Random Forest classifier with time-series cross-validation
5. Uploads the trained model and metadata to S3

Usage:
    python scripts/train_model.py [--test] [--stocks AAPL,MSFT] [--local]

Options:
    --test      Use smaller dataset for testing (5 stocks, 6 months)
    --stocks    Comma-separated list of specific stocks to train on
    --local     Save model locally instead of uploading to S3
"""

import argparse
import json
import logging
import os
import sys
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional

import time

import boto3
import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
try:
    from xgboost import XGBClassifier
    HAS_XGBOOST = True
except ImportError:
    HAS_XGBOOST = False
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    classification_report,
    confusion_matrix
)
from sklearn.model_selection import TimeSeriesSplit

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
from config.sp500_top50 import get_top_50, get_test_subset, get_diverse_universe, get_stocks_by_category
from utils.indicators import calculate_all_indicators, get_ml_features

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Constants
MODEL_VERSION = "1.2.0"
TARGET_RETURN_THRESHOLD = 0.01  # 1% gain (more achievable)
TARGET_HORIZON_DAYS = 5  # 5 trading days forward
TRAIN_PERIOD_YEARS = 2
MIN_SAMPLES_PER_STOCK = 200
DEFAULT_CLASSIFICATION_THRESHOLD = 0.5  # Standard threshold
PRECISION_FOCUSED_THRESHOLD = 0.65  # Higher threshold for precision


class ModelTrainer:
    """Handles ML model training for stock prediction"""

    def __init__(self, s3_bucket: Optional[str] = None, local_mode: bool = False):
        """
        Initialize the trainer

        Args:
            s3_bucket: S3 bucket name for storing models
            local_mode: If True, save locally instead of S3
        """
        self.s3_bucket = s3_bucket or os.environ.get('S3_BUCKET', 'stockscout-storage')
        self.local_mode = local_mode
        self.s3_client = None if local_mode else boto3.client('s3')
        self.model = None
        self.feature_names = None
        self.training_metadata = {}
        self.market_data = None  # Cache for SPY data

    def fetch_market_data(self) -> Optional[pd.DataFrame]:
        """Fetch SPY data as market proxy"""
        if self.market_data is not None:
            return self.market_data

        from utils.yfinance_helpers import fetch_ticker_data

        logger.info("Fetching market data (SPY)...")
        data = fetch_ticker_data("SPY", period="2y", interval="1d")
        if data is not None and not data.empty:
            self.market_data = data
            return data
        logger.warning("Could not fetch market data for SPY")
        return None

    def get_market_features(self, date: pd.Timestamp) -> Dict[str, float]:
        """Get market-wide features for a specific date"""
        features = {}
        market_data = self.fetch_market_data()

        if market_data is None or date not in market_data.index:
            return features

        try:
            idx = market_data.index.get_loc(date)
            if idx < 20:
                return features

            close = market_data['Close']

            # Market returns
            features['spy_return_1d'] = (close.iloc[idx] - close.iloc[idx-1]) / close.iloc[idx-1]
            features['spy_return_5d'] = (close.iloc[idx] - close.iloc[idx-5]) / close.iloc[idx-5]
            features['spy_return_20d'] = (close.iloc[idx] - close.iloc[idx-20]) / close.iloc[idx-20]

            # Market trend (price vs MAs)
            spy_sma_20 = close.iloc[idx-19:idx+1].mean()
            spy_sma_50 = close.iloc[max(0,idx-49):idx+1].mean()
            features['spy_vs_sma20'] = (close.iloc[idx] - spy_sma_20) / spy_sma_20
            features['spy_vs_sma50'] = (close.iloc[idx] - spy_sma_50) / spy_sma_50

            # Market volatility
            returns = close.pct_change().iloc[idx-19:idx+1]
            features['spy_volatility'] = returns.std() * np.sqrt(252)

            # Market momentum (bullish or bearish regime)
            features['spy_bullish'] = 1.0 if close.iloc[idx] > spy_sma_20 > spy_sma_50 else 0.0

        except Exception as e:
            logger.debug(f"Error getting market features for {date}: {e}")

        return features

    def fetch_stock_data(self, symbol: str, period: str = "2y") -> Optional[pd.DataFrame]:
        """
        Fetch historical stock data with retry logic

        Args:
            symbol: Stock ticker symbol
            period: Data period (default 2 years)

        Returns:
            DataFrame with OHLCV data or None if failed
        """
        from utils.yfinance_helpers import fetch_ticker_data

        logger.info(f"Fetching data for {symbol}...")
        data = fetch_ticker_data(symbol, period=period, interval="1d")

        if data is None:
            return None

        if len(data) < MIN_SAMPLES_PER_STOCK:
            logger.warning(f"Insufficient data for {symbol}: {len(data)} samples")
            return None

        return data

    def create_features(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Create ML features from stock data including market-wide features

        Args:
            data: DataFrame with OHLCV data

        Returns:
            DataFrame with features
        """
        features_list = []

        for i in range(200, len(data)):  # Need 200 days for longest MA
            window_data = data.iloc[:i+1]
            try:
                ml_features = get_ml_features(window_data)
                ml_features['date'] = data.index[i]

                # Add market-wide features
                market_features = self.get_market_features(data.index[i])
                ml_features.update(market_features)

                features_list.append(ml_features)
            except Exception as e:
                logger.debug(f"Error creating features at index {i}: {e}")
                continue

        if not features_list:
            return pd.DataFrame()

        features_df = pd.DataFrame(features_list)
        features_df.set_index('date', inplace=True)

        return features_df

    def create_target(self, data: pd.DataFrame, threshold: float = TARGET_RETURN_THRESHOLD,
                      horizon: int = TARGET_HORIZON_DAYS) -> pd.Series:
        """
        Create target variable: 1 if stock gains > threshold in horizon days, 0 otherwise

        Args:
            data: DataFrame with Close prices
            threshold: Minimum return threshold (default 2%)
            horizon: Number of trading days to look forward (default 5)

        Returns:
            Series with binary target
        """
        future_close = data['Close'].shift(-horizon)
        returns = (future_close - data['Close']) / data['Close']
        target = (returns > threshold).astype(int)
        return target

    def prepare_training_data(self, symbols: List[str]) -> Tuple[pd.DataFrame, pd.Series]:
        """
        Prepare training data for all symbols

        Args:
            symbols: List of stock symbols

        Returns:
            Tuple of (features DataFrame, target Series)
        """
        all_features = []
        all_targets = []

        for i, symbol in enumerate(symbols):
            if i > 0:
                time.sleep(0.5)  # Rate limiting between yfinance requests
            data = self.fetch_stock_data(symbol)
            if data is None:
                continue

            # Create features
            features = self.create_features(data)
            if features.empty:
                logger.warning(f"No features created for {symbol}")
                continue

            # Create target
            target = self.create_target(data)

            # Align features and target
            common_idx = features.index.intersection(target.dropna().index)
            if len(common_idx) < 50:
                logger.warning(f"Insufficient aligned samples for {symbol}: {len(common_idx)}")
                continue

            features_aligned = features.loc[common_idx]
            target_aligned = target.loc[common_idx]

            # Add symbol column for tracking
            features_aligned = features_aligned.copy()
            features_aligned['symbol'] = symbol

            all_features.append(features_aligned)
            all_targets.append(target_aligned)

            logger.info(f"Prepared {len(features_aligned)} samples for {symbol}")

        if not all_features:
            raise ValueError("No training data available")

        X = pd.concat(all_features, axis=0)
        y = pd.concat(all_targets, axis=0)

        # Store feature names (excluding 'symbol')
        self.feature_names = [col for col in X.columns if col != 'symbol']

        logger.info(f"Total training samples: {len(X)}")
        logger.info(f"Features: {len(self.feature_names)}")
        logger.info(f"Target distribution: {y.value_counts().to_dict()}")

        return X, y

    def train_model(self, X: pd.DataFrame, y: pd.Series, n_splits: int = 5,
                    optimize_for: str = 'f1') -> Dict:
        """
        Train Random Forest with time-series cross-validation and hyperparameter tuning

        Args:
            X: Features DataFrame
            y: Target Series
            n_splits: Number of CV splits
            optimize_for: 'f1', 'precision', or 'balanced' (f1 with precision >= 0.75)

        Returns:
            Dict with training metrics
        """
        logger.info(f"Starting model training (optimizing for {optimize_for})...")

        # Remove symbol column for training
        X_train = X[self.feature_names].copy()

        # Handle missing values
        X_train = X_train.fillna(0)

        # Model configurations to try - expanded search
        model_configs = [
            # Random Forest configs - best from previous runs
            ('RF', RandomForestClassifier, {'n_estimators': 400, 'max_depth': 10, 'min_samples_split': 25, 'min_samples_leaf': 12, 'class_weight': 'balanced', 'random_state': 42, 'n_jobs': -1}),
            ('RF', RandomForestClassifier, {'n_estimators': 500, 'max_depth': 12, 'min_samples_split': 20, 'min_samples_leaf': 8, 'class_weight': 'balanced', 'random_state': 42, 'n_jobs': -1}),
            # More conservative configs (shallower trees = less overfitting, higher precision)
            ('RF', RandomForestClassifier, {'n_estimators': 600, 'max_depth': 8, 'min_samples_split': 50, 'min_samples_leaf': 20, 'class_weight': 'balanced', 'random_state': 42, 'n_jobs': -1}),
            ('RF', RandomForestClassifier, {'n_estimators': 500, 'max_depth': 6, 'min_samples_split': 100, 'min_samples_leaf': 30, 'class_weight': 'balanced', 'random_state': 42, 'n_jobs': -1}),
        ]

        # Add XGBoost if available (often best for tabular data)
        if HAS_XGBOOST:
            model_configs.extend([
                ('XGB', XGBClassifier, {'n_estimators': 200, 'max_depth': 5, 'learning_rate': 0.1, 'subsample': 0.8, 'colsample_bytree': 0.8, 'random_state': 42, 'n_jobs': -1, 'eval_metric': 'logloss'}),
                ('XGB', XGBClassifier, {'n_estimators': 300, 'max_depth': 6, 'learning_rate': 0.05, 'subsample': 0.8, 'colsample_bytree': 0.8, 'random_state': 42, 'n_jobs': -1, 'eval_metric': 'logloss'}),
                ('XGB', XGBClassifier, {'n_estimators': 400, 'max_depth': 4, 'learning_rate': 0.05, 'subsample': 0.9, 'colsample_bytree': 0.9, 'min_child_weight': 5, 'random_state': 42, 'n_jobs': -1, 'eval_metric': 'logloss'}),
            ])

        best_score = 0
        best_model_type = None
        best_model_class = None
        best_params = None
        best_cv_scores = []

        # Time series cross-validation
        tscv = TimeSeriesSplit(n_splits=n_splits)

        for model_type, model_class, params in model_configs:
            cv_scores = []
            cv_precision = []
            cv_recall = []

            for fold, (train_idx, val_idx) in enumerate(tscv.split(X_train)):
                X_fold_train, X_fold_val = X_train.iloc[train_idx], X_train.iloc[val_idx]
                y_fold_train, y_fold_val = y.iloc[train_idx], y.iloc[val_idx]

                model = model_class(**params)
                model.fit(X_fold_train, y_fold_train)

                y_pred = model.predict(X_fold_val)
                fold_f1 = f1_score(y_fold_val, y_pred, zero_division=0)
                fold_prec = precision_score(y_fold_val, y_pred, zero_division=0)
                fold_rec = recall_score(y_fold_val, y_pred, zero_division=0)
                cv_scores.append(fold_f1)
                cv_precision.append(fold_prec)
                cv_recall.append(fold_rec)

            mean_f1 = np.mean(cv_scores)
            mean_prec = np.mean(cv_precision)
            mean_rec = np.mean(cv_recall)

            # Scoring based on optimization target
            if optimize_for == 'precision':
                score = mean_prec
            elif optimize_for == 'balanced':
                # F1 but only if precision >= 0.75
                score = mean_f1 if mean_prec >= 0.75 else mean_f1 * 0.5
            else:
                score = mean_f1

            logger.info(f"{model_type} {params.get('n_estimators', 0)}est/{params.get('max_depth', 0)}depth: F1={mean_f1:.4f} Prec={mean_prec:.4f} Rec={mean_rec:.4f}")

            if score > best_score:
                best_score = score
                best_model_type = model_type
                best_model_class = model_class
                best_params = params
                best_cv_scores = cv_scores

        logger.info(f"Best model: {best_model_type} with score = {best_score:.4f}")

        # Train final model with best config
        self.model = best_model_class(**best_params)
        self.model.fit(X_train, y)

        # Final evaluation
        y_pred_final = self.model.predict(X_train)
        y_proba = self.model.predict_proba(X_train)[:, 1]

        metrics = {
            'cv_f1_mean': np.mean(best_cv_scores),
            'cv_f1_std': np.std(best_cv_scores),
            'best_params': best_params,
            'final_accuracy': accuracy_score(y, y_pred_final),
            'precision': precision_score(y, y_pred_final, zero_division=0),
            'recall': recall_score(y, y_pred_final, zero_division=0),
            'f1': f1_score(y, y_pred_final, zero_division=0),
            'n_samples': len(X_train),
            'n_features': len(self.feature_names),
            'positive_class_ratio': float(y.mean())
        }

        # Threshold analysis - find optimal threshold for different precision targets
        logger.info("\n--- Threshold Analysis ---")
        threshold_analysis = []
        for threshold in [0.40, 0.45, 0.50, 0.55, 0.60, 0.65, 0.70, 0.75, 0.80]:
            y_pred_thresh = (y_proba >= threshold).astype(int)
            n_positive = y_pred_thresh.sum()
            if n_positive > 0:
                prec = precision_score(y, y_pred_thresh, zero_division=0)
                rec = recall_score(y, y_pred_thresh, zero_division=0)
                f1 = f1_score(y, y_pred_thresh, zero_division=0)
                threshold_analysis.append({
                    'threshold': threshold,
                    'precision': prec,
                    'recall': rec,
                    'f1': f1,
                    'n_signals': int(n_positive),
                    'signal_rate': float(n_positive / len(y))
                })
                logger.info(f"  Threshold {threshold:.2f}: Prec={prec:.2%} Rec={rec:.2%} F1={f1:.2%} Signals={n_positive}")

        metrics['threshold_analysis'] = threshold_analysis

        # Find recommended threshold (highest F1 with precision >= 80%)
        high_prec_thresholds = [t for t in threshold_analysis if t['precision'] >= 0.80]
        if high_prec_thresholds:
            best_thresh = max(high_prec_thresholds, key=lambda x: x['f1'])
            metrics['recommended_threshold'] = best_thresh['threshold']
            metrics['recommended_precision'] = best_thresh['precision']
            metrics['recommended_recall'] = best_thresh['recall']
            logger.info(f"\n  RECOMMENDED: threshold={best_thresh['threshold']:.2f} for {best_thresh['precision']:.0%} precision")

        # Feature importance
        importance = pd.DataFrame({
            'feature': self.feature_names,
            'importance': self.model.feature_importances_
        }).sort_values('importance', ascending=False)

        metrics['top_features'] = importance.head(10).to_dict('records')

        logger.info(f"Training complete. CV F1: {metrics['cv_f1_mean']:.4f} (+/- {metrics['cv_f1_std']:.4f})")
        logger.info(f"Precision: {metrics['precision']:.4f}, Recall: {metrics['recall']:.4f}, F1: {metrics['f1']:.4f}")

        return metrics

    def save_model(self, metrics: Dict, symbols: List[str]) -> str:
        """
        Save model and metadata to S3 or locally

        Args:
            metrics: Training metrics
            symbols: List of symbols used for training

        Returns:
            Path where model was saved
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Prepare metadata
        metadata = {
            'version': MODEL_VERSION,
            'timestamp': datetime.now().isoformat(),
            'training_params': {
                'target_return_threshold': TARGET_RETURN_THRESHOLD,
                'target_return_pct': f"{TARGET_RETURN_THRESHOLD:.0%}",
                'target_horizon_days': TARGET_HORIZON_DAYS,
                'train_period_years': TRAIN_PERIOD_YEARS
            },
            'symbols_trained': symbols,
            'symbols_count': len(symbols),
            'feature_names': self.feature_names,
            'metrics': metrics,
            'recommended_threshold': metrics.get('recommended_threshold', 0.55),
            'recommended_precision': metrics.get('recommended_precision', 0.80)
        }

        if self.local_mode:
            # Save locally
            output_dir = os.path.join(os.path.dirname(__file__), '..', 'models')
            os.makedirs(output_dir, exist_ok=True)

            model_path = os.path.join(output_dir, f'model_{timestamp}.joblib')
            metadata_path = os.path.join(output_dir, f'metadata_{timestamp}.json')
            current_model_path = os.path.join(output_dir, 'current_model.joblib')
            current_metadata_path = os.path.join(output_dir, 'current_metadata.json')

            joblib.dump(self.model, model_path)
            joblib.dump(self.model, current_model_path)

            with open(metadata_path, 'w') as f:
                json.dump(metadata, f, indent=2)
            with open(current_metadata_path, 'w') as f:
                json.dump(metadata, f, indent=2)

            logger.info(f"Model saved locally to {model_path}")
            return model_path

        else:
            # Save to S3
            import tempfile

            with tempfile.TemporaryDirectory() as tmpdir:
                model_file = os.path.join(tmpdir, 'model.joblib')
                metadata_file = os.path.join(tmpdir, 'metadata.json')

                joblib.dump(self.model, model_file)
                with open(metadata_file, 'w') as f:
                    json.dump(metadata, f, indent=2)

                # Upload to S3
                # Versioned path
                s3_model_key = f'models/{timestamp}/model.joblib'
                s3_metadata_key = f'models/{timestamp}/metadata.json'

                # Current/latest path
                s3_current_model_key = 'models/current/model.joblib'
                s3_current_metadata_key = 'models/current/metadata.json'

                self.s3_client.upload_file(model_file, self.s3_bucket, s3_model_key)
                self.s3_client.upload_file(metadata_file, self.s3_bucket, s3_metadata_key)
                self.s3_client.upload_file(model_file, self.s3_bucket, s3_current_model_key)
                self.s3_client.upload_file(metadata_file, self.s3_bucket, s3_current_metadata_key)

                logger.info(f"Model uploaded to s3://{self.s3_bucket}/{s3_model_key}")
                return f"s3://{self.s3_bucket}/{s3_current_model_key}"


def main():
    """Main training entry point"""
    parser = argparse.ArgumentParser(description='Train StockScout ML Model')
    parser.add_argument('--test', action='store_true', help='Use test subset (5 stocks, faster)')
    parser.add_argument('--stocks', type=str, help='Comma-separated list of stock symbols')
    parser.add_argument('--local', action='store_true', help='Save model locally instead of S3')
    parser.add_argument('--diverse', action='store_true', help='Use diverse stock universe (150+ stocks)')
    parser.add_argument('--category', type=str, help='Use specific category: large_cap_tech, mid_cap_growth, etc.')
    parser.add_argument('--optimize', type=str, choices=['f1', 'precision', 'balanced'],
                        default='balanced', help='Optimization target: f1, precision, or balanced (default)')
    parser.add_argument('--target-return', type=float, default=0.01,
                        help='Target return threshold (default: 0.01 = 1%%)')
    args = parser.parse_args()

    # Determine which stocks to use
    if args.stocks:
        symbols = [s.strip().upper() for s in args.stocks.split(',')]
        logger.info(f"Using custom stock list: {symbols}")
    elif args.test:
        symbols = get_test_subset()
        logger.info(f"Using test subset: {symbols}")
    elif args.diverse:
        symbols = get_diverse_universe()
        logger.info(f"Using diverse stock universe: {len(symbols)} stocks")
    elif args.category:
        symbols = get_stocks_by_category(args.category)
        logger.info(f"Using category '{args.category}': {len(symbols)} stocks")
    else:
        symbols = get_top_50()
        logger.info(f"Using full S&P 500 top 50: {len(symbols)} stocks")

    # Override target return if specified
    global TARGET_RETURN_THRESHOLD
    if args.target_return != 0.01:
        TARGET_RETURN_THRESHOLD = args.target_return
        logger.info(f"Using custom target return: {TARGET_RETURN_THRESHOLD:.1%}")

    # Initialize trainer
    trainer = ModelTrainer(local_mode=args.local)

    try:
        # Prepare data
        logger.info("=" * 50)
        logger.info("PHASE 1: Data Collection & Feature Engineering")
        logger.info("=" * 50)
        X, y = trainer.prepare_training_data(symbols)

        # Train model
        logger.info("=" * 50)
        logger.info("PHASE 2: Model Training")
        logger.info("=" * 50)
        metrics = trainer.train_model(X, y, optimize_for=args.optimize)

        # Save model
        logger.info("=" * 50)
        logger.info("PHASE 3: Model Export")
        logger.info("=" * 50)
        model_path = trainer.save_model(metrics, symbols)

        # Summary
        logger.info("=" * 50)
        logger.info("TRAINING COMPLETE")
        logger.info("=" * 50)
        logger.info(f"Model saved to: {model_path}")
        logger.info(f"CV F1 Score: {metrics['cv_f1_mean']:.2%} (+/- {metrics['cv_f1_std']:.2%})")
        logger.info(f"Precision: {metrics['precision']:.2%}")
        logger.info(f"Recall: {metrics['recall']:.2%}")
        logger.info(f"F1 Score: {metrics['f1']:.2%}")
        logger.info(f"Training samples: {metrics['n_samples']}")
        logger.info(f"Features used: {metrics['n_features']}")

        print("\nTop 5 Most Important Features:")
        for feat in metrics['top_features'][:5]:
            print(f"  - {feat['feature']}: {feat['importance']:.4f}")

        # Show threshold recommendations
        if 'recommended_threshold' in metrics:
            print(f"\nRECOMMENDED SETTINGS:")
            print(f"  Classification threshold: {metrics['recommended_threshold']:.2f}")
            print(f"  Expected precision: {metrics['recommended_precision']:.0%}")
            print(f"  Expected recall: {metrics['recommended_recall']:.0%}")
        else:
            print("\nNote: No threshold found with >= 80% precision")

    except Exception as e:
        logger.error(f"Training failed: {e}")
        raise


if __name__ == '__main__':
    main()
