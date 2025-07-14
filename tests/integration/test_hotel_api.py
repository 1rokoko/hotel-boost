"""
Integration tests for hotel API endpoints
"""

import pytest
import uuid
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from unittest.mock import patch, Mock

from app.main import app
from app.database import get_db
from app.models.base import Base
from app.models.hotel import Hotel
from app.schemas.hotel import HotelCreate, HotelUpdate


# Test database setup
SQLALCHEMY_DATABASE_URL = "sqlite:///./test_hotel_api.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    """Override database dependency for testing"""
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(scope="module")
def setup_database():
    """Setup test database"""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client():
    """Test client"""
    return TestClient(app)


@pytest.fixture
def db_session():
    """Database session for tests"""
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def sample_hotel_data():
    """Sample hotel data for testing"""
    return {
        "name": "Test Hotel",
        "whatsapp_number": "+1234567890",
        "green_api_instance_id": "test_instance",
        "green_api_token": "test_token",
        "green_api_webhook_token": "webhook_token_123",
        "settings": {
            "notifications": {"email_enabled": True},
            "auto_responses": {"enabled": True}
        },
        "is_active": True
    }


@pytest.fixture
def created_hotel(db_session, sample_hotel_data):
    """Create a hotel in the database for testing"""
    hotel = Hotel(**sample_hotel_data)
    db_session.add(hotel)
    db_session.commit()
    db_session.refresh(hotel)
    yield hotel
    # Cleanup
    db_session.delete(hotel)
    db_session.commit()


class TestHotelAPIEndpoints:
    """Test hotel API endpoints"""
    
    def test_create_hotel_success(self, client, sample_hotel_data, setup_database):
        """Test successful hotel creation"""
        response = client.post("/api/v1/hotels/", json=sample_hotel_data)
        
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == sample_hotel_data["name"]
        assert data["whatsapp_number"] == sample_hotel_data["whatsapp_number"]
        assert data["is_active"] == sample_hotel_data["is_active"]
        assert "id" in data
        assert "created_at" in data
        assert "updated_at" in data
    
    def test_create_hotel_invalid_data(self, client, setup_database):
        """Test hotel creation with invalid data"""
        invalid_data = {
            "name": "",  # Empty name
            "whatsapp_number": "invalid_number"  # Invalid format
        }
        
        response = client.post("/api/v1/hotels/", json=invalid_data)
        
        assert response.status_code == 422  # Validation error
    
    def test_create_hotel_duplicate_whatsapp(self, client, created_hotel, setup_database):
        """Test hotel creation with duplicate WhatsApp number"""
        duplicate_data = {
            "name": "Another Hotel",
            "whatsapp_number": created_hotel.whatsapp_number,  # Same as existing
            "is_active": True
        }
        
        response = client.post("/api/v1/hotels/", json=duplicate_data)
        
        assert response.status_code == 409  # Conflict
        assert "already exists" in response.json()["detail"]
    
    def test_get_hotel_success(self, client, created_hotel, setup_database):
        """Test successful hotel retrieval"""
        response = client.get(f"/api/v1/hotels/{created_hotel.id}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(created_hotel.id)
        assert data["name"] == created_hotel.name
        assert data["whatsapp_number"] == created_hotel.whatsapp_number
    
    def test_get_hotel_not_found(self, client, setup_database):
        """Test hotel retrieval when hotel not found"""
        non_existent_id = uuid.uuid4()
        response = client.get(f"/api/v1/hotels/{non_existent_id}")
        
        assert response.status_code == 404
        assert "not found" in response.json()["detail"]
    
    def test_get_hotel_invalid_uuid(self, client, setup_database):
        """Test hotel retrieval with invalid UUID"""
        response = client.get("/api/v1/hotels/invalid-uuid")
        
        assert response.status_code == 422  # Validation error
    
    def test_update_hotel_success(self, client, created_hotel, setup_database):
        """Test successful hotel update"""
        update_data = {
            "name": "Updated Hotel Name",
            "is_active": False
        }
        
        response = client.put(f"/api/v1/hotels/{created_hotel.id}", json=update_data)
        
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == update_data["name"]
        assert data["is_active"] == update_data["is_active"]
        assert data["whatsapp_number"] == created_hotel.whatsapp_number  # Unchanged
    
    def test_update_hotel_not_found(self, client, setup_database):
        """Test hotel update when hotel not found"""
        non_existent_id = uuid.uuid4()
        update_data = {"name": "Updated Name"}
        
        response = client.put(f"/api/v1/hotels/{non_existent_id}", json=update_data)
        
        assert response.status_code == 404
        assert "not found" in response.json()["detail"]
    
    def test_delete_hotel_success(self, client, created_hotel, setup_database):
        """Test successful hotel deletion"""
        response = client.delete(f"/api/v1/hotels/{created_hotel.id}")
        
        assert response.status_code == 204
        
        # Verify hotel is deleted
        get_response = client.get(f"/api/v1/hotels/{created_hotel.id}")
        assert get_response.status_code == 404
    
    def test_delete_hotel_not_found(self, client, setup_database):
        """Test hotel deletion when hotel not found"""
        non_existent_id = uuid.uuid4()
        response = client.delete(f"/api/v1/hotels/{non_existent_id}")
        
        assert response.status_code == 404
        assert "not found" in response.json()["detail"]
    
    def test_search_hotels_success(self, client, created_hotel, setup_database):
        """Test successful hotel search"""
        response = client.get("/api/v1/hotels/", params={"name": "Test"})
        
        assert response.status_code == 200
        data = response.json()
        assert "hotels" in data
        assert "total" in data
        assert "page" in data
        assert "size" in data
        assert data["total"] >= 1
        assert len(data["hotels"]) >= 1
    
    def test_search_hotels_with_filters(self, client, created_hotel, setup_database):
        """Test hotel search with filters"""
        params = {
            "is_active": True,
            "page": 1,
            "size": 10,
            "sort_by": "name",
            "sort_order": "asc"
        }
        
        response = client.get("/api/v1/hotels/", params=params)
        
        assert response.status_code == 200
        data = response.json()
        assert data["page"] == 1
        assert data["size"] == 10
    
    def test_search_hotels_pagination(self, client, setup_database):
        """Test hotel search pagination"""
        # Test with page 2 and small size
        params = {"page": 2, "size": 1}
        response = client.get("/api/v1/hotels/", params=params)
        
        assert response.status_code == 200
        data = response.json()
        assert data["page"] == 2
        assert data["size"] == 1
    
    def test_get_active_hotels(self, client, created_hotel, setup_database):
        """Test getting active hotels"""
        response = client.get("/api/v1/hotels/active")
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        # Should include our created hotel if it's active
        if created_hotel.is_active:
            hotel_ids = [hotel["id"] for hotel in data]
            assert str(created_hotel.id) in hotel_ids
    
    def test_get_operational_hotels(self, client, created_hotel, setup_database):
        """Test getting operational hotels"""
        response = client.get("/api/v1/hotels/operational")
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        # Should include our created hotel if it's operational
        if created_hotel.is_operational:
            hotel_ids = [hotel["id"] for hotel in data]
            assert str(created_hotel.id) in hotel_ids
    
    def test_get_hotel_by_whatsapp_number(self, client, created_hotel, setup_database):
        """Test getting hotel by WhatsApp number"""
        # URL encode the + in the phone number
        encoded_number = created_hotel.whatsapp_number.replace("+", "%2B")
        response = client.get(f"/api/v1/hotels/whatsapp/{encoded_number}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(created_hotel.id)
        assert data["whatsapp_number"] == created_hotel.whatsapp_number
    
    def test_get_hotel_by_whatsapp_number_not_found(self, client, setup_database):
        """Test getting hotel by WhatsApp number when not found"""
        non_existent_number = "%2B9999999999"
        response = client.get(f"/api/v1/hotels/whatsapp/{non_existent_number}")
        
        assert response.status_code == 404
        assert "not found" in response.json()["detail"]
    
    def test_update_hotel_config(self, client, created_hotel, setup_database):
        """Test updating hotel configuration"""
        config_data = {
            "settings": {
                "notifications": {
                    "email_enabled": False,
                    "sms_enabled": True
                }
            },
            "merge": True
        }
        
        response = client.patch(f"/api/v1/hotels/{created_hotel.id}/config", json=config_data)
        
        assert response.status_code == 200
        data = response.json()
        assert data["settings"]["notifications"]["sms_enabled"] is True
    
    def test_update_hotel_config_not_found(self, client, setup_database):
        """Test updating hotel configuration when hotel not found"""
        non_existent_id = uuid.uuid4()
        config_data = {
            "settings": {"test": "value"},
            "merge": True
        }
        
        response = client.patch(f"/api/v1/hotels/{non_existent_id}/config", json=config_data)
        
        assert response.status_code == 404
        assert "not found" in response.json()["detail"]
    
    def test_update_hotel_status(self, client, created_hotel, setup_database):
        """Test updating hotel status"""
        status_data = {
            "is_active": False,
            "reason": "Maintenance"
        }
        
        response = client.patch(f"/api/v1/hotels/{created_hotel.id}/status", json=status_data)
        
        assert response.status_code == 200
        data = response.json()
        assert data["is_active"] is False
    
    def test_update_hotel_status_not_found(self, client, setup_database):
        """Test updating hotel status when hotel not found"""
        non_existent_id = uuid.uuid4()
        status_data = {
            "is_active": False,
            "reason": "Test"
        }
        
        response = client.patch(f"/api/v1/hotels/{non_existent_id}/status", json=status_data)
        
        assert response.status_code == 404
        assert "not found" in response.json()["detail"]


class TestHotelAPIErrorHandling:
    """Test error handling in hotel API"""
    
    def test_internal_server_error_handling(self, client, setup_database):
        """Test internal server error handling"""
        with patch('app.services.hotel_service.HotelService.create_hotel') as mock_create:
            mock_create.side_effect = Exception("Database connection failed")
            
            sample_data = {
                "name": "Test Hotel",
                "whatsapp_number": "+1234567890"
            }
            
            response = client.post("/api/v1/hotels/", json=sample_data)
            
            assert response.status_code == 500
            assert "Failed to create hotel" in response.json()["detail"]
    
    def test_validation_error_response_format(self, client, setup_database):
        """Test validation error response format"""
        invalid_data = {
            "name": "",  # Invalid: empty name
            "whatsapp_number": "invalid"  # Invalid: bad format
        }
        
        response = client.post("/api/v1/hotels/", json=invalid_data)
        
        assert response.status_code == 422
        error_data = response.json()
        assert "detail" in error_data
        assert isinstance(error_data["detail"], list)


class TestHotelAPIAuthentication:
    """Test authentication and authorization for hotel API"""
    
    @pytest.mark.skip(reason="Authentication not implemented yet")
    def test_unauthorized_access(self, client, setup_database):
        """Test unauthorized access to hotel endpoints"""
        # This test would be implemented when authentication is added
        pass
    
    @pytest.mark.skip(reason="Authorization not implemented yet")
    def test_insufficient_permissions(self, client, setup_database):
        """Test access with insufficient permissions"""
        # This test would be implemented when role-based access is added
        pass
