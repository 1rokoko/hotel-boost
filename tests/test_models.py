"""
Unit tests for database models
"""

import pytest
import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from unittest.mock import patch

from app.models.hotel import Hotel
from app.models.guest import Guest
from app.models.trigger import Trigger, TriggerType
from app.models.message import Message, Conversation, MessageType, SentimentType
from app.models.notification import StaffNotification, NotificationType, NotificationStatus


class TestHotelModel:
    """Test cases for Hotel model"""
    
    def test_hotel_creation(self):
        """Test basic hotel creation"""
        hotel = Hotel(
            name="Test Hotel",
            whatsapp_number="+1234567890",
            green_api_instance_id="test_instance",
            green_api_token="test_token"
        )
        
        assert hotel.name == "Test Hotel"
        assert hotel.whatsapp_number == "+1234567890"
        assert hotel.green_api_instance_id == "test_instance"
        assert hotel.green_api_token == "test_token"
        assert hotel.is_active is True
        assert isinstance(hotel.settings, dict)
    
    def test_hotel_whatsapp_number_validation(self):
        """Test WhatsApp number validation"""
        # Valid numbers
        hotel = Hotel(name="Test", whatsapp_number="1234567890")
        assert hotel.whatsapp_number == "+1234567890"
        
        hotel = Hotel(name="Test", whatsapp_number="+1234567890")
        assert hotel.whatsapp_number == "+1234567890"
        
        # Invalid numbers
        with pytest.raises(ValueError):
            Hotel(name="Test", whatsapp_number="123")  # Too short
        
        with pytest.raises(ValueError):
            Hotel(name="Test", whatsapp_number="")  # Empty
        
        with pytest.raises(ValueError):
            Hotel(name="Test", whatsapp_number="abc123")  # Invalid format
    
    def test_hotel_name_validation(self):
        """Test hotel name validation"""
        # Valid names
        hotel = Hotel(name="Test Hotel", whatsapp_number="+1234567890")
        assert hotel.name == "Test Hotel"
        
        # Invalid names
        with pytest.raises(ValueError):
            Hotel(name="", whatsapp_number="+1234567890")  # Empty
        
        with pytest.raises(ValueError):
            Hotel(name="A", whatsapp_number="+1234567890")  # Too short
        
        with pytest.raises(ValueError):
            Hotel(name="A" * 256, whatsapp_number="+1234567890")  # Too long
    
    def test_hotel_settings_management(self):
        """Test hotel settings management"""
        hotel = Hotel(name="Test", whatsapp_number="+1234567890")
        
        # Test setting values
        hotel.set_setting("test.key", "test_value")
        assert hotel.get_setting("test.key") == "test_value"
        
        # Test nested settings
        hotel.set_setting("nested.deep.key", "deep_value")
        assert hotel.get_setting("nested.deep.key") == "deep_value"
        
        # Test default values
        assert hotel.get_setting("nonexistent", "default") == "default"
        
        # Test default settings application
        hotel.apply_default_settings()
        assert "notifications" in hotel.settings
        assert "auto_responses" in hotel.settings
    
    def test_hotel_properties(self):
        """Test hotel computed properties"""
        hotel = Hotel(name="Test", whatsapp_number="+1234567890")
        
        # Test has_green_api_credentials
        assert not hotel.has_green_api_credentials
        
        hotel.green_api_instance_id = "test_instance"
        assert not hotel.has_green_api_credentials  # Still missing token
        
        hotel.green_api_token = "test_token"
        assert hotel.has_green_api_credentials
        
        # Test is_operational
        assert hotel.is_operational  # Active and has credentials
        
        hotel.is_active = False
        assert not hotel.is_operational  # Not active


