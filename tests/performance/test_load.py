"""
Load testing for Hotel WhatsApp Bot
Tests system performance under various load conditions
"""

import pytest
import asyncio
import time
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import AsyncMock, patch
from httpx import AsyncClient
import statistics

from app.main import app
from app.models.hotel import Hotel
from app.models.guest import Guest
from app.services.green_api_service import GreenAPIService
from app.services.deepseek_client import DeepSeekClient


@pytest.mark.performance
@pytest.mark.asyncio
class TestLoadPerformance:
    """Load testing for various system components"""

    async def test_webhook_processing_load(
        self,
        async_client: AsyncClient,
        sample_hotel,
        mock_green_api_client,
        mock_deepseek_client,
        performance_tracker
    ):
        """Test webhook processing under load"""

        # Mock services for consistent performance
        mock_green_api_client.send_text_message = AsyncMock(return_value={
            "idMessage": "load_test_msg",
            "statusMessage": "sent"
        })

        mock_deepseek_client.analyze_sentiment = AsyncMock(return_value={
            "sentiment": "positive",
            "confidence": 0.8,
            "requires_attention": False
        })

        # Prepare webhook payload template
        webhook_template = {
            "typeWebhook": "incomingMessageReceived",
            "instanceData": {
                "idInstance": sample_hotel.green_api_instance_id,
                "wid": f"{sample_hotel.whatsapp_number}@c.us",
                "typeInstance": "whatsapp"
            },
            "timestamp": int(datetime.utcnow().timestamp()),
            "messageData": {
                "typeMessage": "textMessage",
                "textMessageData": {
                    "textMessage": "Load test message"
                }
            }
        }

        # Test parameters
        num_requests = 100
        concurrent_requests = 10
        response_times = []

        async def send_webhook_request(request_id: int):
            """Send a single webhook request"""
            webhook_payload = webhook_template.copy()
            webhook_payload["idMessage"] = f"load_test_{request_id}"
            webhook_payload["senderData"] = {
                "chatId": f"load_user_{request_id}@c.us",
                "sender": f"load_user_{request_id}@c.us",
                "senderName": f"Load User {request_id}"
            }

            start_time = time.time()

            with patch('app.services.green_api_service.get_green_api_client') as mock_get_client:
                mock_get_client.return_value = mock_green_api_client

                with patch('app.services.deepseek_client.DeepSeekClient') as mock_deepseek_class:
                    mock_deepseek_class.return_value = mock_deepseek_client

                    response = await async_client.post(
                        f"/api/v1/webhooks/green-api/{sample_hotel.id}",
                        json=webhook_payload,
                        headers={"Content-Type": "application/json"}
                    )

            end_time = time.time()
            response_time = (end_time - start_time) * 1000  # Convert to milliseconds

            return {
                "status_code": response.status_code,
                "response_time": response_time,
                "request_id": request_id
            }

        # Execute load test
        performance_tracker.start_operation("webhook_load_test")

        # Process requests in batches to control concurrency
        batch_size = concurrent_requests
        all_results = []

        for i in range(0, num_requests, batch_size):
            batch_end = min(i + batch_size, num_requests)
            batch_tasks = [
                send_webhook_request(request_id)
                for request_id in range(i, batch_end)
            ]

            batch_results = await asyncio.gather(*batch_tasks)
            all_results.extend(batch_results)

        performance_tracker.end_operation("webhook_load_test")

        # Analyze results
        successful_requests = [r for r in all_results if r["status_code"] == 200]
        response_times = [r["response_time"] for r in successful_requests]

        # Performance assertions
        success_rate = len(successful_requests) / num_requests
        assert success_rate >= 0.95, f"Success rate {success_rate:.2%} below 95%"

        if response_times:
            avg_response_time = statistics.mean(response_times)
            p95_response_time = statistics.quantiles(response_times, n=20)[18]  # 95th percentile

            assert avg_response_time < 1000, f"Average response time {avg_response_time:.2f}ms exceeds 1000ms"
            assert p95_response_time < 2000, f"95th percentile response time {p95_response_time:.2f}ms exceeds 2000ms"

            # Log performance metrics
            print(f"\nLoad Test Results:")
            print(f"Total requests: {num_requests}")
            print(f"Successful requests: {len(successful_requests)}")
            print(f"Success rate: {success_rate:.2%}")
            print(f"Average response time: {avg_response_time:.2f}ms")
            print(f"95th percentile response time: {p95_response_time:.2f}ms")
            print(f"Min response time: {min(response_times):.2f}ms")
            print(f"Max response time: {max(response_times):.2f}ms")

    async def test_database_operations_load(
        self,
        async_test_session,
        sample_hotel,
        performance_tracker
    ):
        """Test database operations under load"""

        # Test parameters
        num_operations = 500
        concurrent_operations = 20

        async def create_guest_and_conversation(operation_id: int):
            """Create guest and conversation"""
            start_time = time.time()

            # Create guest
            guest = Guest(
                hotel_id=sample_hotel.id,
                phone=f"+123456789{operation_id:03d}",
                name=f"Load Test Guest {operation_id}"
            )
            async_test_session.add(guest)
            await async_test_session.flush()

            # Create conversation
            from app.models.message import Conversation
            conversation = Conversation(
                hotel_id=sample_hotel.id,
                guest_id=guest.id,
                started_at=datetime.utcnow()
            )
            async_test_session.add(conversation)
            await async_test_session.flush()

            end_time = time.time()
            operation_time = (end_time - start_time) * 1000

            return {
                "operation_time": operation_time,
                "operation_id": operation_id,
                "guest_id": guest.id,
                "conversation_id": conversation.id
            }

        # Execute database load test
        performance_tracker.start_operation("database_load_test")

        # Process operations in batches
        batch_size = concurrent_operations
        all_results = []

        for i in range(0, num_operations, batch_size):
            batch_end = min(i + batch_size, num_operations)
            batch_tasks = [
                create_guest_and_conversation(operation_id)
                for operation_id in range(i, batch_end)
            ]

            batch_results = await asyncio.gather(*batch_tasks)
            all_results.extend(batch_results)

            # Commit batch
            await async_test_session.commit()

        performance_tracker.end_operation("database_load_test")

        # Analyze database performance
        operation_times = [r["operation_time"] for r in all_results]
        avg_operation_time = statistics.mean(operation_times)
        p95_operation_time = statistics.quantiles(operation_times, n=20)[18]

        # Performance assertions
        assert avg_operation_time < 100, f"Average DB operation time {avg_operation_time:.2f}ms exceeds 100ms"
        assert p95_operation_time < 200, f"95th percentile DB operation time {p95_operation_time:.2f}ms exceeds 200ms"

        print(f"\nDatabase Load Test Results:")
        print(f"Total operations: {num_operations}")
        print(f"Average operation time: {avg_operation_time:.2f}ms")
        print(f"95th percentile operation time: {p95_operation_time:.2f}ms")