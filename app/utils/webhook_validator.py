"""
Webhook validation utilities for Green API
"""

import hmac
import hashlib
import time
from typing import Optional, Dict, Any
import structlog

logger = structlog.get_logger(__name__)


def validate_green_api_webhook(
    body: bytes,
    signature: Optional[str],
    secret: str,
    timestamp_tolerance: int = 300  # 5 minutes
) -> bool:
    """
    Validate Green API webhook signature
    
    Args:
        body: Raw webhook body as bytes
        signature: Webhook signature from header
        secret: Webhook secret token
        timestamp_tolerance: Maximum age of webhook in seconds
        
    Returns:
        bool: True if webhook is valid, False otherwise
    """
    if not signature or not secret:
        logger.warning("Missing signature or secret for webhook validation")
        return False
    
    try:
        # Green API uses HMAC-SHA256 for webhook signatures
        # The signature format is typically: sha256=<hex_digest>
        
        # Remove 'sha256=' prefix if present
        if signature.startswith('sha256='):
            signature = signature[7:]
        
        # Calculate expected signature
        expected_signature = hmac.new(
            secret.encode('utf-8'),
            body,
            hashlib.sha256
        ).hexdigest()
        
        # Compare signatures using constant-time comparison
        is_valid = hmac.compare_digest(signature, expected_signature)
        
        if is_valid:
            logger.debug("Webhook signature validation successful")
        else:
            logger.warning("Webhook signature validation failed",
                         expected_length=len(expected_signature),
                         received_length=len(signature))
        
        return is_valid
        
    except Exception as e:
        logger.error("Error validating webhook signature", error=str(e))
        return False


def validate_webhook_timestamp(
    timestamp: Optional[int],
    tolerance: int = 300
) -> bool:
    """
    Validate webhook timestamp to prevent replay attacks
    
    Args:
        timestamp: Webhook timestamp in seconds
        tolerance: Maximum age of webhook in seconds
        
    Returns:
        bool: True if timestamp is within tolerance, False otherwise
    """
    if timestamp is None:
        logger.warning("Missing timestamp in webhook")
        return False
    
    try:
        current_time = int(time.time())
        age = current_time - timestamp
        
        if age < 0:
            logger.warning("Webhook timestamp is in the future", 
                         timestamp=timestamp,
                         current_time=current_time)
            return False
        
        if age > tolerance:
            logger.warning("Webhook timestamp is too old",
                         age=age,
                         tolerance=tolerance,
                         timestamp=timestamp)
            return False
        
        logger.debug("Webhook timestamp validation successful", age=age)
        return True
        
    except Exception as e:
        logger.error("Error validating webhook timestamp", error=str(e))
        return False


def validate_webhook_structure(webhook_data: Dict[str, Any]) -> bool:
    """
    Validate basic webhook structure
    
    Args:
        webhook_data: Parsed webhook data
        
    Returns:
        bool: True if structure is valid, False otherwise
    """
    try:
        # Check required fields
        required_fields = ['typeWebhook', 'instanceData', 'timestamp']
        
        for field in required_fields:
            if field not in webhook_data:
                logger.warning("Missing required field in webhook", field=field)
                return False
        
        # Validate instance data structure
        instance_data = webhook_data.get('instanceData', {})
        if not isinstance(instance_data, dict):
            logger.warning("Invalid instanceData structure")
            return False
        
        # Check for instance ID
        if 'idInstance' not in instance_data:
            logger.warning("Missing idInstance in instanceData")
            return False
        
        # Validate timestamp
        timestamp = webhook_data.get('timestamp')
        if not isinstance(timestamp, int):
            logger.warning("Invalid timestamp format", timestamp=timestamp)
            return False
        
        logger.debug("Webhook structure validation successful")
        return True
        
    except Exception as e:
        logger.error("Error validating webhook structure", error=str(e))
        return False


