"""
Pydantic schemas for Green API integration
"""

from typing import Optional, Dict, Any, List, Union
from pydantic import BaseModel, Field, field_validator
from datetime import datetime
from enum import Enum


class MessageType(str, Enum):
    """Green API message types"""
    TEXT = "textMessage"
    IMAGE = "imageMessage"
    VIDEO = "videoMessage"
    AUDIO = "audioMessage"
    DOCUMENT = "documentMessage"
    LOCATION = "locationMessage"
    CONTACT = "contactMessage"
    POLL = "pollMessage"
    BUTTONS = "buttonsMessage"
    LIST = "listMessage"


class WebhookType(str, Enum):
    """Green API webhook types"""
    INCOMING_MESSAGE = "incomingMessageReceived"
    OUTGOING_MESSAGE = "outgoingMessageReceived"
    MESSAGE_STATUS = "outgoingMessageStatus"
    DEVICE_INFO = "deviceInfo"
    STATE_INSTANCE = "stateInstanceChanged"
    INCOMING_CALL = "incomingCall"


class MessageStatus(str, Enum):
    """Message delivery status"""
    SENT = "sent"
    DELIVERED = "delivered"
    READ = "read"
    FAILED = "failed"
    PENDING = "pending"


# Base schemas
class GreenAPIBaseRequest(BaseModel):
    """Base request schema for Green API"""
    class Config:
        extra = "forbid"


class GreenAPIBaseResponse(BaseModel):
    """Base response schema from Green API"""
    idMessage: Optional[str] = None
    
    class Config:
        extra = "allow"


# Message sending schemas
class SendTextMessageRequest(GreenAPIBaseRequest):
    """Request schema for sending text message"""
    chatId: str = Field(..., description="Chat ID (phone number with @c.us)")
    message: str = Field(..., min_length=1, max_length=4096, description="Message text")
    quotedMessageId: Optional[str] = Field(None, description="ID of message to quote")
    
    @field_validator('chatId')
    @classmethod
    def validate_chat_id(cls, v):
        """Validate chat ID format"""
        if not v.endswith('@c.us') and not v.endswith('@g.us'):
            raise ValueError("chatId must end with @c.us (personal) or @g.us (group)")
        return v


class SendFileRequest(GreenAPIBaseRequest):
    """Request schema for sending file"""
    chatId: str = Field(..., description="Chat ID")
    urlFile: str = Field(..., description="URL of file to send")
    fileName: str = Field(..., description="File name")
    caption: Optional[str] = Field(None, max_length=1024, description="File caption")
    quotedMessageId: Optional[str] = None


class SendLocationRequest(GreenAPIBaseRequest):
    """Request schema for sending location"""
    chatId: str
    nameLocation: Optional[str] = None
    address: Optional[str] = None
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)


class SendContactRequest(GreenAPIBaseRequest):
    """Request schema for sending contact"""
    chatId: str
    contact: Dict[str, str] = Field(..., description="Contact information")


class SendPollRequest(GreenAPIBaseRequest):
    """Request schema for sending poll"""
    chatId: str
    message: str = Field(..., min_length=1, max_length=255)
    options: List[Dict[str, str]] = Field(..., min_items=2, max_items=12)
    multipleAnswers: bool = Field(default=False)


# Response schemas
class SendMessageResponse(GreenAPIBaseResponse):
    """Response schema for message sending"""
    idMessage: str = Field(..., description="Message ID")


class MessageStatusResponse(GreenAPIBaseResponse):
    """Response schema for message status"""
    status: MessageStatus
    timestamp: int
    chatId: str
    idMessage: str


# Webhook schemas
class WebhookMessageData(BaseModel):
    """Message data in webhook"""
    typeMessage: MessageType
    textMessageData: Optional[Dict[str, Any]] = None
    imageMessageData: Optional[Dict[str, Any]] = None
    videoMessageData: Optional[Dict[str, Any]] = None
    audioMessageData: Optional[Dict[str, Any]] = None
    documentMessageData: Optional[Dict[str, Any]] = None
    locationMessageData: Optional[Dict[str, Any]] = None
    contactMessageData: Optional[Dict[str, Any]] = None
    extendedTextMessageData: Optional[Dict[str, Any]] = None
    quotedMessage: Optional[Dict[str, Any]] = None


class WebhookSenderData(BaseModel):
    """Sender data in webhook"""
    chatId: str
    chatName: Optional[str] = None
    sender: Optional[str] = None
    senderName: Optional[str] = None


class IncomingMessageWebhook(BaseModel):
    """Incoming message webhook schema"""
    typeWebhook: WebhookType
    instanceData: Dict[str, Any]
    timestamp: int
    idMessage: str
    senderData: WebhookSenderData
    messageData: WebhookMessageData


class OutgoingMessageStatusWebhook(BaseModel):
    """Outgoing message status webhook schema"""
    typeWebhook: WebhookType
    instanceData: Dict[str, Any]
    timestamp: int
    idMessage: str
    status: MessageStatus
    chatId: str


