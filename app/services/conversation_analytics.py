"""
Conversation analytics service for insights and reporting
"""

from typing import Dict, Any, Optional, List, Tuple
from uuid import UUID
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_
import structlog

from app.models.message import Conversation, ConversationState, ConversationStatus, Message
from app.models.hotel import Hotel
from app.models.guest import Guest
from app.core.logging import get_logger

logger = get_logger(__name__)


class ConversationAnalytics:
    """
    Service for generating conversation analytics and insights
    """
    
    def __init__(self, db: Session):
        self.db = db
    
    def get_hotel_dashboard_metrics(
        self,
        hotel_id: UUID,
        days: int = 30
    ) -> Dict[str, Any]:
        """
        Get dashboard metrics for a hotel
        
        Args:
            hotel_id: Hotel ID
            days: Number of days to analyze
            
        Returns:
            Dict with dashboard metrics
        """
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)
        
        # Base query for conversations in date range
        base_query = self.db.query(Conversation).filter(
            Conversation.hotel_id == hotel_id,
            Conversation.created_at >= start_date
        )
        
        # Total conversations
        total_conversations = base_query.count()
        
        # Active conversations
        active_conversations = base_query.filter(
            Conversation.status == ConversationStatus.ACTIVE
        ).count()
        
        # Completed conversations
        completed_conversations = base_query.filter(
            Conversation.status == ConversationStatus.CLOSED
        ).count()
        
        # Escalated conversations
        escalated_conversations = base_query.filter(
            Conversation.status == ConversationStatus.ESCALATED
        ).count()
        
        # Calculate rates
        completion_rate = (completed_conversations / total_conversations * 100) if total_conversations > 0 else 0
        escalation_rate = (escalated_conversations / total_conversations * 100) if total_conversations > 0 else 0
        
        # Average response time (time to first state transition)
        avg_response_time = self._calculate_avg_response_time(hotel_id, start_date, end_date)
        
        # Most common intents
        common_intents = self._get_common_intents(hotel_id, start_date, end_date)
        
        # State distribution
        state_distribution = self._get_state_distribution(hotel_id, start_date, end_date)
        
        # Daily conversation trends
        daily_trends = self._get_daily_conversation_trends(hotel_id, start_date, end_date)
        
        return {
            'period': {
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat(),
                'days': days
            },
            'overview': {
                'total_conversations': total_conversations,
                'active_conversations': active_conversations,
                'completed_conversations': completed_conversations,
                'escalated_conversations': escalated_conversations,
                'completion_rate': round(completion_rate, 2),
                'escalation_rate': round(escalation_rate, 2)
            },
            'performance': {
                'avg_response_time_minutes': round(avg_response_time, 2),
                'state_distribution': state_distribution,
                'common_intents': common_intents
            },
            'trends': {
                'daily_conversations': daily_trends
            }
        }
    
    def get_conversation_flow_analysis(
        self,
        hotel_id: UUID,
        days: int = 30
    ) -> Dict[str, Any]:
        """
        Analyze conversation flows and state transitions
        
        Args:
            hotel_id: Hotel ID
            days: Number of days to analyze
            
        Returns:
            Dict with flow analysis
        """
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)
        
        conversations = self.db.query(Conversation).filter(
            Conversation.hotel_id == hotel_id,
            Conversation.created_at >= start_date
        ).all()
        
        # Analyze state transitions
        state_transitions = {}
        completion_paths = []
        escalation_paths = []
        
        for conversation in conversations:
            # Track final outcomes
            if conversation.status == ConversationStatus.CLOSED:
                completion_paths.append(conversation.current_state.value)
            elif conversation.status == ConversationStatus.ESCALATED:
                escalation_paths.append(conversation.current_state.value)
        
        # Most common completion states
        completion_state_counts = {}
        for state in completion_paths:
            completion_state_counts[state] = completion_state_counts.get(state, 0) + 1
        
        # Most common escalation states
        escalation_state_counts = {}
        for state in escalation_paths:
            escalation_state_counts[state] = escalation_state_counts.get(state, 0) + 1
        
        return {
            'period': {
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat(),
                'days': days
            },
            'flow_analysis': {
                'total_conversations_analyzed': len(conversations),
                'completion_paths': completion_state_counts,
                'escalation_paths': escalation_state_counts,
                'most_common_completion_state': max(completion_state_counts.keys(), key=completion_state_counts.get) if completion_state_counts else None,
                'most_common_escalation_state': max(escalation_state_counts.keys(), key=escalation_state_counts.get) if escalation_state_counts else None
            }
        }
    
    def get_guest_satisfaction_metrics(
        self,
        hotel_id: UUID,
        days: int = 30
    ) -> Dict[str, Any]:
        """
        Analyze guest satisfaction based on conversation outcomes
        
        Args:
            hotel_id: Hotel ID
            days: Number of days to analyze
            
        Returns:
            Dict with satisfaction metrics
        """
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)
        
        conversations = self.db.query(Conversation).filter(
            Conversation.hotel_id == hotel_id,
            Conversation.created_at >= start_date
        ).all()
        
        # Analyze sentiment trends
        positive_outcomes = 0
        negative_outcomes = 0
        neutral_outcomes = 0
        
        for conversation in conversations:
            # Analyze final sentiment from context
            if conversation.context:
                last_sentiment = conversation.context.get('last_sentiment', 0)
                if last_sentiment > 0.2:
                    positive_outcomes += 1
                elif last_sentiment < -0.2:
                    negative_outcomes += 1
                else:
                    neutral_outcomes += 1
        
        total_analyzed = positive_outcomes + negative_outcomes + neutral_outcomes
        
        # Calculate satisfaction score
        satisfaction_score = 0
        if total_analyzed > 0:
            satisfaction_score = ((positive_outcomes * 100) + (neutral_outcomes * 50)) / (total_analyzed * 100) * 100
        
        return {
            'period': {
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat(),
                'days': days
            },
            'satisfaction_metrics': {
                'satisfaction_score': round(satisfaction_score, 2),
                'positive_outcomes': positive_outcomes,
                'negative_outcomes': negative_outcomes,
                'neutral_outcomes': neutral_outcomes,
                'total_analyzed': total_analyzed,
                'sentiment_distribution': {
                    'positive': round((positive_outcomes / total_analyzed * 100), 2) if total_analyzed > 0 else 0,
                    'negative': round((negative_outcomes / total_analyzed * 100), 2) if total_analyzed > 0 else 0,
                    'neutral': round((neutral_outcomes / total_analyzed * 100), 2) if total_analyzed > 0 else 0
                }
            }
        }
    
    def get_performance_insights(
        self,
        hotel_id: UUID,
        days: int = 30
    ) -> Dict[str, Any]:
        """
        Get performance insights and recommendations
        
        Args:
            hotel_id: Hotel ID
            days: Number of days to analyze
            
        Returns:
            Dict with performance insights
        """
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)
        
        conversations = self.db.query(Conversation).filter(
            Conversation.hotel_id == hotel_id,
            Conversation.created_at >= start_date
        ).all()
        
        insights = []
        recommendations = []
        
        if not conversations:
            return {
                'insights': ['No conversations found in the specified period'],
                'recommendations': ['Start engaging with guests to gather data'],
                'performance_score': 0
            }
        
        # Analyze escalation rate
        escalated_count = len([c for c in conversations if c.status == ConversationStatus.ESCALATED])
        escalation_rate = escalated_count / len(conversations) * 100
        
        if escalation_rate > 20:
            insights.append(f"High escalation rate: {escalation_rate:.1f}%")
            recommendations.append("Review escalation triggers and improve automated responses")
        elif escalation_rate < 5:
            insights.append(f"Low escalation rate: {escalation_rate:.1f}%")
            recommendations.append("Consider if escalation thresholds are appropriate")
        
        # Analyze completion rate
        completed_count = len([c for c in conversations if c.status == ConversationStatus.CLOSED])
        completion_rate = completed_count / len(conversations) * 100
        
        if completion_rate < 60:
            insights.append(f"Low completion rate: {completion_rate:.1f}%")
            recommendations.append("Review conversation flows and improve resolution processes")
        elif completion_rate > 80:
            insights.append(f"High completion rate: {completion_rate:.1f}%")
            recommendations.append("Excellent conversation resolution performance")
        
        # Analyze response times
        avg_response_time = self._calculate_avg_response_time(hotel_id, start_date, end_date)
        
        if avg_response_time > 60:
            insights.append(f"Slow response time: {avg_response_time:.1f} minutes")
            recommendations.append("Optimize automated responses and staff notification systems")
        elif avg_response_time < 5:
            insights.append(f"Fast response time: {avg_response_time:.1f} minutes")
            recommendations.append("Excellent response time performance")
        
        # Calculate overall performance score
        performance_score = self._calculate_performance_score(
            escalation_rate, completion_rate, avg_response_time
        )
        
        return {
            'period': {
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat(),
                'days': days
            },
            'insights': insights,
            'recommendations': recommendations,
            'performance_score': round(performance_score, 2),
            'metrics': {
                'escalation_rate': round(escalation_rate, 2),
                'completion_rate': round(completion_rate, 2),
                'avg_response_time_minutes': round(avg_response_time, 2)
            }
        }
    
    def _calculate_avg_response_time(
        self,
        hotel_id: UUID,
        start_date: datetime,
        end_date: datetime
    ) -> float:
        """Calculate average response time in minutes"""
        
        conversations = self.db.query(Conversation).filter(
            Conversation.hotel_id == hotel_id,
            Conversation.created_at >= start_date,
            Conversation.created_at <= end_date
        ).all()
        
        response_times = []
        
        for conversation in conversations:
            # Calculate time from creation to first state change
            if conversation.last_message_at and conversation.created_at:
                response_time = (conversation.last_message_at - conversation.created_at).total_seconds() / 60
                response_times.append(response_time)
        
        return sum(response_times) / len(response_times) if response_times else 0
    
    def _get_common_intents(
        self,
        hotel_id: UUID,
        start_date: datetime,
        end_date: datetime,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """Get most common intents"""
        
        conversations = self.db.query(Conversation).filter(
            Conversation.hotel_id == hotel_id,
            Conversation.created_at >= start_date,
            Conversation.created_at <= end_date
        ).all()
        
        intent_counts = {}
        
        for conversation in conversations:
            if conversation.context and 'intent_history' in conversation.context:
                for intent_entry in conversation.context['intent_history']:
                    intent = intent_entry.get('intent')
                    if intent:
                        intent_counts[intent] = intent_counts.get(intent, 0) + 1
        
        # Sort by count and return top intents
        sorted_intents = sorted(intent_counts.items(), key=lambda x: x[1], reverse=True)
        
        return [
            {'intent': intent, 'count': count}
            for intent, count in sorted_intents[:limit]
        ]
    
    def _get_state_distribution(
        self,
        hotel_id: UUID,
        start_date: datetime,
        end_date: datetime
    ) -> Dict[str, int]:
        """Get distribution of conversation states"""
        
        conversations = self.db.query(Conversation).filter(
            Conversation.hotel_id == hotel_id,
            Conversation.created_at >= start_date,
            Conversation.created_at <= end_date
        ).all()
        
        state_counts = {}
        
        for conversation in conversations:
            state = conversation.current_state.value
            state_counts[state] = state_counts.get(state, 0) + 1
        
        return state_counts
    
    def _get_daily_conversation_trends(
        self,
        hotel_id: UUID,
        start_date: datetime,
        end_date: datetime
    ) -> List[Dict[str, Any]]:
        """Get daily conversation trends"""
        
        # Query conversations grouped by date
        daily_counts = self.db.query(
            func.date(Conversation.created_at).label('date'),
            func.count(Conversation.id).label('count')
        ).filter(
            Conversation.hotel_id == hotel_id,
            Conversation.created_at >= start_date,
            Conversation.created_at <= end_date
        ).group_by(
            func.date(Conversation.created_at)
        ).all()
        
        return [
            {
                'date': result.date.isoformat(),
                'conversation_count': result.count
            }
            for result in daily_counts
        ]
    
    def _calculate_performance_score(
        self,
        escalation_rate: float,
        completion_rate: float,
        avg_response_time: float
    ) -> float:
        """Calculate overall performance score (0-100)"""
        
        # Escalation score (lower is better)
        escalation_score = max(0, 100 - (escalation_rate * 2))
        
        # Completion score (higher is better)
        completion_score = completion_rate
        
        # Response time score (lower is better, optimal around 5-15 minutes)
        if avg_response_time <= 15:
            response_score = 100 - (avg_response_time * 2)
        else:
            response_score = max(0, 100 - (avg_response_time * 3))
        
        # Weighted average
        performance_score = (
            escalation_score * 0.3 +
            completion_score * 0.4 +
            response_score * 0.3
        )
        
        return max(0, min(100, performance_score))


# Export analytics service
__all__ = ['ConversationAnalytics']
