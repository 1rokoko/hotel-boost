"""
Language Detection Service
Automatically detects user language based on phone number and message content
"""

import re
import json
from typing import Dict, Optional, Tuple
from app.core.logging import get_logger
from app.services.green_api_client import GreenAPIClient

logger = get_logger(__name__)


class LanguageDetector:
    """Service for detecting user language from phone number and content"""
    
    def __init__(self):
        self.logger = logger.bind(service="language_detector")
        
        # Phone number country code to language mapping
        self.country_language_map = {
            # Russia and CIS
            "7": "ru",      # Russia, Kazakhstan
            "375": "ru",    # Belarus
            "380": "ru",    # Ukraine
            "374": "ru",    # Armenia
            "994": "ru",    # Azerbaijan
            "995": "ru",    # Georgia
            "996": "ru",    # Kyrgyzstan
            "992": "ru",    # Tajikistan
            "993": "ru",    # Turkmenistan
            "998": "ru",    # Uzbekistan
            "373": "ru",    # Moldova
            
            # Thailand
            "66": "th",     # Thailand
            
            # China
            "86": "zh",     # China
            
            # English speaking countries
            "1": "en",      # USA, Canada
            "44": "en",     # UK
            "61": "en",     # Australia
            "64": "en",     # New Zealand
            "27": "en",     # South Africa
            
            # European countries
            "49": "de",     # Germany
            "33": "fr",     # France
            "39": "it",     # Italy
            "34": "es",     # Spain
            "31": "nl",     # Netherlands
            "46": "sv",     # Sweden
            "47": "no",     # Norway
            "45": "da",     # Denmark
            "358": "fi",    # Finland
            "48": "pl",     # Poland
            
            # Asian countries
            "81": "ja",     # Japan
            "82": "ko",     # South Korea
            "91": "hi",     # India
            "62": "id",     # Indonesia
            "60": "ms",     # Malaysia
            "65": "en",     # Singapore
            "63": "en",     # Philippines
            "84": "vi",     # Vietnam
            
            # Middle East
            "971": "ar",    # UAE
            "966": "ar",    # Saudi Arabia
            "974": "ar",    # Qatar
            "965": "ar",    # Kuwait
            "973": "ar",    # Bahrain
            "968": "ar",    # Oman
            "972": "he",    # Israel
            "90": "tr",     # Turkey
            "98": "fa",     # Iran
            
            # Other
            "55": "pt",     # Brazil
            "52": "es",     # Mexico
            "54": "es",     # Argentina
        }
        
        # Language detection patterns for message content
        self.language_patterns = {
            "ru": [
                r'[а-яё]',  # Cyrillic characters
                r'\b(привет|здравствуй|спасибо|пожалуйста|да|нет|как дела)\b',
                r'\b(отель|номер|завтрак|ужин|пляж|море)\b'
            ],
            "en": [
                r'\b(hello|hi|thank|please|yes|no|how are you)\b',
                r'\b(hotel|room|breakfast|dinner|beach|sea)\b',
                r'\b(good|bad|nice|great|awesome)\b'
            ],
            "th": [
                r'[ก-๙]',  # Thai characters
                r'\b(สวัสดี|ขอบคุณ|ครับ|ค่ะ|ใช่|ไม่)\b',
                r'\b(โรงแรม|ห้อง|อาหาร|ชายหาด|ทะเล)\b'
            ],
            "zh": [
                r'[\u4e00-\u9fff]',  # Chinese characters
                r'\b(你好|谢谢|是|不是|酒店|房间)\b'
            ],
            "de": [
                r'\b(hallo|danke|bitte|ja|nein|wie geht)\b',
                r'\b(hotel|zimmer|frühstück|strand|meer)\b'
            ],
            "fr": [
                r'\b(bonjour|merci|sil vous plaît|oui|non|comment allez)\b',
                r'\b(hôtel|chambre|petit déjeuner|plage|mer)\b'
            ],
            "es": [
                r'\b(hola|gracias|por favor|sí|no|cómo está)\b',
                r'\b(hotel|habitación|desayuno|playa|mar)\b'
            ],
            "ar": [
                r'[\u0600-\u06ff]',  # Arabic characters
                r'\b(مرحبا|شكرا|نعم|لا|فندق|غرفة)\b'
            ]
        }
        
        # Default language priorities
        self.language_priorities = {
            "ru": 3,    # High priority for Russian tourists
            "en": 2,    # Medium priority for international
            "th": 1,    # Low priority for local
            "zh": 2,    # Medium priority for Chinese tourists
        }
    
    def detect_language_from_phone(self, phone_number: str) -> Optional[str]:
        """Detect language based on phone number country code"""
        try:
            # Clean phone number
            clean_phone = re.sub(r'[^\d+]', '', phone_number)
            
            # Remove leading + if present
            if clean_phone.startswith('+'):
                clean_phone = clean_phone[1:]
            
            # Try to match country codes (longest first)
            country_codes = sorted(self.country_language_map.keys(), key=len, reverse=True)
            
            for code in country_codes:
                if clean_phone.startswith(code):
                    language = self.country_language_map[code]
                    self.logger.debug("Language detected from phone",
                                    phone=phone_number,
                                    country_code=code,
                                    language=language)
                    return language
            
            self.logger.debug("No language detected from phone", phone=phone_number)
            return None
            
        except Exception as e:
            self.logger.error("Error detecting language from phone",
                            phone=phone_number,
                            error=str(e))
            return None
    
    def detect_language_from_content(self, message_content: str) -> Optional[str]:
        """Detect language based on message content"""
        try:
            if not message_content:
                return None
            
            content_lower = message_content.lower()
            language_scores = {}
            
            # Score each language based on pattern matches
            for lang, patterns in self.language_patterns.items():
                score = 0
                for pattern in patterns:
                    matches = len(re.findall(pattern, content_lower, re.IGNORECASE))
                    score += matches
                
                if score > 0:
                    language_scores[lang] = score
            
            if language_scores:
                # Get language with highest score
                detected_lang = max(language_scores, key=language_scores.get)
                self.logger.debug("Language detected from content",
                                content_preview=message_content[:50],
                                scores=language_scores,
                                detected=detected_lang)
                return detected_lang
            
            return None
            
        except Exception as e:
            self.logger.error("Error detecting language from content",
                            content=message_content[:50],
                            error=str(e))
            return None
    
    def detect_language(self, phone_number: str, message_content: str = None) -> Tuple[str, float]:
        """
        Detect language with confidence score
        
        Returns:
            Tuple[str, float]: (language_code, confidence_score)
        """
        try:
            detected_languages = []
            
            # Try phone number detection
            phone_lang = self.detect_language_from_phone(phone_number)
            if phone_lang:
                detected_languages.append((phone_lang, 0.8))  # High confidence from phone
            
            # Try content detection
            if message_content:
                content_lang = self.detect_language_from_content(message_content)
                if content_lang:
                    detected_languages.append((content_lang, 0.9))  # Very high confidence from content
            
            if not detected_languages:
                # Default to English with low confidence
                return "en", 0.3
            
            # If both methods agree, high confidence
            if len(detected_languages) == 2 and detected_languages[0][0] == detected_languages[1][0]:
                return detected_languages[0][0], 0.95
            
            # If only one method worked, use that
            if len(detected_languages) == 1:
                return detected_languages[0]
            
            # If methods disagree, prefer content over phone
            content_result = next((lang for lang, conf in detected_languages if conf == 0.9), None)
            if content_result:
                return content_result, 0.7
            
            # Fallback to phone detection
            return detected_languages[0]
            
        except Exception as e:
            self.logger.error("Error in language detection",
                            phone=phone_number,
                            content=message_content[:50] if message_content else None,
                            error=str(e))
            return "en", 0.3  # Default fallback
    
    async def get_language_from_green_api(self, phone_number: str, green_api_client: GreenAPIClient) -> Optional[str]:
        """Get additional language info from Green API if available"""
        try:
            # This would use Green API to get additional user info
            # For now, we'll use the phone number detection
            return self.detect_language_from_phone(phone_number)
            
        except Exception as e:
            self.logger.error("Error getting language from Green API",
                            phone=phone_number,
                            error=str(e))
            return None
    
    def get_language_name(self, language_code: str) -> str:
        """Get human-readable language name"""
        language_names = {
            "ru": "Русский",
            "en": "English", 
            "th": "ไทย",
            "zh": "中文",
            "de": "Deutsch",
            "fr": "Français",
            "es": "Español",
            "ar": "العربية",
            "ja": "日本語",
            "ko": "한국어",
            "hi": "हिन्दी",
            "pt": "Português",
            "it": "Italiano",
            "nl": "Nederlands",
            "sv": "Svenska",
            "no": "Norsk",
            "da": "Dansk",
            "fi": "Suomi",
            "pl": "Polski",
            "tr": "Türkçe",
            "he": "עברית",
            "fa": "فارسی",
            "vi": "Tiếng Việt",
            "id": "Bahasa Indonesia",
            "ms": "Bahasa Melayu"
        }
        return language_names.get(language_code, language_code.upper())
    
    def get_supported_languages(self) -> Dict[str, str]:
        """Get list of supported languages"""
        return {code: self.get_language_name(code) for code in self.language_patterns.keys()}
