"""
DeepSeek API client for WhatsApp Hotel Bot
"""

import asyncio
import hashlib
import json
import time
from typing import Optional, Dict, Any, List, Union
from datetime import datetime, timedelta

import structlog
from openai import AsyncOpenAI
from openai.types.chat import ChatCompletion
from tenacity import (
    retry, 
    stop_after_attempt, 
    wait_exponential, 
    retry_if_exception_type,
    before_sleep_log
)
import aiohttp

from app.core.deepseek_config import (
    DeepSeekConfig,
    DeepSeekModel,
    get_global_deepseek_config,
    create_hotel_deepseek_config,
    create_hotel_sentiment_config,
    create_hotel_response_config
)
from app.schemas.deepseek import (
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatMessage,
    MessageRole,
    DeepSeekAPIError,
    DeepSeekOperationLog
)
from app.core.deepseek_logging import get_deepseek_logger, log_deepseek_operation
from app.utils.circuit_breaker import get_circuit_breaker
from app.core.circuit_breaker_config import get_circuit_breaker_config, CircuitBreakerNames
from app.decorators.retry_decorator import retry_http_requests

logger = structlog.get_logger(__name__)


class RateLimiter:
    """Rate limiter for DeepSeek API calls"""
    
    def __init__(self, max_requests_per_minute: int, max_tokens_per_minute: int):
        self.max_requests_per_minute = max_requests_per_minute
        self.max_tokens_per_minute = max_tokens_per_minute
        self.request_times: List[float] = []
        self.token_usage: List[tuple[float, int]] = []  # (timestamp, tokens)
        self._lock = asyncio.Lock()
    
    async def acquire(self, estimated_tokens: int = 0) -> bool:
        """Acquire rate limit permission"""
        async with self._lock:
            now = time.time()
            minute_ago = now - 60
            
            # Clean old entries
            self.request_times = [t for t in self.request_times if t > minute_ago]
            self.token_usage = [(t, tokens) for t, tokens in self.token_usage if t > minute_ago]
            
            # Check request rate limit
            if len(self.request_times) >= self.max_requests_per_minute:
                return False
            
            # Check token rate limit
            current_tokens = sum(tokens for _, tokens in self.token_usage)
            if current_tokens + estimated_tokens > self.max_tokens_per_minute:
                return False
            
            # Record this request
            self.request_times.append(now)
            if estimated_tokens > 0:
                self.token_usage.append((now, estimated_tokens))
            
            return True
    
    def get_wait_time(self) -> float:
        """Get time to wait before next request"""
        now = time.time()
        minute_ago = now - 60
        
        if self.request_times:
            oldest_request = min(self.request_times)
            if oldest_request > minute_ago:
                return 60 - (now - oldest_request)
        
        return 0


