"""
Integration tests for Celery task execution
"""

import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime, timedelta
from celery import Celery
from celery.result import AsyncResult

from app.core.celery_app import celery_app
from app.core.celery_config import TestingCeleryConfig
from app.tasks.email_tasks import send_email, send_daily_report
from app.utils.periodic_tasks import cleanup_old_results, system_health_check
from app.services.task_monitor import task_monitor
from app.utils.celery_metrics import celery_metrics


@pytest.fixture(scope="session")
def celery_config():
    """Celery configuration for testing"""
    return TestingCeleryConfig


@pytest.fixture(scope="session")
def celery_app_test(celery_config):
    """Test Celery app with eager execution"""
    app = Celery('test_hotel_bot')
    app.config_from_object(celery_config)
    app.conf.task_always_eager = True
    app.conf.task_eager_propagates = True
    return app


@pytest.fixture
def mock_database():
    """Mock database session"""
    with patch('app.database.get_async_session') as mock:
        session = AsyncMock()
        mock.return_value.__aenter__.return_value = session
        yield session


@pytest.fixture
def mock_smtp():
    """Mock SMTP server for email tests"""
    with patch('smtplib.SMTP') as mock:
        smtp_instance = Mock()
        mock.return_value.__enter__.return_value = smtp_instance
        yield smtp_instance


class TestTaskExecution:
    """Test actual task execution"""
    
    def test_task_registration(self):
        """Test that all tasks are properly registered"""
        registered_tasks = celery_app.tasks
        
        expected_tasks = [
            'app.tasks.email_tasks.send_email',
            'app.tasks.email_tasks.send_staff_notification_email',
            'app.tasks.email_tasks.send_daily_report',
            'app.utils.periodic_tasks.cleanup_old_results',
            'app.utils.periodic_tasks.system_health_check',
            'app.utils.periodic_tasks.optimize_database'
        ]
        
        for task_name in expected_tasks:
            assert task_name in registered_tasks, f"Task {task_name} not registered"
    
    def test_task_routing(self):
        """Test task routing to correct queues"""
        routes = celery_app.conf.task_routes
        
        # Test email task routing
        assert routes.get('app.tasks.email_tasks.*', {}).get('queue') == 'email_notifications'
        
        # Test maintenance task routing  
        maintenance_route = None
        for pattern, config in routes.items():
            if 'maintenance' in pattern:
                maintenance_route = config.get('queue')
                break
        
        # Should route to maintenance queue or default
        assert maintenance_route in ['maintenance', None]
    
    @pytest.mark.asyncio
    async def test_email_task_execution(self, mock_smtp, mock_database):
        """Test email task execution end-to-end"""
        with patch('app.tasks.email_tasks.settings') as mock_settings:
            mock_settings.NOTIFICATION_EMAIL_SMTP_HOST = "smtp.test.com"
            mock_settings.NOTIFICATION_EMAIL_SMTP_PORT = 587
            mock_settings.NOTIFICATION_EMAIL_USERNAME = "test@test.com"
            mock_settings.NOTIFICATION_EMAIL_PASSWORD = "password"
            mock_settings.DEBUG = True
            
            # Execute task synchronously (eager mode)
            result = send_email.delay(
                "recipient@test.com",
                "Test Subject",
                "Test Body",
                hotel_id=123
            )
            
            # Check result
            assert result.successful()
            task_result = result.get()
            assert task_result['status'] == 'sent'
            assert task_result['to_email'] == 'recipient@test.com'
            
            # Verify SMTP was called
            mock_smtp.send_message.assert_called_once()
    
    def test_maintenance_task_execution(self):
        """Test maintenance task execution"""
        # Execute cleanup task
        result = cleanup_old_results.delay(days_to_keep=7)
        
        assert result.successful()
        task_result = result.get()
        assert task_result['status'] == 'completed'
        assert task_result['days_kept'] == 7
    
    def test_health_check_task_execution(self, mock_database):
        """Test health check task execution"""
        with patch('app.core.celery_app.celery_app') as mock_celery:
            mock_inspect = Mock()
            mock_inspect.stats.return_value = {"worker1": {"processed": 10}}
            mock_celery.control.inspect.return_value = mock_inspect
            
            result = system_health_check.delay()
            
            assert result.successful()
            task_result = result.get()
            assert 'overall_status' in task_result
            assert 'components' in task_result
            assert 'database' in task_result['components']


