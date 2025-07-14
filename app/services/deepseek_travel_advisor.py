"""
DeepSeek Travel Advisor Service
Provides personalized travel recommendations based on guest profiles and travel memory
"""

import json
import uuid
from typing import Dict, List, Optional, Any
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.core.logging import get_logger
from app.services.deepseek_client import DeepSeekClient
from app.services.conversation_memory import ConversationMemory
from app.models.guest import Guest
from app.models.hotel import Hotel

logger = get_logger(__name__)


class TravelAdvisorService:
    """Service for providing personalized travel recommendations"""
    
    def __init__(self, db: Session):
        self.db = db
        self.deepseek_client = DeepSeekClient()
        self.memory = ConversationMemory()
        self.logger = logger.bind(service="travel_advisor")
        
        # Travel advisor conversation flow
        self.conversation_flow = {
            "greeting": {
                "message": "Здравствуйте! Я могу улучшить ваш отпуск на 50% больше эмоций и впечатлений бесплатно. У меня есть лучшие варианты как провести время. Хотите узнать?",
                "next_step": "get_visit_frequency"
            },
            "get_visit_frequency": {
                "message": "Отлично! Скажите, какой раз вы на Пхукете?",
                "options": ["Первый раз", "2-3 раза", "Более 3 раз", "Живу здесь"],
                "next_step": "get_travel_companions"
            },
            "get_travel_companions": {
                "message": "Понятно! А с кем вы приехали?",
                "options": ["Один/одна", "С партнером/девушкой", "Мы 40+", "С детьми", "Компанией друзей"],
                "next_step": "get_interests"
            },
            "get_interests": {
                "message": "Замечательно! Что вас больше всего интересует?",
                "options": ["Пляжи и релакс", "Ночная жизнь", "Культура и храмы", "Активный отдых", "Гастрономия"],
                "next_step": "provide_recommendations"
            }
        }
        
        # Travel recommendations database
        self.travel_database = {
            "first_time": {
                "solo": [
                    "Патонг Бич - центр ночной жизни, много баров и клубов",
                    "Биг Будда - обязательно к посещению, красивые виды",
                    "Старый город Пхукета - аутентичная архитектура",
                    "Смотровая площадка Промтеп - лучшие закаты"
                ],
                "couple": [
                    "Ката Бич - романтичный пляж для пар",
                    "Ужин на пляже Сурин - романтическая атмосфера",
                    "Спа-процедуры в отеле - расслабление вдвоем",
                    "Прогулка по Старому городу - красивые фото"
                ],
                "family": [
                    "Аквариум Пхукета - интересно детям",
                    "Зоопарк Пхукета - животные и шоу",
                    "Пляж Карон - безопасный для детей",
                    "Парк развлечений Splash Jungle"
                ],
                "mature": [
                    "Храм Ват Чалонг - духовное место",
                    "Музей Пхукета - история острова",
                    "Спа-центры - оздоровительные процедуры",
                    "Рынок выходного дня - местная культура"
                ]
            },
            "experienced": {
                "solo": [
                    "Остров Джеймса Бонда - менее туристический",
                    "Национальный парк Као Сок - джунгли",
                    "Дайвинг на Симиланских островах",
                    "Мотопоездка по горам"
                ],
                "couple": [
                    "Частный остров Корал - уединение",
                    "Ужин на яхте - эксклюзивно",
                    "Спа на природе - уникальный опыт",
                    "Фотосессия на скрытых пляжах"
                ],
                "family": [
                    "Рафтинг по реке - приключения",
                    "Ферма слонов - этичное взаимодействие",
                    "Кулинарные мастер-классы",
                    "Рыбалка с детьми"
                ],
                "mature": [
                    "Медитация в храмах",
                    "Традиционный тайский массаж",
                    "Гольф-клубы премиум класса",
                    "Винные дегустации"
                ]
            }
        }
    
    async def start_travel_consultation(self, guest_id: uuid.UUID, hotel_id: uuid.UUID) -> Dict[str, Any]:
        """Start travel consultation for a guest"""
        try:
            # Get guest and hotel info
            guest = self.db.query(Guest).filter(Guest.id == guest_id).first()
            hotel = self.db.query(Hotel).filter(Hotel.id == hotel_id).first()
            
            if not guest or not hotel:
                raise ValueError("Guest or hotel not found")
            
            # Initialize conversation state
            conversation_id = f"travel_consult_{guest_id}_{datetime.utcnow().timestamp()}"
            
            await self.memory.store_context(
                conversation_id=conversation_id,
                key="guest_id",
                value=str(guest_id)
            )
            
            await self.memory.store_context(
                conversation_id=conversation_id,
                key="hotel_id", 
                value=str(hotel_id)
            )
            
            await self.memory.store_context(
                conversation_id=conversation_id,
                key="current_step",
                value="greeting"
            )
            
            # Get greeting message
            greeting = self.conversation_flow["greeting"]["message"]
            
            self.logger.info("Travel consultation started",
                           guest_id=str(guest_id),
                           hotel_id=str(hotel_id),
                           conversation_id=conversation_id)
            
            return {
                "conversation_id": conversation_id,
                "message": greeting,
                "step": "greeting",
                "guest_name": guest.name or "Гость"
            }
            
        except Exception as e:
            self.logger.error("Error starting travel consultation", error=str(e))
            raise
    
    async def process_travel_response(self, conversation_id: str, user_response: str) -> Dict[str, Any]:
        """Process user response in travel consultation"""
        try:
            # Get current conversation state
            current_step = await self.memory.get_context(conversation_id, "current_step")
            guest_id = await self.memory.get_context(conversation_id, "guest_id")
            
            if not current_step or not guest_id:
                raise ValueError("Invalid conversation state")
            
            # Store user response
            await self.memory.store_context(
                conversation_id=conversation_id,
                key=f"response_{current_step}",
                value=user_response
            )
            
            # Determine next step
            flow_step = self.conversation_flow.get(current_step)
            if not flow_step:
                raise ValueError(f"Unknown conversation step: {current_step}")
            
            next_step = flow_step.get("next_step")
            
            if next_step == "provide_recommendations":
                # Generate personalized recommendations
                return await self._generate_recommendations(conversation_id)
            else:
                # Continue conversation flow
                next_flow = self.conversation_flow.get(next_step)
                if not next_flow:
                    raise ValueError(f"Unknown next step: {next_step}")
                
                # Update conversation state
                await self.memory.store_context(
                    conversation_id=conversation_id,
                    key="current_step",
                    value=next_step
                )
                
                return {
                    "conversation_id": conversation_id,
                    "message": next_flow["message"],
                    "options": next_flow.get("options", []),
                    "step": next_step
                }
                
        except Exception as e:
            self.logger.error("Error processing travel response", 
                            conversation_id=conversation_id,
                            error=str(e))
            raise
    
    async def _generate_recommendations(self, conversation_id: str) -> Dict[str, Any]:
        """Generate personalized travel recommendations"""
        try:
            # Get all user responses
            visit_frequency = await self.memory.get_context(conversation_id, "response_get_visit_frequency")
            companions = await self.memory.get_context(conversation_id, "response_get_travel_companions")
            interests = await self.memory.get_context(conversation_id, "response_get_interests")
            guest_id = await self.memory.get_context(conversation_id, "guest_id")
            
            # Determine recommendation category
            experience_level = "first_time" if "первый" in visit_frequency.lower() else "experienced"
            
            companion_type = "solo"
            if "партнер" in companions.lower() or "девушк" in companions.lower():
                companion_type = "couple"
            elif "дет" in companions.lower():
                companion_type = "family"
            elif "40" in companions:
                companion_type = "mature"
            
            # Get base recommendations
            recommendations = self.travel_database.get(experience_level, {}).get(companion_type, [])
            
            # Use DeepSeek to personalize recommendations
            personalized_recs = await self._personalize_with_deepseek(
                recommendations, visit_frequency, companions, interests
            )
            
            # Store final recommendations
            await self.memory.store_context(
                conversation_id=conversation_id,
                key="final_recommendations",
                value=personalized_recs
            )
            
            await self.memory.store_context(
                conversation_id=conversation_id,
                key="current_step",
                value="completed"
            )
            
            self.logger.info("Travel recommendations generated",
                           conversation_id=conversation_id,
                           guest_id=guest_id,
                           experience_level=experience_level,
                           companion_type=companion_type)
            
            return {
                "conversation_id": conversation_id,
                "message": f"Отлично! Основываясь на ваших предпочтениях, вот мои персональные рекомендации:\n\n{personalized_recs}",
                "recommendations": personalized_recs,
                "step": "completed"
            }
            
        except Exception as e:
            self.logger.error("Error generating recommendations", 
                            conversation_id=conversation_id,
                            error=str(e))
            raise
    
    async def _personalize_with_deepseek(self, base_recommendations: List[str], 
                                       visit_frequency: str, companions: str, 
                                       interests: str) -> str:
        """Use DeepSeek to personalize recommendations"""
        try:
            prompt = f"""
            Ты - эксперт по туризму на Пхукете. Персонализируй следующие рекомендации:
            
            Базовые рекомендации:
            {chr(10).join(f"- {rec}" for rec in base_recommendations)}
            
            Профиль гостя:
            - Опыт посещения: {visit_frequency}
            - Компания: {companions}
            - Интересы: {interests}
            
            Создай персонализированный список из 4-5 рекомендаций с кратким описанием каждой (1-2 предложения).
            Используй дружелюбный тон и добавь практические советы.
            """
            
            response = await self.deepseek_client.generate_response(
                message=prompt,
                context={},
                max_tokens=500,
                temperature=0.8
            )
            
            return response.content if response else "Рекомендации временно недоступны"
            
        except Exception as e:
            self.logger.error("Error personalizing with DeepSeek", error=str(e))
            # Fallback to base recommendations
            return "\n".join(f"• {rec}" for rec in base_recommendations)
    
    async def handle_negative_sentiment(self, guest_id: uuid.UUID, hotel_id: uuid.UUID, 
                                      message_content: str, sentiment_score: float) -> Dict[str, Any]:
        """Handle negative sentiment detection"""
        try:
            # Get guest and hotel info
            guest = self.db.query(Guest).filter(Guest.id == guest_id).first()
            hotel = self.db.query(Hotel).filter(Hotel.id == hotel_id).first()
            
            if not guest or not hotel:
                raise ValueError("Guest or hotel not found")
            
            # Generate empathetic response with DeepSeek
            prompt = f"""
            Гость отеля выразил недовольство. Создай сочувствующий ответ и предложи решение.
            
            Сообщение гостя: {message_content}
            Уровень негатива: {sentiment_score}
            Отель: {hotel.name}
            Гость: {guest.name or 'Гость'}
            
            Ответ должен:
            1. Выразить искренние извинения
            2. Показать понимание проблемы
            3. Предложить конкретное решение
            4. Быть дружелюбным и профессиональным
            
            Ограничение: 2-3 предложения.
            """
            
            response = await self.deepseek_client.generate_response(
                message=prompt,
                context={},
                max_tokens=200,
                temperature=0.7
            )
            
            # Notify hotel staff
            staff_notification = {
                "guest_id": str(guest_id),
                "guest_name": guest.name or "Гость",
                "guest_phone": guest.phone,
                "hotel_id": str(hotel_id),
                "message": message_content,
                "sentiment_score": sentiment_score,
                "timestamp": datetime.utcnow().isoformat(),
                "priority": "high" if sentiment_score < -0.7 else "medium"
            }
            
            self.logger.warning("Negative sentiment detected - staff notified",
                              guest_id=str(guest_id),
                              hotel_id=str(hotel_id),
                              sentiment_score=sentiment_score)
            
            return {
                "response_message": response.content if response else "Извините за неудобства. Мы свяжемся с вами для решения проблемы.",
                "staff_notification": staff_notification,
                "requires_staff_attention": True
            }
            
        except Exception as e:
            self.logger.error("Error handling negative sentiment", error=str(e))
            raise
