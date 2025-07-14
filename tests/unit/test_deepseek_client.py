"""
Unit tests for DeepSeek API client
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from app.services.deepseek_client import DeepSeekClient, RateLimiter
from app.core.deepseek_config import DeepSeekConfig, DeepSeekModel
from app.schemas.deepseek import (
    ChatMessage,
    MessageRole,
    ChatCompletionRequest,
    ChatCompletionResponse
)


class TestRateLimiter:
    """Test rate limiter functionality"""
    
    def test_rate_limiter_initialization(self):
        """Test rate limiter initialization"""
        limiter = RateLimiter(max_requests_per_minute=60, max_tokens_per_minute=100000)
        
        assert limiter.max_requests_per_minute == 60
        assert limiter.max_tokens_per_minute == 100000
        assert len(limiter.request_times) == 0
        assert len(limiter.token_usage) == 0
    
    @pytest.mark.asyncio
    async def test_rate_limiter_acquire_success(self):
        """Test successful rate limit acquisition"""
        limiter = RateLimiter(max_requests_per_minute=60, max_tokens_per_minute=100000)
        
        # Should allow first request
        result = await limiter.acquire(estimated_tokens=100)
        assert result is True
        
        # Should allow second request
        result = await limiter.acquire(estimated_tokens=200)
        assert result is True
    
    @pytest.mark.asyncio
    async def test_rate_limiter_request_limit(self):
        """Test request rate limiting"""
        limiter = RateLimiter(max_requests_per_minute=2, max_tokens_per_minute=100000)
        
        # Fill up the request limit
        await limiter.acquire()
        await limiter.acquire()
        
        # Third request should be denied
        result = await limiter.acquire()
        assert result is False
    
    @pytest.mark.asyncio
    async def test_rate_limiter_token_limit(self):
        """Test token rate limiting"""
        limiter = RateLimiter(max_requests_per_minute=60, max_tokens_per_minute=1000)
        
        # Use up most tokens
        await limiter.acquire(estimated_tokens=800)
        
        # Should allow small request
        result = await limiter.acquire(estimated_tokens=100)
        assert result is True
        
        # Should deny large request
        result = await limiter.acquire(estimated_tokens=500)
        assert result is False
    
    def test_rate_limiter_wait_time(self):
        """Test wait time calculation"""
        limiter = RateLimiter(max_requests_per_minute=60, max_tokens_per_minute=100000)
        
        # No requests yet, should be 0 wait time
        wait_time = limiter.get_wait_time()
        assert wait_time == 0


class TestDeepSeekClient:
    """Test DeepSeek API client"""
    
    @pytest.fixture
    def mock_config(self):
        """Mock DeepSeek configuration"""
        return DeepSeekConfig(
            api_key="test-api-key",
            base_url="https://api.deepseek.com",
            default_model=DeepSeekModel.CHAT,
            max_tokens=4096,
            temperature=0.7,
            timeout=60,
            max_requests_per_minute=50,
            max_tokens_per_minute=100000,
            max_retries=3,
            retry_delay=1.0,
            cache_enabled=True,
            cache_ttl=3600
        )
    
    @pytest.fixture
    def mock_openai_response(self):
        """Mock OpenAI API response"""
        mock_response = MagicMock()
        mock_response.id = "test-response-id"
        mock_response.object = "chat.completion"
        mock_response.created = 1234567890
        mock_response.model = "deepseek-chat"
        mock_response.system_fingerprint = "test-fingerprint"
        
        # Mock choice
        mock_choice = MagicMock()
        mock_choice.index = 0
        mock_choice.finish_reason = "stop"
        mock_choice.message.role = "assistant"
        mock_choice.message.content = "Test response content"
        mock_response.choices = [mock_choice]
        
        # Mock usage
        mock_usage = MagicMock()
        mock_usage.prompt_tokens = 10
        mock_usage.completion_tokens = 20
        mock_usage.total_tokens = 30
        mock_response.usage = mock_usage
        
        return mock_response
    
    def test_client_initialization(self, mock_config):
        """Test client initialization"""
        with patch('app.services.deepseek_client.get_global_deepseek_config', return_value=mock_config):
            client = DeepSeekClient()
            
            assert client.config == mock_config
            assert client.rate_limiter.max_requests_per_minute == 50
            assert client.rate_limiter.max_tokens_per_minute == 100000
    
    def test_estimate_tokens(self, mock_config):
        """Test token estimation"""
        with patch('app.services.deepseek_client.get_global_deepseek_config', return_value=mock_config):
            client = DeepSeekClient()
            
            # Test basic estimation
            tokens = client._estimate_tokens("Hello world")
            assert tokens >= 1
            
            # Longer text should have more tokens
            long_text = "This is a much longer text that should have more tokens"
            long_tokens = client._estimate_tokens(long_text)
            assert long_tokens > tokens
    
    def test_create_cache_key(self, mock_config):
        """Test cache key creation"""
        with patch('app.services.deepseek_client.get_global_deepseek_config', return_value=mock_config):
            client = DeepSeekClient()
            
            key = client._create_cache_key("sentiment", "test content", param1="value1")
            
            assert key.startswith("deepseek:sentiment:deepseek-chat:")
            assert len(key.split(":")) == 5
    
    @pytest.mark.asyncio
    async def test_chat_completion_success(self, mock_config, mock_openai_response):
        """Test successful chat completion"""
        with patch('app.services.deepseek_client.get_global_deepseek_config', return_value=mock_config):
            client = DeepSeekClient()
            
            # Mock the OpenAI client
            with patch.object(client.client.chat.completions, 'create', new_callable=AsyncMock) as mock_create:
                mock_create.return_value = mock_openai_response
                
                messages = [
                    ChatMessage(role=MessageRole.USER, content="Hello")
                ]
                
                response = await client.chat_completion(messages=messages)
                
                assert isinstance(response, ChatCompletionResponse)
                assert response.id == "test-response-id"
                assert response.model == "deepseek-chat"
                assert len(response.choices) == 1
                assert response.choices[0].message.content == "Test response content"
                assert response.usage.total_tokens == 30
    
    @pytest.mark.asyncio
    async def test_simple_completion_success(self, mock_config, mock_openai_response):
        """Test successful simple completion"""
        with patch('app.services.deepseek_client.get_global_deepseek_config', return_value=mock_config):
            client = DeepSeekClient()
            
            with patch.object(client, 'chat_completion', new_callable=AsyncMock) as mock_chat:
                mock_response = ChatCompletionResponse(
                    id="test-id",
                    object="chat.completion",
                    created=1234567890,
                    model="deepseek-chat",
                    choices=[{
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": "Test response"
                        },
                        "finish_reason": "stop"
                    }],
                    usage={
                        "prompt_tokens": 10,
                        "completion_tokens": 5,
                        "total_tokens": 15
                    }
                )
                mock_chat.return_value = mock_response
                
                result = await client.simple_completion("Hello")
                
                assert result == "Test response"
                mock_chat.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_simple_completion_no_content(self, mock_config):
        """Test simple completion with no response content"""
        with patch('app.services.deepseek_client.get_global_deepseek_config', return_value=mock_config):
            client = DeepSeekClient()
            
            with patch.object(client, 'chat_completion', new_callable=AsyncMock) as mock_chat:
                mock_response = ChatCompletionResponse(
                    id="test-id",
                    object="chat.completion",
                    created=1234567890,
                    model="deepseek-chat",
                    choices=[],
                    usage=None
                )
                mock_chat.return_value = mock_response
                
                with pytest.raises(Exception, match="No response content received"):
                    await client.simple_completion("Hello")
    
    @pytest.mark.asyncio
    async def test_validate_api_key_success(self, mock_config):
        """Test successful API key validation"""
        with patch('app.services.deepseek_client.get_global_deepseek_config', return_value=mock_config):
            client = DeepSeekClient()
            
            with patch.object(client, 'simple_completion', new_callable=AsyncMock) as mock_simple:
                mock_simple.return_value = "Hello"
                
                result = await client.validate_api_key()
                
                assert result is True
                mock_simple.assert_called_once_with(
                    prompt="Hello",
                    max_tokens=5,
                    correlation_id="api_key_validation"
                )
    
    @pytest.mark.asyncio
    async def test_validate_api_key_failure(self, mock_config):
        """Test API key validation failure"""
        with patch('app.services.deepseek_client.get_global_deepseek_config', return_value=mock_config):
            client = DeepSeekClient()
            
            with patch.object(client, 'simple_completion', new_callable=AsyncMock) as mock_simple:
                mock_simple.side_effect = Exception("API key invalid")
                
                result = await client.validate_api_key()
                
                assert result is False
    
    @pytest.mark.asyncio
    async def test_get_available_models(self, mock_config):
        """Test getting available models"""
        with patch('app.services.deepseek_client.get_global_deepseek_config', return_value=mock_config):
            client = DeepSeekClient()
            
            models = await client.get_available_models()
            
            assert isinstance(models, list)
            assert "deepseek-chat" in models
            assert "deepseek-reasoner" in models
    
    @pytest.mark.asyncio
    async def test_rate_limiting_wait(self, mock_config):
        """Test rate limiting with wait"""
        with patch('app.services.deepseek_client.get_global_deepseek_config', return_value=mock_config):
            client = DeepSeekClient()
            
            # Mock rate limiter to deny first few attempts
            with patch.object(client.rate_limiter, 'acquire', new_callable=AsyncMock) as mock_acquire:
                with patch.object(client.rate_limiter, 'get_wait_time', return_value=0.1) as mock_wait:
                    # First call denied, second call allowed
                    mock_acquire.side_effect = [False, True]
                    
                    with patch.object(client.client.chat.completions, 'create', new_callable=AsyncMock) as mock_create:
                        mock_create.return_value = mock_openai_response
                        
                        request = ChatCompletionRequest(
                            model="deepseek-chat",
                            messages=[ChatMessage(role=MessageRole.USER, content="Hello")]
                        )
                        
                        response = await client._make_request(request)
                        
                        assert mock_acquire.call_count == 2
                        assert response.id == "test-response-id"
    
    @pytest.mark.asyncio
    async def test_close_client(self, mock_config):
        """Test closing the client"""
        with patch('app.services.deepseek_client.get_global_deepseek_config', return_value=mock_config):
            client = DeepSeekClient()
            
            with patch.object(client.client, 'close', new_callable=AsyncMock) as mock_close:
                await client.close()
                mock_close.assert_called_once()


class TestGlobalClientFunctions:
    """Test global client management functions"""
    
    @pytest.mark.asyncio
    async def test_get_deepseek_client(self):
        """Test getting global client"""
        with patch('app.services.deepseek_client.DeepSeekClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value = mock_client
            
            # Clear global client
            import app.services.deepseek_client
            app.services.deepseek_client._global_client = None
            
            client = await app.services.deepseek_client.get_deepseek_client()
            
            assert client == mock_client
            mock_client_class.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_close_deepseek_client(self):
        """Test closing global client"""
        with patch('app.services.deepseek_client.DeepSeekClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value = mock_client
            
            # Set global client
            import app.services.deepseek_client
            app.services.deepseek_client._global_client = mock_client
            
            await app.services.deepseek_client.close_deepseek_client()
            
            mock_client.close.assert_called_once()
            assert app.services.deepseek_client._global_client is None


if __name__ == "__main__":
    pytest.main([__file__])
