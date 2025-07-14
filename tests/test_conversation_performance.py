"""
Performance tests for conversation handler system
"""

import pytest
import asyncio
import time
from unittest.mock import Mock, AsyncMock
from uuid import uuid4
from datetime import datetime
import statistics

from app.services.message_handler import MessageHandler
from app.services.conversation_state_machine import ConversationStateMachine
from app.services.escalation_service import EscalationService
from app.utils.intent_classifier import IntentClassifier, MessageIntent, IntentClassificationResult
from app.models.message import Message, Conversation, ConversationState, ConversationStatus, MessageType


class TestConversationPerformance:
    """Performance tests for conversation handler components"""
    
    @pytest.fixture
    def mock_db(self):
        """Create mock database session"""
        db = Mock()
        db.query = Mock()
        db.add = Mock()
        db.commit = Mock()
        db.rollback = Mock()
        db.flush = Mock()
        return db
    
    @pytest.fixture
    def mock_deepseek_client(self):
        """Create mock DeepSeek client with fast responses"""
        client = Mock()
        client.generate_response = AsyncMock()
        
        # Fast mock response
        client.generate_response.return_value = {
            'content': '{"intent": "general_question", "confidence": 0.8, "sentiment_score": 0.1, "urgency_level": 2, "reasoning": "Quick response"}'
        }
        
        return client
    
    @pytest.fixture
    def sample_conversation(self):
        """Create sample conversation for testing"""
        return Conversation(
            id=uuid4(),
            hotel_id=uuid4(),
            guest_id=uuid4(),
            status=ConversationStatus.ACTIVE,
            current_state=ConversationState.GREETING,
            context={}
        )
    
    @pytest.fixture
    def sample_message(self, sample_conversation):
        """Create sample message for testing"""
        return Message(
            id=uuid4(),
            conversation_id=sample_conversation.id,
            hotel_id=sample_conversation.hotel_id,
            guest_id=sample_conversation.guest_id,
            message_type=MessageType.TEXT,
            content="Hello, I need help with my room",
            direction="inbound"
        )
    
    @pytest.mark.asyncio
    async def test_intent_classification_performance(self, mock_deepseek_client):
        """Test intent classification performance"""
        classifier = IntentClassifier(mock_deepseek_client)
        
        test_messages = [
            "Hello, I need help",
            "This room is terrible!",
            "Can I book a room?",
            "Emergency! Fire in room!",
            "Thank you for your help",
            "The wifi is not working",
            "I want to cancel my booking",
            "What time is checkout?",
            "The air conditioning is broken",
            "This service is excellent"
        ]
        
        # Measure classification time
        start_time = time.time()
        
        tasks = [
            classifier.classify_intent(message)
            for message in test_messages
        ]
        
        results = await asyncio.gather(*tasks)
        
        end_time = time.time()
        total_time = end_time - start_time
        avg_time_per_classification = total_time / len(test_messages)
        
        # Performance assertions
        assert total_time < 5.0  # Should complete within 5 seconds
        assert avg_time_per_classification < 0.5  # Each classification under 500ms
        
        # Verify all classifications succeeded
        for result in results:
            assert isinstance(result, IntentClassificationResult)
            assert result.intent is not None
            assert result.confidence > 0
        
        print(f"Classification performance: {avg_time_per_classification:.3f}s avg per message")
    
    @pytest.mark.asyncio
    async def test_state_machine_transition_performance(self, sample_conversation):
        """Test state machine transition performance"""
        state_machine = ConversationStateMachine()
        
        # Test multiple rapid transitions
        transitions = [
            (ConversationState.GREETING, ConversationState.COLLECTING_INFO),
            (ConversationState.COLLECTING_INFO, ConversationState.PROCESSING_REQUEST),
            (ConversationState.PROCESSING_REQUEST, ConversationState.WAITING_RESPONSE),
            (ConversationState.WAITING_RESPONSE, ConversationState.COMPLETED)
        ]
        
        transition_times = []
        
        for from_state, to_state in transitions:
            sample_conversation.current_state = from_state
            
            start_time = time.time()
            
            result = await state_machine.transition_to(
                conversation=sample_conversation,
                target_state=to_state,
                context={'test': 'data'},
                reason="Performance test"
            )
            
            end_time = time.time()
            transition_time = end_time - start_time
            transition_times.append(transition_time)
            
            assert result.success is True
            assert result.new_state == to_state
        
        avg_transition_time = statistics.mean(transition_times)
        max_transition_time = max(transition_times)
        
        # Performance assertions
        assert avg_transition_time < 0.1  # Average under 100ms
        assert max_transition_time < 0.2  # Max under 200ms
        
        print(f"State transition performance: {avg_transition_time:.3f}s avg, {max_transition_time:.3f}s max")
    
    @pytest.mark.asyncio
    async def test_message_handler_throughput(self, mock_db, mock_deepseek_client, sample_conversation):
        """Test message handler throughput"""
        message_handler = MessageHandler(mock_db, mock_deepseek_client)
        
        # Mock database responses
        mock_db.query.return_value.filter.return_value.first.return_value = sample_conversation
        mock_db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []
        
        # Create test messages
        messages = [
            Message(
                id=uuid4(),
                conversation_id=sample_conversation.id,
                hotel_id=sample_conversation.hotel_id,
                guest_id=sample_conversation.guest_id,
                message_type=MessageType.TEXT,
                content=f"Test message {i}",
                direction="inbound"
            )
            for i in range(50)  # 50 messages
        ]
        
        # Measure processing time
        start_time = time.time()
        
        tasks = [
            message_handler.handle_incoming_message(
                hotel_id=sample_conversation.hotel_id,
                guest_id=sample_conversation.guest_id,
                message=message
            )
            for message in messages
        ]
        
        results = await asyncio.gather(*tasks)
        
        end_time = time.time()
        total_time = end_time - start_time
        messages_per_second = len(messages) / total_time
        
        # Performance assertions
        assert messages_per_second > 10  # At least 10 messages per second
        assert total_time < 10  # Complete within 10 seconds
        
        # Verify all messages processed successfully
        successful_results = [r for r in results if r.success]
        assert len(successful_results) == len(messages)
        
        print(f"Message handler throughput: {messages_per_second:.1f} messages/second")
    
    @pytest.mark.asyncio
    async def test_concurrent_conversation_handling(self, mock_db, mock_deepseek_client):
        """Test handling multiple conversations concurrently"""
        message_handler = MessageHandler(mock_db, mock_deepseek_client)
        
        # Create multiple conversations
        conversations = [
            Conversation(
                id=uuid4(),
                hotel_id=uuid4(),
                guest_id=uuid4(),
                status=ConversationStatus.ACTIVE,
                current_state=ConversationState.GREETING,
                context={}
            )
            for _ in range(20)  # 20 concurrent conversations
        ]
        
        # Mock database to return appropriate conversation
        def mock_db_query(*args):
            query_mock = Mock()
            query_mock.filter.return_value.first.return_value = conversations[0]  # Return first conversation
            query_mock.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []
            return query_mock
        
        mock_db.query.side_effect = mock_db_query
        
        # Create messages for each conversation
        messages = [
            Message(
                id=uuid4(),
                conversation_id=conv.id,
                hotel_id=conv.hotel_id,
                guest_id=conv.guest_id,
                message_type=MessageType.TEXT,
                content=f"Message for conversation {i}",
                direction="inbound"
            )
            for i, conv in enumerate(conversations)
        ]
        
        # Measure concurrent processing time
        start_time = time.time()
        
        tasks = [
            message_handler.handle_incoming_message(
                hotel_id=conv.hotel_id,
                guest_id=conv.guest_id,
                message=msg
            )
            for conv, msg in zip(conversations, messages)
        ]
        
        results = await asyncio.gather(*tasks)
        
        end_time = time.time()
        total_time = end_time - start_time
        conversations_per_second = len(conversations) / total_time
        
        # Performance assertions
        assert conversations_per_second > 5  # At least 5 conversations per second
        assert total_time < 10  # Complete within 10 seconds
        
        # Verify all conversations processed successfully
        successful_results = [r for r in results if r.success]
        assert len(successful_results) == len(conversations)
        
        print(f"Concurrent conversation handling: {conversations_per_second:.1f} conversations/second")
    
    @pytest.mark.asyncio
    async def test_escalation_service_performance(self, mock_db):
        """Test escalation service performance"""
        escalation_service = EscalationService(mock_db)
        
        # Create test conversations
        conversations = [
            Conversation(
                id=uuid4(),
                hotel_id=uuid4(),
                guest_id=uuid4(),
                status=ConversationStatus.ACTIVE,
                current_state=ConversationState.COLLECTING_INFO,
                context={'repeat_count': i % 5}  # Vary repeat count
            )
            for i in range(100)  # 100 conversations
        ]
        
        test_contexts = [
            {
                'sentiment_score': -0.8,
                'urgency_level': 4,
                'message_content': 'This is terrible!'
            },
            {
                'sentiment_score': 0.2,
                'urgency_level': 2,
                'message_content': 'Can you help me?'
            },
            {
                'sentiment_score': -0.3,
                'urgency_level': 1,
                'message_content': 'Not great service'
            }
        ]
        
        # Measure escalation evaluation time
        start_time = time.time()
        
        tasks = [
            escalation_service.evaluate_escalation_triggers(
                conversation=conv,
                message_content=test_contexts[i % len(test_contexts)]['message_content'],
                context=test_contexts[i % len(test_contexts)]
            )
            for i, conv in enumerate(conversations)
        ]
        
        results = await asyncio.gather(*tasks)
        
        end_time = time.time()
        total_time = end_time - start_time
        evaluations_per_second = len(conversations) / total_time
        
        # Performance assertions
        assert evaluations_per_second > 50  # At least 50 evaluations per second
        assert total_time < 5  # Complete within 5 seconds
        
        # Verify all evaluations completed
        assert len(results) == len(conversations)
        
        print(f"Escalation evaluation performance: {evaluations_per_second:.1f} evaluations/second")
    
    @pytest.mark.asyncio
    async def test_memory_operations_performance(self):
        """Test conversation memory operations performance"""
        from unittest.mock import patch
        
        # Mock Redis for performance testing
        with patch('app.services.conversation_memory.redis') as mock_redis:
            mock_redis_client = Mock()
            mock_redis_client.setex.return_value = True
            mock_redis_client.get.return_value = '{"test": "data"}'
            mock_redis_client.keys.return_value = [f"key_{i}" for i in range(10)]
            mock_redis_client.delete.return_value = 1
            mock_redis_client.ping.return_value = True
            mock_redis.from_url.return_value = mock_redis_client
            
            from app.services.conversation_memory import ConversationMemory
            memory_service = ConversationMemory()
            
            conversation_ids = [uuid4() for _ in range(100)]
            
            # Test store operations
            start_time = time.time()
            
            store_tasks = [
                memory_service.store_context(
                    conversation_id=conv_id,
                    key='test_key',
                    value={'data': f'value_{i}'}
                )
                for i, conv_id in enumerate(conversation_ids)
            ]
            
            store_results = await asyncio.gather(*store_tasks)
            
            store_time = time.time() - start_time
            store_ops_per_second = len(conversation_ids) / store_time
            
            # Test get operations
            start_time = time.time()
            
            get_tasks = [
                memory_service.get_context(
                    conversation_id=conv_id,
                    key='test_key'
                )
                for conv_id in conversation_ids
            ]
            
            get_results = await asyncio.gather(*get_tasks)
            
            get_time = time.time() - start_time
            get_ops_per_second = len(conversation_ids) / get_time
            
            # Performance assertions
            assert store_ops_per_second > 100  # At least 100 store ops per second
            assert get_ops_per_second > 100  # At least 100 get ops per second
            assert all(store_results)  # All store operations succeeded
            
            print(f"Memory performance: {store_ops_per_second:.1f} stores/sec, {get_ops_per_second:.1f} gets/sec")
    
    @pytest.mark.asyncio
    async def test_end_to_end_conversation_performance(self, mock_db, mock_deepseek_client):
        """Test end-to-end conversation performance"""
        message_handler = MessageHandler(mock_db, mock_deepseek_client)
        
        # Create conversation
        conversation = Conversation(
            id=uuid4(),
            hotel_id=uuid4(),
            guest_id=uuid4(),
            status=ConversationStatus.ACTIVE,
            current_state=ConversationState.GREETING,
            context={}
        )
        
        # Mock database
        mock_db.query.return_value.filter.return_value.first.return_value = conversation
        mock_db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []
        
        # Simulate a complete conversation flow
        conversation_messages = [
            "Hello, good morning!",
            "I need help with my room",
            "The air conditioning is not working",
            "Room 205",
            "Thank you for your help!",
            "Perfect, all fixed now!"
        ]
        
        # Measure complete conversation processing
        start_time = time.time()
        
        for i, content in enumerate(conversation_messages):
            message = Message(
                id=uuid4(),
                conversation_id=conversation.id,
                hotel_id=conversation.hotel_id,
                guest_id=conversation.guest_id,
                message_type=MessageType.TEXT,
                content=content,
                direction="inbound"
            )
            
            result = await message_handler.handle_incoming_message(
                hotel_id=conversation.hotel_id,
                guest_id=conversation.guest_id,
                message=message
            )
            
            assert result.success is True
        
        end_time = time.time()
        total_time = end_time - start_time
        avg_time_per_message = total_time / len(conversation_messages)
        
        # Performance assertions
        assert total_time < 5.0  # Complete conversation under 5 seconds
        assert avg_time_per_message < 1.0  # Each message under 1 second
        
        print(f"End-to-end conversation performance: {total_time:.2f}s total, {avg_time_per_message:.3f}s per message")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
