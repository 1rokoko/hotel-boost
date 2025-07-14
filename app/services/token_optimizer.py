"""
Token optimization service for DeepSeek AI
"""

import re
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta

import structlog

from app.schemas.deepseek import ChatMessage, MessageRole
from app.models.message import Message
from app.models.guest import Guest
from app.models.hotel import Hotel

logger = structlog.get_logger(__name__)


class TokenOptimizer:
    """Service for optimizing token usage in DeepSeek API calls"""
    
    def __init__(self):
        # Token estimation constants (rough approximations)
        self.chars_per_token = 4  # Average characters per token
        self.max_context_tokens = 8000  # Leave room for response
        
        # Optimization strategies
        self.strategies = {
            'compress_whitespace': True,
            'remove_redundant_info': True,
            'summarize_long_context': True,
            'prioritize_recent_messages': True,
            'use_abbreviated_prompts': False,  # Can reduce quality
            'remove_metadata': True
        }
        
        # Token usage tracking
        self.usage_stats = {
            'total_tokens_saved': 0,
            'optimizations_applied': 0,
            'average_reduction_percent': 0.0
        }
    
    def estimate_tokens(self, text: str) -> int:
        """Estimate token count for text"""
        if not text:
            return 0
        
        # Remove extra whitespace for more accurate estimation
        cleaned_text = re.sub(r'\s+', ' ', text.strip())
        
        # Rough estimation: 1 token ≈ 4 characters for English
        # Add some buffer for special tokens and formatting
        estimated_tokens = max(1, len(cleaned_text) // self.chars_per_token)
        
        return int(estimated_tokens * 1.1)  # 10% buffer
    
    def optimize_text(self, text: str, max_tokens: Optional[int] = None) -> str:
        """Optimize text to reduce token usage"""
        if not text:
            return text
        
        original_length = len(text)
        optimized_text = text
        
        # Apply optimization strategies
        if self.strategies['compress_whitespace']:
            optimized_text = self._compress_whitespace(optimized_text)
        
        if self.strategies['remove_redundant_info']:
            optimized_text = self._remove_redundant_info(optimized_text)
        
        if max_tokens and self.estimate_tokens(optimized_text) > max_tokens:
            optimized_text = self._truncate_to_token_limit(optimized_text, max_tokens)
        
        # Track optimization stats
        if len(optimized_text) < original_length:
            self.usage_stats['optimizations_applied'] += 1
            reduction_percent = (original_length - len(optimized_text)) / original_length * 100
            
            # Update average reduction
            current_avg = self.usage_stats['average_reduction_percent']
            count = self.usage_stats['optimizations_applied']
            self.usage_stats['average_reduction_percent'] = (
                (current_avg * (count - 1) + reduction_percent) / count
            )
            
            logger.debug("Text optimized",
                        original_length=original_length,
                        optimized_length=len(optimized_text),
                        reduction_percent=round(reduction_percent, 2))
        
        return optimized_text
    
    def _compress_whitespace(self, text: str) -> str:
        """Compress multiple whitespace characters"""
        # Replace multiple spaces with single space
        text = re.sub(r' +', ' ', text)
        
        # Replace multiple newlines with single newline
        text = re.sub(r'\n+', '\n', text)
        
        # Remove trailing/leading whitespace
        text = text.strip()
        
        return text
    
    def _remove_redundant_info(self, text: str) -> str:
        """Remove redundant information from text"""
        # Remove common redundant phrases
        redundant_patterns = [
            r'\b(please note that|it should be noted that|it is important to note that)\b',
            r'\b(as mentioned before|as previously stated|as we discussed)\b',
            r'\b(in other words|that is to say|to put it simply)\b',
            r'\b(obviously|clearly|of course|naturally)\b'
        ]
        
        for pattern in redundant_patterns:
            text = re.sub(pattern, '', text, flags=re.IGNORECASE)
        
        # Clean up extra spaces created by removals
        text = re.sub(r' +', ' ', text)
        
        return text.strip()
    
    def _truncate_to_token_limit(self, text: str, max_tokens: int) -> str:
        """Truncate text to fit within token limit"""
        estimated_tokens = self.estimate_tokens(text)
        
        if estimated_tokens <= max_tokens:
            return text
        
        # Calculate target character count
        target_chars = int(max_tokens * self.chars_per_token * 0.9)  # 10% safety margin
        
        if len(text) <= target_chars:
            return text
        
        # Truncate at word boundary
        truncated = text[:target_chars]
        last_space = truncated.rfind(' ')
        
        if last_space > target_chars * 0.8:  # If we can find a reasonable word boundary
            truncated = truncated[:last_space]
        
        # Add truncation indicator
        truncated += "... [truncated]"
        
        logger.debug("Text truncated for token limit",
                    original_tokens=estimated_tokens,
                    max_tokens=max_tokens,
                    original_length=len(text),
                    truncated_length=len(truncated))
        
        return truncated
    
    def optimize_conversation_history(
        self,
        messages: List[Dict[str, Any]],
        max_context_tokens: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Optimize conversation history to reduce token usage"""
        if not messages:
            return messages
        
        max_tokens = max_context_tokens or self.max_context_tokens
        
        # Start with most recent messages
        optimized_messages = []
        current_tokens = 0
        
        for message in reversed(messages):
            message_content = message.get('content', '')
            message_tokens = self.estimate_tokens(message_content)
            
            # Check if adding this message would exceed limit
            if current_tokens + message_tokens > max_tokens:
                # Try to optimize the message content
                optimized_content = self.optimize_text(
                    message_content,
                    max_tokens - current_tokens
                )
                optimized_tokens = self.estimate_tokens(optimized_content)
                
                if current_tokens + optimized_tokens <= max_tokens:
                    # Use optimized version
                    optimized_message = message.copy()
                    optimized_message['content'] = optimized_content
                    optimized_messages.insert(0, optimized_message)
                    current_tokens += optimized_tokens
                else:
                    # Can't fit even optimized version, stop here
                    break
            else:
                # Message fits as-is
                optimized_messages.insert(0, message)
                current_tokens += message_tokens
        
        logger.debug("Conversation history optimized",
                    original_messages=len(messages),
                    optimized_messages=len(optimized_messages),
                    estimated_tokens=current_tokens,
                    max_tokens=max_tokens)
        
        return optimized_messages
    
    def optimize_chat_messages(
        self,
        messages: List[ChatMessage],
        max_total_tokens: Optional[int] = None
    ) -> List[ChatMessage]:
        """Optimize ChatMessage list for API call"""
        if not messages:
            return messages
        
        max_tokens = max_total_tokens or self.max_context_tokens
        
        optimized_messages = []
        current_tokens = 0
        
        # Always keep system message if present
        system_messages = [msg for msg in messages if msg.role == MessageRole.SYSTEM]
        other_messages = [msg for msg in messages if msg.role != MessageRole.SYSTEM]
        
        # Add system messages first
        for msg in system_messages:
            optimized_content = self.optimize_text(msg.content)
            msg_tokens = self.estimate_tokens(optimized_content)
            
            if current_tokens + msg_tokens <= max_tokens:
                optimized_msg = ChatMessage(
                    role=msg.role,
                    content=optimized_content,
                    name=msg.name
                )
                optimized_messages.append(optimized_msg)
                current_tokens += msg_tokens
        
        # Add other messages (prioritize recent ones)
        for msg in reversed(other_messages):
            optimized_content = self.optimize_text(msg.content)
            msg_tokens = self.estimate_tokens(optimized_content)
            
            if current_tokens + msg_tokens <= max_tokens:
                optimized_msg = ChatMessage(
                    role=msg.role,
                    content=optimized_content,
                    name=msg.name
                )
                optimized_messages.insert(-len(system_messages) if system_messages else 0, optimized_msg)
                current_tokens += msg_tokens
            else:
                # Try to fit a truncated version
                available_tokens = max_tokens - current_tokens
                if available_tokens > 50:  # Minimum useful tokens
                    truncated_content = self.optimize_text(msg.content, available_tokens)
                    truncated_msg = ChatMessage(
                        role=msg.role,
                        content=truncated_content,
                        name=msg.name
                    )
                    optimized_messages.insert(-len(system_messages) if system_messages else 0, truncated_msg)
                    break
        
        logger.debug("Chat messages optimized",
                    original_messages=len(messages),
                    optimized_messages=len(optimized_messages),
                    estimated_tokens=current_tokens,
                    max_tokens=max_tokens)
        
        return optimized_messages
    
    def create_context_hash(self, context_data: Dict[str, Any]) -> str:
        """Create hash for context data to use in caching"""
        import hashlib
        import json
        
        # Extract key context elements for hashing
        key_elements = {
            'hotel_id': context_data.get('hotel_id'),
            'guest_preferences': context_data.get('guest_preferences', {}),
            'conversation_length': len(context_data.get('conversation_history', [])),
            'recent_sentiment': context_data.get('sentiment_context', {}).get('sentiment_type')
        }
        
        # Create hash
        context_str = json.dumps(key_elements, sort_keys=True)
        return hashlib.md5(context_str.encode()).hexdigest()
    
    def get_optimization_stats(self) -> Dict[str, Any]:
        """Get token optimization statistics"""
        return {
            'total_optimizations': self.usage_stats['optimizations_applied'],
            'average_reduction_percent': round(self.usage_stats['average_reduction_percent'], 2),
            'strategies_enabled': {k: v for k, v in self.strategies.items() if v},
            'estimated_tokens_saved': self.usage_stats['total_tokens_saved']
        }
    
    def reset_stats(self):
        """Reset optimization statistics"""
        self.usage_stats = {
            'total_tokens_saved': 0,
            'optimizations_applied': 0,
            'average_reduction_percent': 0.0
        }
        
        logger.info("Token optimization stats reset")
    
    def configure_strategies(self, strategies: Dict[str, bool]):
        """Configure optimization strategies"""
        for strategy, enabled in strategies.items():
            if strategy in self.strategies:
                self.strategies[strategy] = enabled
        
        logger.info("Token optimization strategies updated",
                   strategies=self.strategies)
    
    def analyze_token_usage(
        self,
        prompt_tokens: int,
        completion_tokens: int,
        operation_type: str
    ) -> Dict[str, Any]:
        """Analyze token usage for optimization insights"""
        total_tokens = prompt_tokens + completion_tokens
        
        # Calculate efficiency metrics
        prompt_ratio = prompt_tokens / total_tokens if total_tokens > 0 else 0
        completion_ratio = completion_tokens / total_tokens if total_tokens > 0 else 0
        
        # Provide optimization recommendations
        recommendations = []
        
        if prompt_ratio > 0.8:
            recommendations.append("Consider reducing prompt length or context")
        
        if completion_tokens > 1000 and operation_type == 'sentiment':
            recommendations.append("Sentiment analysis responses are unusually long")
        
        if total_tokens > 6000:
            recommendations.append("High token usage - consider caching or optimization")
        
        return {
            'total_tokens': total_tokens,
            'prompt_tokens': prompt_tokens,
            'completion_tokens': completion_tokens,
            'prompt_ratio': round(prompt_ratio, 3),
            'completion_ratio': round(completion_ratio, 3),
            'operation_type': operation_type,
            'recommendations': recommendations,
            'efficiency_score': round((1 - prompt_ratio) * 100, 1)  # Higher is better
        }


# Global optimizer instance
_global_optimizer: Optional[TokenOptimizer] = None


def get_token_optimizer() -> TokenOptimizer:
    """Get global token optimizer instance"""
    global _global_optimizer
    if _global_optimizer is None:
        _global_optimizer = TokenOptimizer()
    return _global_optimizer


# Export main components
__all__ = [
    'TokenOptimizer',
    'get_token_optimizer'
]
