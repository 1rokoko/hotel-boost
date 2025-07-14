"""
Unit tests for staff notification system
"""

import pytest
import uuid
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timedelta

from app.services.staff_notification import StaffNotificationService
from app.models.staff_alert import StaffAlert, AlertType, AlertStatus, AlertPriority
from app.models.message import Message, MessageType
from app.utils.notification_channels import (
    NotificationChannel,
    get_notification_channels,
    get_channel_config,
    format_notification_message
)
from app.tasks.send_staff_alert import send_staff_alert_task


class TestStaffNotificationService:
    """Test cases for StaffNotificationService"""
    
    @pytest.fixture
    def mock_db(self):
        """Mock database session"""
        return Mock()
    
    @pytest.fixture
    def notification_service(self, mock_db):
        """Create StaffNotificationService instance"""
        return StaffNotificationService(mock_db)
    
    @pytest.fixture
    def sample_alert(self):
        """Create sample staff alert"""
        return StaffAlert(
            id=uuid.uuid4(),
            hotel_id=uuid.uuid4(),
            alert_type=AlertType.NEGATIVE_SENTIMENT.value,
            priority=AlertPriority.HIGH.name.lower(),
            status=AlertStatus.PENDING.value,
            message_id=uuid.uuid4(),
            guest_id=uuid.uuid4(),
            title="Negative sentiment detected",
            description="Guest expressed dissatisfaction",
            sentiment_score=-0.6,
            urgency_level=4,
            created_at=datetime.utcnow()
        )
    
    @pytest.mark.asyncio
    async def test_send_alert_notification_email(
        self,
        notification_service,
        sample_alert
    ):
        """Test sending alert notification via email"""
        with patch.object(notification_service, '_send_email_notification') as mock_email:
            mock_email.return_value = True
            
            result = await notification_service.send_alert_notification(
                alert=sample_alert,
                channel=NotificationChannel.EMAIL,
                correlation_id="test-correlation-id"
            )
            
            assert result is True
            mock_email.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_send_alert_notification_sms(
        self,
        notification_service,
        sample_alert
    ):
        """Test sending alert notification via SMS"""
        with patch.object(notification_service, '_send_sms_notification') as mock_sms:
            mock_sms.return_value = True
            
            result = await notification_service.send_alert_notification(
                alert=sample_alert,
                channel=NotificationChannel.SMS,
                correlation_id="test-correlation-id"
            )
            
            assert result is True
            mock_sms.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_send_alert_notification_slack(
        self,
        notification_service,
        sample_alert
    ):
        """Test sending alert notification via Slack"""
        with patch.object(notification_service, '_send_slack_notification') as mock_slack:
            mock_slack.return_value = True
            
            result = await notification_service.send_alert_notification(
                alert=sample_alert,
                channel=NotificationChannel.SLACK,
                correlation_id="test-correlation-id"
            )
            
            assert result is True
            mock_slack.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_send_alert_notification_failure(
        self,
        notification_service,
        sample_alert
    ):
        """Test handling of notification failure"""
        with patch.object(notification_service, '_send_email_notification') as mock_email:
            mock_email.side_effect = Exception("Email service unavailable")
            
            result = await notification_service.send_alert_notification(
                alert=sample_alert,
                channel=NotificationChannel.EMAIL,
                correlation_id="test-correlation-id"
            )
            
            assert result is False
    
    @pytest.mark.asyncio
    async def test_send_escalation_notification(
        self,
        notification_service,
        sample_alert
    ):
        """Test sending escalation notification"""
        from app.models.staff_alert import AlertEscalation
        
        escalation = AlertEscalation(
            id=uuid.uuid4(),
            hotel_id=sample_alert.hotel_id,
            alert_id=sample_alert.id,
            escalation_level="manager",
            escalated_to="manager@hotel.com",
            reason="Alert overdue"
        )
        
        with patch.object(notification_service, '_send_email_notification') as mock_email:
            mock_email.return_value = True
            
            result = await notification_service.send_escalation_notification(
                escalation=escalation,
                correlation_id="test-correlation-id"
            )
            
            assert result is True
            mock_email.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_send_daily_summary(
        self,
        notification_service
    ):
        """Test sending daily summary"""
        summary = {
            "date": "2024-01-15",
            "total_alerts": 10,
            "priority_breakdown": {"high": 3, "medium": 5, "low": 2},
            "average_response_time_minutes": 25.5
        }
        
        with patch.object(notification_service, '_send_email_notification') as mock_email:
            mock_email.return_value = True
            
            result = await notification_service.send_daily_summary(
                hotel_id=str(uuid.uuid4()),
                summary=summary,
                correlation_id="test-correlation-id"
            )
            
            assert result is True
            mock_email.assert_called_once()
    
    def test_format_alert_message_email(self, notification_service, sample_alert):
        """Test formatting alert message for email"""
        message = notification_service._format_alert_message(
            alert=sample_alert,
            channel=NotificationChannel.EMAIL
        )
        
        assert "subject" in message
        assert "body" in message
        assert "Negative sentiment detected" in message["subject"]
        assert str(sample_alert.sentiment_score) in message["body"]
    
    def test_format_alert_message_sms(self, notification_service, sample_alert):
        """Test formatting alert message for SMS"""
        message = notification_service._format_alert_message(
            alert=sample_alert,
            channel=NotificationChannel.SMS
        )
        
        assert "body" in message
        assert len(message["body"]) <= 160  # SMS length limit
        assert "sentiment" in message["body"].lower()
    
    def test_get_notification_context(self, notification_service, sample_alert):
        """Test getting notification context"""
        context = notification_service._get_notification_context(sample_alert)
        
        assert "hotel_name" in context
        assert "guest_name" in context
        assert "sentiment_score" in context
        assert "urgency_level" in context
        assert context["sentiment_score"] == sample_alert.sentiment_score


