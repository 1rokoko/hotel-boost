"""
Variable resolver for template system
"""

import uuid
from typing import Dict, Any, List, Optional, Union
from datetime import datetime, date, time
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import structlog

from app.models.hotel import Hotel
from app.models.guest import Guest
from app.models.message import Conversation, Message
from app.core.logging import get_logger

logger = get_logger(__name__)


class VariableResolverError(Exception):
    """Base exception for variable resolver errors"""
    pass


class VariableResolver:
    """
    Resolves template variables from various data sources

    This class extracts and resolves template variables from guest data,
    conversation context, hotel settings, and other sources.
    """

    def __init__(self, db_session: AsyncSession):
        """
        Initialize variable resolver

        Args:
            db_session: Database session
        """
        self.db = db_session
        self.logger = logger.bind(service="variable_resolver")

    async def resolve_context(
        self,
        base_context: Dict[str, Any],
        required_variables: List[str],
        hotel_id: Union[str, uuid.UUID]
    ) -> Dict[str, Any]:
        """
        Resolve template context with required variables

        Args:
            base_context: Base context provided by caller
            required_variables: List of variables needed by template
            hotel_id: Hotel ID for data resolution

        Returns:
            Dict[str, Any]: Resolved context with all variables
        """
        try:
            resolved_context = base_context.copy()

            # Add standard variables
            resolved_context.update(await self._get_standard_variables())

            # Resolve hotel-specific variables
            if any(var.startswith('hotel_') for var in required_variables):
                hotel_vars = await self._resolve_hotel_variables(hotel_id)
                resolved_context.update(hotel_vars)

            # Resolve guest-specific variables
            guest_id = base_context.get('guest_id')
            if guest_id and any(var.startswith('guest_') for var in required_variables):
                guest_vars = await self._resolve_guest_variables(guest_id, hotel_id)
                resolved_context.update(guest_vars)

            # Resolve conversation-specific variables
            conversation_id = base_context.get('conversation_id')
            if conversation_id and any(var.startswith('conversation_') for var in required_variables):
                conv_vars = await self._resolve_conversation_variables(conversation_id, hotel_id)
                resolved_context.update(conv_vars)

            # Resolve message-specific variables
            message_id = base_context.get('message_id')
            if message_id and any(var.startswith('message_') for var in required_variables):
                msg_vars = await self._resolve_message_variables(message_id, hotel_id)
                resolved_context.update(msg_vars)

            # Add fallback values for missing variables
            for var in required_variables:
                if var not in resolved_context:
                    resolved_context[var] = self._get_fallback_value(var)

            self.logger.debug(
                "Context resolved successfully",
                hotel_id=str(hotel_id),
                required_variables=required_variables,
                resolved_count=len(resolved_context)
            )

            return resolved_context

        except Exception as e:
            self.logger.error(
                "Error resolving context",
                hotel_id=str(hotel_id),
                required_variables=required_variables,
                error=str(e)
            )
            raise VariableResolverError(f"Failed to resolve context: {str(e)}")

    async def _get_standard_variables(self) -> Dict[str, Any]:
        """
        Get standard variables available to all templates

        Returns:
            Dict[str, Any]: Standard variables
        """
        now = datetime.now()
        return {
            'current_date': now.strftime('%Y-%m-%d'),
            'current_time': now.strftime('%H:%M'),
            'current_datetime': now.strftime('%Y-%m-%d %H:%M'),
            'current_year': now.year,
            'current_month': now.month,
            'current_day': now.day,
            'weekday': now.strftime('%A'),
            'month_name': now.strftime('%B')
        }

    async def _resolve_hotel_variables(self, hotel_id: Union[str, uuid.UUID]) -> Dict[str, Any]:
        """
        Resolve hotel-specific variables

        Args:
            hotel_id: Hotel ID

        Returns:
            Dict[str, Any]: Hotel variables
        """
        try:
            query = select(Hotel).where(Hotel.id == hotel_id)
            result = await self.db.execute(query)
            hotel = result.scalar_one_or_none()

            if not hotel:
                self.logger.warning("Hotel not found for variable resolution", hotel_id=str(hotel_id))
                return {}

            return {
                'hotel_name': hotel.name or 'Hotel',
                'hotel_phone': hotel.whatsapp_number or '',
                'hotel_id': str(hotel.id)
            }

        except Exception as e:
            self.logger.error(
                "Error resolving hotel variables",
                hotel_id=str(hotel_id),
                error=str(e)
            )
            return {}

    async def _resolve_guest_variables(
        self,
        guest_id: Union[str, uuid.UUID],
        hotel_id: Union[str, uuid.UUID]
    ) -> Dict[str, Any]:
        """
        Resolve guest-specific variables

        Args:
            guest_id: Guest ID
            hotel_id: Hotel ID for validation

        Returns:
            Dict[str, Any]: Guest variables
        """
        try:
            query = select(Guest).where(
                Guest.id == guest_id,
                Guest.hotel_id == hotel_id
            )
            result = await self.db.execute(query)
            guest = result.scalar_one_or_none()

            if not guest:
                self.logger.warning(
                    "Guest not found for variable resolution",
                    guest_id=str(guest_id),
                    hotel_id=str(hotel_id)
                )
                return {}

            # Extract preferences if available
            preferences = guest.preferences if isinstance(guest.preferences, dict) else {}

            return {
                'guest_name': guest.name or 'Guest',
                'guest_phone': guest.phone or '',
                'guest_language': guest.language or 'en',
                'guest_id': str(guest.id),
                'guest_preferences': preferences
            }

        except Exception as e:
            self.logger.error(
                "Error resolving guest variables",
                guest_id=str(guest_id),
                hotel_id=str(hotel_id),
                error=str(e)
            )
            return {}

    async def _resolve_conversation_variables(
        self,
        conversation_id: Union[str, uuid.UUID],
        hotel_id: Union[str, uuid.UUID]
    ) -> Dict[str, Any]:
        """
        Resolve conversation-specific variables

        Args:
            conversation_id: Conversation ID
            hotel_id: Hotel ID for validation

        Returns:
            Dict[str, Any]: Conversation variables
        """
        try:
            query = select(Conversation).where(
                Conversation.id == conversation_id,
                Conversation.hotel_id == hotel_id
            )
            result = await self.db.execute(query)
            conversation = result.scalar_one_or_none()

            if not conversation:
                self.logger.warning(
                    "Conversation not found for variable resolution",
                    conversation_id=str(conversation_id),
                    hotel_id=str(hotel_id)
                )
                return {}

            return {
                'conversation_id': str(conversation.id),
                'conversation_status': conversation.status or 'active',
                'conversation_started': conversation.created_at.strftime('%Y-%m-%d %H:%M') if conversation.created_at else '',
                'conversation_last_activity': conversation.updated_at.strftime('%Y-%m-%d %H:%M') if conversation.updated_at else ''
            }

        except Exception as e:
            self.logger.error(
                "Error resolving conversation variables",
                conversation_id=str(conversation_id),
                hotel_id=str(hotel_id),
                error=str(e)
            )
            return {}

    async def _resolve_message_variables(
        self,
        message_id: Union[str, uuid.UUID],
        hotel_id: Union[str, uuid.UUID]
    ) -> Dict[str, Any]:
        """
        Resolve message-specific variables

        Args:
            message_id: Message ID
            hotel_id: Hotel ID for validation

        Returns:
            Dict[str, Any]: Message variables
        """
        try:
            query = select(Message).where(
                Message.id == message_id,
                Message.hotel_id == hotel_id
            )
            result = await self.db.execute(query)
            message = result.scalar_one_or_none()

            if not message:
                self.logger.warning(
                    "Message not found for variable resolution",
                    message_id=str(message_id),
                    hotel_id=str(hotel_id)
                )
                return {}

            return {
                'message_id': str(message.id),
                'message_content': message.content or '',
                'message_type': message.message_type.value if message.message_type else 'text',
                'message_timestamp': message.created_at.strftime('%Y-%m-%d %H:%M') if message.created_at else '',
                'message_sentiment': message.sentiment_score or 0.0
            }

        except Exception as e:
            self.logger.error(
                "Error resolving message variables",
                message_id=str(message_id),
                hotel_id=str(hotel_id),
                error=str(e)
            )
            return {}

    def _get_fallback_value(self, variable_name: str) -> str:
        """
        Get fallback value for missing variables

        Args:
            variable_name: Name of the variable

        Returns:
            str: Fallback value
        """
        fallbacks = {
            'guest_name': 'Guest',
            'hotel_name': 'Hotel',
            'guest_phone': '',
            'hotel_phone': '',
            'room_number': '',
            'booking_id': '',
            'check_in_date': '',
            'check_out_date': '',
            'guest_language': 'en'
        }

        return fallbacks.get(variable_name, f'[{variable_name}]')

    async def generate_sample_context(
        self,
        required_variables: List[str],
        hotel_id: Union[str, uuid.UUID]
    ) -> Dict[str, Any]:
        """
        Generate sample context for template preview

        Args:
            required_variables: List of variables needed
            hotel_id: Hotel ID for real data where possible

        Returns:
            Dict[str, Any]: Sample context
        """
        try:
            sample_context = {}

            # Add standard variables
            sample_context.update(await self._get_standard_variables())

            # Add hotel variables if needed
            if any(var.startswith('hotel_') for var in required_variables):
                hotel_vars = await self._resolve_hotel_variables(hotel_id)
                sample_context.update(hotel_vars)

            # Add sample guest variables
            if any(var.startswith('guest_') for var in required_variables):
                sample_context.update({
                    'guest_name': 'John Doe',
                    'guest_phone': '+1234567890',
                    'guest_language': 'en',
                    'guest_preferences': {'room_type': 'deluxe', 'floor': 'high'}
                })

            # Add sample conversation variables
            if any(var.startswith('conversation_') for var in required_variables):
                sample_context.update({
                    'conversation_status': 'active',
                    'conversation_started': datetime.now().strftime('%Y-%m-%d %H:%M'),
                    'conversation_last_activity': datetime.now().strftime('%Y-%m-%d %H:%M')
                })

            # Add sample message variables
            if any(var.startswith('message_') for var in required_variables):
                sample_context.update({
                    'message_content': 'Hello, I need assistance with my booking.',
                    'message_type': 'text',
                    'message_timestamp': datetime.now().strftime('%Y-%m-%d %H:%M'),
                    'message_sentiment': 0.1
                })

            # Add sample booking variables
            if any(var.startswith('booking_') or var.startswith('room_') for var in required_variables):
                sample_context.update({
                    'booking_id': 'BK123456',
                    'room_number': '205',
                    'check_in_date': '2025-07-15',
                    'check_out_date': '2025-07-18',
                    'room_type': 'Deluxe Suite'
                })

            # Add fallback values for any missing variables
            for var in required_variables:
                if var not in sample_context:
                    sample_context[var] = self._get_fallback_value(var)

            self.logger.debug(
                "Sample context generated",
                hotel_id=str(hotel_id),
                required_variables=required_variables,
                sample_count=len(sample_context)
            )

            return sample_context

        except Exception as e:
            self.logger.error(
                "Error generating sample context",
                hotel_id=str(hotel_id),
                required_variables=required_variables,
                error=str(e)
            )
            # Return basic fallback context
            return {var: self._get_fallback_value(var) for var in required_variables}