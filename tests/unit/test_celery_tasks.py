"""
Unit tests for Celery tasks
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime, timedelta
from celery.exceptions import Retry

from app.tasks.base import (
    BaseTask, TenantAwareTask, TimedTask, CriticalTask,
    WhatsAppTask, AITask, EmailTask, MaintenanceTask
)
from app.tasks.email_tasks import send_email, send_staff_notification_email, send_daily_report
from app.utils.periodic_tasks import (
    cleanup_old_results, system_health_check, optimize_database
)
from app.core.celery_app import celery_app


class TestBaseTask:
    """Test base task functionality"""
    
    def test_base_task_initialization(self):
        """Test BaseTask initialization"""
        task = BaseTask()
        assert task.task_logger is not None
        assert task.autoretry_for == (Exception,)
        assert task.retry_kwargs['max_retries'] == 3
    
    def test_base_task_success_callback(self):
        """Test BaseTask success callback"""
        task = BaseTask()
        task.name = "test_task"
        
        with patch.object(task.task_logger, 'log_task_success') as mock_log:
            task.on_success("result", "task_id", (), {})
            mock_log.assert_called_once()
    
    def test_base_task_failure_callback(self):
        """Test BaseTask failure callback"""
        task = BaseTask()
        task.name = "test_task"
        
        with patch.object(task.task_logger, 'log_task_failure') as mock_log:
            exc = Exception("Test error")
            task.on_failure(exc, "task_id", (), {}, None)
            mock_log.assert_called_once()
    
    def test_base_task_retry_callback(self):
        """Test BaseTask retry callback"""
        task = BaseTask()
        task.name = "test_task"
        task.request = Mock()
        task.request.retries = 1
        
        with patch.object(task.task_logger, 'log_task_retry') as mock_log:
            exc = Exception("Test error")
            task.on_retry(exc, "task_id", (), {}, None)
            mock_log.assert_called_once()


class TestTenantAwareTask:
    """Test tenant-aware task functionality"""
    
    def test_tenant_aware_task_with_hotel_id(self):
        """Test TenantAwareTask with hotel_id in kwargs"""
        task = TenantAwareTask()
        task.run = Mock(return_value="success")
        
        with patch('app.tasks.base.TenantContext') as mock_context:
            result = task(hotel_id=123)
            
            mock_context.assert_called_once_with(123)
            mock_context.return_value.__enter__.assert_called_once()
            assert result == "success"
    
    def test_tenant_aware_task_with_hotel_id_in_args(self):
        """Test TenantAwareTask with hotel_id in args"""
        task = TenantAwareTask()
        task.run = Mock(return_value="success")
        
        with patch('app.tasks.base.TenantContext') as mock_context:
            result = task(123)
            
            mock_context.assert_called_once_with(123)
            assert result == "success"
    
    def test_tenant_aware_task_without_hotel_id(self):
        """Test TenantAwareTask without hotel_id"""
        task = TenantAwareTask()
        task.name = "test_task"
        task.run = Mock(return_value="success")
        
        result = task()
        assert result == "success"


class TestTimedTask:
    """Test timed task functionality"""
    
    def test_timed_task_success(self):
        """Test TimedTask successful execution"""
        task = TimedTask()
        task.name = "test_task"
        task.request = Mock()
        task.request.id = "task_id"
        task.run = Mock(return_value="success")
        
        with patch.object(task.task_logger, 'log_task_timing') as mock_log:
            result = task()
            
            assert result == "success"
            mock_log.assert_called_once()
            
            # Check that timing was logged
            call_args = mock_log.call_args[1]
            assert call_args['task_id'] == "task_id"
            assert call_args['task_name'] == "test_task"
            assert 'execution_time' in call_args
    
    def test_timed_task_failure(self):
        """Test TimedTask failure handling"""
        task = TimedTask()
        task.name = "test_task"
        task.request = Mock()
        task.request.id = "task_id"
        task.run = Mock(side_effect=Exception("Test error"))
        
        with pytest.raises(Exception, match="Test error"):
            task()


class TestEmailTasks:
    """Test email task implementations"""
    
    @pytest.fixture
    def mock_smtp(self):
        """Mock SMTP server"""
        with patch('app.tasks.email_tasks.smtplib.SMTP') as mock:
            smtp_instance = Mock()
            mock.return_value.__enter__.return_value = smtp_instance
            yield smtp_instance
    
    def test_send_email_success(self, mock_smtp):
        """Test successful email sending"""
        with patch('app.tasks.email_tasks.settings') as mock_settings:
            mock_settings.NOTIFICATION_EMAIL_SMTP_HOST = "smtp.test.com"
            mock_settings.NOTIFICATION_EMAIL_SMTP_PORT = 587
            mock_settings.NOTIFICATION_EMAIL_USERNAME = "test@test.com"
            mock_settings.NOTIFICATION_EMAIL_PASSWORD = "password"
            
            # Create a mock task instance
            task_instance = Mock()
            task_instance.request.id = "test_task_id"
            task_instance.name = "send_email"
            task_instance.validate_email_params.return_value = True
            
            with patch('app.tasks.email_tasks.task_logger') as mock_logger:
                result = send_email.__wrapped__(
                    task_instance,
                    "recipient@test.com",
                    "Test Subject",
                    "Test Body"
                )
                
                assert result['status'] == 'sent'
                assert result['to_email'] == 'recipient@test.com'
                assert result['subject'] == 'Test Subject'
                mock_smtp.send_message.assert_called_once()
    
    def test_send_email_failure(self, mock_smtp):
        """Test email sending failure"""
        mock_smtp.send_message.side_effect = Exception("SMTP Error")
        
        with patch('app.tasks.email_tasks.settings') as mock_settings:
            mock_settings.NOTIFICATION_EMAIL_SMTP_HOST = "smtp.test.com"
            mock_settings.NOTIFICATION_EMAIL_SMTP_PORT = 587
            mock_settings.NOTIFICATION_EMAIL_USERNAME = "test@test.com"
            mock_settings.NOTIFICATION_EMAIL_PASSWORD = "password"
            
            task_instance = Mock()
            task_instance.request.id = "test_task_id"
            task_instance.name = "send_email"
            task_instance.validate_email_params.return_value = True
            
            with patch('app.tasks.email_tasks.task_logger'):
                with pytest.raises(Exception, match="SMTP Error"):
                    send_email.__wrapped__(
                        task_instance,
                        "recipient@test.com",
                        "Test Subject",
                        "Test Body"
                    )
    
    @pytest.mark.asyncio
    async def test_send_staff_notification_email(self):
        """Test staff notification email"""
        with patch('app.tasks.email_tasks.get_async_session') as mock_session:
            # Mock database objects
            mock_notification = Mock()
            mock_notification.guest.phone = "+1234567890"
            mock_notification.conversation_id = "conv_123"
            mock_notification.sentiment_score = -0.8
            mock_notification.message_content = "I'm very unhappy!"
            mock_notification.created_at = datetime.utcnow()
            
            mock_hotel = Mock()
            mock_hotel.name = "Test Hotel"
            mock_hotel.staff_notification_emails = ["staff@hotel.com"]
            
            mock_session_instance = AsyncMock()
            mock_session_instance.get.side_effect = [mock_notification, mock_hotel]
            mock_session.return_value.__aenter__.return_value = mock_session_instance
            
            task_instance = Mock()
            task_instance.request.id = "test_task_id"
            task_instance.name = "send_staff_notification_email"
            
            with patch('app.tasks.email_tasks.send_email') as mock_send:
                mock_send.apply_async.return_value.get.return_value = {"status": "sent"}
                
                with patch('app.tasks.email_tasks.task_logger'):
                    result = await send_staff_notification_email.__wrapped__(
                        task_instance,
                        123,  # notification_id
                        456   # hotel_id
                    )
                    
                    assert result['status'] == 'completed'
                    assert result['notification_id'] == 123
                    mock_send.apply_async.assert_called_once()


class TestMaintenanceTasks:
    """Test maintenance task implementations"""
    
    def test_cleanup_old_results(self):
        """Test cleanup old results task"""
        task_instance = Mock()
        task_instance.request.id = "test_task_id"
        task_instance.name = "cleanup_old_results"
        
        with patch('app.utils.periodic_tasks.task_logger') as mock_logger:
            result = cleanup_old_results.__wrapped__(task_instance, days_to_keep=7)
            
            assert result['status'] == 'completed'
            assert result['days_kept'] == 7
            assert 'cutoff_date' in result
            mock_logger.log_task_custom.assert_called()
    
    def test_system_health_check(self):
        """Test system health check task"""
        task_instance = Mock()
        task_instance.request.id = "test_task_id"
        task_instance.name = "system_health_check"
        
        with patch('app.utils.periodic_tasks.get_async_session') as mock_session:
            mock_session_instance = AsyncMock()
            mock_session.return_value.__aenter__.return_value = mock_session_instance
            
            with patch('app.utils.periodic_tasks.task_logger') as mock_logger:
                with patch('app.core.celery_app.celery_app') as mock_celery:
                    mock_inspect = Mock()
                    mock_inspect.stats.return_value = {"worker1": {}}
                    mock_celery.control.inspect.return_value = mock_inspect
                    
                    result = system_health_check.__wrapped__(task_instance)
                    
                    assert result['overall_status'] in ['healthy', 'degraded', 'unhealthy']
                    assert 'components' in result
                    assert 'database' in result['components']
                    assert 'celery_workers' in result['components']
                    mock_logger.log_task_custom.assert_called()
    
    @pytest.mark.asyncio
    async def test_optimize_database(self):
        """Test database optimization task"""
        task_instance = Mock()
        task_instance.request.id = "test_task_id"
        task_instance.name = "optimize_database"
        
        with patch('app.utils.periodic_tasks.get_async_session') as mock_session:
            mock_session_instance = AsyncMock()
            mock_result = Mock()
            mock_result.rowcount = 5
            mock_session_instance.execute.return_value = mock_result
            mock_session.return_value.__aenter__.return_value = mock_session_instance
            
            with patch('app.utils.periodic_tasks.task_logger') as mock_logger:
                result = await optimize_database.__wrapped__(task_instance)
                
                assert 'operations' in result
                assert len(result['operations']) > 0
                mock_logger.log_task_custom.assert_called()


class TestCeleryConfiguration:
    """Test Celery configuration"""
    
    def test_celery_app_creation(self):
        """Test Celery app is properly configured"""
        assert celery_app.main == "hotel_bot"
        assert celery_app.conf.task_serializer == 'json'
        assert celery_app.conf.result_serializer == 'json'
        assert celery_app.conf.timezone == 'UTC'
    
    def test_task_routes_configuration(self):
        """Test task routing configuration"""
        routes = celery_app.conf.task_routes
        assert 'app.tasks.email_tasks.*' in routes
        assert routes['app.tasks.email_tasks.*']['queue'] == 'email_notifications'
    
    def test_queue_configuration(self):
        """Test queue configuration"""
        queues = celery_app.conf.task_queues
        queue_names = [q.name for q in queues]
        
        expected_queues = [
            'default', 'incoming_messages', 'outgoing_messages',
            'sentiment_analysis', 'response_generation', 'monitoring',
            'trigger_execution', 'high_priority', 'email_notifications',
            'maintenance'
        ]
        
        for expected_queue in expected_queues:
            assert expected_queue in queue_names


class TestTaskDecorators:
    """Test task decorators"""
    
    def test_email_task_decorator(self):
        """Test email task decorator"""
        from app.tasks.base import email_task
        
        @email_task
        def test_email_task():
            return "email_task_result"
        
        # Check that the task is properly registered
        assert hasattr(test_email_task, 'delay')
        assert hasattr(test_email_task, 'apply_async')
    
    def test_maintenance_task_decorator(self):
        """Test maintenance task decorator"""
        from app.tasks.base import maintenance_task
        
        @maintenance_task
        def test_maintenance_task():
            return "maintenance_task_result"
        
        # Check that the task is properly registered
        assert hasattr(test_maintenance_task, 'delay')
        assert hasattr(test_maintenance_task, 'apply_async')
    
    def test_whatsapp_task_decorator(self):
        """Test WhatsApp task decorator"""
        from app.tasks.base import whatsapp_task
        
        @whatsapp_task
        def test_whatsapp_task():
            return "whatsapp_task_result"
        
        # Check that the task is properly registered
        assert hasattr(test_whatsapp_task, 'delay')
        assert hasattr(test_whatsapp_task, 'apply_async')


if __name__ == "__main__":
    pytest.main([__file__])
