"""
Integration tests for sentiment analysis system
"""

import pytest
import uuid
import asyncio
from datetime import datetime, timedelta
from unittest.mock import patch, Mock

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.database import get_db
from app.models.message import Message, MessageType
from app.models.guest import Guest
from app.models.hotel import Hotel
from app.models.sentiment import SentimentAnalysis
from app.models.staff_alert import StaffAlert, AlertType, AlertStatus
from app.services.realtime_sentiment import RealtimeSentimentAnalyzer
from app.tasks.analyze_message_sentiment import analyze_message_sentiment_realtime_task
from app.schemas.deepseek import SentimentAnalysisResult, SentimentType


class TestSentimentAnalysisIntegration:
    """Integration tests for sentiment analysis workflow"""
    
    @pytest.fixture
    def client(self):
        """Create test client"""
        return TestClient(app)
    
    @pytest.fixture
    def db_session(self):
        """Create test database session"""
        # This would typically use a test database
        # For now, we'll mock it
        return Mock(spec=Session)
    
    @pytest.fixture
    def test_hotel(self, db_session):
        """Create test hotel"""
        hotel = Hotel(
            id=uuid.uuid4(),
            name="Test Hotel",
            email="test@hotel.com",
            phone="+1234567890",
            address="123 Test St",
            is_active=True
        )
        return hotel
    
    @pytest.fixture
    def test_guest(self, db_session, test_hotel):
        """Create test guest"""
        guest = Guest(
            id=uuid.uuid4(),
            hotel_id=test_hotel.id,
            phone_number="+1987654321",
            name="John Doe",
            email="john@example.com",
            is_active=True
        )
        return guest
    
    @pytest.fixture
    def negative_message(self, test_hotel, test_guest):
        """Create negative sentiment message"""
        return Message(
            id=uuid.uuid4(),
            hotel_id=test_hotel.id,
            guest_id=test_guest.id,
            conversation_id=uuid.uuid4(),
            content="The room was dirty and the staff was rude. This is unacceptable!",
            message_type=MessageType.TEXT,
            direction="inbound",
            created_at=datetime.utcnow()
        )
    
    @pytest.fixture
    def positive_message(self, test_hotel, test_guest):
        """Create positive sentiment message"""
        return Message(
            id=uuid.uuid4(),
            hotel_id=test_hotel.id,
            guest_id=test_guest.id,
            conversation_id=uuid.uuid4(),
            content="The hotel is amazing! Excellent service and beautiful rooms.",
            message_type=MessageType.TEXT,
            direction="inbound",
            created_at=datetime.utcnow()
        )
    
    @pytest.mark.asyncio
    async def test_end_to_end_negative_sentiment_workflow(
        self,
        db_session,
        negative_message,
        test_hotel,
        test_guest
    ):
        """Test complete workflow for negative sentiment detection"""
        # Mock database queries
        db_session.query.return_value.filter.return_value.first.return_value = negative_message
        db_session.query.return_value.filter.return_value.count.return_value = 1
        db_session.add = Mock()
        db_session.commit = Mock()
        db_session.refresh = Mock()
        
        # Create realtime analyzer
        analyzer = RealtimeSentimentAnalyzer(db_session)
        
        # Mock sentiment analysis result
        negative_result = SentimentAnalysisResult(
            sentiment=SentimentType.NEGATIVE,
            score=-0.7,
            confidence=0.85,
            requires_attention=True,
            reason="Guest expressed strong dissatisfaction with room cleanliness and staff behavior",
            keywords=["dirty", "rude", "unacceptable"]
        )
        
        with patch.object(analyzer.sentiment_analyzer, 'analyze_message_sentiment', return_value=negative_result):
            with patch.object(analyzer, 'trigger_alerts_if_needed') as mock_trigger_alerts:
                
                # Execute analysis
                result = await analyzer.analyze_message(
                    message=negative_message,
                    conversation_id=str(negative_message.conversation_id),
                    correlation_id="integration-test-001"
                )
                
                # Verify sentiment analysis
                assert result.sentiment == SentimentType.NEGATIVE
                assert result.score == -0.7
                assert result.requires_attention is True
                assert "dirty" in result.keywords
                
                # Verify alert triggering was called
                mock_trigger_alerts.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_sentiment_analysis_with_alert_creation(
        self,
        db_session,
        negative_message
    ):
        """Test sentiment analysis that creates staff alert"""
        # Mock database operations
        db_session.query.return_value.filter.return_value.first.return_value = negative_message
        db_session.query.return_value.filter.return_value.count.return_value = 2  # Recent negative count
        db_session.add = Mock()
        db_session.commit = Mock()
        db_session.refresh = Mock()
        
        # Mock alert creation
        mock_alert = StaffAlert(
            id=uuid.uuid4(),
            hotel_id=negative_message.hotel_id,
            alert_type=AlertType.NEGATIVE_SENTIMENT.value,
            priority="high",
            status=AlertStatus.PENDING.value,
            message_id=negative_message.id,
            guest_id=negative_message.guest_id,
            title="Negative sentiment detected",
            description="Guest expressed dissatisfaction",
            sentiment_score=-0.7,
            urgency_level=4
        )
        
        analyzer = RealtimeSentimentAnalyzer(db_session)
        
        # Mock sentiment analysis
        negative_result = SentimentAnalysisResult(
            sentiment=SentimentType.NEGATIVE,
            score=-0.7,
            confidence=0.85,
            requires_attention=True,
            reason="Negative sentiment detected",
            keywords=["dirty", "rude"]
        )
        
        with patch.object(analyzer.sentiment_analyzer, 'analyze_message_sentiment', return_value=negative_result):
            with patch('app.tasks.send_staff_alert.send_staff_alert_task.delay') as mock_task:
                
                # Execute analysis
                result = await analyzer.analyze_message(
                    message=negative_message,
                    conversation_id=str(negative_message.conversation_id),
                    correlation_id="integration-test-002"
                )
                
                # Verify sentiment analysis
                assert result.score == -0.7
                assert result.requires_attention is True
                
                # Verify alert task was triggered
                mock_task.assert_called_once()
                call_args = mock_task.call_args[1]
                assert call_args["message_id"] == str(negative_message.id)
                assert call_args["sentiment_score"] == -0.7
    
    @pytest.mark.asyncio
    async def test_positive_sentiment_no_alert(
        self,
        db_session,
        positive_message
    ):
        """Test that positive sentiment doesn't trigger alerts"""
        # Mock database operations
        db_session.query.return_value.filter.return_value.first.return_value = positive_message
        db_session.query.return_value.filter.return_value.count.return_value = 0
        
        analyzer = RealtimeSentimentAnalyzer(db_session)
        
        # Mock positive sentiment analysis
        positive_result = SentimentAnalysisResult(
            sentiment=SentimentType.POSITIVE,
            score=0.8,
            confidence=0.9,
            requires_attention=False,
            reason="Guest expressed satisfaction",
            keywords=["amazing", "excellent", "beautiful"]
        )
        
        with patch.object(analyzer.sentiment_analyzer, 'analyze_message_sentiment', return_value=positive_result):
            with patch('app.tasks.send_staff_alert.send_staff_alert_task.delay') as mock_task:
                
                # Execute analysis
                result = await analyzer.analyze_message(
                    message=positive_message,
                    conversation_id=str(positive_message.conversation_id),
                    correlation_id="integration-test-003"
                )
                
                # Verify sentiment analysis
                assert result.sentiment == SentimentType.POSITIVE
                assert result.score == 0.8
                assert result.requires_attention is False
                
                # Verify no alert was triggered
                mock_task.assert_not_called()
    
    def test_sentiment_analytics_api_overview(self, client, test_hotel):
        """Test sentiment analytics API overview endpoint"""
        hotel_id = str(test_hotel.id)
        
        # Mock database queries for analytics
        with patch('app.api.v1.endpoints.sentiment_analytics.get_sentiment_analytics_service') as mock_service:
            from app.schemas.sentiment_analytics import SentimentOverviewResponse
            
            mock_overview = SentimentOverviewResponse(
                hotel_id=hotel_id,
                period="7d",
                total_messages=100,
                average_sentiment_score=0.2,
                positive_count=60,
                negative_count=25,
                neutral_count=15,
                requires_attention_count=5,
                alerts_triggered=8,
                response_rate=87.5,
                average_response_time_minutes=22.3
            )
            
            mock_service.return_value.get_sentiment_overview.return_value = mock_overview
            
            # Mock tenant context
            with patch('app.api.v1.endpoints.sentiment_analytics.require_tenant_context'):
                with patch('app.api.v1.endpoints.sentiment_analytics.get_current_tenant_id', return_value="test-tenant"):
                    
                    response = client.get(f"/api/v1/sentiment-analytics/overview?hotel_id={hotel_id}")
                    
                    assert response.status_code == 200
                    data = response.json()
                    assert data["hotel_id"] == hotel_id
                    assert data["total_messages"] == 100
                    assert data["average_sentiment_score"] == 0.2
                    assert data["alerts_triggered"] == 8
    
    def test_sentiment_analytics_api_trends(self, client, test_hotel):
        """Test sentiment analytics API trends endpoint"""
        hotel_id = str(test_hotel.id)
        
        with patch('app.api.v1.endpoints.sentiment_analytics.get_sentiment_analytics_service') as mock_service:
            from app.schemas.sentiment_analytics import SentimentTrendsResponse, SentimentDataPoint
            
            mock_trends = SentimentTrendsResponse(
                hotel_id=hotel_id,
                period_days=7,
                granularity="daily",
                data_points=[
                    SentimentDataPoint(
                        timestamp=datetime.utcnow() - timedelta(days=1),
                        average_score=0.1,
                        message_count=15,
                        positive_count=8,
                        negative_count=4,
                        neutral_count=3
                    )
                ],
                trend_direction="stable"
            )
            
            mock_service.return_value.get_sentiment_trends.return_value = mock_trends
            
            with patch('app.api.v1.endpoints.sentiment_analytics.require_tenant_context'):
                with patch('app.api.v1.endpoints.sentiment_analytics.get_current_tenant_id', return_value="test-tenant"):
                    
                    response = client.get(f"/api/v1/sentiment-analytics/trends?hotel_id={hotel_id}&days=7")
                    
                    assert response.status_code == 200
                    data = response.json()
                    assert data["hotel_id"] == hotel_id
                    assert data["period_days"] == 7
                    assert data["trend_direction"] == "stable"
                    assert len(data["data_points"]) == 1
    
    @pytest.mark.asyncio
    async def test_celery_task_integration(self, negative_message):
        """Test Celery task integration for sentiment analysis"""
        message_id = str(negative_message.id)
        conversation_id = str(negative_message.conversation_id)
        
        # Mock database and services
        with patch('app.tasks.analyze_message_sentiment.get_db') as mock_get_db:
            mock_db = Mock()
            mock_get_db.return_value.__next__.return_value = mock_db
            mock_db.query.return_value.filter.return_value.first.return_value = negative_message
            
            with patch('app.tasks.analyze_message_sentiment.get_realtime_sentiment_analyzer') as mock_analyzer:
                mock_analyzer_instance = Mock()
                mock_analyzer.return_value = mock_analyzer_instance
                
                # Mock async analysis method
                async def mock_analyze_message(*args, **kwargs):
                    return SentimentAnalysisResult(
                        sentiment=SentimentType.NEGATIVE,
                        score=-0.6,
                        confidence=0.8,
                        requires_attention=True,
                        reason="Negative sentiment",
                        keywords=["dirty"]
                    )
                
                mock_analyzer_instance.analyze_message = mock_analyze_message
                
                # Execute task
                result = analyze_message_sentiment_realtime_task(
                    message_id=message_id,
                    conversation_id=conversation_id,
                    correlation_id="celery-test-001"
                )
                
                # Verify task completed
                assert result is None  # Task doesn't return value on success
                mock_analyzer.assert_called_once()
    
    def test_threshold_configuration_integration(self, db_session, test_hotel):
        """Test threshold configuration integration"""
        from app.utils.threshold_manager import ThresholdManager
        
        # Mock database operations
        db_session.query.return_value.filter.return_value.first.return_value = None
        
        threshold_manager = ThresholdManager(db_session)
        
        # Test getting default thresholds
        thresholds = asyncio.run(threshold_manager.get_hotel_thresholds(str(test_hotel.id)))
        
        assert "negative_sentiment_threshold" in thresholds
        assert "critical_sentiment_threshold" in thresholds
        assert thresholds["negative_sentiment_threshold"] == -0.3
        assert thresholds["critical_sentiment_threshold"] == -0.8
    
    def test_rules_engine_integration(self, db_session, negative_message):
        """Test sentiment rules engine integration"""
        from app.services.sentiment_rules import SentimentRulesEngine
        from app.schemas.deepseek import SentimentAnalysisResult, SentimentType
        
        # Mock database operations
        db_session.query.return_value.filter.return_value.count.return_value = 1
        
        rules_engine = SentimentRulesEngine(db_session)
        
        negative_result = SentimentAnalysisResult(
            sentiment=SentimentType.NEGATIVE,
            score=-0.7,
            confidence=0.85,
            requires_attention=True,
            reason="Negative sentiment",
            keywords=["dirty", "rude"]
        )
        
        # Test rule evaluation
        should_alert = asyncio.run(rules_engine.should_alert_staff(
            sentiment=negative_result,
            message=negative_message,
            hotel_id=str(negative_message.hotel_id)
        ))
        
        assert should_alert is True
        
        # Test escalation level
        escalation_level = asyncio.run(rules_engine.get_escalation_level(
            sentiment=negative_result,
            message=negative_message,
            hotel_id=str(negative_message.hotel_id)
        ))
        
        assert escalation_level.value in ["supervisor", "manager"]
