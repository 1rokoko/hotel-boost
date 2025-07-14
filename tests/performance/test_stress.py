"""
Stress testing for Hotel WhatsApp Bot
Tests system behavior under extreme load and failure conditions
"""

import pytest
import asyncio
import time
import random
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch, Mock
from httpx import AsyncClient
import statistics

from app.main import app
from app.models.hotel import Hotel
from app.models.guest import Guest
from app.services.green_api_service import GreenAPIService
from app.services.deepseek_client import DeepSeekClient


@pytest.mark.performance
@pytest.mark.stress
@pytest.mark.asyncio
class TestStressPerformance:
    """Stress testing for system resilience"""

    async def test_extreme_concurrent_webhooks(
        self,
        async_client: AsyncClient,
        sample_hotel,
        mock_green_api_client,
        mock_deepseek_client,
        performance_tracker
    ):
        """Test system behavior under extreme concurrent webhook load"""

        # Mock services with variable response times to simulate real conditions
        async def variable_response_mock(*args, **kwargs):
            # Simulate variable response times (50-500ms)
            await asyncio.sleep(random.uniform(0.05, 0.5))
            return {
                "idMessage": f"stress_msg_{random.randint(1000, 9999)}",
                "statusMessage": "sent"
            }

        mock_green_api_client.send_text_message = AsyncMock(side_effect=variable_response_mock)
        mock_deepseek_client.analyze_sentiment = AsyncMock(return_value={
            "sentiment": random.choice(["positive", "negative", "neutral"]),
            "confidence": random.uniform(0.6, 0.9),
            "requires_attention": random.choice([True, False])
        })

        # Stress test parameters
        num_requests = 1000
        max_concurrent = 100
        burst_size = 50

        webhook_template = {
            "typeWebhook": "incomingMessageReceived",
            "instanceData": {
                "idInstance": sample_hotel.green_api_instance_id,
                "wid": f"{sample_hotel.whatsapp_number}@c.us",
                "typeInstance": "whatsapp"
            },
            "messageData": {
                "typeMessage": "textMessage",
                "textMessageData": {
                    "textMessage": "Stress test message"
                }
            }
        }

        async def send_stress_request(request_id: int):
            """Send a stress test request with random delays"""
            # Add random jitter to simulate real-world conditions
            await asyncio.sleep(random.uniform(0, 0.1))

            webhook_payload = webhook_template.copy()
            webhook_payload["idMessage"] = f"stress_test_{request_id}"
            webhook_payload["timestamp"] = int(datetime.utcnow().timestamp())
            webhook_payload["senderData"] = {
                "chatId": f"stress_user_{request_id}@c.us",
                "sender": f"stress_user_{request_id}@c.us",
                "senderName": f"Stress User {request_id}"
            }

            start_time = time.time()

            try:
                with patch('app.services.green_api_service.get_green_api_client') as mock_get_client:
                    mock_get_client.return_value = mock_green_api_client

                    with patch('app.services.deepseek_client.DeepSeekClient') as mock_deepseek_class:
                        mock_deepseek_class.return_value = mock_deepseek_client

                        response = await async_client.post(
                            f"/api/v1/webhooks/green-api/{sample_hotel.id}",
                            json=webhook_payload,
                            headers={"Content-Type": "application/json"},
                            timeout=30.0  # Longer timeout for stress test
                        )

                end_time = time.time()
                response_time = (end_time - start_time) * 1000

                return {
                    "status_code": response.status_code,
                    "response_time": response_time,
                    "request_id": request_id,
                    "success": True
                }

            except Exception as e:
                end_time = time.time()
                response_time = (end_time - start_time) * 1000

                return {
                    "status_code": 0,
                    "response_time": response_time,
                    "request_id": request_id,
                    "success": False,
                    "error": str(e)
                }

        # Execute stress test with bursts
        performance_tracker.start_operation("stress_test")

        all_results = []
        semaphore = asyncio.Semaphore(max_concurrent)

        async def controlled_request(request_id: int):
            async with semaphore:
                return await send_stress_request(request_id)

        # Send requests in bursts to simulate traffic spikes
        for burst_start in range(0, num_requests, burst_size):
            burst_end = min(burst_start + burst_size, num_requests)

            # Create burst of requests
            burst_tasks = [
                controlled_request(request_id)
                for request_id in range(burst_start, burst_end)
            ]

            # Execute burst
            burst_results = await asyncio.gather(*burst_tasks, return_exceptions=True)

            # Process results, handling exceptions
            for result in burst_results:
                if isinstance(result, Exception):
                    all_results.append({
                        "status_code": 0,
                        "response_time": 0,
                        "success": False,
                        "error": str(result)
                    })
                else:
                    all_results.append(result)

            # Brief pause between bursts
            await asyncio.sleep(0.1)

        performance_tracker.end_operation("stress_test")

        # Analyze stress test results
        successful_requests = [r for r in all_results if r.get("success", False)]
        failed_requests = [r for r in all_results if not r.get("success", False)]

        success_rate = len(successful_requests) / len(all_results)

        # Stress test assertions (more lenient than load test)
        assert success_rate >= 0.80, f"Success rate {success_rate:.2%} below 80% under stress"

        if successful_requests:
            response_times = [r["response_time"] for r in successful_requests]
            avg_response_time = statistics.mean(response_times)
            p99_response_time = statistics.quantiles(response_times, n=100)[98]  # 99th percentile

            # More lenient thresholds for stress test
            assert avg_response_time < 5000, f"Average response time {avg_response_time:.2f}ms exceeds 5000ms under stress"
            assert p99_response_time < 10000, f"99th percentile response time {p99_response_time:.2f}ms exceeds 10000ms under stress"

            print(f"\nStress Test Results:")
            print(f"Total requests: {len(all_results)}")
            print(f"Successful requests: {len(successful_requests)}")
            print(f"Failed requests: {len(failed_requests)}")
            print(f"Success rate: {success_rate:.2%}")
            print(f"Average response time: {avg_response_time:.2f}ms")
            print(f"99th percentile response time: {p99_response_time:.2f}ms")

            if failed_requests:
                error_types = {}
                for req in failed_requests:
                    error = req.get("error", "Unknown")
                    error_types[error] = error_types.get(error, 0) + 1
                print(f"Error breakdown: {error_types}")

    async def test_memory_stress_with_large_payloads(
        self,
        async_client: AsyncClient,
        sample_hotel,
        mock_green_api_client,
        performance_tracker
    ):
        """Test system behavior with large message payloads"""

        # Mock service
        mock_green_api_client.send_text_message = AsyncMock(return_value={
            "idMessage": "large_payload_msg",
            "statusMessage": "sent"
        })

        # Generate large message content (simulate long customer messages)
        large_message_sizes = [1000, 5000, 10000, 50000]  # Characters
        num_requests_per_size = 10

        async def send_large_payload_request(size: int, request_id: int):
            """Send request with large payload"""
            large_content = "A" * size  # Simple large content

            webhook_payload = {
                "typeWebhook": "incomingMessageReceived",
                "instanceData": {
                    "idInstance": sample_hotel.green_api_instance_id,
                    "wid": f"{sample_hotel.whatsapp_number}@c.us",
                    "typeInstance": "whatsapp"
                },
                "timestamp": int(datetime.utcnow().timestamp()),
                "idMessage": f"large_payload_{size}_{request_id}",
                "senderData": {
                    "chatId": f"large_user_{request_id}@c.us",
                    "sender": f"large_user_{request_id}@c.us",
                    "senderName": f"Large Payload User {request_id}"
                },
                "messageData": {
                    "typeMessage": "textMessage",
                    "textMessageData": {
                        "textMessage": large_content
                    }
                }
            }

            start_time = time.time()

            with patch('app.services.green_api_service.get_green_api_client') as mock_get_client:
                mock_get_client.return_value = mock_green_api_client

                response = await async_client.post(
                    f"/api/v1/webhooks/green-api/{sample_hotel.id}",
                    json=webhook_payload,
                    headers={"Content-Type": "application/json"}
                )

            end_time = time.time()
            response_time = (end_time - start_time) * 1000

            return {
                "status_code": response.status_code,
                "response_time": response_time,
                "payload_size": size,
                "request_id": request_id
            }

        # Execute memory stress test
        performance_tracker.start_operation("memory_stress_test")

        all_results = []

        for size in large_message_sizes:
            size_tasks = [
                send_large_payload_request(size, request_id)
                for request_id in range(num_requests_per_size)
            ]

            size_results = await asyncio.gather(*size_tasks)
            all_results.extend(size_results)

        performance_tracker.end_operation("memory_stress_test")

        # Analyze memory stress results
        successful_requests = [r for r in all_results if r["status_code"] == 200]
        success_rate = len(successful_requests) / len(all_results)

        # Memory stress assertions
        assert success_rate >= 0.90, f"Success rate {success_rate:.2%} below 90% with large payloads"

        # Analyze performance by payload size
        for size in large_message_sizes:
            size_results = [r for r in successful_requests if r["payload_size"] == size]
            if size_results:
                avg_time = statistics.mean([r["response_time"] for r in size_results])
                print(f"Payload size {size} chars: {len(size_results)} requests, avg time: {avg_time:.2f}ms")

                # Ensure response time doesn't grow exponentially with payload size
                max_expected_time = 1000 + (size / 1000) * 100  # Base time + linear growth
                assert avg_time < max_expected_time, f"Response time {avg_time:.2f}ms too high for payload size {size}"