#!/usr/bin/env python3
"""
Minimal script to test hotel creation without any relationships
"""

import sys
import os

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, Column, String, Boolean, UUID, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.dialects.postgresql import JSONB
import uuid

Base = declarative_base()

class MinimalHotel(Base):
    """Minimal hotel model for testing"""
    __tablename__ = "hotels"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    whatsapp_number = Column(String(20), nullable=False, unique=True)
    green_api_instance_id = Column(String(50), nullable=True)
    green_api_token = Column(String(255), nullable=True)
    settings = Column(JSONB, nullable=False, default=dict)
    is_active = Column(Boolean, nullable=False, default=True)


def create_minimal_hotel():
    """Create a minimal hotel for testing"""
    
    # Create engine
    engine = create_engine("sqlite:///test_hotel.db", echo=True)
    
    # Create tables
    Base.metadata.create_all(engine)
    
    # Create session
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    
    try:
        # Check if hotel exists
        existing = session.query(MinimalHotel).filter(
            MinimalHotel.whatsapp_number == "+1234567890"
        ).first()
        
        if existing:
            print(f"✅ Hotel already exists: {existing.name}")
            return
        
        # Create hotel
        hotel = MinimalHotel(
            name="Minimal Test Hotel",
            whatsapp_number="+1234567890",
            green_api_instance_id="1234567890",
            green_api_token="test_token",
            settings={"test": "value"},
            is_active=True
        )
        
        session.add(hotel)
        session.commit()
        
        print(f"✅ Hotel created successfully!")
        print(f"   ID: {hotel.id}")
        print(f"   Name: {hotel.name}")
        print(f"   WhatsApp: {hotel.whatsapp_number}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    print("🚀 Creating minimal test hotel...")
    create_minimal_hotel()
