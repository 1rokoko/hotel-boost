"""
Performance benchmarks for Hotel WhatsApp Bot
Measures and tracks performance metrics over time
"""

import pytest
import asyncio
import time
from datetime import datetime
from unittest.mock import AsyncMock, patch
from sqlalchemy import select

from app.main import app
from app.models.hotel import Hotel
from app.models.guest import Guest
from app.models.message import Message, Conversation, MessageType
from app.services.green_api_service import GreenAPIService
from app.services.deepseek_client import DeepSeekClient
from app.services.sentiment_analyzer import SentimentAnalyzer
from app.services.message_handler import MessageHandler


@pytest.mark.performance
@pytest.mark.benchmark
@pytest.mark.asyncio
class TestPerformanceBenchmarks:
    """Performance benchmarks for key system components"""

    def test_message_processing_benchmark(
        self,
        benchmark,
        async_test_session,
        sample_hotel,
        sample_guest,
        mock_deepseek_client
    ):
        """Benchmark message processing performance"""

        # Mock DeepSeek client
        mock_deepseek_client.analyze_sentiment = AsyncMock(return_value={
            "sentiment": "positive",
            "confidence": 0.8,
            "requires_attention": False,
            "reasoning": "Positive customer message"
        })

        async def process_message():
            """Process a single message"""
            # Create conversation
            conversation = Conversation(
                hotel_id=sample_hotel.id,
                guest_id=sample_guest.id,
                started_at=datetime.utcnow()
            )
            async_test_session.add(conversation)
            await async_test_session.flush()

            # Create message
            message = Message(
                conversation_id=conversation.id,
                guest_id=sample_guest.id,
                content="Hello, I need help with my reservation",
                message_type=MessageType.INCOMING
            )
            async_test_session.add(message)
            await async_test_session.flush()

            # Process with message handler
            message_handler = MessageHandler(async_test_session, mock_deepseek_client)
            result = await message_handler.handle_incoming_message(
                sample_hotel.id,
                sample_guest.id,
                message
            )

            await async_test_session.commit()
            return result

        # Benchmark the message processing
        def sync_wrapper():
            return asyncio.run(process_message())

        result = benchmark(sync_wrapper)

        # Verify the benchmark completed successfully
        assert result is not None

        # Performance assertions
        stats = benchmark.stats
        assert stats.mean < 0.5, f"Message processing took {stats.mean:.3f}s, expected < 0.5s"
        assert stats.stddev < 0.1, f"Message processing stddev {stats.stddev:.3f}s too high"

    def test_database_query_benchmark(
        self,
        benchmark,
        async_test_session,
        sample_hotel
    ):
        """Benchmark database query performance"""

        async def setup_test_data():
            """Setup test data for benchmarking"""
            # Create multiple guests and conversations
            guests = []
            conversations = []

            for i in range(50):
                guest = Guest(
                    hotel_id=sample_hotel.id,
                    phone=f"+12345678{i:02d}",
                    name=f"Benchmark Guest {i}"
                )
                async_test_session.add(guest)
                guests.append(guest)

            await async_test_session.flush()

            for guest in guests:
                conversation = Conversation(
                    hotel_id=sample_hotel.id,
                    guest_id=guest.id,
                    started_at=datetime.utcnow()
                )
                async_test_session.add(conversation)
                conversations.append(conversation)

            await async_test_session.commit()
            return guests, conversations

        # Setup data
        guests, conversations = asyncio.run(setup_test_data())

        async def query_conversations():
            """Query conversations for hotel"""
            result = await async_test_session.execute(
                select(Conversation)
                .where(Conversation.hotel_id == sample_hotel.id)
                .limit(20)
            )
            return result.scalars().all()

        def sync_wrapper():
            return asyncio.run(query_conversations())

        # Benchmark the query
        result = benchmark(sync_wrapper)

        # Verify results
        assert len(result) == 20

        # Performance assertions
        stats = benchmark.stats
        assert stats.mean < 0.1, f"Database query took {stats.mean:.3f}s, expected < 0.1s"

    def test_sentiment_analysis_benchmark(
        self,
        benchmark,
        async_test_session,
        sample_hotel,
        sample_guest,
        mock_deepseek_client
    ):
        """Benchmark sentiment analysis performance"""

        # Mock DeepSeek with realistic response time
        async def mock_analyze_sentiment(*args, **kwargs):
            # Simulate API call delay
            await asyncio.sleep(0.1)
            return {
                "sentiment": "positive",
                "confidence": 0.85,
                "requires_attention": False,
                "reasoning": "Customer expressing satisfaction"
            }

        mock_deepseek_client.analyze_sentiment = AsyncMock(side_effect=mock_analyze_sentiment)

        async def analyze_message_sentiment():
            """Analyze sentiment of a message"""
            # Create message
            message = Message(
                guest_id=sample_guest.id,
                content="Thank you for the excellent service! I'm very happy with my stay.",
                message_type=MessageType.INCOMING
            )
            async_test_session.add(message)
            await async_test_session.flush()

            # Analyze sentiment
            analyzer = SentimentAnalyzer(async_test_session, mock_deepseek_client)
            result = await analyzer.analyze_message_sentiment(message)

            await async_test_session.commit()
            return result

        def sync_wrapper():
            return asyncio.run(analyze_message_sentiment())

        # Benchmark sentiment analysis
        result = benchmark(sync_wrapper)

        # Verify results
        assert result is not None
        assert result.sentiment == "positive"

        # Performance assertions (including API call simulation)
        stats = benchmark.stats
        assert stats.mean < 0.2, f"Sentiment analysis took {stats.mean:.3f}s, expected < 0.2s"

    def test_webhook_parsing_benchmark(
        self,
        benchmark,
        sample_hotel
    ):
        """Benchmark webhook payload parsing performance"""

        # Sample webhook payload
        webhook_payload = {
            "typeWebhook": "incomingMessageReceived",
            "instanceData": {
                "idInstance": sample_hotel.green_api_instance_id,
                "wid": f"{sample_hotel.whatsapp_number}@c.us",
                "typeInstance": "whatsapp"
            },
            "timestamp": int(datetime.utcnow().timestamp()),
            "idMessage": "benchmark_msg_123",
            "senderData": {
                "chatId": "1234567890@c.us",
                "sender": "1234567890@c.us",
                "senderName": "Benchmark User"
            },
            "messageData": {
                "typeMessage": "textMessage",
                "textMessageData": {
                    "textMessage": "This is a benchmark message for parsing performance testing"
                }
            }
        }

        def parse_webhook():
            """Parse webhook payload"""
            from app.schemas.green_api import WebhookMessage

            # Parse and validate webhook
            webhook = WebhookMessage(**webhook_payload)

            # Extract key information
            message_content = webhook.messageData.textMessageData.textMessage
            sender_phone = webhook.senderData.sender.replace("@c.us", "")
            sender_name = webhook.senderData.senderName

            return {
                "content": message_content,
                "phone": sender_phone,
                "name": sender_name,
                "timestamp": webhook.timestamp
            }

        # Benchmark webhook parsing
        result = benchmark(parse_webhook)

        # Verify parsing results
        assert result["content"] == webhook_payload["messageData"]["textMessageData"]["textMessage"]
        assert result["phone"] == "1234567890"
        assert result["name"] == "Benchmark User"

        # Performance assertions
        stats = benchmark.stats
        assert stats.mean < 0.001, f"Webhook parsing took {stats.mean:.6f}s, expected < 0.001s"
        assert stats.stddev < 0.0005, f"Webhook parsing stddev {stats.stddev:.6f}s too high"

    def test_concurrent_processing_benchmark(
        self,
        benchmark,
        async_test_session,
        sample_hotel,
        mock_green_api_client,
        mock_deepseek_client
    ):
        """Benchmark concurrent message processing"""

        # Mock services
        mock_green_api_client.send_text_message = AsyncMock(return_value={
            "idMessage": "concurrent_msg",
            "statusMessage": "sent"
        })

        mock_deepseek_client.analyze_sentiment = AsyncMock(return_value={
            "sentiment": "neutral",
            "confidence": 0.7,
            "requires_attention": False
        })

        async def process_concurrent_messages():
            """Process multiple messages concurrently"""

            # Create multiple guests
            guests = []
            for i in range(10):
                guest = Guest(
                    hotel_id=sample_hotel.id,
                    phone=f"+987654321{i}",
                    name=f"Concurrent User {i}"
                )
                async_test_session.add(guest)
                guests.append(guest)

            await async_test_session.flush()

            # Process messages concurrently
            async def process_single_message(guest, message_id):
                conversation = Conversation(
                    hotel_id=sample_hotel.id,
                    guest_id=guest.id,
                    started_at=datetime.utcnow()
                )
                async_test_session.add(conversation)
                await async_test_session.flush()

                message = Message(
                    conversation_id=conversation.id,
                    guest_id=guest.id,
                    content=f"Concurrent message {message_id}",
                    message_type=MessageType.INCOMING
                )
                async_test_session.add(message)
                await async_test_session.flush()

                return message

            # Process all messages concurrently
            tasks = [
                process_single_message(guest, i)
                for i, guest in enumerate(guests)
            ]

            results = await asyncio.gather(*tasks)
            await async_test_session.commit()

            return results

        def sync_wrapper():
            return asyncio.run(process_concurrent_messages())

        # Benchmark concurrent processing
        result = benchmark(sync_wrapper)

        # Verify results
        assert len(result) == 10

        # Performance assertions
        stats = benchmark.stats
        assert stats.mean < 1.0, f"Concurrent processing took {stats.mean:.3f}s, expected < 1.0s"