"""
Context manager utilities for conversation management
"""

from typing import Dict, Any, Optional, List, Union
from uuid import UUID
from datetime import datetime, timedelta
from enum import Enum
import structlog

from app.services.conversation_memory import ConversationMemory
from app.core.logging import get_logger

logger = get_logger(__name__)


class ContextType(str, Enum):
    """Types of context data"""
    CURRENT_REQUEST = "current_request"
    GUEST_PREFERENCES = "guest_preferences"
    CONVERSATION_HISTORY = "conversation_history"
    PENDING_ACTIONS = "pending_actions"
    COLLECTED_INFO = "collected_info"
    INTENT_HISTORY = "intent_history"
    SENTIMENT_HISTORY = "sentiment_history"
    ESCALATION_TRIGGERS = "escalation_triggers"
    SESSION_DATA = "session_data"


class ContextManager:
    """
    Manager for conversation context with intelligent data handling
    """
    
    def __init__(self, memory_service: ConversationMemory):
        self.memory = memory_service
        self.context_schemas = self._setup_context_schemas()
    
    def _setup_context_schemas(self) -> Dict[ContextType, Dict[str, Any]]:
        """Setup schemas for different context types"""
        return {
            ContextType.CURRENT_REQUEST: {
                'type': 'object',
                'properties': {
                    'request_type': {'type': 'string'},
                    'details': {'type': 'object'},
                    'status': {'type': 'string', 'enum': ['pending', 'processing', 'completed']},
                    'created_at': {'type': 'string'},
                    'updated_at': {'type': 'string'}
                }
            },
            ContextType.GUEST_PREFERENCES: {
                'type': 'object',
                'properties': {
                    'room_type': {'type': 'string'},
                    'floor_preference': {'type': 'string'},
                    'amenities': {'type': 'array'},
                    'dietary_restrictions': {'type': 'array'},
                    'communication_style': {'type': 'string'},
                    'language': {'type': 'string'},
                    'special_needs': {'type': 'array'}
                }
            },
            ContextType.COLLECTED_INFO: {
                'type': 'object',
                'properties': {
                    'check_in_date': {'type': 'string'},
                    'check_out_date': {'type': 'string'},
                    'guest_count': {'type': 'integer'},
                    'room_number': {'type': 'string'},
                    'booking_reference': {'type': 'string'},
                    'contact_info': {'type': 'object'},
                    'special_requests': {'type': 'array'}
                }
            }
        }
    
    async def set_current_request(
        self,
        conversation_id: Union[str, UUID],
        request_type: str,
        details: Dict[str, Any],
        status: str = 'pending'
    ) -> bool:
        """
        Set current request context
        
        Args:
            conversation_id: Conversation ID
            request_type: Type of request
            details: Request details
            status: Request status
            
        Returns:
            bool: Success status
        """
        request_data = {
            'request_type': request_type,
            'details': details,
            'status': status,
            'created_at': datetime.utcnow().isoformat(),
            'updated_at': datetime.utcnow().isoformat()
        }
        
        return await self.memory.store_context(
            conversation_id=conversation_id,
            key=ContextType.CURRENT_REQUEST.value,
            value=request_data
        )
    
    async def get_current_request(
        self,
        conversation_id: Union[str, UUID]
    ) -> Optional[Dict[str, Any]]:
        """Get current request context"""
        return await self.memory.get_context(
            conversation_id=conversation_id,
            key=ContextType.CURRENT_REQUEST.value
        )
    
    async def update_request_status(
        self,
        conversation_id: Union[str, UUID],
        status: str,
        additional_details: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Update current request status
        
        Args:
            conversation_id: Conversation ID
            status: New status
            additional_details: Additional details to merge
            
        Returns:
            bool: Success status
        """
        current_request = await self.get_current_request(conversation_id)
        if not current_request:
            return False
        
        current_request['status'] = status
        current_request['updated_at'] = datetime.utcnow().isoformat()
        
        if additional_details:
            current_request['details'].update(additional_details)
        
        return await self.memory.store_context(
            conversation_id=conversation_id,
            key=ContextType.CURRENT_REQUEST.value,
            value=current_request
        )
    
    async def add_collected_info(
        self,
        conversation_id: Union[str, UUID],
        info_type: str,
        value: Any,
        confidence: float = 1.0
    ) -> bool:
        """
        Add collected information to context
        
        Args:
            conversation_id: Conversation ID
            info_type: Type of information
            value: Information value
            confidence: Confidence level (0-1)
            
        Returns:
            bool: Success status
        """
        collected_info = await self.memory.get_context(
            conversation_id=conversation_id,
            key=ContextType.COLLECTED_INFO.value,
            default={}
        )
        
        collected_info[info_type] = {
            'value': value,
            'confidence': confidence,
            'collected_at': datetime.utcnow().isoformat()
        }
        
        return await self.memory.store_context(
            conversation_id=conversation_id,
            key=ContextType.COLLECTED_INFO.value,
            value=collected_info
        )
    
    async def get_collected_info(
        self,
        conversation_id: Union[str, UUID],
        info_type: Optional[str] = None
    ) -> Union[Dict[str, Any], Any, None]:
        """
        Get collected information
        
        Args:
            conversation_id: Conversation ID
            info_type: Specific info type (if None, returns all)
            
        Returns:
            Collected information or None
        """
        collected_info = await self.memory.get_context(
            conversation_id=conversation_id,
            key=ContextType.COLLECTED_INFO.value,
            default={}
        )
        
        if info_type:
            info_data = collected_info.get(info_type)
            return info_data['value'] if info_data else None
        
        return collected_info
    
    async def add_intent_to_history(
        self,
        conversation_id: Union[str, UUID],
        intent: str,
        confidence: float,
        timestamp: Optional[datetime] = None
    ) -> bool:
        """
        Add intent to conversation history
        
        Args:
            conversation_id: Conversation ID
            intent: Intent value
            confidence: Confidence level
            timestamp: Optional timestamp
            
        Returns:
            bool: Success status
        """
        intent_history = await self.memory.get_context(
            conversation_id=conversation_id,
            key=ContextType.INTENT_HISTORY.value,
            default=[]
        )
        
        intent_entry = {
            'intent': intent,
            'confidence': confidence,
            'timestamp': (timestamp or datetime.utcnow()).isoformat()
        }
        
        intent_history.append(intent_entry)
        
        # Keep only last 20 intents
        if len(intent_history) > 20:
            intent_history = intent_history[-20:]
        
        return await self.memory.store_context(
            conversation_id=conversation_id,
            key=ContextType.INTENT_HISTORY.value,
            value=intent_history
        )
    
    async def get_intent_patterns(
        self,
        conversation_id: Union[str, UUID],
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Get recent intent patterns
        
        Args:
            conversation_id: Conversation ID
            limit: Number of recent intents to return
            
        Returns:
            List of recent intents
        """
        intent_history = await self.memory.get_context(
            conversation_id=conversation_id,
            key=ContextType.INTENT_HISTORY.value,
            default=[]
        )
        
        return intent_history[-limit:] if intent_history else []
    
    async def add_pending_action(
        self,
        conversation_id: Union[str, UUID],
        action_type: str,
        action_data: Dict[str, Any],
        priority: int = 1,
        expires_at: Optional[datetime] = None
    ) -> bool:
        """
        Add pending action to context
        
        Args:
            conversation_id: Conversation ID
            action_type: Type of action
            action_data: Action data
            priority: Priority level (1-5)
            expires_at: Optional expiration time
            
        Returns:
            bool: Success status
        """
        pending_actions = await self.memory.get_context(
            conversation_id=conversation_id,
            key=ContextType.PENDING_ACTIONS.value,
            default=[]
        )
        
        action = {
            'id': f"{action_type}_{datetime.utcnow().timestamp()}",
            'type': action_type,
            'data': action_data,
            'priority': priority,
            'created_at': datetime.utcnow().isoformat(),
            'expires_at': expires_at.isoformat() if expires_at else None,
            'status': 'pending'
        }
        
        pending_actions.append(action)
        
        # Sort by priority (higher first)
        pending_actions.sort(key=lambda x: x['priority'], reverse=True)
        
        return await self.memory.store_context(
            conversation_id=conversation_id,
            key=ContextType.PENDING_ACTIONS.value,
            value=pending_actions
        )
    
    async def get_pending_actions(
        self,
        conversation_id: Union[str, UUID],
        action_type: Optional[str] = None,
        include_expired: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Get pending actions
        
        Args:
            conversation_id: Conversation ID
            action_type: Filter by action type
            include_expired: Include expired actions
            
        Returns:
            List of pending actions
        """
        pending_actions = await self.memory.get_context(
            conversation_id=conversation_id,
            key=ContextType.PENDING_ACTIONS.value,
            default=[]
        )
        
        now = datetime.utcnow()
        filtered_actions = []
        
        for action in pending_actions:
            # Check expiration
            if not include_expired and action.get('expires_at'):
                expires_at = datetime.fromisoformat(action['expires_at'])
                if expires_at < now:
                    continue
            
            # Filter by type
            if action_type and action['type'] != action_type:
                continue
            
            # Only include pending actions
            if action.get('status') == 'pending':
                filtered_actions.append(action)
        
        return filtered_actions
    
    async def complete_action(
        self,
        conversation_id: Union[str, UUID],
        action_id: str,
        result: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Mark action as completed
        
        Args:
            conversation_id: Conversation ID
            action_id: Action ID
            result: Optional result data
            
        Returns:
            bool: Success status
        """
        pending_actions = await self.memory.get_context(
            conversation_id=conversation_id,
            key=ContextType.PENDING_ACTIONS.value,
            default=[]
        )
        
        for action in pending_actions:
            if action['id'] == action_id:
                action['status'] = 'completed'
                action['completed_at'] = datetime.utcnow().isoformat()
                if result:
                    action['result'] = result
                break
        
        return await self.memory.store_context(
            conversation_id=conversation_id,
            key=ContextType.PENDING_ACTIONS.value,
            value=pending_actions
        )
    
    async def clear_context_type(
        self,
        conversation_id: Union[str, UUID],
        context_type: ContextType
    ) -> bool:
        """
        Clear specific context type
        
        Args:
            conversation_id: Conversation ID
            context_type: Type of context to clear
            
        Returns:
            bool: Success status
        """
        return await self.memory.delete_context(
            conversation_id=conversation_id,
            key=context_type.value
        )
    
    async def get_context_summary(
        self,
        conversation_id: Union[str, UUID]
    ) -> Dict[str, Any]:
        """
        Get summary of all context data
        
        Args:
            conversation_id: Conversation ID
            
        Returns:
            Context summary
        """
        all_context = await self.memory.get_context(conversation_id)
        
        summary = {
            'conversation_id': str(conversation_id),
            'context_types': list(all_context.keys()) if all_context else [],
            'has_current_request': ContextType.CURRENT_REQUEST.value in (all_context or {}),
            'collected_info_count': len(all_context.get(ContextType.COLLECTED_INFO.value, {})),
            'pending_actions_count': len(all_context.get(ContextType.PENDING_ACTIONS.value, [])),
            'intent_history_count': len(all_context.get(ContextType.INTENT_HISTORY.value, [])),
            'last_updated': datetime.utcnow().isoformat()
        }
        
        return summary


# Export context manager
__all__ = ['ContextManager', 'ContextType']
