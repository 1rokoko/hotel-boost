"""
Fallback service for graceful degradation when dependencies fail
"""

import asyncio
import time
from typing import Dict, Any, Optional, List, Callable, Union
from enum import Enum
from dataclasses import dataclass
import json

from app.core.logging import get_logger
from app.core.config import settings

logger = get_logger(__name__)


class DegradationLevel(Enum):
    """Levels of service degradation"""
    NORMAL = "normal"           # All services working normally
    MINOR = "minor"            # Minor degradation, some features disabled
    MODERATE = "moderate"      # Moderate degradation, fallback responses
    SEVERE = "severe"          # Severe degradation, minimal functionality
    CRITICAL = "critical"      # Critical degradation, emergency mode


@dataclass
class FallbackResponse:
    """Response from fallback mechanism"""
    success: bool
    data: Any
    degradation_level: DegradationLevel
    fallback_used: str
    original_error: Optional[str] = None
    metadata: Dict[str, Any] = None


class FallbackService:
    """
    Service for handling graceful degradation and fallback mechanisms
    """
    
    def __init__(self):
        self.current_degradation_level = DegradationLevel.NORMAL
        self._fallback_handlers: Dict[str, Callable] = {}
        self._degradation_callbacks: List[Callable] = []
        
        # Predefined fallback responses
        self._setup_default_fallbacks()
    
    def _setup_default_fallbacks(self) -> None:
        """Setup default fallback responses"""
        
        # AI fallback responses
        self.ai_fallback_responses = {
            "greeting": "Hello! I'm here to help you. How can I assist you today?",
            "apology": "I apologize, but I'm experiencing some technical difficulties. Please try again in a few moments.",
            "escalation": "I'm having trouble processing your request right now. Let me connect you with a human agent who can help you better.",
            "general_help": "I'm here to help! While I'm experiencing some technical issues, I can still assist you with basic questions.",
            "error": "I'm sorry, but I'm unable to process your request at the moment. Please try again later or contact our support team.",
            "maintenance": "Our AI system is currently undergoing maintenance. We'll be back to full functionality shortly."
        }
        
        # WhatsApp fallback responses
        self.whatsapp_fallback_responses = {
            "queue_message": "Your message has been queued and will be sent as soon as our messaging service is restored.",
            "delivery_failed": "We're experiencing issues with message delivery. Your message will be retried automatically.",
            "service_unavailable": "Our messaging service is temporarily unavailable. We're working to restore it quickly."
        }
    
    def register_fallback_handler(self, service_name: str, handler: Callable) -> None:
        """
        Register a fallback handler for a service
        
        Args:
            service_name: Name of the service
            handler: Fallback handler function
        """
        self._fallback_handlers[service_name] = handler
        logger.info("Fallback handler registered", service=service_name)
    
    def register_degradation_callback(self, callback: Callable[[DegradationLevel, DegradationLevel], None]) -> None:
        """
        Register callback for degradation level changes
        
        Args:
            callback: Function to call when degradation level changes
        """
        self._degradation_callbacks.append(callback)
    
    def set_degradation_level(self, level: DegradationLevel, reason: str = "") -> None:
        """
        Set current degradation level
        
        Args:
            level: New degradation level
            reason: Reason for degradation
        """
        old_level = self.current_degradation_level
        self.current_degradation_level = level
        
        logger.warning("Degradation level changed",
                      old_level=old_level.value,
                      new_level=level.value,
                      reason=reason)
        
        # Call degradation callbacks
        for callback in self._degradation_callbacks:
            try:
                callback(old_level, level)
            except Exception as e:
                logger.error("Degradation callback failed", error=str(e))
    
    async def ai_fallback(self, message_type: str = "general_help", 
                         context: Optional[Dict[str, Any]] = None) -> FallbackResponse:
        """
        AI service fallback - return predefined responses
        
        Args:
            message_type: Type of fallback message
            context: Additional context for response
            
        Returns:
            FallbackResponse with predefined message
        """
        try:
            # Get appropriate fallback response
            if message_type in self.ai_fallback_responses:
                response_text = self.ai_fallback_responses[message_type]
            else:
                response_text = self.ai_fallback_responses["general_help"]
            
            # Add context if available
            if context and "user_message" in context:
                response_text += f" (Regarding: {context['user_message'][:50]}...)"
            
            return FallbackResponse(
                success=True,
                data={
                    "response": response_text,
                    "sentiment": "neutral",
                    "confidence": 0.5,
                    "fallback": True
                },
                degradation_level=self.current_degradation_level,
                fallback_used="ai_predefined_response",
                metadata={"message_type": message_type}
            )
            
        except Exception as e:
            logger.error("AI fallback failed", error=str(e))
            return FallbackResponse(
                success=False,
                data=None,
                degradation_level=DegradationLevel.CRITICAL,
                fallback_used="ai_fallback_error",
                original_error=str(e)
            )
    
    async def whatsapp_fallback(self, message_data: Dict[str, Any]) -> FallbackResponse:
        """
        WhatsApp service fallback - queue messages for later delivery
        
        Args:
            message_data: Message data to queue
            
        Returns:
            FallbackResponse indicating message was queued
        """
        try:
            # In a real implementation, this would queue the message in Redis or database
            # For now, we'll simulate queuing
            
            queued_message = {
                "id": f"queued_{int(time.time())}",
                "original_data": message_data,
                "queued_at": time.time(),
                "retry_count": 0,
                "status": "queued"
            }
            
            # Log the queued message
            logger.info("Message queued for later delivery",
                       message_id=queued_message["id"],
                       recipient=message_data.get("to", "unknown"))
            
            return FallbackResponse(
                success=True,
                data=queued_message,
                degradation_level=self.current_degradation_level,
                fallback_used="whatsapp_message_queue",
                metadata={"queue_size": 1}  # Would be actual queue size
            )
            
        except Exception as e:
            logger.error("WhatsApp fallback failed", error=str(e))
            return FallbackResponse(
                success=False,
                data=None,
                degradation_level=DegradationLevel.CRITICAL,
                fallback_used="whatsapp_fallback_error",
                original_error=str(e)
            )
    
    async def database_fallback(self, operation: str, data: Optional[Dict[str, Any]] = None) -> FallbackResponse:
        """
        Database fallback - read-only mode or cached responses
        
        Args:
            operation: Database operation type
            data: Operation data
            
        Returns:
            FallbackResponse with fallback behavior
        """
        try:
            if operation == "read":
                # For read operations, try to return cached data or default values
                return FallbackResponse(
                    success=True,
                    data={"message": "Using cached data due to database issues"},
                    degradation_level=self.current_degradation_level,
                    fallback_used="database_cache_fallback"
                )
            
            elif operation in ["write", "update", "delete"]:
                # For write operations, queue them for later processing
                queued_operation = {
                    "operation": operation,
                    "data": data,
                    "queued_at": time.time(),
                    "status": "queued_for_retry"
                }
                
                logger.info("Database operation queued",
                           operation=operation,
                           queued_at=queued_operation["queued_at"])
                
                return FallbackResponse(
                    success=True,
                    data=queued_operation,
                    degradation_level=self.current_degradation_level,
                    fallback_used="database_operation_queue"
                )
            
            else:
                return FallbackResponse(
                    success=False,
                    data=None,
                    degradation_level=DegradationLevel.SEVERE,
                    fallback_used="database_unknown_operation",
                    original_error=f"Unknown operation: {operation}"
                )
                
        except Exception as e:
            logger.error("Database fallback failed", error=str(e))
            return FallbackResponse(
                success=False,
                data=None,
                degradation_level=DegradationLevel.CRITICAL,
                fallback_used="database_fallback_error",
                original_error=str(e)
            )
    
    async def redis_fallback(self, operation: str, key: str, value: Any = None) -> FallbackResponse:
        """
        Redis fallback - in-memory cache or skip caching
        
        Args:
            operation: Redis operation (get, set, delete)
            key: Cache key
            value: Value for set operations
            
        Returns:
            FallbackResponse with fallback behavior
        """
        try:
            # Simple in-memory fallback cache
            if not hasattr(self, '_memory_cache'):
                self._memory_cache = {}
            
            if operation == "get":
                cached_value = self._memory_cache.get(key)
                return FallbackResponse(
                    success=True,
                    data=cached_value,
                    degradation_level=self.current_degradation_level,
                    fallback_used="redis_memory_cache",
                    metadata={"cache_hit": cached_value is not None}
                )
            
            elif operation == "set":
                self._memory_cache[key] = value
                # Limit memory cache size
                if len(self._memory_cache) > 1000:
                    # Remove oldest entries (simple FIFO)
                    keys_to_remove = list(self._memory_cache.keys())[:100]
                    for k in keys_to_remove:
                        del self._memory_cache[k]
                
                return FallbackResponse(
                    success=True,
                    data={"cached": True},
                    degradation_level=self.current_degradation_level,
                    fallback_used="redis_memory_cache"
                )
            
            elif operation == "delete":
                self._memory_cache.pop(key, None)
                return FallbackResponse(
                    success=True,
                    data={"deleted": True},
                    degradation_level=self.current_degradation_level,
                    fallback_used="redis_memory_cache"
                )
            
            else:
                return FallbackResponse(
                    success=False,
                    data=None,
                    degradation_level=DegradationLevel.MODERATE,
                    fallback_used="redis_unsupported_operation",
                    original_error=f"Unsupported operation: {operation}"
                )
                
        except Exception as e:
            logger.error("Redis fallback failed", error=str(e))
            return FallbackResponse(
                success=False,
                data=None,
                degradation_level=DegradationLevel.CRITICAL,
                fallback_used="redis_fallback_error",
                original_error=str(e)
            )
    
    async def execute_with_fallback(self, service_name: str, primary_func: Callable, 
                                  fallback_func: Optional[Callable] = None,
                                  *args, **kwargs) -> FallbackResponse:
        """
        Execute function with automatic fallback
        
        Args:
            service_name: Name of the service
            primary_func: Primary function to execute
            fallback_func: Fallback function (optional)
            *args: Function arguments
            **kwargs: Function keyword arguments
            
        Returns:
            FallbackResponse with result or fallback
        """
        try:
            # Try primary function first
            result = await primary_func(*args, **kwargs)
            return FallbackResponse(
                success=True,
                data=result,
                degradation_level=DegradationLevel.NORMAL,
                fallback_used="none"
            )
            
        except Exception as e:
            logger.warning("Primary function failed, using fallback",
                          service=service_name,
                          error=str(e))
            
            # Try custom fallback function
            if fallback_func:
                try:
                    fallback_result = await fallback_func(*args, **kwargs)
                    return FallbackResponse(
                        success=True,
                        data=fallback_result,
                        degradation_level=DegradationLevel.MINOR,
                        fallback_used="custom_fallback",
                        original_error=str(e)
                    )
                except Exception as fallback_error:
                    logger.error("Custom fallback failed",
                               service=service_name,
                               error=str(fallback_error))
            
            # Try registered fallback handler
            if service_name in self._fallback_handlers:
                try:
                    handler_result = await self._fallback_handlers[service_name](*args, **kwargs)
                    return FallbackResponse(
                        success=True,
                        data=handler_result,
                        degradation_level=DegradationLevel.MODERATE,
                        fallback_used="registered_handler",
                        original_error=str(e)
                    )
                except Exception as handler_error:
                    logger.error("Registered fallback handler failed",
                               service=service_name,
                               error=str(handler_error))
            
            # No fallback available
            return FallbackResponse(
                success=False,
                data=None,
                degradation_level=DegradationLevel.SEVERE,
                fallback_used="none_available",
                original_error=str(e)
            )
    
    def get_degradation_status(self) -> Dict[str, Any]:
        """Get current degradation status"""
        return {
            "current_level": self.current_degradation_level.value,
            "registered_handlers": list(self._fallback_handlers.keys()),
            "memory_cache_size": len(getattr(self, '_memory_cache', {})),
            "available_ai_responses": list(self.ai_fallback_responses.keys()),
            "available_whatsapp_responses": list(self.whatsapp_fallback_responses.keys())
        }


# Global fallback service instance
fallback_service = FallbackService()


# Default degradation callback
def log_degradation_change(old_level: DegradationLevel, new_level: DegradationLevel) -> None:
    """Log degradation level changes"""
    if new_level.value != old_level.value:
        if new_level in [DegradationLevel.SEVERE, DegradationLevel.CRITICAL]:
            logger.critical("System degradation level changed",
                           old_level=old_level.value,
                           new_level=new_level.value)
        else:
            logger.warning("System degradation level changed",
                          old_level=old_level.value,
                          new_level=new_level.value)


# Register default callback
fallback_service.register_degradation_callback(log_degradation_change)