class TestGuestModel:
    """Test cases for Guest model"""
    
    def test_guest_creation(self):
        """Test basic guest creation"""
        hotel_id = uuid.uuid4()
        guest = Guest(
            hotel_id=hotel_id,
            phone="+1234567890",
            name="John Doe"
        )
        
        assert guest.hotel_id == hotel_id
        assert guest.phone == "+1234567890"
        assert guest.name == "John Doe"
        assert isinstance(guest.preferences, dict)
    
    def test_guest_phone_validation(self):
        """Test guest phone validation"""
        hotel_id = uuid.uuid4()
        
        # Valid phones
        guest = Guest(hotel_id=hotel_id, phone="1234567890")
        assert guest.phone == "+1234567890"
        
        # Invalid phones
        with pytest.raises(ValueError):
            Guest(hotel_id=hotel_id, phone="123")  # Too short
        
        with pytest.raises(ValueError):
            Guest(hotel_id=hotel_id, phone="")  # Empty
    
    def test_guest_name_validation(self):
        """Test guest name validation"""
        hotel_id = uuid.uuid4()
        
        # Valid names
        guest = Guest(hotel_id=hotel_id, phone="+1234567890", name="John Doe")
        assert guest.name == "John Doe"
        
        # None name should be allowed
        guest = Guest(hotel_id=hotel_id, phone="+1234567890", name=None)
        assert guest.name is None
        
        # Empty string should become None
        guest = Guest(hotel_id=hotel_id, phone="+1234567890", name="")
        assert guest.name is None
        
        # Too long name
        with pytest.raises(ValueError):
            Guest(hotel_id=hotel_id, phone="+1234567890", name="A" * 256)
    
    def test_guest_preferences_management(self):
        """Test guest preferences management"""
        hotel_id = uuid.uuid4()
        guest = Guest(hotel_id=hotel_id, phone="+1234567890")
        
        # Test setting preferences
        guest.set_preference("language", "en")
        assert guest.get_preference("language") == "en"
        
        # Test nested preferences
        guest.set_preference("stay.room_type", "suite")
        assert guest.get_preference("stay.room_type") == "suite"
        
        # Test default preferences
        guest.apply_default_preferences()
        assert "communication" in guest.preferences
        assert "stay" in guest.preferences
    
    def test_guest_interaction_tracking(self):
        """Test guest interaction tracking"""
        hotel_id = uuid.uuid4()
        guest = Guest(hotel_id=hotel_id, phone="+1234567890")
        
        # Initially no interaction
        assert guest.last_interaction is None
        assert not guest.is_recent_guest
        
        # Update interaction
        guest.update_last_interaction()
        assert guest.last_interaction is not None
        assert guest.is_recent_guest
        
        # Old interaction
        guest.last_interaction = datetime.utcnow() - timedelta(days=35)
        assert not guest.is_recent_guest
    
    def test_guest_utility_methods(self):
        """Test guest utility methods"""
        hotel_id = uuid.uuid4()
        guest = Guest(hotel_id=hotel_id, phone="+1234567890")
        
        # Test display name without name
        assert guest.get_display_name() == "+1234567890"
        
        # Test display name with name
        guest.name = "John Doe"
        assert guest.get_display_name() == "John Doe"
        
        # Test visit count increment
        count = guest.increment_visit_count()
        assert count == 1
        assert guest.get_preference("profile.visit_count") == 1
        
        # Test special requests
        guest.add_special_request("Late checkout")
        requests = guest.get_preference("stay.special_requests")
        assert "Late checkout" in requests


