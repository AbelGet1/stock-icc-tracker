"""
Tests for FastAPI endpoints
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from src.api.main import app

client = TestClient(app)


def test_root_endpoint():
    """Test health check endpoint"""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "service" in data


@patch('src.api.main.lambda_client')
def test_analyze_endpoint_success(mock_lambda):
    """Test successful stock analysis"""
    # Mock Lambda response
    mock_response = {
        'Payload': MagicMock()
    }
    mock_response['Payload'].read.return_value = b'{"statusCode": 200, "body": {"message": "Analysis complete", "results": []}}'
    mock_lambda.invoke.return_value = mock_response
    
    response = client.post(
        "/analyze",
        json={
            "symbols": ["AAPL"],
            "timeframes": ["1d"]
        }
    )
    
    assert response.status_code == 200
    data = response.json()
    assert "message" in data or "results" in data


@patch('src.api.main.lambda_client')
def test_analyze_endpoint_lambda_not_found(mock_lambda):
    """Test Lambda function not found error"""
    # Create a mock exception class that mimics the Lambda client's exception
    mock_exception = type('ResourceNotFoundException', (Exception,), {})
    mock_lambda.exceptions.ResourceNotFoundException = mock_exception
    mock_lambda.invoke.side_effect = mock_exception("Function not found")

    response = client.post(
        "/analyze",
        json={
            "symbols": ["AAPL"],
            "timeframes": ["1d"]
        }
    )

    assert response.status_code == 503


@patch('src.api.main.dynamodb')
def test_subscribe_endpoint(mock_dynamodb):
    """Test alert subscription"""
    mock_table = MagicMock()
    mock_dynamodb.Table.return_value = mock_table
    
    response = client.post(
        "/subscribe",
        json={
            "email": "test@example.com",
            "symbols": ["AAPL", "TSLA"],
            "min_confidence": 0.7
        }
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "test@example.com"
    assert mock_table.put_item.called


@patch('src.api.main.dynamodb')
def test_get_patterns_endpoint(mock_dynamodb):
    """Test get patterns for a symbol"""
    mock_table = MagicMock()
    mock_table.query.return_value = {
        'Items': [
            {
                "symbol": "AAPL",
                "timestamp": "2024-01-01T00:00:00",
                "confidence_score": 0.85
            }
        ]
    }
    mock_dynamodb.Table.return_value = mock_table
    
    response = client.get("/patterns/AAPL")
    
    assert response.status_code == 200
    data = response.json()
    assert data["symbol"] == "AAPL"
    assert "patterns" in data


@patch('src.api.main.dynamodb')
def test_list_all_patterns_endpoint(mock_dynamodb):
    """Test list all patterns"""
    mock_table = MagicMock()
    mock_table.scan.return_value = {
        'Items': [
            {
                "symbol": "AAPL",
                "timestamp": "2024-01-01T00:00:00",
                "confidence_score": 0.85
            }
        ]
    }
    mock_dynamodb.Table.return_value = mock_table
    
    response = client.get("/patterns")
    
    assert response.status_code == 200
    data = response.json()
    assert "patterns" in data
    assert isinstance(data["patterns"], list)
