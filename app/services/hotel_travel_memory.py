"""
Hotel-Specific Travel Advisory Memory Service

This service manages travel advisory memory that is unique to each hotel,
allowing personalized recommendations based on hotel location and guest profiles.
"""

import uuid
import json
from typing import Dict, List, Any, Optional
from sqlalchemy.orm import Session
import structlog

from app.models.hotel import Hotel
from app.services.deepseek_client import get_hotel_deepseek_client

logger = structlog.get_logger(__name__)


class HotelTravelMemoryService:
    """Service for managing hotel-specific travel advisory memory"""
    
    def __init__(self, db: Session):
        self.db = db
        self.logger = logger
    
    def get_hotel_travel_memory(self, hotel_id: uuid.UUID) -> Dict[str, Any]:
        """
        Get travel advisory memory for a specific hotel
        
        Args:
            hotel_id: Hotel UUID
            
        Returns:
            Dict containing travel memory data
        """
        try:
            hotel = self.db.query(Hotel).filter(Hotel.id == hotel_id).first()
            if not hotel:
                raise ValueError(f"Hotel {hotel_id} not found")
            
            deepseek_settings = hotel.get_deepseek_settings()
            travel_memory = deepseek_settings.get("travel_memory", "")
            
            # Parse travel memory into structured format
            return self._parse_travel_memory(travel_memory)
            
        except Exception as e:
            self.logger.error("Error getting hotel travel memory", hotel_id=str(hotel_id), error=str(e))
            return self._get_default_travel_memory()
    
    def update_hotel_travel_memory(self, hotel_id: uuid.UUID, travel_memory: str) -> bool:
        """
        Update travel advisory memory for a specific hotel
        
        Args:
            hotel_id: Hotel UUID
            travel_memory: Travel memory content
            
        Returns:
            bool: Success status
        """
        try:
            hotel = self.db.query(Hotel).filter(Hotel.id == hotel_id).first()
            if not hotel:
                raise ValueError(f"Hotel {hotel_id} not found")
            
            # Update travel memory in hotel settings
            deepseek_settings = hotel.get_deepseek_settings()
            deepseek_settings["travel_memory"] = travel_memory
            hotel.update_deepseek_settings(deepseek_settings)
            
            self.db.commit()
            
            self.logger.info("Hotel travel memory updated", hotel_id=str(hotel_id))
            return True
            
        except Exception as e:
            self.logger.error("Error updating hotel travel memory", hotel_id=str(hotel_id), error=str(e))
            self.db.rollback()
            return False
    
    def get_personalized_recommendations(
        self, 
        hotel_id: uuid.UUID, 
        guest_profile: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Get personalized travel recommendations based on guest profile
        
        Args:
            hotel_id: Hotel UUID
            guest_profile: Guest information (visit_frequency, companion_type, interests)
            
        Returns:
            Dict containing personalized recommendations
        """
        try:
            travel_memory = self.get_hotel_travel_memory(hotel_id)
            
            # Extract guest profile information
            visit_frequency = guest_profile.get("visit_frequency", "first_time")
            companion_type = guest_profile.get("companion_type", "solo")
            interests = guest_profile.get("interests", [])
            
            # Get base recommendations from travel memory
            recommendations = self._get_recommendations_by_profile(
                travel_memory, visit_frequency, companion_type, interests
            )
            
            return {
                "recommendations": recommendations,
                "guest_profile": guest_profile,
                "hotel_id": str(hotel_id)
            }
            
        except Exception as e:
            self.logger.error("Error getting personalized recommendations", 
                            hotel_id=str(hotel_id), error=str(e))
            return {"recommendations": [], "error": str(e)}
    
    async def enhance_with_ai(
        self, 
        hotel_id: uuid.UUID, 
        recommendations: List[str], 
        guest_profile: Dict[str, Any]
    ) -> List[str]:
        """
        Enhance recommendations using DeepSeek AI
        
        Args:
            hotel_id: Hotel UUID
            recommendations: Base recommendations
            guest_profile: Guest profile information
            
        Returns:
            List of AI-enhanced recommendations
        """
        try:
            hotel = self.db.query(Hotel).filter(Hotel.id == hotel_id).first()
            if not hotel:
                return recommendations
            
            # Get hotel-specific DeepSeek client
            hotel_settings = hotel.get_deepseek_settings()
            deepseek_client = await get_hotel_deepseek_client(str(hotel_id), hotel_settings)
            
            # Create AI prompt for personalization
            prompt = self._create_personalization_prompt(recommendations, guest_profile)
            
            # Get AI response
            response = await deepseek_client.generate_response(prompt)
            
            if response and response.get("content"):
                enhanced_recommendations = self._parse_ai_recommendations(response["content"])
                return enhanced_recommendations
            
            return recommendations
            
        except Exception as e:
            self.logger.error("Error enhancing recommendations with AI", 
                            hotel_id=str(hotel_id), error=str(e))
            return recommendations
    
    def _parse_travel_memory(self, travel_memory: str) -> Dict[str, Any]:
        """Parse travel memory text into structured format"""
        if not travel_memory:
            return self._get_default_travel_memory()
        
        # Simple parsing logic - can be enhanced
        sections = {}
        current_section = None
        current_items = []
        
        for line in travel_memory.split('\n'):
            line = line.strip()
            if not line:
                continue
                
            # Check if it's a section header (contains ':' and is uppercase)
            if ':' in line and line.split(':')[0].isupper():
                # Save previous section
                if current_section:
                    sections[current_section] = current_items
                
                # Start new section
                current_section = line.split(':')[0].lower().replace(' ', '_')
                current_items = []
            elif line.startswith('-') or line.startswith('•'):
                # Add item to current section
                current_items.append(line[1:].strip())
        
        # Save last section
        if current_section:
            sections[current_section] = current_items
        
        return sections
    
    def _get_default_travel_memory(self) -> Dict[str, Any]:
        """Get default travel memory structure"""
        return {
            "first_time_visitors": [
                "Welcome package with local map and recommendations",
                "Guided tour of hotel facilities",
                "Introduction to local culture and customs"
            ],
            "returning_guests": [
                "Personalized welcome based on previous preferences",
                "New experiences since last visit",
                "Exclusive returning guest benefits"
            ],
            "families_with_children": [
                "Kid-friendly activities and attractions",
                "Safe swimming areas and playgrounds",
                "Family restaurants with children's menus"
            ],
            "couples": [
                "Romantic dining options",
                "Sunset viewing spots",
                "Couples spa treatments"
            ],
            "solo_travelers": [
                "Safe areas for solo exploration",
                "Group activities and tours",
                "Local meetup opportunities"
            ]
        }
    
    def _get_recommendations_by_profile(
        self, 
        travel_memory: Dict[str, Any], 
        visit_frequency: str, 
        companion_type: str, 
        interests: List[str]
    ) -> List[str]:
        """Get recommendations based on guest profile"""
        recommendations = []
        
        # Add recommendations based on visit frequency
        if visit_frequency == "first_time":
            recommendations.extend(travel_memory.get("first_time_visitors", []))
        else:
            recommendations.extend(travel_memory.get("returning_guests", []))
        
        # Add recommendations based on companion type
        companion_key = f"{companion_type}s" if not companion_type.endswith('s') else companion_type
        recommendations.extend(travel_memory.get(companion_key, []))
        
        # Add recommendations based on interests
        for interest in interests:
            interest_key = interest.lower().replace(' ', '_')
            recommendations.extend(travel_memory.get(interest_key, []))
        
        # Remove duplicates while preserving order
        seen = set()
        unique_recommendations = []
        for rec in recommendations:
            if rec not in seen:
                seen.add(rec)
                unique_recommendations.append(rec)
        
        return unique_recommendations
    
    def _create_personalization_prompt(
        self, 
        recommendations: List[str], 
        guest_profile: Dict[str, Any]
    ) -> str:
        """Create AI prompt for personalizing recommendations"""
        visit_frequency = guest_profile.get("visit_frequency", "first_time")
        companion_type = guest_profile.get("companion_type", "solo")
        interests = guest_profile.get("interests", [])
        
        prompt = f"""
        Please personalize these travel recommendations for a guest with the following profile:
        - Visit frequency: {visit_frequency}
        - Traveling: {companion_type}
        - Interests: {', '.join(interests) if interests else 'general tourism'}
        
        Base recommendations:
        {chr(10).join(f'- {rec}' for rec in recommendations)}
        
        Please provide 5-7 personalized, specific recommendations that would be most relevant 
        for this guest profile. Make them actionable and include specific details when possible.
        
        Format as a simple list with one recommendation per line starting with '-'.
        """
        
        return prompt
    
    def _parse_ai_recommendations(self, ai_response: str) -> List[str]:
        """Parse AI response into list of recommendations"""
        recommendations = []
        
        for line in ai_response.split('\n'):
            line = line.strip()
            if line.startswith('-') or line.startswith('•'):
                recommendations.append(line[1:].strip())
        
        return recommendations if recommendations else [ai_response.strip()]
