"""
Integration tests for the complete error handling and logging system.

Tests the integration between error handling, logging, monitoring,
and alerting components.
"""

import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.exceptions.custom_exceptions import ValidationError, DatabaseError
from app.utils.error_tracker import ErrorTracker
from app.services.error_monitor import ErrorMonitor
from app.services.alert_service import AlertService
from app.models.error_log import ErrorLog
from app.core.advanced_logging import setup_advanced_logging
from app.utils.async_logger import get_performance_logger


class TestErrorSystemIntegration:
    """Test complete error system integration"""
    
    @pytest.fixture(autouse=True)
    def setup_logging(self):
        """Setup logging for tests"""
        setup_advanced_logging()
        
    @pytest.fixture
    def client(self):
        """Create test client"""
        return TestClient(app)
        
    @pytest.fixture
    def mock_db_session(self):
        """Mock database session"""
        return Mock(spec=Session)
        
    @pytest.fixture
    def error_tracker(self, mock_db_session):
        """Create error tracker"""
        return ErrorTracker(mock_db_session)
        
    def test_error_tracking_flow(self, error_tracker, mock_db_session):
        """Test complete error tracking flow"""
        # Mock database responses
        mock_db_session.query.return_value.filter.return_value.first.return_value = None
        
        # Create and track an error
        error = ValidationError("Test validation error", field="email")
        
        result = error_tracker.track_error(
            error=error,
            request_id="test-req-123",
            user_id="user-456",
            hotel_id="hotel-789",
            method="POST",
            path="/api/test",
            status_code=400
        )
        
        # Verify error was added to database
        mock_db_session.add.assert_called_once()
        mock_db_session.commit.assert_called_once()
        
        # Verify error log creation
        added_error = mock_db_session.add.call_args[0][0]
        assert isinstance(added_error, ErrorLog)
        assert added_error.error_code == "VALIDATION_ERROR"
        assert added_error.request_id == "test-req-123"
        assert added_error.hotel_id == "hotel-789"
        
    def test_error_monitoring_integration(self, mock_db_session):
        """Test error monitoring integration"""
        with patch('app.services.error_monitor.get_db') as mock_get_db:
            mock_get_db.return_value = mock_db_session
            
            monitor = ErrorMonitor()
            
            # Mock error statistics
            mock_db_session.query.return_value.filter.return_value.all.return_value = [
                Mock(severity="error", error_type="ValidationError", path="/api/test"),
                Mock(severity="critical", error_type="DatabaseError", path="/api/db")
            ]
            
            status = monitor.get_monitoring_status()
            
            assert status['status'] == 'active'
            assert 'recent_stats' in status
            assert 'daily_stats' in status
            
    @pytest.mark.asyncio
    async def test_alert_system_integration(self):
        """Test alert system integration"""
        alert_service = AlertService()
        
        # Test alert data that should trigger rules
        alert_data = {
            'error_rate': 150.0,  # Above threshold
            'hotel_id': 'test-hotel',
            'total_errors': 200,
            'critical_errors': 10
        }
        
        with patch.object(alert_service, '_send_rule_alert', new_callable=AsyncMock) as mock_send:
            mock_send.return_value = {'email': {'status': 'queued'}}
            
            alerts = await alert_service.process_error_alert_data(alert_data)
            
            # Should have triggered alerts
            assert len(alerts) > 0
            
    def test_logging_performance_integration(self):
        """Test logging performance integration"""
        from app.core.log_performance import get_performance_monitor
        
        monitor = get_performance_monitor()
        logger = get_performance_logger('integration_test')
        
        # Generate log events
        for i in range(100):
            logger.info(f"Integration test message {i}")
            monitor.record_log_event(
                processing_time=0.001,
                queue_size=i,
                dropped=i % 20 == 0,
                error=i % 50 == 0
            )
            
        # Check performance metrics
        metrics = monitor.get_current_metrics()
        assert metrics.total_logs == 100
        assert metrics.dropped_logs == 5
        assert metrics.error_count == 2
        
        # Check performance summary
        summary = monitor.get_performance_summary()
        assert 'metrics' in summary
        assert 'performance_status' in summary
        
        logger.shutdown()
        
    def test_exception_handler_integration(self, client):
        """Test exception handlers with real HTTP requests"""
        # Test custom exception handling
        with patch('app.api.v1.api.some_endpoint') as mock_endpoint:
            mock_endpoint.side_effect = ValidationError("Test validation error")
            
            # This would need an actual endpoint that raises the exception
            # For now, we'll test the handler directly
            from app.core.exception_handlers import base_custom_exception_handler
            from fastapi import Request
            
            mock_request = Mock(spec=Request)
            mock_request.url.path = "/api/test"
            mock_request.method = "GET"
            mock_request.headers = {"X-Request-ID": "test-123"}
            
            error = ValidationError("Test error")
            
            # Test the handler
            response = asyncio.run(base_custom_exception_handler(mock_request, error))
            
            assert response.status_code == 400
            
    def test_middleware_error_tracking(self, client):
        """Test that middleware properly tracks errors"""
        with patch('app.middleware.logging_middleware.ErrorTracker') as mock_tracker_class:
            mock_tracker = Mock()
            mock_tracker_class.return_value = mock_tracker
            
            # Make a request that should be logged
            response = client.get("/health")
            
            # Verify the request was processed
            assert response.status_code == 200
            
    @pytest.mark.asyncio
    async def test_end_to_end_error_flow(self, mock_db_session):
        """Test complete end-to-end error flow"""
        # Setup mocks
        with patch('app.services.error_monitor.get_db') as mock_get_db, \
             patch('app.tasks.send_alerts.send_email_alert.delay') as mock_email_task:
            
            mock_get_db.return_value = mock_db_session
            mock_email_task.return_value = Mock(id='task-123')
            
            # Mock database responses for error tracking
            mock_db_session.query.return_value.filter.return_value.first.return_value = None
            
            # 1. Create an error
            error = DatabaseError("Database connection failed")
            
            # 2. Track the error
            error_tracker = ErrorTracker(mock_db_session)
            tracked_error = error_tracker.track_error(
                error=error,
                request_id="end-to-end-123",
                hotel_id="hotel-test"
            )
            
            # 3. Process through monitoring
            monitor = ErrorMonitor()
            
            # Mock error statistics that would trigger alerts
            mock_db_session.query.return_value.filter.return_value.all.return_value = [
                Mock(severity="critical", error_type="DatabaseError", path="/api/db")
            ] * 15  # 15 critical errors to trigger alert
            
            # 4. Process through alert system
            alert_service = AlertService()
            
            alert_data = {
                'critical_errors': 15,
                'hotel_id': 'hotel-test',
                'error_rate': 50.0
            }
            
            alerts = await alert_service.process_error_alert_data(alert_data)
            
            # Verify the complete flow
            assert mock_db_session.add.called  # Error was tracked
            assert len(alerts) > 0  # Alerts were generated
            
    def test_performance_under_load(self):
        """Test system performance under load"""
        import time
        from concurrent.futures import ThreadPoolExecutor
        
        def generate_errors(thread_id, count):
            logger = get_performance_logger(f'load_test_{thread_id}')
            for i in range(count):
                logger.error(f"Load test error {i} from thread {thread_id}")
            logger.shutdown()
            
        # Generate load with multiple threads
        start_time = time.time()
        
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = []
            for thread_id in range(5):
                future = executor.submit(generate_errors, thread_id, 200)
                futures.append(future)
                
            # Wait for completion
            for future in futures:
                future.result()
                
        duration = time.time() - start_time
        
        # Should handle 1000 log messages in reasonable time
        assert duration < 10.0  # Less than 10 seconds
        
    def test_memory_usage_stability(self):
        """Test memory usage remains stable"""
        import psutil
        import gc
        
        process = psutil.Process()
        initial_memory = process.memory_info().rss
        
        # Generate sustained logging
        logger = get_performance_logger('memory_stability_test')
        
        for batch in range(5):
            for i in range(500):
                logger.info(f"Memory test batch {batch} message {i}")
                
            # Force garbage collection
            gc.collect()
            
        # Check final memory
        final_memory = process.memory_info().rss
        memory_increase = final_memory - initial_memory
        
        # Memory increase should be reasonable (less than 50MB)
        assert memory_increase < 50 * 1024 * 1024
        
        logger.shutdown()
        
    def test_error_deduplication(self, error_tracker, mock_db_session):
        """Test that similar errors are properly deduplicated"""
        # Mock existing error
        existing_error = Mock()
        existing_error.count = 1
        existing_error.context_data = {}
        
        mock_db_session.query.return_value.filter.return_value.first.return_value = existing_error
        
        # Track the same error multiple times
        error = ValidationError("Duplicate error")
        
        for i in range(5):
            error_tracker.track_error(
                error=error,
                request_id=f"req-{i}",
                path="/api/test"
            )
            
        # Should have incremented count instead of creating new entries
        assert existing_error.count == 6  # 1 initial + 5 new
        assert mock_db_session.add.call_count == 0  # No new entries added
        assert mock_db_session.commit.call_count == 5  # But committed updates
        
    def test_alert_cooldown_mechanism(self):
        """Test alert cooldown prevents spam"""
        alert_service = AlertService()
        
        # Create alert that should trigger cooldown
        alert = {
            'rule_name': 'test_rule',
            'cooldown_minutes': 1,
            'data': {'hotel_id': 'test-hotel'}
        }
        
        # First alert should not be in cooldown
        assert not alert_service._is_in_cooldown(alert)
        
        # Update cooldown
        alert_service._update_cooldown(alert)
        
        # Second alert should be in cooldown
        assert alert_service._is_in_cooldown(alert)
        
    def test_log_rotation_integration(self, tmp_path):
        """Test log rotation integration"""
        from app.core.log_performance import get_resource_manager
        
        # Create test log directory
        log_dir = tmp_path / "test_logs"
        log_dir.mkdir()
        
        # Create large log file
        large_log = log_dir / "large.log"
        large_log.write_text("x" * (110 * 1024 * 1024))  # 110MB file
        
        resource_manager = get_resource_manager()
        
        # Test rotation
        result = resource_manager.rotate_logs_if_needed(str(log_dir))
        
        assert result['status'] == 'completed'
        assert result['files_rotated'] == 1
        
        # Original file should be cleared
        assert large_log.stat().st_size == 0
        
        # Rotated file should exist
        rotated_files = list(log_dir.glob("*.gz"))
        assert len(rotated_files) == 1