class TestTriggerModel:
    """Test cases for Trigger model"""
    
    def test_trigger_creation(self):
        """Test basic trigger creation"""
        hotel_id = uuid.uuid4()
        trigger = Trigger(
            hotel_id=hotel_id,
            name="Welcome Message",
            trigger_type=TriggerType.TIME_BASED,
            message_template="Welcome to our hotel!"
        )
        
        assert trigger.hotel_id == hotel_id
        assert trigger.name == "Welcome Message"
        assert trigger.trigger_type == TriggerType.TIME_BASED
        assert trigger.message_template == "Welcome to our hotel!"
        assert trigger.is_active is True
        assert trigger.priority == 1
    
    def test_trigger_validation(self):
        """Test trigger validation"""
        hotel_id = uuid.uuid4()
        
        # Valid trigger
        trigger = Trigger(
            hotel_id=hotel_id,
            name="Test Trigger",
            trigger_type=TriggerType.TIME_BASED,
            message_template="Test message"
        )
        
        # Invalid name
        with pytest.raises(ValueError):
            Trigger(
                hotel_id=hotel_id,
                name="",
                trigger_type=TriggerType.TIME_BASED,
                message_template="Test"
            )
        
        # Invalid message template
        with pytest.raises(ValueError):
            Trigger(
                hotel_id=hotel_id,
                name="Test",
                trigger_type=TriggerType.TIME_BASED,
                message_template=""
            )
        
        # Invalid priority
        with pytest.raises(ValueError):
            Trigger(
                hotel_id=hotel_id,
                name="Test",
                trigger_type=TriggerType.TIME_BASED,
                message_template="Test",
                priority=11
            )
    
    def test_trigger_conditions_management(self):
        """Test trigger conditions management"""
        hotel_id = uuid.uuid4()
        trigger = Trigger(
            hotel_id=hotel_id,
            name="Test",
            trigger_type=TriggerType.TIME_BASED,
            message_template="Test"
        )
        
        # Test setting conditions
        trigger.set_condition("schedule_type", "hours_after_checkin")
        assert trigger.get_condition("schedule_type") == "hours_after_checkin"
        
        # Test nested conditions
        trigger.set_condition("timing.hours", 2)
        assert trigger.get_condition("timing.hours") == 2
        
        # Test default conditions
        trigger.apply_default_conditions()
        assert "schedule_type" in trigger.conditions
    
    def test_trigger_properties(self):
        """Test trigger computed properties"""
        hotel_id = uuid.uuid4()
        
        # Time-based trigger
        trigger = Trigger(
            hotel_id=hotel_id,
            name="Test",
            trigger_type=TriggerType.TIME_BASED,
            message_template="Test"
        )
        assert trigger.is_time_based
        assert not trigger.is_condition_based
        assert not trigger.is_event_based
        
        # Condition-based trigger
        trigger.trigger_type = TriggerType.CONDITION_BASED
        assert not trigger.is_time_based
        assert trigger.is_condition_based
        assert not trigger.is_event_based


class TestMessageAndConversationModels:
    """Test cases for Message and Conversation models"""
    
    def test_conversation_creation(self):
        """Test basic conversation creation"""
        hotel_id = uuid.uuid4()
        guest_id = uuid.uuid4()
        
        conversation = Conversation(
            hotel_id=hotel_id,
            guest_id=guest_id
        )
        
        assert conversation.hotel_id == hotel_id
        assert conversation.guest_id == guest_id
        assert conversation.status == "active"
        assert conversation.last_message_at is not None
    
    def test_conversation_status_management(self):
        """Test conversation status management"""
        hotel_id = uuid.uuid4()
        guest_id = uuid.uuid4()
        
        conversation = Conversation(hotel_id=hotel_id, guest_id=guest_id)
        
        # Test status changes
        assert conversation.is_active
        
        conversation.close_conversation()
        assert conversation.status == "closed"
        assert conversation.is_closed
        
        conversation.escalate_conversation()
        assert conversation.status == "escalated"
        assert conversation.is_escalated
        
        conversation.archive_conversation()
        assert conversation.status == "archived"
    
    def test_message_creation(self):
        """Test basic message creation"""
        conversation_id = uuid.uuid4()
        
        message = Message(
            conversation_id=conversation_id,
            message_type=MessageType.INCOMING,
            content="Hello, I need help with my booking"
        )
        
        assert message.conversation_id == conversation_id
        assert message.message_type == MessageType.INCOMING
        assert message.content == "Hello, I need help with my booking"
        assert message.sentiment_score is None
        assert message.sentiment_type is None
    
    def test_message_sentiment_management(self):
        """Test message sentiment management"""
        conversation_id = uuid.uuid4()
        
        message = Message(
            conversation_id=conversation_id,
            message_type=MessageType.INCOMING,
            content="I'm very unhappy with the service"
        )
        
        # Test setting sentiment
        message.set_sentiment(-0.8)
        assert message.sentiment_score == Decimal("-0.8")
        assert message.sentiment_type == SentimentType.REQUIRES_ATTENTION
        assert message.has_negative_sentiment
        assert message.requires_attention
        
        # Test positive sentiment
        message.set_sentiment(0.7)
        assert message.sentiment_type == SentimentType.POSITIVE
        assert not message.has_negative_sentiment
    
    def test_message_validation(self):
        """Test message validation"""
        conversation_id = uuid.uuid4()
        
        # Valid message
        message = Message(
            conversation_id=conversation_id,
            message_type=MessageType.INCOMING,
            content="Valid message"
        )
        
        # Invalid content
        with pytest.raises(ValueError):
            Message(
                conversation_id=conversation_id,
                message_type=MessageType.INCOMING,
                content=""
            )
        
        # Invalid sentiment score
        with pytest.raises(ValueError):
            message = Message(
                conversation_id=conversation_id,
                message_type=MessageType.INCOMING,
                content="Test"
            )
            message.sentiment_score = Decimal("2.0")  # Out of range
    
    def test_message_metadata_management(self):
        """Test message metadata management"""
        conversation_id = uuid.uuid4()
        
        message = Message(
            conversation_id=conversation_id,
            message_type=MessageType.INCOMING,
            content="Test message"
        )
        
        # Test setting metadata
        message.set_metadata("whatsapp.message_id", "msg_123")
        assert message.get_metadata("whatsapp.message_id") == "msg_123"
        
        # Test nested metadata
        message.set_metadata("delivery.status", "delivered")
        assert message.get_metadata("delivery.status") == "delivered"
        
        # Test default values
        assert message.get_metadata("nonexistent", "default") == "default"


