"""
API Response Fixtures for Testing
Comprehensive collection of realistic API responses for mocking
"""

import time
from datetime import datetime
from typing import Dict, Any, List


class GreenAPIFixtures:
    """Green API response fixtures"""

    @staticmethod
    def send_message_success(message_id: str = "msg_123456789") -> Dict[str, Any]:
        """Successful message send response"""
        return {
            "idMessage": message_id,
            "statusMessage": "sent"
        }

    @staticmethod
    def send_message_error() -> Dict[str, Any]:
        """Error message send response"""
        return {
            "error": "Message sending failed",
            "errorCode": 400,
            "errorMessage": "Invalid chat ID format"
        }

    @staticmethod
    def incoming_text_webhook(
        chat_id: str = "1234567890@c.us",
        message: str = "Hello, I need help",
        sender_name: str = "John Doe",
        instance_id: str = "1234567890"
    ) -> Dict[str, Any]:
        """Incoming text message webhook"""
        return {
            "typeWebhook": "incomingMessageReceived",
            "instanceData": {
                "idInstance": instance_id,
                "wid": f"{instance_id}@c.us",
                "typeInstance": "whatsapp"
            },
            "timestamp": int(time.time()),
            "idMessage": f"incoming_{int(time.time())}",
            "senderData": {
                "chatId": chat_id,
                "sender": chat_id,
                "senderName": sender_name
            },
            "messageData": {
                "typeMessage": "textMessage",
                "textMessageData": {
                    "textMessage": message
                }
            }
        }

    @staticmethod
    def incoming_image_webhook(
        chat_id: str = "1234567890@c.us",
        caption: str = "Here's the issue",
        sender_name: str = "Jane Doe",
        instance_id: str = "1234567890"
    ) -> Dict[str, Any]:
        """Incoming image message webhook"""
        return {
            "typeWebhook": "incomingMessageReceived",
            "instanceData": {
                "idInstance": instance_id,
                "wid": f"{instance_id}@c.us",
                "typeInstance": "whatsapp"
            },
            "timestamp": int(time.time()),
            "idMessage": f"incoming_img_{int(time.time())}",
            "senderData": {
                "chatId": chat_id,
                "sender": chat_id,
                "senderName": sender_name
            },
            "messageData": {
                "typeMessage": "imageMessage",
                "fileMessageData": {
                    "downloadUrl": "https://api.green-api.com/file/download/example.jpg",
                    "caption": caption,
                    "fileName": "issue_photo.jpg",
                    "jpegThumbnail": "/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAYEBQYFBAYGBQYHBwYIChAKCgkJChQODwwQFxQYGBcUFhYaHSUfGhsjHBYWICwgIyYnKSopGR8tMC0oMCUoKSj/2wBDAQcHBwoIChMKChMoGhYaKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCj/wAARCAABAAEDASIAAhEBAxEB/8QAFQABAQAAAAAAAAAAAAAAAAAAAAv/xAAUEAEAAAAAAAAAAAAAAAAAAAAA/8QAFQEBAQAAAAAAAAAAAAAAAAAAAAX/xAAUEQEAAAAAAAAAAAAAAAAAAAAA/9oADAMBAAIRAxEAPwCdABmX/9k="
                }
            }
        }

    @staticmethod
    def outgoing_message_status_webhook(
        message_id: str = "msg_123456789",
        status: str = "delivered",
        chat_id: str = "1234567890@c.us",
        instance_id: str = "1234567890"
    ) -> Dict[str, Any]:
        """Outgoing message status webhook"""
        return {
            "typeWebhook": "outgoingMessageStatus",
            "instanceData": {
                "idInstance": instance_id,
                "wid": f"{instance_id}@c.us",
                "typeInstance": "whatsapp"
            },
            "timestamp": int(time.time()),
            "idMessage": message_id,
            "status": status,
            "chatId": chat_id,
            "sendByApi": True
        }

    @staticmethod
    def instance_state_webhook(
        state: str = "authorized",
        instance_id: str = "1234567890"
    ) -> Dict[str, Any]:
        """Instance state change webhook"""
        return {
            "typeWebhook": "stateInstanceChanged",
            "instanceData": {
                "idInstance": instance_id,
                "wid": f"{instance_id}@c.us",
                "typeInstance": "whatsapp"
            },
            "timestamp": int(time.time()),
            "stateInstance": state
        }

    @staticmethod
    def get_settings_response() -> Dict[str, Any]:
        """Get settings response"""
        return {
            "wh_url": "https://example.com/webhook",
            "wh_urlToken": "webhook_token_123",
            "delaySendMessagesMilliseconds": 1000,
            "markIncomingMessagesReaded": "yes",
            "outgoingWebhook": "yes",
            "incomingWebhook": "yes",
            "stateWebhook": "yes",
            "incomingBlock": "no",
            "outgoingBlock": "no"
        }

    @staticmethod
    def get_state_instance_response(state: str = "authorized") -> Dict[str, Any]:
        """Get state instance response"""
        return {
            "stateInstance": state
        }

    @staticmethod
    def get_status_instance_response(status: str = "online") -> Dict[str, Any]:
        """Get status instance response"""
        return {
            "statusInstance": status
        }


class DeepSeekFixtures:
    """DeepSeek API response fixtures"""

    @staticmethod
    def sentiment_analysis_positive() -> Dict[str, Any]:
        """Positive sentiment analysis response"""
        return {
            "sentiment": "positive",
            "confidence": 0.85,
            "requires_attention": False,
            "reasoning": "Message contains positive language and expressions of satisfaction",
            "categories": ["general", "satisfaction"],
            "tokens_used": 15
        }

    @staticmethod
    def sentiment_analysis_negative() -> Dict[str, Any]:
        """Negative sentiment analysis response"""
        return {
            "sentiment": "negative",
            "confidence": 0.92,
            "requires_attention": True,
            "reasoning": "Message contains negative language and complaints requiring immediate attention",
            "categories": ["complaint", "room_service"],
            "tokens_used": 18
        }

    @staticmethod
    def sentiment_analysis_neutral() -> Dict[str, Any]:
        """Neutral sentiment analysis response"""
        return {
            "sentiment": "neutral",
            "confidence": 0.75,
            "requires_attention": False,
            "reasoning": "Message appears to be informational or neutral inquiry",
            "categories": ["general", "inquiry"],
            "tokens_used": 12
        }

    @staticmethod
    def response_generation_greeting() -> Dict[str, Any]:
        """Response generation for greeting"""
        return {
            "response": "Hello! Welcome to our hotel. How can I assist you today?",
            "confidence": 0.88,
            "suggested_actions": ["send_welcome_message", "offer_assistance"],
            "tokens_used": 20
        }

    @staticmethod
    def response_generation_complaint() -> Dict[str, Any]:
        """Response generation for complaint"""
        return {
            "response": "I sincerely apologize for any inconvenience. Let me help resolve this issue immediately.",
            "confidence": 0.91,
            "suggested_actions": ["escalate_to_manager", "send_apology", "schedule_follow_up"],
            "tokens_used": 25
        }

    @staticmethod
    def chat_completion_response(content: str = "I understand. How can I help you further?") -> Dict[str, Any]:
        """Chat completion response"""
        return {
            "id": f"chatcmpl-{int(time.time())}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": "deepseek-chat",
            "choices": [{
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": content
                },
                "finish_reason": "stop"
            }],
            "usage": {
                "prompt_tokens": 50,
                "completion_tokens": 20,
                "total_tokens": 70
            }
        }