def validate_message_webhook(webhook_data: Dict[str, Any]) -> bool:
    """
    Validate message-specific webhook data
    
    Args:
        webhook_data: Parsed webhook data
        
    Returns:
        bool: True if message webhook is valid, False otherwise
    """
    try:
        webhook_type = webhook_data.get('typeWebhook')
        
        # Check if it's a message webhook
        message_types = [
            'incomingMessageReceived',
            'outgoingMessageReceived',
            'outgoingMessageStatus'
        ]
        
        if webhook_type not in message_types:
            return True  # Not a message webhook, skip validation
        
        # Validate message-specific fields
        if webhook_type in ['incomingMessageReceived', 'outgoingMessageReceived']:
            # Check for message ID
            if 'idMessage' not in webhook_data:
                logger.warning("Missing idMessage in message webhook")
                return False
            
            # Check for sender data (incoming messages)
            if webhook_type == 'incomingMessageReceived':
                if 'senderData' not in webhook_data:
                    logger.warning("Missing senderData in incoming message webhook")
                    return False
                
                sender_data = webhook_data['senderData']
                if 'chatId' not in sender_data:
                    logger.warning("Missing chatId in senderData")
                    return False
            
            # Check for message data
            if 'messageData' not in webhook_data:
                logger.warning("Missing messageData in message webhook")
                return False
        
        elif webhook_type == 'outgoingMessageStatus':
            # Check for status fields
            required_status_fields = ['idMessage', 'status', 'chatId']
            for field in required_status_fields:
                if field not in webhook_data:
                    logger.warning("Missing field in status webhook", field=field)
                    return False
        
        logger.debug("Message webhook validation successful")
        return True
        
    except Exception as e:
        logger.error("Error validating message webhook", error=str(e))
        return False


def comprehensive_webhook_validation(
    body: bytes,
    webhook_data: Dict[str, Any],
    signature: Optional[str],
    secret: Optional[str],
    timestamp_tolerance: int = 300
) -> Dict[str, Any]:
    """
    Perform comprehensive webhook validation
    
    Args:
        body: Raw webhook body as bytes
        webhook_data: Parsed webhook data
        signature: Webhook signature from header
        secret: Webhook secret token
        timestamp_tolerance: Maximum age of webhook in seconds
        
    Returns:
        Dict containing validation results
    """
    results = {
        'is_valid': True,
        'errors': [],
        'warnings': []
    }
    
    try:
        # Validate structure
        if not validate_webhook_structure(webhook_data):
            results['is_valid'] = False
            results['errors'].append('Invalid webhook structure')
        
        # Validate timestamp
        timestamp = webhook_data.get('timestamp')
        if not validate_webhook_timestamp(timestamp, timestamp_tolerance):
            results['warnings'].append('Webhook timestamp validation failed')
        
        # Validate signature if secret is provided
        if secret:
            if not validate_green_api_webhook(body, signature, secret, timestamp_tolerance):
                results['is_valid'] = False
                results['errors'].append('Invalid webhook signature')
        else:
            results['warnings'].append('No webhook secret provided, skipping signature validation')
        
        # Validate message-specific data
        if not validate_message_webhook(webhook_data):
            results['is_valid'] = False
            results['errors'].append('Invalid message webhook data')
        
        # Log validation results
        if results['is_valid']:
            logger.info("Webhook validation successful",
                       warnings_count=len(results['warnings']))
        else:
            logger.error("Webhook validation failed",
                        errors=results['errors'],
                        warnings=results['warnings'])
        
        return results
        
    except Exception as e:
        logger.error("Error in comprehensive webhook validation", error=str(e))
        return {
            'is_valid': False,
            'errors': [f'Validation error: {str(e)}'],
            'warnings': []
        }


def extract_webhook_metadata(webhook_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract metadata from webhook for logging and monitoring
    
    Args:
        webhook_data: Parsed webhook data
        
    Returns:
        Dict containing extracted metadata
    """
    try:
        metadata = {
            'webhook_type': webhook_data.get('typeWebhook'),
            'timestamp': webhook_data.get('timestamp'),
            'instance_id': webhook_data.get('instanceData', {}).get('idInstance'),
            'message_id': webhook_data.get('idMessage'),
            'chat_id': None,
            'sender': None,
            'message_type': None
        }
        
        # Extract message-specific metadata
        if 'senderData' in webhook_data:
            sender_data = webhook_data['senderData']
            metadata['chat_id'] = sender_data.get('chatId')
            metadata['sender'] = sender_data.get('sender')
        
        if 'messageData' in webhook_data:
            message_data = webhook_data['messageData']
            metadata['message_type'] = message_data.get('typeMessage')
        
        # For status webhooks
        if webhook_data.get('typeWebhook') == 'outgoingMessageStatus':
            metadata['chat_id'] = webhook_data.get('chatId')
            metadata['status'] = webhook_data.get('status')
        
        return metadata
        
    except Exception as e:
        logger.error("Error extracting webhook metadata", error=str(e))
        return {}


# Export main functions
__all__ = [
    'validate_green_api_webhook',
    'validate_webhook_timestamp',
    'validate_webhook_structure',
    'validate_message_webhook',
    'comprehensive_webhook_validation',
    'extract_webhook_metadata'
]