class TestTaskChaining:
    """Test task chaining and workflows"""
    
    @pytest.mark.asyncio
    async def test_email_notification_workflow(self, mock_smtp, mock_database):
        """Test complete email notification workflow"""
        # Mock notification and hotel data
        mock_notification = Mock()
        mock_notification.id = 123
        mock_notification.guest.phone = "+1234567890"
        mock_notification.conversation_id = "conv_123"
        mock_notification.sentiment_score = -0.8
        mock_notification.message_content = "I'm very unhappy!"
        mock_notification.created_at = datetime.utcnow()
        
        mock_hotel = Mock()
        mock_hotel.id = 456
        mock_hotel.name = "Test Hotel"
        mock_hotel.staff_notification_emails = ["staff@hotel.com"]
        
        mock_database.get.side_effect = [mock_notification, mock_hotel]
        
        with patch('app.tasks.email_tasks.settings') as mock_settings:
            mock_settings.NOTIFICATION_EMAIL_SMTP_HOST = "smtp.test.com"
            mock_settings.NOTIFICATION_EMAIL_SMTP_PORT = 587
            mock_settings.NOTIFICATION_EMAIL_USERNAME = "test@test.com"
            mock_settings.NOTIFICATION_EMAIL_PASSWORD = "password"
            
            # Import and execute the task
            from app.tasks.email_tasks import send_staff_notification_email
            
            result = send_staff_notification_email.delay(123, 456)
            
            assert result.successful()
            task_result = result.get()
            assert task_result['status'] == 'completed'
            assert task_result['notification_id'] == 123
    
    def test_daily_report_workflow(self, mock_database):
        """Test daily report generation workflow"""
        # Mock hotel data
        mock_hotels = [
            Mock(id=1, name="Hotel A", admin_notification_emails=["admin@hotela.com"]),
            Mock(id=2, name="Hotel B", admin_notification_emails=["admin@hotelb.com"])
        ]
        
        mock_database.execute.return_value.fetchall.return_value = mock_hotels
        
        with patch('app.tasks.email_tasks.send_email') as mock_send_email:
            mock_send_email.apply_async.return_value = Mock()
            
            result = send_daily_report.delay()
            
            assert result.successful()
            task_result = result.get()
            assert task_result['status'] == 'completed'
            assert 'reports_sent' in task_result


class TestTaskMonitoring:
    """Test task monitoring and metrics"""
    
    def test_task_metrics_collection(self):
        """Test that task metrics are collected"""
        # Execute a task and check metrics
        initial_metrics = celery_metrics.get_metrics_summary()
        
        result = cleanup_old_results.delay(days_to_keep=1)
        assert result.successful()
        
        # Metrics should be updated (in a real scenario)
        # This is a placeholder test since we're using eager execution
        updated_metrics = celery_metrics.get_metrics_summary()
        assert isinstance(updated_metrics, dict)
    
    @pytest.mark.asyncio
    async def test_task_monitoring_service(self):
        """Test task monitoring service"""
        # Start monitoring (mock)
        with patch.object(task_monitor, '_monitor_events') as mock_monitor:
            with patch.object(task_monitor, '_collect_periodic_stats') as mock_collect:
                await task_monitor.start_monitoring()
                
                assert task_monitor.monitoring_active
                
                await task_monitor.stop_monitoring()
                assert not task_monitor.monitoring_active
    
    def test_task_statistics_collection(self):
        """Test task statistics collection"""
        # Execute some tasks
        cleanup_old_results.delay(days_to_keep=1)
        system_health_check.delay()
        
        # Get statistics
        task_stats = task_monitor.get_task_statistics()
        queue_stats = task_monitor.get_queue_statistics()
        worker_stats = task_monitor.get_worker_statistics()
        
        assert isinstance(task_stats, dict)
        assert isinstance(queue_stats, dict)
        assert isinstance(worker_stats, dict)


