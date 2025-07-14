"""
Pydantic schemas for DeepSeek API requests and responses
"""

from typing import Optional, List, Dict, Any, Union
from pydantic import BaseModel, Field, validator
from enum import Enum
from datetime import datetime
import uuid


class MessageRole(str, Enum):
    """Message roles for chat completion"""
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


class SentimentType(str, Enum):
    """Sentiment analysis result types"""
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"
    REQUIRES_ATTENTION = "requires_attention"


class ChatMessage(BaseModel):
    """Chat message for DeepSeek API"""
    role: MessageRole
    content: str
    name: Optional[str] = None
    
    @validator('content')
    def validate_content(cls, v):
        if not v or not v.strip():
            raise ValueError("Message content cannot be empty")
        return v.strip()


class ChatCompletionRequest(BaseModel):
    """Request schema for chat completion"""
    model: str = Field(default="deepseek-chat", description="Model to use")
    messages: List[ChatMessage] = Field(..., min_items=1, description="List of messages")
    max_tokens: Optional[int] = Field(default=None, ge=1, le=8192, description="Maximum tokens to generate")
    temperature: Optional[float] = Field(default=None, ge=0.0, le=2.0, description="Sampling temperature")
    top_p: Optional[float] = Field(default=None, ge=0.0, le=1.0, description="Nucleus sampling parameter")
    frequency_penalty: Optional[float] = Field(default=None, ge=-2.0, le=2.0, description="Frequency penalty")
    presence_penalty: Optional[float] = Field(default=None, ge=-2.0, le=2.0, description="Presence penalty")
    stop: Optional[Union[str, List[str]]] = Field(default=None, description="Stop sequences")
    stream: bool = Field(default=False, description="Enable streaming")
    
    @validator('messages')
    def validate_messages(cls, v):
        if not v:
            raise ValueError("At least one message is required")
        return v


class ChatCompletionChoice(BaseModel):
    """Choice in chat completion response"""
    index: int
    message: ChatMessage
    finish_reason: Optional[str] = None


class Usage(BaseModel):
    """Token usage information"""
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    prompt_cache_hit_tokens: Optional[int] = None
    prompt_cache_miss_tokens: Optional[int] = None


class ChatCompletionResponse(BaseModel):
    """Response schema for chat completion"""
    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: List[ChatCompletionChoice]
    usage: Optional[Usage] = None
    system_fingerprint: Optional[str] = None


class SentimentAnalysisRequest(BaseModel):
    """Request schema for sentiment analysis"""
    text: str = Field(..., min_length=1, max_length=10000, description="Text to analyze")
    context: Optional[Dict[str, Any]] = Field(default=None, description="Additional context")
    language: Optional[str] = Field(default="en", description="Text language")
    hotel_id: Optional[str] = Field(default=None, description="Hotel ID for context")
    guest_id: Optional[str] = Field(default=None, description="Guest ID for context")
    
    @validator('text')
    def validate_text(cls, v):
        if not v or not v.strip():
            raise ValueError("Text cannot be empty")
        return v.strip()


class SentimentAnalysisResult(BaseModel):
    """Result schema for sentiment analysis"""
    sentiment: SentimentType
    score: float = Field(..., ge=-1.0, le=1.0, description="Sentiment score from -1 to 1")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score from 0 to 1")
    requires_attention: bool = Field(default=False, description="Whether this requires staff attention")
    reason: Optional[str] = Field(default=None, description="Explanation for the sentiment")
    keywords: Optional[List[str]] = Field(default=None, description="Key sentiment indicators")
    
    @validator('score')
    def validate_score_sentiment_consistency(cls, v, values):
        if 'sentiment' in values:
            sentiment = values['sentiment']
            if sentiment == SentimentType.POSITIVE and v < 0:
                raise ValueError("Positive sentiment must have positive score")
            elif sentiment == SentimentType.NEGATIVE and v > 0:
                raise ValueError("Negative sentiment must have negative score")
        return v


class ResponseGenerationRequest(BaseModel):
    """Request schema for response generation"""
    message: str = Field(..., min_length=1, description="Guest message to respond to")
    context: Optional[Dict[str, Any]] = Field(default=None, description="Conversation context")
    hotel_id: str = Field(..., description="Hotel ID")
    guest_id: Optional[str] = Field(default=None, description="Guest ID")
    conversation_history: Optional[List[Dict[str, Any]]] = Field(default=None, description="Recent conversation history")
    guest_preferences: Optional[Dict[str, Any]] = Field(default=None, description="Guest preferences")
    hotel_settings: Optional[Dict[str, Any]] = Field(default=None, description="Hotel-specific settings")
    language: Optional[str] = Field(default="en", description="Response language")
    response_type: Optional[str] = Field(default="helpful", description="Type of response to generate")
    
    @validator('message')
    def validate_message(cls, v):
        if not v or not v.strip():
            raise ValueError("Message cannot be empty")
        return v.strip()


class ResponseGenerationResult(BaseModel):
    """Result schema for response generation"""
    response: str = Field(..., min_length=1, description="Generated response")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence in the response")
    response_type: str = Field(default="helpful", description="Type of response generated")
    reasoning: Optional[str] = Field(default=None, description="Reasoning behind the response")
    suggested_actions: Optional[List[str]] = Field(default=None, description="Suggested follow-up actions")
    
    @validator('response')
    def validate_response(cls, v):
        if not v or not v.strip():
            raise ValueError("Response cannot be empty")
        return v.strip()


class DeepSeekAPIError(BaseModel):
    """Error response from DeepSeek API"""
    error: Dict[str, Any]
    
    @property
    def error_type(self) -> Optional[str]:
        return self.error.get('type')
    
    @property
    def error_message(self) -> Optional[str]:
        return self.error.get('message')
    
    @property
    def error_code(self) -> Optional[str]:
        return self.error.get('code')


class DeepSeekOperationLog(BaseModel):
    """Log entry for DeepSeek operations"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    operation_type: str = Field(..., description="Type of operation (sentiment, response, etc.)")
    hotel_id: Optional[str] = None
    guest_id: Optional[str] = None
    message_id: Optional[str] = None
    model_used: str = Field(..., description="DeepSeek model used")
    tokens_used: Optional[int] = None
    api_response_time_ms: Optional[int] = None
    success: bool = Field(default=True)
    error_message: Optional[str] = None
    correlation_id: Optional[str] = None
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class CacheKey(BaseModel):
    """Cache key for DeepSeek responses"""
    operation_type: str
    content_hash: str
    model: str
    parameters_hash: str
    
    def to_string(self) -> str:
        """Convert cache key to string"""
        return f"deepseek:{self.operation_type}:{self.model}:{self.content_hash}:{self.parameters_hash}"


class CachedResponse(BaseModel):
    """Cached DeepSeek response"""
    key: CacheKey
    response: Dict[str, Any]
    created_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: datetime
    hit_count: int = Field(default=0)
    
    @property
    def is_expired(self) -> bool:
        return datetime.utcnow() > self.expires_at
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


# Export main components
__all__ = [
    'MessageRole',
    'SentimentType',
    'ChatMessage',
    'ChatCompletionRequest',
    'ChatCompletionChoice',
    'Usage',
    'ChatCompletionResponse',
    'SentimentAnalysisRequest',
    'SentimentAnalysisResult',
    'ResponseGenerationRequest',
    'ResponseGenerationResult',
    'DeepSeekAPIError',
    'DeepSeekOperationLog',
    'CacheKey',
    'CachedResponse'
]