class StateInstanceWebhook(BaseModel):
    """State instance webhook schema"""
    typeWebhook: WebhookType
    instanceData: Dict[str, Any]
    timestamp: int
    stateInstance: str


class DeviceInfoWebhook(BaseModel):
    """Device info webhook schema"""
    typeWebhook: WebhookType
    instanceData: Dict[str, Any]
    timestamp: int
    deviceData: Dict[str, Any]


# Union type for all webhook types
WebhookData = Union[
    IncomingMessageWebhook,
    OutgoingMessageStatusWebhook,
    StateInstanceWebhook,
    DeviceInfoWebhook
]


# API method schemas
class GetSettingsResponse(GreenAPIBaseResponse):
    """Response schema for getSettings"""
    wh_url: Optional[str] = None
    wh_urlToken: Optional[str] = None
    delaySendMessagesMilliseconds: int
    markIncomingMessagesReaded: str
    markIncomingMessagesReadedOnReply: str
    outgoingWebhook: str
    outgoingMessageWebhook: str
    outgoingAPIMessageWebhook: str
    incomingWebhook: str
    deviceWebhook: str
    statusInstanceWebhook: str
    sendFromUTC: str


class SetSettingsRequest(GreenAPIBaseRequest):
    """Request schema for setSettings"""
    webhookUrl: Optional[str] = None
    webhookUrlToken: Optional[str] = None
    delaySendMessagesMilliseconds: Optional[int] = Field(None, ge=0, le=10000)
    markIncomingMessagesReaded: Optional[str] = Field(None, pattern="^(yes|no)$")
    outgoingWebhook: Optional[str] = Field(None, pattern="^(yes|no)$")
    incomingWebhook: Optional[str] = Field(None, pattern="^(yes|no)$")


class GetStateInstanceResponse(GreenAPIBaseResponse):
    """Response schema for getStateInstance"""
    stateInstance: str


class GetStatusInstanceResponse(GreenAPIBaseResponse):
    """Response schema for getStatusInstance"""
    statusInstance: str


class QRCodeResponse(GreenAPIBaseResponse):
    """Response schema for QR code"""
    type: str
    message: str


# Error schemas
class GreenAPIError(BaseModel):
    """Green API error response"""
    error: bool = True
    reason: str
    message: Optional[str] = None


class GreenAPIErrorResponse(BaseModel):
    """Wrapper for error responses"""
    error: GreenAPIError


# Utility functions
def parse_webhook_data(webhook_type: str, data: Dict[str, Any]) -> WebhookData:
    """Parse webhook data based on type"""
    webhook_map = {
        WebhookType.INCOMING_MESSAGE: IncomingMessageWebhook,
        WebhookType.OUTGOING_MESSAGE: IncomingMessageWebhook,  # Same structure
        WebhookType.MESSAGE_STATUS: OutgoingMessageStatusWebhook,
        WebhookType.STATE_INSTANCE: StateInstanceWebhook,
        WebhookType.DEVICE_INFO: DeviceInfoWebhook,
    }
    
    webhook_class = webhook_map.get(webhook_type)
    if not webhook_class:
        raise ValueError(f"Unknown webhook type: {webhook_type}")
    
    return webhook_class(**data)


def extract_phone_number(chat_id: str) -> str:
    """Extract phone number from chat ID"""
    if chat_id.endswith('@c.us'):
        return chat_id.replace('@c.us', '')
    elif chat_id.endswith('@g.us'):
        return chat_id.replace('@g.us', '')
    return chat_id


def format_chat_id(phone_number: str, is_group: bool = False) -> str:
    """Format phone number to chat ID"""
    # Remove any non-digit characters
    clean_number = ''.join(filter(str.isdigit, phone_number))
    
    # Add country code if missing (assuming +1 for demo)
    if len(clean_number) == 10:
        clean_number = '1' + clean_number
    
    suffix = '@g.us' if is_group else '@c.us'
    return f"{clean_number}{suffix}"


# Export all schemas
__all__ = [
    # Enums
    'MessageType', 'WebhookType', 'MessageStatus',
    
    # Request schemas
    'SendTextMessageRequest', 'SendFileRequest', 'SendLocationRequest',
    'SendContactRequest', 'SendPollRequest', 'SetSettingsRequest',
    
    # Response schemas
    'SendMessageResponse', 'MessageStatusResponse', 'GetSettingsResponse',
    'GetStateInstanceResponse', 'GetStatusInstanceResponse', 'QRCodeResponse',
    
    # Webhook schemas
    'IncomingMessageWebhook', 'OutgoingMessageStatusWebhook',
    'StateInstanceWebhook', 'DeviceInfoWebhook', 'WebhookData',
    
    # Error schemas
    'GreenAPIError', 'GreenAPIErrorResponse',
    
    # Utility functions
    'parse_webhook_data', 'extract_phone_number', 'format_chat_id'
]
