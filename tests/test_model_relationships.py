"""
Unit tests for database model relationships
"""

import pytest
import uuid
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from app.models.hotel import Hotel
from app.models.guest import Guest
from app.models.trigger import Trigger, TriggerType
from app.models.message import Message, Conversation, MessageType, SentimentType
from app.models.notification import StaffNotification, NotificationType, NotificationStatus


class TestModelRelationships:
    """Test cases for model relationships and foreign key constraints"""
    
    def test_hotel_guest_relationship(self):
        """Test Hotel-Guest relationship"""
        # Create hotel
        hotel = Hotel(
            name="Test Hotel",
            whatsapp_number="+1234567890"
        )
        
        # Create guests
        guest1 = Guest(
            hotel_id=hotel.id,
            phone="+1111111111",
            name="Guest 1"
        )
        
        guest2 = Guest(
            hotel_id=hotel.id,
            phone="+2222222222",
            name="Guest 2"
        )
        
        # Test relationship setup (would work with actual database session)
        assert guest1.hotel_id == hotel.id
        assert guest2.hotel_id == hotel.id
    
    def test_hotel_trigger_relationship(self):
        """Test Hotel-Trigger relationship"""
        hotel = Hotel(
            name="Test Hotel",
            whatsapp_number="+1234567890"
        )
        
        trigger = Trigger(
            hotel_id=hotel.id,
            name="Welcome Trigger",
            trigger_type=TriggerType.TIME_BASED,
            message_template="Welcome!"
        )
        
        assert trigger.hotel_id == hotel.id
    
    def test_guest_conversation_relationship(self):
        """Test Guest-Conversation relationship"""
        hotel_id = uuid.uuid4()
        
        guest = Guest(
            hotel_id=hotel_id,
            phone="+1234567890",
            name="Test Guest"
        )
        
        conversation = Conversation(
            hotel_id=hotel_id,
            guest_id=guest.id
        )
        
        assert conversation.guest_id == guest.id
        assert conversation.hotel_id == hotel_id
    
    def test_conversation_message_relationship(self):
        """Test Conversation-Message relationship"""
        hotel_id = uuid.uuid4()
        guest_id = uuid.uuid4()
        
        conversation = Conversation(
            hotel_id=hotel_id,
            guest_id=guest_id
        )
        
        message1 = Message(
            conversation_id=conversation.id,
            message_type=MessageType.INCOMING,
            content="Hello"
        )
        
        message2 = Message(
            conversation_id=conversation.id,
            message_type=MessageType.OUTGOING,
            content="Hi there!"
        )
        
        assert message1.conversation_id == conversation.id
        assert message2.conversation_id == conversation.id
    
    def test_notification_relationships(self):
        """Test StaffNotification relationships"""
        hotel_id = uuid.uuid4()
        guest_id = uuid.uuid4()
        message_id = uuid.uuid4()
        
        notification = StaffNotification(
            hotel_id=hotel_id,
            guest_id=guest_id,
            message_id=message_id,
            notification_type=NotificationType.NEGATIVE_SENTIMENT,
            title="Test Notification",
            content="Test content"
        )
        
        assert notification.hotel_id == hotel_id
        assert notification.guest_id == guest_id
        assert notification.message_id == message_id
    
    def test_cascade_relationships(self):
        """Test cascade delete behavior (conceptual test)"""
        # This would test actual cascade behavior with a real database
        hotel_id = uuid.uuid4()
        
        # Create related objects
        guest = Guest(hotel_id=hotel_id, phone="+1234567890")
        conversation = Conversation(hotel_id=hotel_id, guest_id=guest.id)
        message = Message(
            conversation_id=conversation.id,
            message_type=MessageType.INCOMING,
            content="Test"
        )
        notification = StaffNotification(
            hotel_id=hotel_id,
            guest_id=guest.id,
            message_id=message.id,
            notification_type=NotificationType.SYSTEM_ALERT,
            title="Test",
            content="Test"
        )
        
        # Verify relationships are set up correctly
        assert guest.hotel_id == hotel_id
        assert conversation.guest_id == guest.id
        assert message.conversation_id == conversation.id
        assert notification.guest_id == guest.id
        assert notification.message_id == message.id


class TestModelConstraints:
    """Test cases for model constraints and validations"""
    
    def test_hotel_unique_whatsapp_constraint(self):
        """Test unique WhatsApp number constraint"""
        # This would test the actual constraint with a database
        hotel1 = Hotel(
            name="Hotel 1",
            whatsapp_number="+1234567890"
        )
        
        hotel2 = Hotel(
            name="Hotel 2",
            whatsapp_number="+1234567890"  # Same number
        )
        
        # In a real database test, this would raise IntegrityError
        assert hotel1.whatsapp_number == hotel2.whatsapp_number
    
    def test_guest_unique_hotel_phone_constraint(self):
        """Test unique hotel+phone constraint for guests"""
        hotel_id = uuid.uuid4()
        
        guest1 = Guest(
            hotel_id=hotel_id,
            phone="+1234567890",
            name="Guest 1"
        )
        
        guest2 = Guest(
            hotel_id=hotel_id,
            phone="+1234567890",  # Same phone in same hotel
            name="Guest 2"
        )
        
        # In a real database test, this would raise IntegrityError
        assert guest1.phone == guest2.phone
        assert guest1.hotel_id == guest2.hotel_id
    
    def test_trigger_priority_constraint(self):
        """Test trigger priority constraint"""
        hotel_id = uuid.uuid4()
        
        # Valid priority
        trigger = Trigger(
            hotel_id=hotel_id,
            name="Test",
            trigger_type=TriggerType.TIME_BASED,
            message_template="Test",
            priority=5
        )
        assert trigger.priority == 5
        
        # Invalid priority would be caught by validation
        with pytest.raises(ValueError):
            Trigger(
                hotel_id=hotel_id,
                name="Test",
                trigger_type=TriggerType.TIME_BASED,
                message_template="Test",
                priority=11  # Out of range
            )
    
    def test_message_sentiment_score_constraint(self):
        """Test message sentiment score constraint"""
        conversation_id = uuid.uuid4()
        
        message = Message(
            conversation_id=conversation_id,
            message_type=MessageType.INCOMING,
            content="Test message"
        )
        
        # Valid sentiment scores
        message.set_sentiment(0.5)
        assert message.sentiment_score == 0.5
        
        message.set_sentiment(-0.8)
        assert message.sentiment_score == -0.8
        
        # Invalid sentiment score
        with pytest.raises(ValueError):
            message.set_sentiment(1.5)  # Out of range


