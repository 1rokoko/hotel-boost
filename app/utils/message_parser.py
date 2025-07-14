"""
Message parser utilities for WhatsApp messages
"""

import re
from typing import Dict, Any, Optional, List, Tuple
import structlog
from datetime import datetime

logger = structlog.get_logger(__name__)


class MessageParser:
    """Parser for WhatsApp message content and metadata"""
    
    def __init__(self):
        # Common patterns for message parsing
        self.patterns = {
            'email': re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'),
            'phone': re.compile(r'[\+]?[1-9]?[0-9]{7,15}'),
            'url': re.compile(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'),
            'booking_ref': re.compile(r'\b[A-Z0-9]{6,12}\b'),
            'room_number': re.compile(r'\b(?:room|rm|suite)\s*#?(\d{1,4})\b', re.IGNORECASE),
            'date': re.compile(r'\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b'),
            'time': re.compile(r'\b\d{1,2}:\d{2}(?:\s*[AaPp][Mm])?\b'),
        }
        
        # Intent keywords
        self.intent_keywords = {
            'booking': ['book', 'reserve', 'reservation', 'availability', 'check-in', 'check-out'],
            'complaint': ['problem', 'issue', 'complain', 'wrong', 'bad', 'terrible', 'awful', 'disappointed'],
            'compliment': ['great', 'excellent', 'amazing', 'wonderful', 'perfect', 'love', 'fantastic'],
            'question': ['?', 'how', 'what', 'when', 'where', 'why', 'can you', 'could you'],
            'request': ['need', 'want', 'require', 'request', 'please', 'help'],
            'cancellation': ['cancel', 'refund', 'change', 'modify'],
            'emergency': ['emergency', 'urgent', 'help', 'fire', 'medical', 'police'],
        }
    
    def parse_message(self, content: str, message_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse message content and extract structured information
        
        Args:
            content: Message text content
            message_data: Raw message data from Green API
            
        Returns:
            Dict with parsed information
        """
        try:
            parsed = {
                'original_content': content,
                'cleaned_content': self._clean_content(content),
                'extracted_data': self._extract_data(content),
                'intent': self._detect_intent(content),
                'sentiment_indicators': self._detect_sentiment_indicators(content),
                'urgency_level': self._assess_urgency(content),
                'language': self._detect_language(content),
                'message_type': message_data.get('typeMessage', 'textMessage'),
                'parsed_at': datetime.utcnow().isoformat()
            }
            
            # Add media-specific parsing
            if parsed['message_type'] != 'textMessage':
                parsed.update(self._parse_media_message(message_data))
            
            logger.debug("Message parsed successfully",
                        content_length=len(content),
                        intent=parsed['intent'],
                        urgency=parsed['urgency_level'])
            
            return parsed
            
        except Exception as e:
            logger.error("Error parsing message", error=str(e))
            return {
                'original_content': content,
                'error': str(e),
                'parsed_at': datetime.utcnow().isoformat()
            }
    
    def _clean_content(self, content: str) -> str:
        """Clean and normalize message content"""
        if not content:
            return ""
        
        # Remove extra whitespace
        cleaned = re.sub(r'\s+', ' ', content.strip())
        
        # Remove common WhatsApp formatting
        cleaned = re.sub(r'[*_~]', '', cleaned)  # Remove bold, italic, strikethrough
        
        return cleaned
    
    def _extract_data(self, content: str) -> Dict[str, List[str]]:
        """Extract structured data from message content"""
        extracted = {}
        
        for data_type, pattern in self.patterns.items():
            matches = pattern.findall(content)
            if matches:
                extracted[data_type] = matches
        
        return extracted
    
    def _detect_intent(self, content: str) -> str:
        """Detect message intent based on keywords"""
        content_lower = content.lower()
        
        # Count keyword matches for each intent
        intent_scores = {}
        for intent, keywords in self.intent_keywords.items():
            score = sum(1 for keyword in keywords if keyword in content_lower)
            if score > 0:
                intent_scores[intent] = score
        
        # Return intent with highest score
        if intent_scores:
            return max(intent_scores, key=intent_scores.get)
        
        return 'general'


def parse_whatsapp_message(message_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Enhanced parse WhatsApp message data from Green API webhook

    Args:
        message_data: Raw message data from webhook

    Returns:
        Dict containing parsed message information
    """
    try:
        parsed = {
            'message_id': message_data.get('idMessage'),
            'timestamp': message_data.get('timestamp'),
            'chat_id': message_data.get('chatId'),
            'sender_name': message_data.get('senderName', ''),
            'message_type': 'text',  # Default
            'content': '',
            'media_url': None,
            'media_type': None,
            'metadata': {},
            'entities': {},
            'urgency_level': 1,
            'language': 'en'
        }

        # Extract message content based on type
        message_body = message_data.get('messageData', {})

        if 'textMessageData' in message_body:
            parsed['message_type'] = 'text'
            content = message_body['textMessageData'].get('textMessage', '')
            parsed['content'] = clean_message_content(content)

        elif 'imageMessageData' in message_body:
            parsed['message_type'] = 'image'
            image_data = message_body['imageMessageData']
            parsed['content'] = clean_message_content(image_data.get('caption', '[Image]'))
            parsed['media_url'] = image_data.get('downloadUrl')
            parsed['media_type'] = 'image'

        # Extract phone number from chat_id
        if parsed['chat_id']:
            phone_match = re.search(r'(\d+)@', parsed['chat_id'])
            if phone_match:
                parsed['phone_number'] = phone_match.group(1)

        # Parse timestamp
        if parsed['timestamp']:
            try:
                parsed['datetime'] = datetime.fromtimestamp(int(parsed['timestamp']))
            except (ValueError, TypeError):
                parsed['datetime'] = datetime.utcnow()
        else:
            parsed['datetime'] = datetime.utcnow()

        # Enhanced parsing for text content
        if parsed['content'] and parsed['message_type'] == 'text':
            parsed['entities'] = extract_entities(parsed['content'])
            parsed['urgency_level'] = assess_message_urgency(parsed['content'])
            parsed['language'] = detect_language(parsed['content'])

        return parsed

    except Exception as e:
        logger.error("Failed to parse WhatsApp message", error=str(e))
        return {
            'message_id': None,
            'timestamp': None,
            'chat_id': None,
            'sender_name': '',
            'message_type': 'unknown',
            'content': str(message_data),
            'media_url': None,
            'media_type': None,
            'metadata': {},
            'entities': {},
            'urgency_level': 1,
            'language': 'en',
            'datetime': datetime.utcnow(),
            'parse_error': str(e)
        }


def extract_entities(text: str) -> Dict[str, List[str]]:
    """Extract entities from message text"""
    entities = {
        'dates': [],
        'times': [],
        'phone_numbers': [],
        'emails': [],
        'room_numbers': [],
        'amounts': [],
        'urls': []
    }

    # Date patterns
    date_patterns = [
        r'\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b',
        r'\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]* \d{1,2},? \d{4}\b'
    ]

    for pattern in date_patterns:
        entities['dates'].extend(re.findall(pattern, text, re.IGNORECASE))

    # Time patterns
    time_pattern = r'\b\d{1,2}:\d{2}(?::\d{2})?\s*(?:AM|PM|am|pm)?\b'
    entities['times'] = re.findall(time_pattern, text)

    # Phone numbers
    phone_pattern = r'\b(?:\+?1[-.\s]?)?\(?[0-9]{3}\)?[-.\s]?[0-9]{3}[-.\s]?[0-9]{4}\b'
    entities['phone_numbers'] = re.findall(phone_pattern, text)

    # Email addresses
    email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    entities['emails'] = re.findall(email_pattern, text)

    # Room numbers
    room_patterns = [
        r'\broom\s+(\d{3,4})\b',
        r'\b(\d{3,4})\s*(?:room|rm)\b'
    ]

    for pattern in room_patterns:
        entities['room_numbers'].extend(re.findall(pattern, text, re.IGNORECASE))

    # Remove duplicates
    for key in entities:
        entities[key] = list(set(filter(None, entities[key])))

    return entities


def assess_message_urgency(text: str, sentiment_score: Optional[float] = None) -> int:
    """Assess message urgency on a scale of 1-5"""
    urgency = 1
    text_lower = text.lower()

    # Emergency keywords
    emergency_keywords = ['emergency', 'urgent', 'help', 'fire', 'police', 'ambulance', 'medical']
    if any(keyword in text_lower for keyword in emergency_keywords):
        urgency = 5

    # High priority keywords
    high_priority = ['broken', 'not working', 'problem', 'issue', 'complaint', 'immediately', 'asap']
    if any(keyword in text_lower for keyword in high_priority):
        urgency = max(urgency, 4)

    # Medium priority keywords
    medium_priority = ['request', 'need', 'want', 'could you', 'please']
    if any(keyword in text_lower for keyword in medium_priority):
        urgency = max(urgency, 2)

    return min(urgency, 5)


def detect_language(text: str) -> str:
    """Simple language detection based on common words"""
    text_lower = text.lower()

    language_indicators = {
        'es': ['hola', 'gracias', 'por favor', 'habitación', 'hotel', 'problema'],
        'fr': ['bonjour', 'merci', 'chambre', 'hôtel', 'problème', 'aide'],
        'de': ['hallo', 'danke', 'zimmer', 'hotel', 'problem', 'hilfe']
    }

    scores = {}
    for lang, words in language_indicators.items():
        score = sum(1 for word in words if word in text_lower)
        if score > 0:
            scores[lang] = score

    if scores:
        return max(scores.keys(), key=lambda k: scores[k])

    return 'en'


def clean_message_content(text: str) -> str:
    """Clean and normalize message content"""
    if not text:
        return ""

    # Remove excessive whitespace
    text = re.sub(r'\s+', ' ', text.strip())

    # Remove or replace common emoji/unicode issues
    text = re.sub(r'[\u200b-\u200d\ufeff]', '', text)

    # Normalize quotes
    text = re.sub(r'[""''`]', '"', text)

    return text
    
    def _detect_sentiment_indicators(self, content: str) -> Dict[str, List[str]]:
        """Detect sentiment indicators in message"""
        content_lower = content.lower()
        
        positive_words = ['good', 'great', 'excellent', 'amazing', 'wonderful', 'perfect', 'love', 'fantastic', 'happy', 'satisfied']
        negative_words = ['bad', 'terrible', 'awful', 'horrible', 'disappointed', 'angry', 'frustrated', 'upset', 'problem', 'issue']
        
        indicators = {
            'positive': [word for word in positive_words if word in content_lower],
            'negative': [word for word in negative_words if word in content_lower]
        }
        
        return indicators
    
    def _assess_urgency(self, content: str) -> str:
        """Assess message urgency level"""
        content_lower = content.lower()
        
        # High urgency indicators
        high_urgency = ['emergency', 'urgent', 'asap', 'immediately', 'fire', 'medical', 'police', 'help']
        if any(word in content_lower for word in high_urgency):
            return 'high'
        
        # Medium urgency indicators
        medium_urgency = ['soon', 'quickly', 'problem', 'issue', 'broken', 'not working']
        if any(word in content_lower for word in medium_urgency):
            return 'medium'
        
        # Check for multiple question marks or exclamation marks
        if content.count('!') >= 3 or content.count('?') >= 2:
            return 'medium'
        
        return 'low'
    
    def _detect_language(self, content: str) -> str:
        """Detect message language (basic implementation)"""
        # This is a very basic implementation
        # In production, you might want to use a proper language detection library
        
        # Common Spanish words
        spanish_words = ['hola', 'gracias', 'por favor', 'sí', 'no', 'bueno', 'malo', 'habitación']
        if any(word in content.lower() for word in spanish_words):
            return 'es'
        
        # Common French words
        french_words = ['bonjour', 'merci', 's\'il vous plaît', 'oui', 'non', 'bon', 'mauvais', 'chambre']
        if any(word in content.lower() for word in french_words):
            return 'fr'
        
        # Default to English
        return 'en'
    
    def _parse_media_message(self, message_data: Dict[str, Any]) -> Dict[str, Any]:
        """Parse media-specific message data"""
        message_type = message_data.get('typeMessage', '')
        parsed_media = {}
        
        if message_type == 'imageMessage':
            image_data = message_data.get('imageMessageData', {})
            parsed_media.update({
                'media_type': 'image',
                'caption': image_data.get('caption', ''),
                'file_name': image_data.get('fileName', ''),
                'mime_type': image_data.get('mimeType', ''),
                'file_size': image_data.get('fileSize', 0)
            })
        
        elif message_type == 'videoMessage':
            video_data = message_data.get('videoMessageData', {})
            parsed_media.update({
                'media_type': 'video',
                'caption': video_data.get('caption', ''),
                'file_name': video_data.get('fileName', ''),
                'mime_type': video_data.get('mimeType', ''),
                'file_size': video_data.get('fileSize', 0)
            })
        
        elif message_type == 'audioMessage':
            audio_data = message_data.get('audioMessageData', {})
            parsed_media.update({
                'media_type': 'audio',
                'file_name': audio_data.get('fileName', ''),
                'mime_type': audio_data.get('mimeType', ''),
                'file_size': audio_data.get('fileSize', 0)
            })
        
        elif message_type == 'documentMessage':
            doc_data = message_data.get('documentMessageData', {})
            parsed_media.update({
                'media_type': 'document',
                'caption': doc_data.get('caption', ''),
                'file_name': doc_data.get('fileName', ''),
                'mime_type': doc_data.get('mimeType', ''),
                'file_size': doc_data.get('fileSize', 0)
            })
        
        elif message_type == 'locationMessage':
            location_data = message_data.get('locationMessageData', {})
            parsed_media.update({
                'media_type': 'location',
                'latitude': location_data.get('latitude'),
                'longitude': location_data.get('longitude'),
                'name': location_data.get('nameLocation', ''),
                'address': location_data.get('address', '')
            })
        
        elif message_type == 'contactMessage':
            contact_data = message_data.get('contactMessageData', {})
            parsed_media.update({
                'media_type': 'contact',
                'display_name': contact_data.get('displayName', ''),
                'vcard': contact_data.get('vcard', '')
            })
        
        return parsed_media
    
    def extract_booking_info(self, content: str) -> Optional[Dict[str, Any]]:
        """Extract booking-related information from message"""
        booking_info = {}
        
        # Extract booking reference
        booking_refs = self.patterns['booking_ref'].findall(content)
        if booking_refs:
            booking_info['booking_reference'] = booking_refs[0]
        
        # Extract room number
        room_matches = self.patterns['room_number'].findall(content)
        if room_matches:
            booking_info['room_number'] = room_matches[0]
        
        # Extract dates
        dates = self.patterns['date'].findall(content)
        if dates:
            booking_info['dates'] = dates
        
        # Extract times
        times = self.patterns['time'].findall(content)
        if times:
            booking_info['times'] = times
        
        return booking_info if booking_info else None
    
    def is_automated_message(self, content: str) -> bool:
        """Check if message appears to be automated/bot-generated"""
        automated_indicators = [
            'this is an automated message',
            'do not reply',
            'auto-generated',
            'system message',
            'confirmation number',
            'booking confirmed'
        ]
        
        content_lower = content.lower()
        return any(indicator in content_lower for indicator in automated_indicators)
    
    def extract_contact_info(self, content: str) -> Dict[str, List[str]]:
        """Extract contact information from message"""
        contact_info = {}
        
        # Extract emails
        emails = self.patterns['email'].findall(content)
        if emails:
            contact_info['emails'] = emails
        
        # Extract phone numbers
        phones = self.patterns['phone'].findall(content)
        if phones:
            contact_info['phones'] = phones
        
        return contact_info


# Global parser instance
message_parser = MessageParser()


def parse_whatsapp_message(content: str, message_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Parse WhatsApp message content
    
    Args:
        content: Message text content
        message_data: Raw message data from Green API
        
    Returns:
        Dict with parsed information
    """
    return message_parser.parse_message(content, message_data)


def extract_message_intent(content: str) -> str:
    """Extract intent from message content"""
    return message_parser._detect_intent(content)


def assess_message_urgency(content: str) -> str:
    """Assess message urgency level"""
    return message_parser._assess_urgency(content)


# Export main components
__all__ = [
    'MessageParser',
    'message_parser',
    'parse_whatsapp_message',
    'extract_message_intent',
    'assess_message_urgency'
]
