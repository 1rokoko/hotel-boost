"""
Dead Letter Queue handler for processing failed messages and tasks
"""

import asyncio
import json
import time
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import redis.asyncio as redis

from celery import Task
from app.core.celery_app import celery_app
from app.core.config import settings
from app.core.logging import get_logger
from app.utils.retry_handler import RetryHandler, RetryConfig

logger = get_logger(__name__)


class FailureReason(Enum):
    """Reasons for message/task failure"""
    TIMEOUT = "timeout"
    CONNECTION_ERROR = "connection_error"
    VALIDATION_ERROR = "validation_error"
    PROCESSING_ERROR = "processing_error"
    RATE_LIMIT = "rate_limit"
    SERVICE_UNAVAILABLE = "service_unavailable"
    UNKNOWN = "unknown"


@dataclass
class DeadLetterMessage:
    """Message in dead letter queue"""
    id: str
    original_data: Dict[str, Any]
    failure_reason: FailureReason
    error_message: str
    retry_count: int
    max_retries: int
    first_failed_at: datetime
    last_failed_at: datetime
    next_retry_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage"""
        return {
            "id": self.id,
            "original_data": self.original_data,
            "failure_reason": self.failure_reason.value,
            "error_message": self.error_message,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
            "first_failed_at": self.first_failed_at.isoformat(),
            "last_failed_at": self.last_failed_at.isoformat(),
            "next_retry_at": self.next_retry_at.isoformat() if self.next_retry_at else None,
            "metadata": self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DeadLetterMessage':
        """Create from dictionary"""
        return cls(
            id=data["id"],
            original_data=data["original_data"],
            failure_reason=FailureReason(data["failure_reason"]),
            error_message=data["error_message"],
            retry_count=data["retry_count"],
            max_retries=data["max_retries"],
            first_failed_at=datetime.fromisoformat(data["first_failed_at"]),
            last_failed_at=datetime.fromisoformat(data["last_failed_at"]),
            next_retry_at=datetime.fromisoformat(data["next_retry_at"]) if data["next_retry_at"] else None,
            metadata=data.get("metadata", {})
        )


class DeadLetterQueueHandler:
    """
    Handler for dead letter queue operations
    """
    
    def __init__(self, redis_url: str = None):
        self.redis_url = redis_url or settings.REDIS_URL
        self.dlq_key = "dead_letter_queue"
        self.retry_queue_key = "retry_queue"
        self.stats_key = "dlq_stats"
        
        # Retry configuration for DLQ processing
        self.retry_config = RetryConfig(
            max_retries=3,
            base_delay=5.0,
            max_delay=300.0,
            exponential_base=2.0,
            jitter=True
        )
        
        self.retry_handler = RetryHandler(self.retry_config)
        
        # Processing callbacks
        self._message_processors: Dict[str, Callable] = {}
        self._failure_callbacks: List[Callable] = []
    
    async def _get_redis(self) -> redis.Redis:
        """Get Redis connection"""
        return redis.from_url(
            self.redis_url,
            encoding="utf-8",
            decode_responses=True
        )
    
    def register_message_processor(self, message_type: str, processor: Callable) -> None:
        """
        Register a processor for specific message types
        
        Args:
            message_type: Type of message to process
            processor: Async function to process the message
        """
        self._message_processors[message_type] = processor
        logger.info("Message processor registered", message_type=message_type)
    
    def register_failure_callback(self, callback: Callable[[DeadLetterMessage], None]) -> None:
        """
        Register callback for permanent failures
        
        Args:
            callback: Function to call when message permanently fails
        """
        self._failure_callbacks.append(callback)
    
    async def add_to_dlq(self, message_data: Dict[str, Any], error: Exception,
                        message_type: str = "unknown", max_retries: int = 5) -> str:
        """
        Add a failed message to the dead letter queue
        
        Args:
            message_data: Original message data
            error: Exception that caused the failure
            message_type: Type of message
            max_retries: Maximum retry attempts
            
        Returns:
            Message ID in DLQ
        """
        redis_client = await self._get_redis()
        
        try:
            # Generate unique message ID
            message_id = f"dlq_{int(time.time() * 1000)}_{hash(str(message_data)) % 10000}"
            
            # Determine failure reason
            failure_reason = self._classify_error(error)
            
            # Create dead letter message
            now = datetime.now(timezone.utc)
            dlq_message = DeadLetterMessage(
                id=message_id,
                original_data=message_data,
                failure_reason=failure_reason,
                error_message=str(error),
                retry_count=0,
                max_retries=max_retries,
                first_failed_at=now,
                last_failed_at=now,
                metadata={
                    "message_type": message_type,
                    "error_type": type(error).__name__
                }
            )
            
            # Store in Redis
            await redis_client.hset(
                self.dlq_key,
                message_id,
                json.dumps(dlq_message.to_dict())
            )
            
            # Update statistics
            await self._update_stats("messages_added", 1)
            await self._update_stats(f"failure_reason_{failure_reason.value}", 1)
            
            logger.warning("Message added to dead letter queue",
                          message_id=message_id,
                          message_type=message_type,
                          failure_reason=failure_reason.value,
                          error=str(error))
            
            return message_id
            
        finally:
            await redis_client.close()
    
    def _classify_error(self, error: Exception) -> FailureReason:
        """Classify error to determine failure reason"""
        error_type = type(error).__name__.lower()
        error_message = str(error).lower()
        
        if "timeout" in error_type or "timeout" in error_message:
            return FailureReason.TIMEOUT
        elif "connection" in error_type or "connection" in error_message:
            return FailureReason.CONNECTION_ERROR
        elif "validation" in error_type or "validation" in error_message:
            return FailureReason.VALIDATION_ERROR
        elif "rate" in error_message and "limit" in error_message:
            return FailureReason.RATE_LIMIT
        elif "unavailable" in error_message or "503" in error_message:
            return FailureReason.SERVICE_UNAVAILABLE
        else:
            return FailureReason.UNKNOWN
    
    async def get_dlq_messages(self, limit: int = 100) -> List[DeadLetterMessage]:
        """
        Get messages from dead letter queue
        
        Args:
            limit: Maximum number of messages to return
            
        Returns:
            List of dead letter messages
        """
        redis_client = await self._get_redis()
        
        try:
            # Get all messages from DLQ
            messages_data = await redis_client.hgetall(self.dlq_key)
            
            messages = []
            for message_id, message_json in messages_data.items():
                try:
                    message_dict = json.loads(message_json)
                    message = DeadLetterMessage.from_dict(message_dict)
                    messages.append(message)
                except Exception as e:
                    logger.error("Failed to parse DLQ message",
                               message_id=message_id,
                               error=str(e))
            
            # Sort by last failed time (most recent first)
            messages.sort(key=lambda m: m.last_failed_at, reverse=True)
            
            return messages[:limit]
            
        finally:
            await redis_client.close()
    
    async def retry_message(self, message_id: str) -> bool:
        """
        Retry a specific message from DLQ
        
        Args:
            message_id: ID of message to retry
            
        Returns:
            True if retry was successful, False otherwise
        """
        redis_client = await self._get_redis()
        
        try:
            # Get message from DLQ
            message_json = await redis_client.hget(self.dlq_key, message_id)
            if not message_json:
                logger.error("Message not found in DLQ", message_id=message_id)
                return False
            
            message_dict = json.loads(message_json)
            dlq_message = DeadLetterMessage.from_dict(message_dict)
            
            # Check if message can be retried
            if dlq_message.retry_count >= dlq_message.max_retries:
                logger.warning("Message exceeded max retries",
                             message_id=message_id,
                             retry_count=dlq_message.retry_count,
                             max_retries=dlq_message.max_retries)
                return False
            
            # Get processor for message type
            message_type = dlq_message.metadata.get("message_type", "unknown")
            processor = self._message_processors.get(message_type)
            
            if not processor:
                logger.error("No processor found for message type",
                           message_id=message_id,
                           message_type=message_type)
                return False
            
            try:
                # Attempt to process the message
                await processor(dlq_message.original_data)
                
                # Success - remove from DLQ
                await redis_client.hdel(self.dlq_key, message_id)
                await self._update_stats("messages_retried_success", 1)
                
                logger.info("Message successfully retried",
                           message_id=message_id,
                           retry_count=dlq_message.retry_count + 1)
                
                return True
                
            except Exception as e:
                # Retry failed - update message
                dlq_message.retry_count += 1
                dlq_message.last_failed_at = datetime.now(timezone.utc)
                dlq_message.error_message = str(e)
                
                if dlq_message.retry_count >= dlq_message.max_retries:
                    # Permanent failure
                    await self._handle_permanent_failure(dlq_message)
                    await self._update_stats("messages_permanently_failed", 1)
                else:
                    # Update message in DLQ
                    await redis_client.hset(
                        self.dlq_key,
                        message_id,
                        json.dumps(dlq_message.to_dict())
                    )
                
                await self._update_stats("messages_retried_failed", 1)
                
                logger.warning("Message retry failed",
                             message_id=message_id,
                             retry_count=dlq_message.retry_count,
                             error=str(e))
                
                return False
                
        finally:
            await redis_client.close()
    
    async def _handle_permanent_failure(self, message: DeadLetterMessage) -> None:
        """Handle permanently failed message"""
        logger.error("Message permanently failed",
                    message_id=message.id,
                    retry_count=message.retry_count,
                    max_retries=message.max_retries,
                    error=message.error_message)
        
        # Call failure callbacks
        for callback in self._failure_callbacks:
            try:
                callback(message)
            except Exception as e:
                logger.error("Failure callback error", error=str(e))
        
        # Move to permanent failure storage (optional)
        # This could be a separate Redis key or database table
        redis_client = await self._get_redis()
        try:
            await redis_client.hset(
                "permanent_failures",
                message.id,
                json.dumps(message.to_dict())
            )
            # Remove from DLQ
            await redis_client.hdel(self.dlq_key, message.id)
        finally:
            await redis_client.close()
    
    async def process_dlq_batch(self, batch_size: int = 10) -> Dict[str, int]:
        """
        Process a batch of messages from DLQ
        
        Args:
            batch_size: Number of messages to process
            
        Returns:
            Statistics about processing results
        """
        messages = await self.get_dlq_messages(batch_size)
        
        stats = {
            "processed": 0,
            "succeeded": 0,
            "failed": 0,
            "permanently_failed": 0
        }
        
        for message in messages:
            stats["processed"] += 1
            
            success = await self.retry_message(message.id)
            if success:
                stats["succeeded"] += 1
            else:
                stats["failed"] += 1
                if message.retry_count >= message.max_retries:
                    stats["permanently_failed"] += 1
        
        logger.info("DLQ batch processing completed", **stats)
        return stats
    
    async def _update_stats(self, stat_name: str, increment: int = 1) -> None:
        """Update DLQ statistics"""
        redis_client = await self._get_redis()
        try:
            await redis_client.hincrby(self.stats_key, stat_name, increment)
            await redis_client.hincrby(self.stats_key, "last_updated", int(time.time()))
        finally:
            await redis_client.close()
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get DLQ statistics"""
        redis_client = await self._get_redis()
        
        try:
            stats = await redis_client.hgetall(self.stats_key)
            
            # Convert string values to integers
            for key, value in stats.items():
                try:
                    stats[key] = int(value)
                except ValueError:
                    pass
            
            # Add current queue size
            queue_size = await redis_client.hlen(self.dlq_key)
            stats["current_queue_size"] = queue_size
            
            return stats
            
        finally:
            await redis_client.close()
    
    async def clear_dlq(self, confirm: bool = False) -> int:
        """
        Clear all messages from DLQ (use with caution)
        
        Args:
            confirm: Must be True to actually clear
            
        Returns:
            Number of messages cleared
        """
        if not confirm:
            raise ValueError("Must confirm DLQ clearing with confirm=True")
        
        redis_client = await self._get_redis()
        
        try:
            queue_size = await redis_client.hlen(self.dlq_key)
            await redis_client.delete(self.dlq_key)
            
            logger.warning("Dead letter queue cleared", messages_cleared=queue_size)
            await self._update_stats("queue_cleared", 1)
            await self._update_stats("messages_cleared", queue_size)
            
            return queue_size
            
        finally:
            await redis_client.close()


# Global DLQ handler instance
dlq_handler = DeadLetterQueueHandler()


# Celery task for processing DLQ
@celery_app.task(bind=True, name="process_dead_letter_queue")
def process_dead_letter_queue_task(self: Task, batch_size: int = 10) -> Dict[str, int]:
    """
    Celery task to process dead letter queue
    
    Args:
        batch_size: Number of messages to process in this batch
        
    Returns:
        Processing statistics
    """
    try:
        # Run async function in sync context
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            stats = loop.run_until_complete(dlq_handler.process_dlq_batch(batch_size))
            return stats
        finally:
            loop.close()
            
    except Exception as e:
        logger.error("DLQ processing task failed", error=str(e))
        raise


# Default failure callback
def log_permanent_failure(message: DeadLetterMessage) -> None:
    """Log permanently failed messages"""
    logger.critical("Message permanently failed",
                    message_id=message.id,
                    message_type=message.metadata.get("message_type"),
                    failure_reason=message.failure_reason.value,
                    retry_count=message.retry_count,
                    error=message.error_message)


# Register default callback
dlq_handler.register_failure_callback(log_permanent_failure)
