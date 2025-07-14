"""
Service for processing failed messages and implementing recovery strategies
"""

import asyncio
import time
from typing import Dict, Any, Optional, List, Callable
from datetime import datetime, timezone, timedelta
from enum import Enum

from app.core.logging import get_logger
from app.tasks.dead_letter_handler import DeadLetterQueueHandler, DeadLetterMessage, FailureReason
from app.services.fallback_service import FallbackService, DegradationLevel

logger = get_logger(__name__)


class RecoveryStrategy(Enum):
    """Recovery strategies for failed messages"""
    IMMEDIATE_RETRY = "immediate_retry"
    DELAYED_RETRY = "delayed_retry"
    EXPONENTIAL_BACKOFF = "exponential_backoff"
    MANUAL_INTERVENTION = "manual_intervention"
    DISCARD = "discard"


class FailedMessageProcessor:
    """
    Service for processing failed messages with intelligent recovery strategies
    """
    
    def __init__(self, dlq_handler: DeadLetterQueueHandler, fallback_service: FallbackService):
        self.dlq_handler = dlq_handler
        self.fallback_service = fallback_service
        
        # Recovery strategy mapping
        self.recovery_strategies = self._setup_recovery_strategies()
        
        # Message type processors
        self.message_processors = {}
        
        # Processing statistics
        self.stats = {
            "total_processed": 0,
            "successful_recoveries": 0,
            "failed_recoveries": 0,
            "manual_interventions": 0,
            "discarded_messages": 0
        }
        
        # Register default processors
        self._register_default_processors()
    
    def _setup_recovery_strategies(self) -> Dict[FailureReason, RecoveryStrategy]:
        """Setup recovery strategies for different failure reasons"""
        return {
            FailureReason.TIMEOUT: RecoveryStrategy.DELAYED_RETRY,
            FailureReason.CONNECTION_ERROR: RecoveryStrategy.EXPONENTIAL_BACKOFF,
            FailureReason.VALIDATION_ERROR: RecoveryStrategy.MANUAL_INTERVENTION,
            FailureReason.PROCESSING_ERROR: RecoveryStrategy.DELAYED_RETRY,
            FailureReason.RATE_LIMIT: RecoveryStrategy.EXPONENTIAL_BACKOFF,
            FailureReason.SERVICE_UNAVAILABLE: RecoveryStrategy.EXPONENTIAL_BACKOFF,
            FailureReason.UNKNOWN: RecoveryStrategy.DELAYED_RETRY
        }
    
    def _register_default_processors(self) -> None:
        """Register default message processors"""
        
        # WhatsApp message processor
        async def process_whatsapp_message(data: Dict[str, Any]) -> bool:
            """Process failed WhatsApp message"""
            try:
                # Check if WhatsApp service is available
                if self.fallback_service.current_degradation_level in [
                    DegradationLevel.SEVERE, DegradationLevel.CRITICAL
                ]:
                    # Use fallback service
                    fallback_result = await self.fallback_service.whatsapp_fallback(data)
                    return fallback_result.success
                
                # Try to send message normally
                from app.services.green_api import get_green_api_client
                
                async with get_green_api_client() as client:
                    result = await client.send_message(
                        phone=data.get("phone"),
                        message=data.get("message")
                    )
                    return result.get("success", False)
                    
            except Exception as e:
                logger.error("WhatsApp message processing failed", error=str(e))
                return False
        
        # AI processing message processor
        async def process_ai_message(data: Dict[str, Any]) -> bool:
            """Process failed AI message"""
            try:
                # Check if AI service is available
                if self.fallback_service.current_degradation_level in [
                    DegradationLevel.SEVERE, DegradationLevel.CRITICAL
                ]:
                    # Use AI fallback
                    fallback_result = await self.fallback_service.ai_fallback(
                        message_type="general_help",
                        context=data
                    )
                    return fallback_result.success
                
                # Try to process with AI normally
                from app.services.deepseek_client import get_deepseek_client
                
                client = get_deepseek_client()
                result = await client.analyze_sentiment(data.get("message", ""))
                return result is not None
                
            except Exception as e:
                logger.error("AI message processing failed", error=str(e))
                return False
        
        # Database operation processor
        async def process_database_operation(data: Dict[str, Any]) -> bool:
            """Process failed database operation"""
            try:
                # Check if database is available
                if self.fallback_service.current_degradation_level in [
                    DegradationLevel.SEVERE, DegradationLevel.CRITICAL
                ]:
                    # Use database fallback
                    fallback_result = await self.fallback_service.database_fallback(
                        operation=data.get("operation", "read"),
                        data=data
                    )
                    return fallback_result.success
                
                # Try database operation normally
                from app.database import get_db
                
                async with get_db() as db:
                    # This is a simplified example - actual implementation would
                    # depend on the specific operation type
                    operation = data.get("operation")
                    if operation == "read":
                        # Perform read operation
                        return True
                    elif operation in ["write", "update", "delete"]:
                        # Perform write operation
                        return True
                    else:
                        return False
                        
            except Exception as e:
                logger.error("Database operation processing failed", error=str(e))
                return False
        
        # Register processors
        self.register_processor("whatsapp_message", process_whatsapp_message)
        self.register_processor("ai_message", process_ai_message)
        self.register_processor("database_operation", process_database_operation)
    
    def register_processor(self, message_type: str, processor: Callable[[Dict[str, Any]], bool]) -> None:
        """
        Register a processor for a specific message type
        
        Args:
            message_type: Type of message to process
            processor: Async function that processes the message and returns success status
        """
        self.message_processors[message_type] = processor
        self.dlq_handler.register_message_processor(message_type, processor)
        logger.info("Message processor registered", message_type=message_type)
    
    def set_recovery_strategy(self, failure_reason: FailureReason, strategy: RecoveryStrategy) -> None:
        """
        Set recovery strategy for a specific failure reason
        
        Args:
            failure_reason: Failure reason
            strategy: Recovery strategy to use
        """
        self.recovery_strategies[failure_reason] = strategy
        logger.info("Recovery strategy updated",
                   failure_reason=failure_reason.value,
                   strategy=strategy.value)
    
    async def process_failed_message(self, message: DeadLetterMessage) -> bool:
        """
        Process a single failed message using appropriate recovery strategy
        
        Args:
            message: Dead letter message to process
            
        Returns:
            True if message was successfully processed, False otherwise
        """
        self.stats["total_processed"] += 1
        
        # Determine recovery strategy
        strategy = self.recovery_strategies.get(
            message.failure_reason, 
            RecoveryStrategy.DELAYED_RETRY
        )
        
        logger.info("Processing failed message",
                   message_id=message.id,
                   failure_reason=message.failure_reason.value,
                   strategy=strategy.value,
                   retry_count=message.retry_count)
        
        try:
            if strategy == RecoveryStrategy.IMMEDIATE_RETRY:
                success = await self._immediate_retry(message)
            
            elif strategy == RecoveryStrategy.DELAYED_RETRY:
                success = await self._delayed_retry(message)
            
            elif strategy == RecoveryStrategy.EXPONENTIAL_BACKOFF:
                success = await self._exponential_backoff_retry(message)
            
            elif strategy == RecoveryStrategy.MANUAL_INTERVENTION:
                success = await self._manual_intervention(message)
            
            elif strategy == RecoveryStrategy.DISCARD:
                success = await self._discard_message(message)
            
            else:
                logger.error("Unknown recovery strategy", strategy=strategy.value)
                success = False
            
            # Update statistics
            if success:
                self.stats["successful_recoveries"] += 1
            else:
                self.stats["failed_recoveries"] += 1
            
            return success
            
        except Exception as e:
            logger.error("Failed message processing error",
                        message_id=message.id,
                        error=str(e))
            self.stats["failed_recoveries"] += 1
            return False
    
    async def _immediate_retry(self, message: DeadLetterMessage) -> bool:
        """Immediately retry the message"""
        return await self.dlq_handler.retry_message(message.id)
    
    async def _delayed_retry(self, message: DeadLetterMessage) -> bool:
        """Retry the message after a delay"""
        # Calculate delay based on retry count
        delay = min(30 * (2 ** message.retry_count), 300)  # Max 5 minutes
        
        logger.info("Delaying message retry",
                   message_id=message.id,
                   delay_seconds=delay)
        
        await asyncio.sleep(delay)
        return await self.dlq_handler.retry_message(message.id)
    
    async def _exponential_backoff_retry(self, message: DeadLetterMessage) -> bool:
        """Retry the message with exponential backoff"""
        # Calculate exponential backoff delay
        base_delay = 60  # 1 minute base
        delay = min(base_delay * (2 ** message.retry_count), 3600)  # Max 1 hour
        
        logger.info("Exponential backoff retry",
                   message_id=message.id,
                   delay_seconds=delay)
        
        await asyncio.sleep(delay)
        return await self.dlq_handler.retry_message(message.id)
    
    async def _manual_intervention(self, message: DeadLetterMessage) -> bool:
        """Mark message for manual intervention"""
        logger.warning("Message requires manual intervention",
                      message_id=message.id,
                      failure_reason=message.failure_reason.value,
                      error=message.error_message)
        
        # In a real implementation, this would:
        # 1. Send notification to administrators
        # 2. Create a ticket in support system
        # 3. Move message to manual intervention queue
        
        self.stats["manual_interventions"] += 1
        
        # For now, we'll just log and return False to keep in DLQ
        return False
    
    async def _discard_message(self, message: DeadLetterMessage) -> bool:
        """Discard the message (permanent removal)"""
        logger.warning("Discarding message",
                      message_id=message.id,
                      failure_reason=message.failure_reason.value)
        
        self.stats["discarded_messages"] += 1
        
        # Remove from DLQ (this would be implemented in DLQ handler)
        # For now, return True to indicate "successful" processing
        return True
    
    async def process_dlq_with_strategies(self, batch_size: int = 20) -> Dict[str, Any]:
        """
        Process DLQ messages using intelligent recovery strategies
        
        Args:
            batch_size: Number of messages to process
            
        Returns:
            Processing statistics
        """
        start_time = time.time()
        
        # Get messages from DLQ
        messages = await self.dlq_handler.get_dlq_messages(batch_size)
        
        if not messages:
            return {
                "processed": 0,
                "processing_time": 0,
                "message": "No messages in DLQ"
            }
        
        # Process messages concurrently (with limit)
        semaphore = asyncio.Semaphore(5)  # Limit concurrent processing
        
        async def process_with_semaphore(msg):
            async with semaphore:
                return await self.process_failed_message(msg)
        
        # Process all messages
        results = await asyncio.gather(
            *[process_with_semaphore(msg) for msg in messages],
            return_exceptions=True
        )
        
        # Calculate statistics
        successful = sum(1 for r in results if r is True)
        failed = sum(1 for r in results if r is False)
        errors = sum(1 for r in results if isinstance(r, Exception))
        
        processing_time = time.time() - start_time
        
        stats = {
            "processed": len(messages),
            "successful": successful,
            "failed": failed,
            "errors": errors,
            "processing_time": round(processing_time, 2),
            "messages_per_second": round(len(messages) / processing_time, 2) if processing_time > 0 else 0
        }
        
        logger.info("DLQ processing with strategies completed", **stats)
        return stats
    
    async def get_processing_stats(self) -> Dict[str, Any]:
        """Get processing statistics"""
        dlq_stats = await self.dlq_handler.get_stats()
        
        return {
            "processor_stats": self.stats.copy(),
            "dlq_stats": dlq_stats,
            "recovery_strategies": {
                reason.value: strategy.value 
                for reason, strategy in self.recovery_strategies.items()
            },
            "registered_processors": list(self.message_processors.keys())
        }
    
    async def analyze_failure_patterns(self) -> Dict[str, Any]:
        """Analyze failure patterns in DLQ"""
        messages = await self.dlq_handler.get_dlq_messages(1000)  # Analyze up to 1000 messages
        
        if not messages:
            return {"message": "No messages to analyze"}
        
        # Analyze patterns
        failure_reasons = {}
        message_types = {}
        retry_counts = {}
        hourly_failures = {}
        
        for message in messages:
            # Failure reasons
            reason = message.failure_reason.value
            failure_reasons[reason] = failure_reasons.get(reason, 0) + 1
            
            # Message types
            msg_type = message.metadata.get("message_type", "unknown")
            message_types[msg_type] = message_types.get(msg_type, 0) + 1
            
            # Retry counts
            retry_count = message.retry_count
            retry_counts[retry_count] = retry_counts.get(retry_count, 0) + 1
            
            # Hourly failures
            hour = message.last_failed_at.hour
            hourly_failures[hour] = hourly_failures.get(hour, 0) + 1
        
        return {
            "total_messages": len(messages),
            "failure_reasons": failure_reasons,
            "message_types": message_types,
            "retry_count_distribution": retry_counts,
            "hourly_failure_distribution": hourly_failures,
            "analysis_timestamp": datetime.now(timezone.utc).isoformat()
        }


# Global failed message processor instance
failed_message_processor = None


def get_failed_message_processor() -> FailedMessageProcessor:
    """Get or create global failed message processor instance"""
    global failed_message_processor
    if failed_message_processor is None:
        from app.tasks.dead_letter_handler import dlq_handler
        from app.services.fallback_service import fallback_service
        failed_message_processor = FailedMessageProcessor(dlq_handler, fallback_service)
    return failed_message_processor