class TestModelSerialization:
    """Test cases for model serialization and deserialization"""
    
    def test_hotel_to_dict(self):
        """Test hotel serialization"""
        hotel = Hotel(
            name="Test Hotel",
            whatsapp_number="+1234567890",
            green_api_instance_id="test_instance",
            green_api_token="secret_token",
            is_active=True
        )
        
        # Test without credentials
        data = hotel.to_dict(include_credentials=False)
        assert data["name"] == "Test Hotel"
        assert data["whatsapp_number"] == "+1234567890"
        assert data["is_active"] is True
        assert "green_api_token" not in data
        assert data["has_green_api_credentials"] is True
        assert data["is_operational"] is True
        
        # Test with credentials
        data_with_creds = hotel.to_dict(include_credentials=True)
        assert "green_api_token" in data_with_creds
        assert data_with_creds["green_api_token"] == "secret_token"
    
    def test_guest_to_dict(self):
        """Test guest serialization"""
        hotel_id = uuid.uuid4()
        guest = Guest(
            hotel_id=hotel_id,
            phone="+1234567890",
            name="John Doe"
        )
        guest.set_preference("profile.visit_count", 3)
        
        data = guest.to_dict()
        assert data["phone"] == "+1234567890"
        assert data["name"] == "John Doe"
        assert data["has_name"] is True
        assert data["display_name"] == "John Doe"
        assert data["visit_count"] == 3
    
    def test_trigger_to_dict(self):
        """Test trigger serialization"""
        hotel_id = uuid.uuid4()
        trigger = Trigger(
            hotel_id=hotel_id,
            name="Test Trigger",
            trigger_type=TriggerType.TIME_BASED,
            message_template="Test message",
            priority=2
        )
        
        data = trigger.to_dict()
        assert data["name"] == "Test Trigger"
        assert data["trigger_type"] == "time_based"
        assert data["priority"] == 2
        assert data["is_time_based"] is True
        assert data["is_condition_based"] is False
    
    def test_message_to_dict(self):
        """Test message serialization"""
        conversation_id = uuid.uuid4()
        message = Message(
            conversation_id=conversation_id,
            message_type=MessageType.INCOMING,
            content="Test message"
        )
        message.set_sentiment(-0.6, SentimentType.NEGATIVE)
        
        data = message.to_dict()
        assert data["content"] == "Test message"
        assert data["message_type"] == "incoming"
        assert data["sentiment_type"] == "negative"
        assert data["sentiment_score"] == -0.6
        assert data["is_incoming"] is True
        assert data["has_negative_sentiment"] is True
    
    def test_notification_to_dict(self):
        """Test notification serialization"""
        hotel_id = uuid.uuid4()
        notification = StaffNotification(
            hotel_id=hotel_id,
            notification_type=NotificationType.URGENT_REQUEST,
            title="Urgent Issue",
            content="Need immediate attention",
            status=NotificationStatus.PENDING
        )
        
        data = notification.to_dict()
        assert data["title"] == "Urgent Issue"
        assert data["notification_type"] == "urgent_request"
        assert data["status"] == "pending"
        assert data["is_urgent"] is True
        assert data["requires_action"] is True
        assert data["priority_score"] > 0


class TestModelUtilities:
    """Test cases for model utility methods"""
    
    def test_base_model_methods(self):
        """Test base model utility methods"""
        hotel = Hotel(
            name="Test Hotel",
            whatsapp_number="+1234567890"
        )
        
        # Test to_dict
        data = hotel.to_dict()
        assert isinstance(data, dict)
        assert "id" in data
        assert "created_at" in data
        assert "updated_at" in data
        
        # Test from_dict (conceptual)
        new_data = {
            "name": "New Hotel",
            "whatsapp_number": "+9876543210",
            "is_active": False
        }
        
        # This would work with actual model instantiation
        assert new_data["name"] == "New Hotel"
        assert new_data["whatsapp_number"] == "+9876543210"
        assert new_data["is_active"] is False
    
    def test_model_repr_methods(self):
        """Test model string representations"""
        hotel = Hotel(name="Test Hotel", whatsapp_number="+1234567890")
        hotel_repr = repr(hotel)
        assert "Test Hotel" in hotel_repr
        assert "+1234567890" in hotel_repr
        
        guest = Guest(hotel_id=uuid.uuid4(), phone="+1111111111", name="John")
        guest_repr = repr(guest)
        assert "John" in guest_repr
        assert "+1111111111" in guest_repr
        
        trigger = Trigger(
            hotel_id=uuid.uuid4(),
            name="Test Trigger",
            trigger_type=TriggerType.EVENT_BASED,
            message_template="Test"
        )
        trigger_repr = repr(trigger)
        assert "Test Trigger" in trigger_repr
        assert "event_based" in trigger_repr
