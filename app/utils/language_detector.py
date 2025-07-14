"""
Enhanced language detection service for WhatsApp Hotel Bot
"""

import re
from typing import Dict, List, Optional, Tuple
from collections import Counter
import structlog

from app.core.logging import get_logger

logger = get_logger(__name__)


class LanguageDetector:
    """
    Enhanced language detection service

    Detects language from text using pattern matching and keyword analysis.
    Supports English, Spanish, Russian, and French.
    """

    def __init__(self):
        """Initialize language detector with patterns"""
        self.logger = logger.bind(service="language_detector")

        # Language patterns and keywords
        self.language_patterns = {
            'en': {
                'common_words': [
                    'the', 'and', 'is', 'in', 'to', 'of', 'a', 'that', 'it', 'with',
                    'for', 'as', 'was', 'on', 'are', 'you', 'this', 'be', 'at', 'by',
                    'hello', 'hi', 'thank', 'please', 'help', 'room', 'hotel', 'booking'
                ],
                'greetings': ['hello', 'hi', 'hey', 'good morning', 'good afternoon', 'good evening'],
                'patterns': [r'\b(hello|hi|hey|good\s+(morning|afternoon|evening))\b']
            },
            'es': {
                'common_words': [
                    'el', 'la', 'de', 'que', 'y', 'a', 'en', 'un', 'es', 'se',
                    'no', 'te', 'lo', 'le', 'da', 'su', 'por', 'son', 'con', 'para',
                    'hola', 'gracias', 'por favor', 'ayuda', 'habitación', 'hotel', 'reserva'
                ],
                'greetings': ['hola', 'buenos días', 'buenas tardes', 'buenas noches'],
                'patterns': [r'\b(hola|buenos\s+(días|tardes|noches))\b']
            },
            'ru': {
                'common_words': [
                    'и', 'в', 'не', 'на', 'я', 'быть', 'он', 'с', 'что', 'а',
                    'по', 'это', 'она', 'этот', 'к', 'но', 'они', 'мы', 'как', 'из',
                    'привет', 'спасибо', 'пожалуйста', 'помощь', 'номер', 'отель', 'бронирование'
                ],
                'greetings': ['привет', 'здравствуйте', 'добро пожаловать'],
                'patterns': [r'\b(привет|здравствуйте|добро\s+пожаловать)\b']
            },
            'fr': {
                'common_words': [
                    'le', 'de', 'et', 'à', 'un', 'il', 'être', 'et', 'en', 'avoir',
                    'que', 'pour', 'dans', 'ce', 'son', 'une', 'sur', 'avec', 'ne', 'se',
                    'bonjour', 'merci', 's\'il vous plaît', 'aide', 'chambre', 'hôtel', 'réservation'
                ],
                'greetings': ['bonjour', 'bonsoir', 'salut'],
                'patterns': [r'\b(bonjour|bonsoir|salut)\b']
            }
        }

        # Default language
        self.default_language = 'en'

        # Supported languages
        self.supported_languages = list(self.language_patterns.keys())

    def detect_language(self, text: str, confidence_threshold: float = 0.3) -> Tuple[str, float]:
        """
        Detect language from text

        Args:
            text: Text to analyze
            confidence_threshold: Minimum confidence threshold

        Returns:
            Tuple[str, float]: (language_code, confidence_score)
        """
        if not text or not text.strip():
            return self.default_language, 0.0

        text_lower = text.lower().strip()
        scores = {}

        # Calculate scores for each language
        for lang_code, patterns in self.language_patterns.items():
            score = self._calculate_language_score(text_lower, patterns)
            scores[lang_code] = score

        # Find best match
        best_language = max(scores.keys(), key=lambda k: scores[k])
        best_score = scores[best_language]

        # Apply confidence threshold
        if best_score < confidence_threshold:
            self.logger.debug(
                "Language detection confidence below threshold",
                text_preview=text[:50],
                best_language=best_language,
                best_score=best_score,
                threshold=confidence_threshold
            )
            return self.default_language, best_score

        self.logger.debug(
            "Language detected",
            text_preview=text[:50],
            detected_language=best_language,
            confidence=best_score,
            all_scores=scores
        )

        return best_language, best_score

    def _calculate_language_score(self, text: str, patterns: Dict) -> float:
        """
        Calculate language score for given text and patterns

        Args:
            text: Text to analyze (lowercase)
            patterns: Language patterns dictionary

        Returns:
            float: Language score (0.0 to 1.0)
        """
        score = 0.0
        total_checks = 0

        # Check common words
        words = re.findall(r'\b\w+\b', text)
        if words:
            common_words = patterns.get('common_words', [])
            word_matches = sum(1 for word in words if word in common_words)
            word_score = word_matches / len(words) if words else 0
            score += word_score * 0.6  # 60% weight for common words
            total_checks += 0.6

        # Check greeting patterns
        greeting_patterns = patterns.get('patterns', [])
        for pattern in greeting_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                score += 0.4  # 40% weight for greetings
                total_checks += 0.4
                break

        # Normalize score
        return score / total_checks if total_checks > 0 else 0.0

    def get_supported_languages(self) -> List[str]:
        """
        Get list of supported language codes

        Returns:
            List[str]: Supported language codes
        """
        return self.supported_languages.copy()

    def is_language_supported(self, language_code: str) -> bool:
        """
        Check if language is supported

        Args:
            language_code: Language code to check

        Returns:
            bool: True if language is supported
        """
        return language_code in self.supported_languages

    def get_language_name(self, language_code: str) -> str:
        """
        Get human-readable language name

        Args:
            language_code: Language code

        Returns:
            str: Language name
        """
        language_names = {
            'en': 'English',
            'es': 'Spanish',
            'ru': 'Russian',
            'fr': 'French'
        }
        return language_names.get(language_code, language_code.upper())