class TestNotificationChannels:
    """Test cases for notification channel utilities"""
    
    def test_get_notification_channels_minimal_urgency(self):
        """Test channel selection for minimal urgency"""
        channels = get_notification_channels(1)
        assert NotificationChannel.DASHBOARD in channels
        assert len(channels) == 1
    
    def test_get_notification_channels_medium_urgency(self):
        """Test channel selection for medium urgency"""
        channels = get_notification_channels(3)
        assert NotificationChannel.EMAIL in channels
        assert NotificationChannel.WEBHOOK in channels
        assert NotificationChannel.DASHBOARD in channels
    
    def test_get_notification_channels_critical_urgency(self):
        """Test channel selection for critical urgency"""
        channels = get_notification_channels(5)
        assert NotificationChannel.EMAIL in channels
        assert NotificationChannel.SMS in channels
        assert NotificationChannel.SLACK in channels
        assert NotificationChannel.TEAMS in channels
    
    def test_get_channel_config_email(self):
        """Test getting email channel configuration"""
        config = get_channel_config(NotificationChannel.EMAIL)
        
        assert "retry_attempts" in config
        assert "timeout_seconds" in config
        assert config["retry_attempts"] == 3
        assert config["template_type"] == "html"
    
    def test_get_channel_config_sms(self):
        """Test getting SMS channel configuration"""
        config = get_channel_config(NotificationChannel.SMS)
        
        assert "retry_attempts" in config
        assert "max_length" in config
        assert config["max_length"] == 160
    
    def test_format_notification_message_email(self):
        """Test formatting notification message for email"""
        from app.utils.notification_channels import get_channel_template
        
        template = get_channel_template(
            NotificationChannel.EMAIL,
            "negative_sentiment",
            3
        )
        
        context = {
            "hotel_name": "Test Hotel",
            "guest_name": "John Doe",
            "sentiment_score": "-0.6",
            "urgency_level": "3",
            "response_deadline": "2024-01-15 15:30:00",
            "message_content": "The room was not clean"
        }
        
        formatted = format_notification_message(
            NotificationChannel.EMAIL,
            template,
            context
        )
        
        assert "subject" in formatted
        assert "body" in formatted
        assert "Test Hotel" in formatted["subject"]
        assert "John Doe" in formatted["body"]
        assert "-0.6" in formatted["body"]
    
    def test_format_notification_message_sms(self):
        """Test formatting notification message for SMS"""
        from app.utils.notification_channels import get_channel_template
        
        template = get_channel_template(
            NotificationChannel.SMS,
            "negative_sentiment",
            4
        )
        
        context = {
            "hotel_name": "Test Hotel",
            "sentiment_score": "-0.7"
        }
        
        formatted = format_notification_message(
            NotificationChannel.SMS,
            template,
            context
        )
        
        assert "body" in formatted
        assert len(formatted["body"]) <= 160
        assert "Test Hotel" in formatted["body"]
        assert "-0.7" in formatted["body"]
    
    def test_format_notification_message_missing_context(self):
        """Test formatting with missing context keys"""
        from app.utils.notification_channels import get_channel_template
        
        template = get_channel_template(
            NotificationChannel.EMAIL,
            "negative_sentiment",
            3
        )
        
        # Missing required context keys
        context = {
            "hotel_name": "Test Hotel"
            # Missing guest_name, sentiment_score, etc.
        }
        
        formatted = format_notification_message(
            NotificationChannel.EMAIL,
            template,
            context
        )
        
        # Should return fallback message
        assert "subject" in formatted
        assert "body" in formatted
        assert "Test Hotel" in formatted["subject"]


