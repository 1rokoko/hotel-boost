"""
Unit tests for Green API client
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
import httpx
from datetime import datetime

from app.core.green_api_config import GreenAPIConfig, GreenAPIRetryConfig, GreenAPIRateLimitConfig
from app.services.green_api import GreenAPIClient, RateLimiter, RetryHandler
from app.schemas.green_api import (
    SendTextMessageRequest, SendMessageResponse,
    GetSettingsResponse, GetStateInstanceResponse
)


class TestGreenAPIConfig:
    """Test Green API configuration"""
    
    def test_config_creation(self):
        """Test basic config creation"""
        config = GreenAPIConfig(
            base_url="https://api.green-api.com",
            instance_id="1234567890",
            token="test_token"
        )
        
        assert config.base_url == "https://api.green-api.com"
        assert config.instance_id == "1234567890"
        assert config.token == "test_token"
        assert config.api_version == "v1"
    
    def test_config_validation(self):
        """Test config validation"""
        # Test invalid base URL
        with pytest.raises(ValueError, match="base_url must start with"):
            GreenAPIConfig(base_url="invalid-url")
        
        # Test base URL normalization
        config = GreenAPIConfig(base_url="https://api.green-api.com/")
        assert config.base_url == "https://api.green-api.com"
    
    def test_get_api_url(self):
        """Test API URL generation"""
        config = GreenAPIConfig(
            base_url="https://api.green-api.com",
            instance_id="1234567890"
        )
        
        url = config.get_api_url()
        assert url == "https://api.green-api.com/waInstance1234567890"
        
        # Test with custom instance ID
        url = config.get_api_url("9876543210")
        assert url == "https://api.green-api.com/waInstance9876543210"
    
    def test_httpx_timeout_conversion(self):
        """Test conversion to httpx timeout format"""
        config = GreenAPIConfig()
        timeout_dict = config.to_httpx_timeout()
        
        assert "connect" in timeout_dict
        assert "read" in timeout_dict
        assert "write" in timeout_dict
        assert "pool" in timeout_dict


class TestRateLimiter:
    """Test rate limiter functionality"""
    
    @pytest.mark.asyncio
    async def test_rate_limiter_basic(self):
        """Test basic rate limiting"""
        limiter = RateLimiter(
            requests_per_minute=60,
            requests_per_second=2,
            burst_limit=5
        )
        
        # Should allow first request immediately
        start_time = asyncio.get_event_loop().time()
        await limiter.acquire()
        elapsed = asyncio.get_event_loop().time() - start_time
        
        assert elapsed < 0.1  # Should be immediate
    
    @pytest.mark.asyncio
    async def test_rate_limiter_per_second_limit(self):
        """Test per-second rate limiting"""
        limiter = RateLimiter(
            requests_per_minute=60,
            requests_per_second=1,  # Very restrictive
            burst_limit=2
        )
        
        # First request should be immediate
        await limiter.acquire()
        
        # Second request should be delayed
        start_time = asyncio.get_event_loop().time()
        await limiter.acquire()
        elapsed = asyncio.get_event_loop().time() - start_time
        
        assert elapsed >= 0.9  # Should wait ~1 second


class TestRetryHandler:
    """Test retry handler functionality"""
    
    def test_retry_handler_creation(self):
        """Test retry handler creation"""
        config = GreenAPIConfig()
        handler = RetryHandler(config)
        
        assert handler.max_retries == config.retry.max_retries
        assert handler.base_delay == config.retry.base_delay
    
    def test_calculate_delay(self):
        """Test delay calculation"""
        config = GreenAPIConfig()
        config.retry.base_delay = 1.0
        config.retry.exponential_base = 2.0
        config.retry.jitter = False  # Disable jitter for predictable testing
        
        handler = RetryHandler(config)
        
        # Test exponential backoff
        assert handler._calculate_delay(0) == 1.0
        assert handler._calculate_delay(1) == 2.0
        assert handler._calculate_delay(2) == 4.0
    
    def test_calculate_delay_rate_limiting(self):
        """Test delay calculation for rate limiting"""
        config = GreenAPIConfig()
        config.retry.base_delay = 1.0
        config.retry.jitter = False
        
        handler = RetryHandler(config)
        
        # Rate limiting should cap at 60 seconds
        delay = handler._calculate_delay(10, status_code=429)
        assert delay <= 60.0
    
    @pytest.mark.asyncio
    async def test_execute_with_retry_success(self):
        """Test successful execution without retry"""
        config = GreenAPIConfig()
        handler = RetryHandler(config)
        
        mock_func = AsyncMock(return_value="success")
        
        result = await handler.execute_with_retry(mock_func, "arg1", kwarg1="value1")
        
        assert result == "success"
        mock_func.assert_called_once_with("arg1", kwarg1="value1")
    
    @pytest.mark.asyncio
    async def test_execute_with_retry_failure(self):
        """Test retry on failure"""
        config = GreenAPIConfig()
        config.retry.max_retries = 2
        config.retry.base_delay = 0.01  # Very short delay for testing
        
        handler = RetryHandler(config)
        
        # Mock function that always fails
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        
        mock_func = AsyncMock(side_effect=httpx.HTTPStatusError(
            "Server error", request=Mock(), response=mock_response
        ))
        
        with pytest.raises(httpx.HTTPStatusError):
            await handler.execute_with_retry(mock_func)
        
        # Should be called max_retries + 1 times (initial + retries)
        assert mock_func.call_count == 3


class TestGreenAPIClient:
    """Test Green API client functionality"""
    
    @pytest.fixture
    def config(self):
        """Create test configuration"""
        return GreenAPIConfig(
            base_url="https://api.green-api.com",
            instance_id="1234567890",
            token="test_token"
        )
    
    @pytest.fixture
    def client(self, config):
        """Create test client"""
        return GreenAPIClient(config)
    
    @pytest.mark.asyncio
    async def test_client_context_manager(self, client):
        """Test client as async context manager"""
        async with client as c:
            assert c._client is not None
        
        # Client should be closed after context
        assert client._client is None
    
    @pytest.mark.asyncio
    async def test_send_text_message_success(self, client):
        """Test successful text message sending"""
        # Mock HTTP response
        mock_response = {
            "idMessage": "test_message_id_123"
        }
        
        with patch.object(client, '_make_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response
            
            request = SendTextMessageRequest(
                chatId="1234567890@c.us",
                message="Test message"
            )
            
            response = await client.send_text_message(request)
            
            assert isinstance(response, SendMessageResponse)
            assert response.idMessage == "test_message_id_123"
            
            mock_request.assert_called_once_with(
                "POST", "sendMessage", request.dict()
            )
    
    @pytest.mark.asyncio
    async def test_get_settings_success(self, client):
        """Test successful settings retrieval"""
        mock_response = {
            "wh_url": "https://example.com/webhook",
            "delaySendMessagesMilliseconds": 1000,
            "markIncomingMessagesReaded": "yes"
        }
        
        with patch.object(client, '_make_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response
            
            response = await client.get_settings()
            
            assert isinstance(response, GetSettingsResponse)
            assert response.wh_url == "https://example.com/webhook"
            assert response.delaySendMessagesMilliseconds == 1000
    
    @pytest.mark.asyncio
    async def test_get_state_instance_success(self, client):
        """Test successful state instance retrieval"""
        mock_response = {
            "stateInstance": "authorized"
        }
        
        with patch.object(client, '_make_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response
            
            response = await client.get_state_instance()
            
            assert isinstance(response, GetStateInstanceResponse)
            assert response.stateInstance == "authorized"
    
    @pytest.mark.asyncio
    async def test_receive_notification_empty(self, client):
        """Test receiving empty notification"""
        with patch.object(client, '_make_request', new_callable=AsyncMock) as mock_request:
            # Mock 204 No Content response
            mock_response = Mock()
            mock_response.status_code = 204
            
            mock_request.side_effect = httpx.HTTPStatusError(
                "No Content", request=Mock(), response=mock_response
            )
            
            result = await client.receive_notification()
            
            assert result is None
    
    def test_get_metrics(self, client):
        """Test metrics retrieval"""
        client.request_count = 10
        client.error_count = 2
        client.last_request_time = datetime(2023, 1, 1, 12, 0, 0)
        
        metrics = client.get_metrics()
        
        assert metrics["request_count"] == 10
        assert metrics["error_count"] == 2
        assert metrics["error_rate"] == 0.2
        assert metrics["instance_id"] == client.config.instance_id
        assert "last_request_time" in metrics
    
    @pytest.mark.asyncio
    async def test_make_request_rate_limiting(self, client):
        """Test that _make_request applies rate limiting"""
        with patch.object(client.rate_limiter, 'acquire', new_callable=AsyncMock) as mock_acquire:
            with patch.object(client, '_client') as mock_http_client:
                mock_response = Mock()
                mock_response.json.return_value = {"success": True}
                mock_http_client.request = AsyncMock(return_value=mock_response)
                
                await client._make_request("GET", "test")
                
                mock_acquire.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_make_request_retry_on_failure(self, client):
        """Test that _make_request retries on failure"""
        with patch.object(client.rate_limiter, 'acquire', new_callable=AsyncMock):
            with patch.object(client.retry_handler, 'execute_with_retry', new_callable=AsyncMock) as mock_retry:
                mock_retry.return_value = {"success": True}
                
                result = await client._make_request("GET", "test")
                
                assert result == {"success": True}
                mock_retry.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__])