class TestStaffNotificationModel:
    """Test cases for StaffNotification model"""
    
    def test_notification_creation(self):
        """Test basic notification creation"""
        hotel_id = uuid.uuid4()
        guest_id = uuid.uuid4()
        
        notification = StaffNotification(
            hotel_id=hotel_id,
            guest_id=guest_id,
            notification_type=NotificationType.NEGATIVE_SENTIMENT,
            title="Negative feedback detected",
            content="Guest expressed dissatisfaction with room service"
        )
        
        assert notification.hotel_id == hotel_id
        assert notification.guest_id == guest_id
        assert notification.notification_type == NotificationType.NEGATIVE_SENTIMENT
        assert notification.title == "Negative feedback detected"
        assert notification.status == NotificationStatus.PENDING
    
    def test_notification_status_management(self):
        """Test notification status management"""
        hotel_id = uuid.uuid4()
        
        notification = StaffNotification(
            hotel_id=hotel_id,
            notification_type=NotificationType.SYSTEM_ALERT,
            title="Test Alert",
            content="Test content"
        )
        
        # Test status changes
        assert notification.is_pending
        
        notification.mark_as_sent()
        assert notification.is_sent
        assert notification.sent_at is not None
        
        notification.acknowledge()
        assert notification.is_acknowledged
        assert notification.acknowledged_at is not None
        
        notification.resolve()
        assert notification.is_resolved
        assert notification.resolved_at is not None
    
    def test_notification_priority(self):
        """Test notification priority scoring"""
        hotel_id = uuid.uuid4()
        
        # High priority notification
        urgent_notification = StaffNotification(
            hotel_id=hotel_id,
            notification_type=NotificationType.ESCALATION,
            title="Urgent Issue",
            content="Critical problem"
        )
        
        # Low priority notification
        system_notification = StaffNotification(
            hotel_id=hotel_id,
            notification_type=NotificationType.SYSTEM_ALERT,
            title="System Info",
            content="System information"
        )
        
        assert urgent_notification.get_priority_score() > system_notification.get_priority_score()
        assert urgent_notification.is_urgent
        assert not system_notification.is_urgent
    
    def test_notification_factory_methods(self):
        """Test notification factory methods"""
        hotel_id = uuid.uuid4()
        guest_id = uuid.uuid4()
        message_id = uuid.uuid4()
        
        # Test create_from_message
        notification = StaffNotification.create_from_message(
            hotel_id=hotel_id,
            message_id=message_id,
            guest_id=guest_id,
            notification_type=NotificationType.NEGATIVE_SENTIMENT,
            title="Negative sentiment",
            content="Guest is unhappy"
        )
        
        assert notification.hotel_id == hotel_id
        assert notification.message_id == message_id
        assert notification.guest_id == guest_id
        
        # Test create_system_alert
        alert = StaffNotification.create_system_alert(
            hotel_id=hotel_id,
            title="System Alert",
            content="System issue detected"
        )
        
        assert alert.notification_type == NotificationType.SYSTEM_ALERT
        assert alert.guest_id is None
        assert alert.message_id is None