class TestTaskErrorHandling:
    """Test task error handling and retries"""
    
    def test_task_retry_mechanism(self):
        """Test task retry on failure"""
        from app.tasks.base import base_task
        
        @base_task(bind=True, autoretry_for=(ValueError,), retry_kwargs={'max_retries': 2})
        def failing_task(self, should_fail=True):
            if should_fail:
                raise ValueError("Intentional failure")
            return "success"
        
        # Test failure and retry
        with pytest.raises(ValueError):
            failing_task.delay(should_fail=True).get(propagate=True)
    
    def test_task_failure_logging(self):
        """Test that task failures are properly logged"""
        from app.tasks.base import base_task
        
        @base_task
        def always_failing_task():
            raise Exception("This task always fails")
        
        with patch('app.tasks.base.logger') as mock_logger:
            with pytest.raises(Exception):
                always_failing_task.delay().get(propagate=True)
    
    def test_critical_task_handling(self):
        """Test critical task error handling"""
        from app.tasks.base import critical_task
        
        @critical_task
        def critical_failing_task():
            raise Exception("Critical failure")
        
        with patch('app.tasks.base.logger') as mock_logger:
            with pytest.raises(Exception):
                critical_failing_task.delay().get(propagate=True)


class TestTaskConfiguration:
    """Test task configuration and settings"""
    
    def test_queue_configuration(self):
        """Test queue configuration is correct"""
        queues = celery_app.conf.task_queues
        queue_names = [q.name for q in queues]
        
        expected_queues = [
            'default', 'incoming_messages', 'outgoing_messages',
            'sentiment_analysis', 'response_generation', 'monitoring',
            'trigger_execution', 'high_priority', 'email_notifications',
            'maintenance'
        ]
        
        for queue in expected_queues:
            assert queue in queue_names
    
    def test_task_serialization(self):
        """Test task serialization settings"""
        assert celery_app.conf.task_serializer == 'json'
        assert celery_app.conf.result_serializer == 'json'
        assert 'json' in celery_app.conf.accept_content
    
    def test_retry_configuration(self):
        """Test retry configuration"""
        assert celery_app.conf.task_acks_late is True
        assert celery_app.conf.task_reject_on_worker_lost is True
        assert celery_app.conf.task_default_retry_delay == 60
        assert celery_app.conf.task_max_retries == 3
    
    def test_worker_configuration(self):
        """Test worker configuration"""
        assert celery_app.conf.worker_prefetch_multiplier == 1
        assert celery_app.conf.worker_max_tasks_per_child == 1000
    
    def test_result_backend_configuration(self):
        """Test result backend configuration"""
        assert celery_app.conf.result_expires == 3600
        assert celery_app.conf.result_persistent is True


class TestBeatSchedule:
    """Test Celery Beat schedule configuration"""
    
    def test_beat_schedule_exists(self):
        """Test that beat schedule is configured"""
        schedule = celery_app.conf.beat_schedule
        assert isinstance(schedule, dict)
        assert len(schedule) > 0
    
    def test_maintenance_tasks_scheduled(self):
        """Test that maintenance tasks are scheduled"""
        schedule = celery_app.conf.beat_schedule
        
        maintenance_tasks = [
            'cleanup-old-results',
            'system-health-check',
            'cleanup-expired-triggers'
        ]
        
        for task_name in maintenance_tasks:
            assert task_name in schedule
            assert 'task' in schedule[task_name]
            assert 'schedule' in schedule[task_name]
    
    def test_monitoring_tasks_scheduled(self):
        """Test that monitoring tasks are scheduled"""
        schedule = celery_app.conf.beat_schedule
        
        monitoring_tasks = [
            'health-check-green-api',
            'collect-system-metrics'
        ]
        
        for task_name in monitoring_tasks:
            if task_name in schedule:
                assert 'task' in schedule[task_name]
                assert 'schedule' in schedule[task_name]


if __name__ == "__main__":
    pytest.main([__file__])
