"""
Enhanced conversation management endpoints with state machine support
"""

from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
import structlog

from app.database import get_db
from app.models.hotel import Hotel
from app.models.guest import Guest
from app.models.message import Conversation, Message, ConversationState, ConversationStatus
from app.services.message_processor import MessageProcessor
from app.services.conversation_service import ConversationService
from app.services.conversation_state_machine import ConversationStateMachine
from app.services.conversation_memory import ConversationMemory
from app.utils.context_manager import ContextManager
from app.schemas.conversation import (
    ConversationResponse, ConversationDetailResponse, ConversationCreate,
    ConversationUpdate, ConversationListFilter, ConversationStats,
    StateTransitionRequest, StateTransitionResponse, ConversationContextUpdate
)

logger = structlog.get_logger(__name__)

router = APIRouter()


@router.get("/conversations")
def get_conversations(
    hotel_id: str,
    status: Optional[str] = Query(None, description="Filter by conversation status"),
    limit: int = Query(50, ge=1, le=100, description="Number of conversations to return"),
    offset: int = Query(0, ge=0, description="Number of conversations to skip"),
    db: Session = Depends(get_db)
):
    """
    Get conversations for a hotel
    
    Returns a list of conversations with basic information.
    """
    try:
        # Verify hotel exists
        hotel = db.query(Hotel).filter(Hotel.id == hotel_id).first()
        if not hotel:
            raise HTTPException(status_code=404, detail="Hotel not found")
        
        # Build query
        query = db.query(Conversation).filter(Conversation.hotel_id == hotel_id)
        
        if status:
            query = query.filter(Conversation.status == status)
        
        # Get conversations with pagination
        conversations = query.order_by(
            Conversation.last_message_at.desc()
        ).offset(offset).limit(limit).all()
        
        # Format response
        result = []
        for conv in conversations:
            # Get last message
            last_message = db.query(Message).filter(
                Message.conversation_id == conv.id
            ).order_by(Message.created_at.desc()).first()
            
            # Count unread messages (incoming messages without read status)
            unread_count = db.query(Message).filter(
                Message.conversation_id == conv.id,
                Message.message_type == 'incoming',
                Message.message_metadata['delivery_status'].astext != 'read'
            ).count()
            
            conv_data = {
                'id': str(conv.id),
                'guest': {
                    'id': str(conv.guest.id),
                    'name': conv.guest.name,
                    'phone_number': conv.guest.phone_number
                },
                'status': conv.status,
                'created_at': conv.created_at.isoformat(),
                'last_message_at': conv.last_message_at.isoformat(),
                'unread_count': unread_count,
                'last_message': {
                    'content': last_message.content[:100] + '...' if len(last_message.content) > 100 else last_message.content,
                    'type': last_message.message_type.value,
                    'created_at': last_message.created_at.isoformat()
                } if last_message else None
            }
            
            result.append(conv_data)
        
        logger.info("Retrieved conversations",
                   hotel_id=hotel_id,
                   count=len(result),
                   status_filter=status)
        
        return {
            'conversations': result,
            'total': len(result),
            'offset': offset,
            'limit': limit
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error retrieving conversations",
                    hotel_id=hotel_id,
                    error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/conversations/{conversation_id}")
def get_conversation_details(
    conversation_id: str,
    db: Session = Depends(get_db)
):
    """
    Get detailed conversation information including messages
    """
    try:
        # Get conversation
        conversation = db.query(Conversation).filter(
            Conversation.id == conversation_id
        ).first()
        
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")
        
        # Get conversation summary using MessageProcessor
        processor = MessageProcessor(db)
        summary = processor.get_conversation_summary(conversation_id)
        
        logger.info("Retrieved conversation details",
                   conversation_id=conversation_id,
                   message_count=summary['message_counts']['total'])
        
        return summary
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error retrieving conversation details",
                    conversation_id=conversation_id,
                    error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/conversations/{conversation_id}/messages")
def get_conversation_messages(
    conversation_id: str,
    limit: int = Query(50, ge=1, le=100, description="Number of messages to return"),
    offset: int = Query(0, ge=0, description="Number of messages to skip"),
    db: Session = Depends(get_db)
):
    """
    Get messages for a specific conversation
    """
    try:
        # Verify conversation exists
        conversation = db.query(Conversation).filter(
            Conversation.id == conversation_id
        ).first()
        
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")
        
        # Get messages with pagination
        messages = db.query(Message).filter(
            Message.conversation_id == conversation_id
        ).order_by(Message.created_at.desc()).offset(offset).limit(limit).all()
        
        # Format messages
        result = []
        for msg in messages:
            msg_data = {
                'id': str(msg.id),
                'type': msg.message_type.value,
                'content': msg.content,
                'created_at': msg.created_at.isoformat(),
                'sentiment': {
                    'score': float(msg.sentiment_score) if msg.sentiment_score else None,
                    'type': msg.sentiment_type.value if msg.sentiment_type else None
                },
                'metadata': msg.message_metadata,
                'green_api_message_id': msg.get_metadata('green_api_message_id'),
                'delivery_status': msg.get_metadata('delivery_status')
            }
            
            result.append(msg_data)
        
        logger.info("Retrieved conversation messages",
                   conversation_id=conversation_id,
                   count=len(result))
        
        return {
            'messages': result,
            'conversation_id': conversation_id,
            'total': len(result),
            'offset': offset,
            'limit': limit
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error retrieving conversation messages",
                    conversation_id=conversation_id,
                    error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")


@router.patch("/conversations/{conversation_id}/status")
def update_conversation_status(
    conversation_id: str,
    status: str,
    db: Session = Depends(get_db)
):
    """
    Update conversation status
    """
    try:
        # Verify conversation exists
        conversation = db.query(Conversation).filter(
            Conversation.id == conversation_id
        ).first()
        
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")
        
        # Validate status
        valid_statuses = ['active', 'closed', 'archived', 'escalated']
        if status not in valid_statuses:
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid status. Must be one of: {valid_statuses}"
            )
        
        # Update status
        old_status = conversation.status
        conversation.status = status
        
        if status == 'closed':
            conversation.close_conversation()
        elif status == 'escalated':
            conversation.escalate_conversation()
        elif status == 'archived':
            conversation.archive_conversation()
        
        db.commit()
        
        logger.info("Conversation status updated",
                   conversation_id=conversation_id,
                   old_status=old_status,
                   new_status=status)
        
        return {
            'conversation_id': conversation_id,
            'old_status': old_status,
            'new_status': status,
            'updated_at': conversation.updated_at.isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error("Error updating conversation status",
                    conversation_id=conversation_id,
                    status=status,
                    error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/conversations/stats/{hotel_id}")
def get_conversation_stats(
    hotel_id: str,
    db: Session = Depends(get_db)
):
    """
    Get conversation statistics for a hotel
    """
    try:
        # Verify hotel exists
        hotel = db.query(Hotel).filter(Hotel.id == hotel_id).first()
        if not hotel:
            raise HTTPException(status_code=404, detail="Hotel not found")
        
        # Get conversation counts by status
        status_counts = {}
        for status in ['active', 'closed', 'archived', 'escalated']:
            count = db.query(Conversation).filter(
                Conversation.hotel_id == hotel_id,
                Conversation.status == status
            ).count()
            status_counts[status] = count
        
        # Get total message counts
        total_messages = db.query(Message).join(Conversation).filter(
            Conversation.hotel_id == hotel_id
        ).count()
        
        incoming_messages = db.query(Message).join(Conversation).filter(
            Conversation.hotel_id == hotel_id,
            Message.message_type == 'incoming'
        ).count()
        
        outgoing_messages = total_messages - incoming_messages
        
        # Get sentiment distribution
        sentiment_counts = {}
        for sentiment in ['positive', 'negative', 'neutral', 'requires_attention']:
            count = db.query(Message).join(Conversation).filter(
                Conversation.hotel_id == hotel_id,
                Message.sentiment_type == sentiment
            ).count()
            sentiment_counts[sentiment] = count
        
        stats = {
            'hotel_id': hotel_id,
            'conversation_counts': status_counts,
            'message_counts': {
                'total': total_messages,
                'incoming': incoming_messages,
                'outgoing': outgoing_messages
            },
            'sentiment_distribution': sentiment_counts,
            'total_conversations': sum(status_counts.values())
        }
        
        logger.info("Retrieved conversation stats",
                   hotel_id=hotel_id,
                   total_conversations=stats['total_conversations'])
        
        return stats
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error retrieving conversation stats",
                    hotel_id=hotel_id,
                    error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{conversation_id}/transition", response_model=dict)
async def transition_conversation_state(
    conversation_id: str,
    target_state: ConversationState,
    reason: Optional[str] = None,
    context_updates: Optional[dict] = None,
    db: Session = Depends(get_db)
):
    """
    Execute state transition for conversation
    """
    try:
        # Get conversation
        conversation = db.query(Conversation).filter(
            Conversation.id == conversation_id
        ).first()

        if not conversation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found"
            )

        # Initialize state machine
        state_machine = ConversationStateMachine()

        # Execute transition
        result = await state_machine.transition_to(
            conversation=conversation,
            target_state=target_state,
            context=context_updates or {},
            reason=reason
        )

        if result.success:
            db.commit()
        else:
            db.rollback()

        logger.info("State transition executed",
                   conversation_id=conversation_id,
                   target_state=target_state.value,
                   success=result.success)

        return {
            "success": result.success,
            "previous_state": result.previous_state.value,
            "new_state": result.new_state.value,
            "timestamp": result.timestamp.isoformat(),
            "message": result.message
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error("Failed to execute state transition",
                    conversation_id=conversation_id,
                    error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to execute state transition"
        )


@router.post("/{conversation_id}/escalate")
def escalate_conversation(
    conversation_id: str,
    reason: str = Query(..., description="Reason for escalation"),
    urgency_level: int = Query(3, ge=1, le=5, description="Urgency level (1-5)"),
    db: Session = Depends(get_db)
):
    """
    Escalate conversation to staff
    """
    try:
        # Get conversation
        conversation = db.query(Conversation).filter(
            Conversation.id == conversation_id
        ).first()

        if not conversation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found"
            )

        # Escalate conversation
        conversation.escalate_conversation()

        # Create staff notification task
        from app.tasks.process_message import escalate_conversation_task
        escalate_conversation_task.delay(
            conversation_id=str(conversation_id),
            escalation_reason=reason,
            urgency_level=urgency_level
        )

        db.commit()

        logger.info("Conversation escalated",
                   conversation_id=conversation_id,
                   reason=reason,
                   urgency_level=urgency_level)

        return {
            "success": True,
            "message": "Conversation escalated successfully",
            "escalation_reason": reason,
            "urgency_level": urgency_level
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error("Failed to escalate conversation",
                    conversation_id=conversation_id,
                    error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to escalate conversation"
        )


@router.get("/{conversation_id}/context")
async def get_conversation_context(
    conversation_id: str,
    context_type: Optional[str] = Query(None, description="Filter by context type")
):
    """
    Get conversation context data
    """
    try:
        memory_service = ConversationMemory()

        if context_type:
            context_data = await memory_service.get_context(conversation_id, context_type)
        else:
            context_data = await memory_service.get_context(conversation_id)

        logger.info("Context retrieved",
                   conversation_id=conversation_id,
                   context_type=context_type)

        return {
            "conversation_id": conversation_id,
            "context_type": context_type,
            "context_data": context_data
        }

    except Exception as e:
        logger.error("Failed to get conversation context",
                    conversation_id=conversation_id,
                    error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve conversation context"
        )


@router.put("/{conversation_id}/context")
async def update_conversation_context(
    conversation_id: str,
    updates: dict,
    merge: bool = Query(True, description="Whether to merge with existing context")
):
    """
    Update conversation context
    """
    try:
        memory_service = ConversationMemory()

        if merge:
            # Merge with existing context
            success = await memory_service.update_context(conversation_id, updates)
        else:
            # Replace context
            await memory_service.delete_context(conversation_id)
            success = await memory_service.update_context(conversation_id, updates)

        logger.info("Context updated",
                   conversation_id=conversation_id,
                   merge=merge,
                   updates_count=len(updates))

        return {
            "success": success,
            "conversation_id": conversation_id,
            "updates_applied": len(updates),
            "merge_mode": merge
        }

    except Exception as e:
        logger.error("Failed to update conversation context",
                    conversation_id=conversation_id,
                    error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update conversation context"
        )


# Export router
__all__ = ['router']
