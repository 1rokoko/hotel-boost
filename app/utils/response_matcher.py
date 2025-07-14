"""
Response matcher utility for auto-response system
"""

import re
from typing import Dict, Any, List, Optional, Set, Tuple
from datetime import datetime
import structlog

from app.core.logging import get_logger

logger = get_logger(__name__)


class ResponseMatcher:
    """
    Utility for matching incoming messages against response patterns

    This class provides various matching algorithms for determining
    if messages should trigger automatic responses.
    """

    def __init__(self):
        """Initialize response matcher"""
        self.logger = logger.bind(service="response_matcher")

        # Common greeting patterns
        self.greeting_patterns = [
            r'\b(hello|hi|hey|good\s+(morning|afternoon|evening)|greetings)\b',
            r'\b(hola|buenos\s+(días|tardes|noches))\b',  # Spanish
            r'\b(привет|здравствуйте|добро\s+пожаловать)\b',  # Russian
            r'\b(bonjour|bonsoir|salut)\b'  # French
        ]

        # Common help/assistance patterns
        self.help_patterns = [
            r'\b(help|assist|support|problem|issue|trouble)\b',
            r'\b(ayuda|asistencia|problema)\b',  # Spanish
            r'\b(помощь|поддержка|проблема)\b',  # Russian
            r'\b(aide|assistance|problème)\b'  # French
        ]

        # Common complaint patterns
        self.complaint_patterns = [
            r'\b(complaint|complain|unhappy|dissatisfied|angry|frustrated)\b',
            r'\b(queja|quejarse|insatisfecho|enojado)\b',  # Spanish
            r'\b(жалоба|недоволен|расстроен)\b',  # Russian
            r'\b(plainte|mécontent|frustré)\b'  # French
        ]

        # Common booking patterns
        self.booking_patterns = [
            r'\b(book|booking|reservation|reserve|room|stay)\b',
            r'\b(reserva|reservación|habitación)\b',  # Spanish
            r'\b(бронирование|резерв|номер)\b',  # Russian
            r'\b(réservation|réserver|chambre)\b'  # French
        ]

    def match_keywords(
        self,
        message_content: str,
        keywords: List[str],
        match_type: str = "any",
        case_sensitive: bool = False
    ) -> Tuple[bool, List[str]]:
        """
        Match keywords in message content

        Args:
            message_content: Message text to search
            keywords: List of keywords to match
            match_type: 'any' or 'all' - whether any or all keywords must match
            case_sensitive: Whether matching should be case sensitive

        Returns:
            Tuple[bool, List[str]]: (match_found, matched_keywords)
        """
        if not message_content or not keywords:
            return False, []

        content = message_content if case_sensitive else message_content.lower()
        search_keywords = keywords if case_sensitive else [kw.lower() for kw in keywords]

        matched = []
        for keyword in search_keywords:
            if keyword in content:
                matched.append(keyword)

        if match_type == "all":
            success = len(matched) == len(keywords)
        else:  # "any"
            success = len(matched) > 0

        return success, matched

    def match_patterns(
        self,
        message_content: str,
        patterns: List[str],
        flags: int = re.IGNORECASE
    ) -> Tuple[bool, List[str]]:
        """
        Match regex patterns in message content

        Args:
            message_content: Message text to search
            patterns: List of regex patterns to match
            flags: Regex flags

        Returns:
            Tuple[bool, List[str]]: (match_found, matched_patterns)
        """
        if not message_content or not patterns:
            return False, []

        matched = []
        for pattern in patterns:
            try:
                if re.search(pattern, message_content, flags):
                    matched.append(pattern)
            except re.error as e:
                self.logger.warning(
                    "Invalid regex pattern",
                    pattern=pattern,
                    error=str(e)
                )

        return len(matched) > 0, matched

    def detect_intent(self, message_content: str) -> Dict[str, Any]:
        """
        Detect intent from message content using predefined patterns

        Args:
            message_content: Message text to analyze

        Returns:
            Dict[str, Any]: Intent detection results
        """
        if not message_content:
            return {"intent": "unknown", "confidence": 0.0, "patterns": []}

        results = {}

        # Check for greetings
        greeting_match, greeting_patterns = self.match_patterns(
            message_content, self.greeting_patterns
        )
        if greeting_match:
            results["greeting"] = {
                "confidence": 0.8,
                "patterns": greeting_patterns
            }

        # Check for help requests
        help_match, help_patterns = self.match_patterns(
            message_content, self.help_patterns
        )
        if help_match:
            results["help_request"] = {
                "confidence": 0.9,
                "patterns": help_patterns
            }

        # Check for complaints
        complaint_match, complaint_patterns = self.match_patterns(
            message_content, self.complaint_patterns
        )
        if complaint_match:
            results["complaint"] = {
                "confidence": 0.85,
                "patterns": complaint_patterns
            }

        # Check for booking inquiries
        booking_match, booking_patterns = self.match_patterns(
            message_content, self.booking_patterns
        )
        if booking_match:
            results["booking_inquiry"] = {
                "confidence": 0.75,
                "patterns": booking_patterns
            }

        # Determine primary intent
        if results:
            primary_intent = max(results.keys(), key=lambda k: results[k]["confidence"])
            return {
                "intent": primary_intent,
                "confidence": results[primary_intent]["confidence"],
                "patterns": results[primary_intent]["patterns"],
                "all_intents": results
            }

        return {"intent": "unknown", "confidence": 0.0, "patterns": []}