class TestStaffAlertTasks:
    """Test cases for staff alert Celery tasks"""
    
    @pytest.fixture
    def sample_message(self):
        """Create sample message"""
        return Message(
            id=uuid.uuid4(),
            hotel_id=uuid.uuid4(),
            guest_id=uuid.uuid4(),
            conversation_id=uuid.uuid4(),
            content="The service was terrible",
            message_type=MessageType.TEXT,
            created_at=datetime.utcnow()
        )
    
    @patch('app.tasks.send_staff_alert.get_db')
    @patch('app.tasks.send_staff_alert.StaffNotificationService')
    def test_send_staff_alert_task_success(
        self,
        mock_notification_service,
        mock_get_db,
        sample_message
    ):
        """Test successful staff alert task execution"""
        # Mock database and services
        mock_db = Mock()
        mock_get_db.return_value.__next__.return_value = mock_db
        mock_db.query.return_value.filter.return_value.first.return_value = sample_message
        
        mock_service = Mock()
        mock_notification_service.return_value = mock_service
        mock_service.send_alert_notification = AsyncMock(return_value=True)
        
        # Mock alert creation
        with patch('app.tasks.send_staff_alert._create_staff_alert') as mock_create_alert:
            mock_alert = Mock()
            mock_alert.id = uuid.uuid4()
            mock_create_alert.return_value = mock_alert
            
            with patch('app.tasks.send_staff_alert.get_notification_channels') as mock_channels:
                mock_channels.return_value = [NotificationChannel.EMAIL]
                
                # Execute task
                result = send_staff_alert_task(
                    message_id=str(sample_message.id),
                    sentiment_type="negative",
                    sentiment_score=-0.6,
                    urgency_level=3,
                    correlation_id="test-correlation-id"
                )
                
                # Verify task completed without errors
                assert result is None  # Task doesn't return value on success
    
    @patch('app.tasks.send_staff_alert.get_db')
    def test_send_staff_alert_task_message_not_found(self, mock_get_db):
        """Test staff alert task when message not found"""
        # Mock database returning no message
        mock_db = Mock()
        mock_get_db.return_value.__next__.return_value = mock_db
        mock_db.query.return_value.filter.return_value.first.return_value = None
        
        # Execute task
        result = send_staff_alert_task(
            message_id=str(uuid.uuid4()),
            sentiment_type="negative",
            sentiment_score=-0.6,
            urgency_level=3,
            correlation_id="test-correlation-id"
        )
        
        # Task should complete without error but not send notifications
        assert result is None
    
    def test_calculate_urgency_level_mapping(self):
        """Test urgency level to priority mapping"""
        from app.tasks.send_staff_alert import _get_priority_from_urgency
        
        assert _get_priority_from_urgency(1) == "low"
        assert _get_priority_from_urgency(2) == "medium"
        assert _get_priority_from_urgency(3) == "high"
        assert _get_priority_from_urgency(4) == "critical"
        assert _get_priority_from_urgency(5) == "urgent"
    
    def test_response_time_calculation(self):
        """Test response time calculation by urgency"""
        from app.tasks.send_staff_alert import _get_response_time_minutes
        
        assert _get_response_time_minutes(1) == 120  # 2 hours
        assert _get_response_time_minutes(2) == 60   # 1 hour
        assert _get_response_time_minutes(3) == 30   # 30 minutes
        assert _get_response_time_minutes(4) == 15   # 15 minutes
        assert _get_response_time_minutes(5) == 5    # 5 minutes
