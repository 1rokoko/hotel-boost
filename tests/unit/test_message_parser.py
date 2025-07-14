"""
Unit tests for message parser
"""

import pytest
from app.utils.message_parser import MessageParser, parse_whatsapp_message


class TestMessageParser:
    """Test message parser functionality"""
    
    @pytest.fixture
    def parser(self):
        """Create message parser instance"""
        return MessageParser()
    
    def test_clean_content(self, parser):
        """Test content cleaning"""
        # Test whitespace normalization
        content = "  Hello   world  \n\n  "
        cleaned = parser._clean_content(content)
        assert cleaned == "Hello world"
        
        # Test formatting removal
        content = "*Bold* _italic_ ~strikethrough~"
        cleaned = parser._clean_content(content)
        assert cleaned == "Bold italic strikethrough"
        
        # Test empty content
        assert parser._clean_content("") == ""
        assert parser._clean_content(None) == ""
    
    def test_extract_data(self, parser):
        """Test data extraction from message"""
        content = "My email is test@example.com and phone is +1234567890. Visit https://example.com"
        
        extracted = parser._extract_data(content)
        
        assert "email" in extracted
        assert "test@example.com" in extracted["email"]
        
        assert "phone" in extracted
        assert "+1234567890" in extracted["phone"]
        
        assert "url" in extracted
        assert "https://example.com" in extracted["url"]
    
    def test_detect_intent_booking(self, parser):
        """Test booking intent detection"""
        content = "I want to book a room for tomorrow"
        intent = parser._detect_intent(content)
        assert intent == "booking"
        
        content = "Do you have availability for check-in?"
        intent = parser._detect_intent(content)
        assert intent == "booking"
    
    def test_detect_intent_complaint(self, parser):
        """Test complaint intent detection"""
        content = "I have a problem with my room, it's terrible"
        intent = parser._detect_intent(content)
        assert intent == "complaint"
        
        content = "This is awful, I'm very disappointed"
        intent = parser._detect_intent(content)
        assert intent == "complaint"
    
    def test_detect_intent_question(self, parser):
        """Test question intent detection"""
        content = "What time is breakfast served?"
        intent = parser._detect_intent(content)
        assert intent == "question"
        
        content = "How can I get to the airport?"
        intent = parser._detect_intent(content)
        assert intent == "question"
    
    def test_detect_intent_emergency(self, parser):
        """Test emergency intent detection"""
        content = "EMERGENCY! I need help immediately!"
        intent = parser._detect_intent(content)
        assert intent == "emergency"
        
        content = "This is urgent, please help"
        intent = parser._detect_intent(content)
        assert intent == "emergency"
    
    def test_detect_sentiment_indicators(self, parser):
        """Test sentiment indicator detection"""
        # Positive sentiment
        content = "Great service, I love this hotel!"
        indicators = parser._detect_sentiment_indicators(content)
        
        assert "positive" in indicators
        assert "great" in indicators["positive"]
        assert "love" in indicators["positive"]
        
        # Negative sentiment
        content = "This is terrible, I'm very disappointed"
        indicators = parser._detect_sentiment_indicators(content)
        
        assert "negative" in indicators
        assert "terrible" in indicators["negative"]
        assert "disappointed" in indicators["negative"]
    
    def test_assess_urgency_high(self, parser):
        """Test high urgency assessment"""
        content = "EMERGENCY! Fire in my room!"
        urgency = parser._assess_urgency(content)
        assert urgency == "high"
        
        content = "I need help immediately, this is urgent!"
        urgency = parser._assess_urgency(content)
        assert urgency == "high"
    
    def test_assess_urgency_medium(self, parser):
        """Test medium urgency assessment"""
        content = "I have a problem with my room, please fix it soon"
        urgency = parser._assess_urgency(content)
        assert urgency == "medium"
        
        content = "The air conditioning is not working!!!"
        urgency = parser._assess_urgency(content)
        assert urgency == "medium"
    
    def test_assess_urgency_low(self, parser):
        """Test low urgency assessment"""
        content = "What time is breakfast served?"
        urgency = parser._assess_urgency(content)
        assert urgency == "low"
        
        content = "Thank you for the great service"
        urgency = parser._assess_urgency(content)
        assert urgency == "low"
    
    def test_detect_language_english(self, parser):
        """Test English language detection"""
        content = "Hello, I need help with my booking"
        language = parser._detect_language(content)
        assert language == "en"
    
    def test_detect_language_spanish(self, parser):
        """Test Spanish language detection"""
        content = "Hola, necesito ayuda con mi habitación"
        language = parser._detect_language(content)
        assert language == "es"
    
    def test_detect_language_french(self, parser):
        """Test French language detection"""
        content = "Bonjour, j'ai besoin d'aide avec ma chambre"
        language = parser._detect_language(content)
        assert language == "fr"
    
    def test_parse_media_message_image(self, parser):
        """Test image message parsing"""
        message_data = {
            "typeMessage": "imageMessage",
            "imageMessageData": {
                "caption": "Beautiful sunset",
                "fileName": "sunset.jpg",
                "mimeType": "image/jpeg",
                "fileSize": 1024000
            }
        }
        
        parsed = parser._parse_media_message(message_data)
        
        assert parsed["media_type"] == "image"
        assert parsed["caption"] == "Beautiful sunset"
        assert parsed["file_name"] == "sunset.jpg"
        assert parsed["mime_type"] == "image/jpeg"
        assert parsed["file_size"] == 1024000
    
    def test_parse_media_message_location(self, parser):
        """Test location message parsing"""
        message_data = {
            "typeMessage": "locationMessage",
            "locationMessageData": {
                "latitude": 40.7128,
                "longitude": -74.0060,
                "nameLocation": "New York City",
                "address": "New York, NY, USA"
            }
        }
        
        parsed = parser._parse_media_message(message_data)
        
        assert parsed["media_type"] == "location"
        assert parsed["latitude"] == 40.7128
        assert parsed["longitude"] == -74.0060
        assert parsed["name"] == "New York City"
        assert parsed["address"] == "New York, NY, USA"
    
    def test_extract_booking_info(self, parser):
        """Test booking information extraction"""
        content = "My booking reference is ABC123456 for room 205 on 12/25/2023 at 3:00 PM"
        
        booking_info = parser.extract_booking_info(content)
        
        assert booking_info is not None
        assert "booking_reference" in booking_info
        assert booking_info["booking_reference"] == "ABC123456"
        
        assert "room_number" in booking_info
        assert booking_info["room_number"] == "205"
        
        assert "dates" in booking_info
        assert "12/25/2023" in booking_info["dates"]
        
        assert "times" in booking_info
        assert "3:00 PM" in booking_info["times"]
    
    def test_extract_booking_info_none(self, parser):
        """Test booking info extraction with no booking data"""
        content = "Hello, how are you today?"
        
        booking_info = parser.extract_booking_info(content)
        
        assert booking_info is None
    
    def test_is_automated_message(self, parser):
        """Test automated message detection"""
        # Automated message
        content = "This is an automated message. Your booking is confirmed. Do not reply."
        assert parser.is_automated_message(content) is True
        
        content = "System message: Your payment has been processed"
        assert parser.is_automated_message(content) is True
        
        # Human message
        content = "Hello, I need help with my room"
        assert parser.is_automated_message(content) is False
    
    def test_extract_contact_info(self, parser):
        """Test contact information extraction"""
        content = "Please contact me at john@example.com or call +1234567890"
        
        contact_info = parser.extract_contact_info(content)
        
        assert "emails" in contact_info
        assert "john@example.com" in contact_info["emails"]
        
        assert "phones" in contact_info
        assert "+1234567890" in contact_info["phones"]
    
    def test_parse_message_complete(self, parser):
        """Test complete message parsing"""
        content = "I have a problem with room 205. Please help urgently! My email is guest@example.com"
        message_data = {
            "typeMessage": "textMessage",
            "textMessageData": {
                "textMessage": content
            }
        }
        
        parsed = parser.parse_message(content, message_data)
        
        assert parsed["original_content"] == content
        assert parsed["cleaned_content"] == content  # No formatting to clean
        assert parsed["intent"] == "complaint"  # Should detect complaint
        assert parsed["urgency_level"] == "medium"  # Should detect urgency
        assert parsed["language"] == "en"  # Should detect English
        assert parsed["message_type"] == "textMessage"
        
        # Check extracted data
        extracted = parsed["extracted_data"]
        assert "email" in extracted
        assert "guest@example.com" in extracted["email"]
        assert "room_number" in extracted
        assert "205" in extracted["room_number"]
        
        # Check sentiment indicators
        sentiment = parsed["sentiment_indicators"]
        assert "negative" in sentiment
        assert "problem" in sentiment["negative"]


class TestMessageParserFunctions:
    """Test module-level parser functions"""
    
    def test_parse_whatsapp_message(self):
        """Test parse_whatsapp_message function"""
        content = "Hello, I need help!"
        message_data = {"typeMessage": "textMessage"}
        
        result = parse_whatsapp_message(content, message_data)
        
        assert "original_content" in result
        assert "intent" in result
        assert "urgency_level" in result
        assert result["original_content"] == content


if __name__ == "__main__":
    pytest.main([__file__])