class DeepSeekClient:
    """Async client for DeepSeek API"""
    
    def __init__(self, config: Optional[DeepSeekConfig] = None):
        self.config = config or get_global_deepseek_config()
        self.client = AsyncOpenAI(
            api_key=self.config.api_key,
            base_url=self.config.base_url,
            timeout=self.config.timeout
        )
        self.rate_limiter = RateLimiter(
            self.config.max_requests_per_minute,
            self.config.max_tokens_per_minute
        )
        self.logger = get_deepseek_logger()

        # Circuit breaker for reliability
        cb_config = get_circuit_breaker_config(CircuitBreakerNames.DEEPSEEK_API)
        self.circuit_breaker = get_circuit_breaker(CircuitBreakerNames.DEEPSEEK_API, cb_config)

        logger.info("DeepSeek client initialized",
                   base_url=self.config.base_url,
                   model=self.config.default_model.value,
                   max_tokens=self.config.max_tokens)
    
    def _estimate_tokens(self, text: str) -> int:
        """Estimate token count for text (rough approximation)"""
        # Rough estimation: 1 token ≈ 4 characters for English
        return max(1, len(text) // 4)
    
    def _create_cache_key(self, operation: str, content: str, **kwargs) -> str:
        """Create cache key for request"""
        content_hash = hashlib.md5(content.encode()).hexdigest()
        params_hash = hashlib.md5(json.dumps(kwargs, sort_keys=True).encode()).hexdigest()
        return f"deepseek:{operation}:{self.config.default_model.value}:{content_hash}:{params_hash}"
    
    async def _make_request(
        self,
        request: ChatCompletionRequest,
        operation_type: str = "chat_completion",
        correlation_id: Optional[str] = None
    ) -> ChatCompletionResponse:
        """Make request to DeepSeek API with circuit breaker and retry logic"""

        # Estimate tokens for rate limiting
        total_content = " ".join([msg.content for msg in request.messages])
        estimated_tokens = self._estimate_tokens(total_content) + (request.max_tokens or 0)

        # Wait for rate limit
        max_wait_attempts = 5
        wait_attempts = 0

        while not await self.rate_limiter.acquire(estimated_tokens):
            if wait_attempts >= max_wait_attempts:
                raise Exception("Rate limit exceeded, max wait attempts reached")

            wait_time = self.rate_limiter.get_wait_time()
            logger.warning("Rate limit hit, waiting",
                         wait_time=wait_time,
                         attempt=wait_attempts + 1)
            await asyncio.sleep(wait_time + 1)
            wait_attempts += 1

        # Execute with circuit breaker protection
        async def make_api_request():
            start_time = time.time()

            # Make API call
            response = await self.client.chat.completions.create(
                model=request.model,
                messages=[{"role": msg.role.value, "content": msg.content} for msg in request.messages],
                max_tokens=request.max_tokens,
                temperature=request.temperature,
                top_p=request.top_p,
                frequency_penalty=request.frequency_penalty,
                presence_penalty=request.presence_penalty,
                stop=request.stop,
                stream=request.stream
            )

            response_time = int((time.time() - start_time) * 1000)

            # Convert to our schema
            result = ChatCompletionResponse(
                id=response.id,
                object=response.object,
                created=response.created,
                model=response.model,
                choices=[
                    {
                        "index": choice.index,
                        "message": {
                            "role": choice.message.role,
                            "content": choice.message.content or ""
                        },
                        "finish_reason": choice.finish_reason
                    }
                    for choice in response.choices
                ],
                usage={
                    "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                    "completion_tokens": response.usage.completion_tokens if response.usage else 0,
                    "total_tokens": response.usage.total_tokens if response.usage else 0
                } if response.usage else None,
                system_fingerprint=response.system_fingerprint
            )

            # Log successful operation
            log_deepseek_operation(
                operation_type=operation_type,
                model=request.model,
                input_tokens=result.usage["prompt_tokens"] if result.usage else 0,
                output_tokens=result.usage["completion_tokens"] if result.usage else 0,
                response_time_ms=response_time,
                correlation_id=correlation_id
            )

            return result

        try:
            # Execute with circuit breaker
            return await self.circuit_breaker.call(make_api_request)
        except Exception as e:
            # Log error
            logger.error("DeepSeek API request failed",
                        operation_type=operation_type,
                        model=request.model,
                        error=str(e),
                        error_type=type(e).__name__)

            # Log failed operation
            log_deepseek_operation(
                operation_type=operation_type,
                model=request.model,
                input_tokens=estimated_tokens,
                output_tokens=0,
                response_time_ms=0,
                correlation_id=correlation_id,
                error=str(e)
            )

            raise DeepSeekAPIError(f"DeepSeek API request failed: {str(e)}") from e
    
    async def chat_completion(
        self,
        messages: List[ChatMessage],
        model: Optional[DeepSeekModel] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        correlation_id: Optional[str] = None,
        **kwargs
    ) -> ChatCompletionResponse:
        """Create chat completion"""
        
        request = ChatCompletionRequest(
            model=(model or self.config.default_model).value,
            messages=messages,
            max_tokens=max_tokens or self.config.max_tokens,
            temperature=temperature or self.config.temperature,
            **kwargs
        )
        
        return await self._make_request(
            request, 
            operation_type="chat_completion",
            correlation_id=correlation_id
        )
    
    async def simple_completion(
        self,
        prompt: str,
        system_message: Optional[str] = None,
        model: Optional[DeepSeekModel] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        correlation_id: Optional[str] = None
    ) -> str:
        """Simple text completion"""
        
        messages = []
        if system_message:
            messages.append(ChatMessage(role=MessageRole.SYSTEM, content=system_message))
        messages.append(ChatMessage(role=MessageRole.USER, content=prompt))
        
        response = await self.chat_completion(
            messages=messages,
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            correlation_id=correlation_id
        )
        
        if response.choices and response.choices[0].message.content:
            return response.choices[0].message.content
        
        raise Exception("No response content received from DeepSeek API")
    
    async def validate_api_key(self) -> bool:
        """Validate API key by making a simple request"""
        try:
            await self.simple_completion(
                prompt="Hello",
                max_tokens=5,
                correlation_id="api_key_validation"
            )
            return True
        except Exception as e:
            logger.error("API key validation failed", error=str(e))
            return False
    
    async def get_available_models(self) -> List[str]:
        """Get list of available models"""
        try:
            # DeepSeek API doesn't have a models endpoint, return known models
            return [model.value for model in DeepSeekModel]
        except Exception as e:
            logger.error("Failed to get available models", error=str(e))
            return []
    
    async def close(self):
        """Close the client"""
        await self.client.close()
        logger.info("DeepSeek client closed")


# Global client instance
_global_client: Optional[DeepSeekClient] = None


async def get_deepseek_client() -> DeepSeekClient:
    """Get global DeepSeek client instance"""
    global _global_client
    if _global_client is None:
        _global_client = DeepSeekClient()
    return _global_client


async def close_deepseek_client():
    """Close global DeepSeek client"""
    global _global_client
    if _global_client:
        await _global_client.close()
        _global_client = None


# Hotel-specific client management
_hotel_clients: Dict[str, DeepSeekClient] = {}


async def get_hotel_deepseek_client(hotel_id: str, hotel_settings: Dict[str, Any]) -> DeepSeekClient:
    """
    Get or create hotel-specific DeepSeek client

    Args:
        hotel_id: Hotel identifier
        hotel_settings: Hotel's DeepSeek settings from database

    Returns:
        DeepSeekClient: Hotel-specific client
    """
    global _hotel_clients

    # Check if we already have a client for this hotel
    if hotel_id in _hotel_clients:
        return _hotel_clients[hotel_id]

    # Create hotel-specific configuration
    hotel_config = create_hotel_deepseek_config(hotel_id, hotel_settings)

    # Create and store client
    client = DeepSeekClient(hotel_config)
    _hotel_clients[hotel_id] = client

    logger.info("Created hotel-specific DeepSeek client", hotel_id=hotel_id)

    return client


async def close_hotel_deepseek_client(hotel_id: str):
    """Close hotel-specific DeepSeek client"""
    global _hotel_clients

    if hotel_id in _hotel_clients:
        await _hotel_clients[hotel_id].close()
        del _hotel_clients[hotel_id]
        logger.info("Closed hotel-specific DeepSeek client", hotel_id=hotel_id)


async def close_all_hotel_clients():
    """Close all hotel-specific DeepSeek clients"""
    global _hotel_clients

    for hotel_id, client in _hotel_clients.items():
        await client.close()
        logger.info("Closed hotel DeepSeek client", hotel_id=hotel_id)

    _hotel_clients.clear()


def get_hotel_client_metrics() -> Dict[str, Dict[str, Any]]:
    """Get metrics for all hotel clients"""
    global _hotel_clients

    metrics = {}
    for hotel_id, client in _hotel_clients.items():
        metrics[hotel_id] = {
            "model": client.config.default_model.value,
            "max_tokens": client.config.max_tokens,
            "temperature": client.config.temperature,
            "has_api_key": bool(client.config.api_key),
            "rate_limit_rpm": client.config.max_requests_per_minute,
            "rate_limit_tpm": client.config.max_tokens_per_minute
        }

    return metrics


# Factory function for hotel-specific clients
def create_hotel_deepseek_client(hotel_id: str, hotel_settings: Dict[str, Any]) -> DeepSeekClient:
    """
    Create hotel-specific DeepSeek client

    Args:
        hotel_id: Hotel identifier
        hotel_settings: Hotel's DeepSeek settings

    Returns:
        DeepSeekClient: Configured client for the hotel
    """
    hotel_config = create_hotel_deepseek_config(hotel_id, hotel_settings)
    return DeepSeekClient(hotel_config)


# Export main components
__all__ = [
    'DeepSeekClient',
    'RateLimiter',
    'get_deepseek_client',
    'close_deepseek_client',
    'get_hotel_deepseek_client',
    'close_hotel_deepseek_client',
    'close_all_hotel_clients',
    'get_hotel_client_metrics',
    'create_hotel_deepseek_client'
]
