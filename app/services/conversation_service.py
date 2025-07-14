"""
Conversation service for managing guest conversations
"""

from typing import Dict, Any, Optional, List
from uuid import UUID
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc
import structlog

from app.models.message import Conversation, ConversationStatus, ConversationState
from app.models.hotel import Hotel
from app.models.guest import Guest
from app.schemas.conversation import (
    ConversationCreate, ConversationUpdate, ConversationListFilter,
    StateTransitionRequest, ConversationStats
)
from app.core.logging import get_logger

logger = get_logger(__name__)


class ConversationService:
    """Service for managing conversations"""
    
    def __init__(self, db: Session):
        self.db = db
    
    async def create_conversation(
        self,
        conversation_data: ConversationCreate
    ) -> Conversation:
        """
        Create a new conversation
        
        Args:
            conversation_data: Conversation creation data
            
        Returns:
            Conversation: Created conversation
            
        Raises:
            ValueError: If hotel or guest not found
        """
        # Verify hotel exists
        hotel = self.db.query(Hotel).filter(Hotel.id == conversation_data.hotel_id).first()
        if not hotel:
            raise ValueError(f"Hotel not found: {conversation_data.hotel_id}")
        
        # Verify guest exists and belongs to hotel
        guest = self.db.query(Guest).filter(
            and_(
                Guest.id == conversation_data.guest_id,
                Guest.hotel_id == conversation_data.hotel_id
            )
        ).first()
        if not guest:
            raise ValueError(f"Guest not found or doesn't belong to hotel: {conversation_data.guest_id}")
        
        # Check for existing active conversation
        existing = self.db.query(Conversation).filter(
            and_(
                Conversation.hotel_id == conversation_data.hotel_id,
                Conversation.guest_id == conversation_data.guest_id,
                Conversation.status == ConversationStatus.ACTIVE
            )
        ).first()
        
        if existing:
            logger.info("Returning existing active conversation",
                       conversation_id=existing.id,
                       hotel_id=conversation_data.hotel_id,
                       guest_id=conversation_data.guest_id)
            return existing
        
        # Create new conversation
        conversation = Conversation(
            hotel_id=conversation_data.hotel_id,
            guest_id=conversation_data.guest_id,
            status=conversation_data.status,
            current_state=conversation_data.current_state,
            context=conversation_data.context
        )
        
        self.db.add(conversation)
        self.db.flush()
        
        logger.info("New conversation created",
                   conversation_id=conversation.id,
                   hotel_id=conversation_data.hotel_id,
                   guest_id=conversation_data.guest_id,
                   initial_state=conversation_data.current_state.value)
        
        return conversation
    
    async def get_conversation(self, conversation_id: UUID) -> Optional[Conversation]:
        """Get conversation by ID"""
        return self.db.query(Conversation).filter(Conversation.id == conversation_id).first()
    
    async def get_conversations(
        self,
        filters: ConversationListFilter
    ) -> List[Conversation]:
        """
        Get conversations with filtering
        
        Args:
            filters: Filter criteria
            
        Returns:
            List[Conversation]: Filtered conversations
        """
        query = self.db.query(Conversation)
        
        if filters.hotel_id:
            query = query.filter(Conversation.hotel_id == filters.hotel_id)
        
        if filters.guest_id:
            query = query.filter(Conversation.guest_id == filters.guest_id)
        
        if filters.status:
            query = query.filter(Conversation.status == filters.status)
        
        if filters.current_state:
            query = query.filter(Conversation.current_state == filters.current_state)
        
        # Order by last message time (most recent first)
        query = query.order_by(desc(Conversation.last_message_at))
        
        # Apply pagination
        query = query.offset(filters.offset).limit(filters.limit)
        
        return query.all()
    
    async def update_conversation(
        self,
        conversation_id: UUID,
        updates: ConversationUpdate
    ) -> Optional[Conversation]:
        """
        Update conversation
        
        Args:
            conversation_id: Conversation ID
            updates: Update data
            
        Returns:
            Optional[Conversation]: Updated conversation or None if not found
        """
        conversation = await self.get_conversation(conversation_id)
        if not conversation:
            return None
        
        if updates.status is not None:
            conversation.status = updates.status
        
        if updates.current_state is not None:
            conversation.current_state = updates.current_state
        
        if updates.context is not None:
            conversation.context = updates.context
        
        conversation.update_last_message_time()
        
        logger.info("Conversation updated",
                   conversation_id=conversation_id,
                   updates=updates.dict(exclude_none=True))
        
        return conversation
    
    async def get_or_create_conversation(
        self,
        hotel_id: UUID,
        guest_id: UUID
    ) -> Conversation:
        """
        Get existing active conversation or create new one
        
        Args:
            hotel_id: Hotel ID
            guest_id: Guest ID
            
        Returns:
            Conversation: Existing or new conversation
        """
        # Try to find existing active conversation
        existing = self.db.query(Conversation).filter(
            and_(
                Conversation.hotel_id == hotel_id,
                Conversation.guest_id == guest_id,
                Conversation.status == ConversationStatus.ACTIVE
            )
        ).first()
        
        if existing:
            return existing
        
        # Create new conversation
        conversation_data = ConversationCreate(
            hotel_id=hotel_id,
            guest_id=guest_id
        )
        
        return await self.create_conversation(conversation_data)
    
    async def get_conversation_stats(self, hotel_id: UUID) -> ConversationStats:
        """
        Get conversation statistics for a hotel
        
        Args:
            hotel_id: Hotel ID
            
        Returns:
            ConversationStats: Statistics
        """
        base_query = self.db.query(Conversation).filter(Conversation.hotel_id == hotel_id)
        
        total = base_query.count()
        active = base_query.filter(Conversation.status == ConversationStatus.ACTIVE).count()
        escalated = base_query.filter(Conversation.status == ConversationStatus.ESCALATED).count()
        completed = base_query.filter(Conversation.current_state == ConversationState.COMPLETED).count()
        
        # Get state distribution
        state_counts = {}
        for state in ConversationState:
            count = base_query.filter(Conversation.current_state == state).count()
            state_counts[state.value] = count
        
        return ConversationStats(
            total_conversations=total,
            active_conversations=active,
            escalated_conversations=escalated,
            completed_conversations=completed,
            state_distribution=state_counts
        )


# Export service
__all__ = ['ConversationService']
