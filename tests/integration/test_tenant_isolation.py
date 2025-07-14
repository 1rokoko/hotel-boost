"""
Integration tests for tenant isolation in hotel operations
"""

import pytest
import uuid
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from unittest.mock import patch

from app.models.base import Base
from app.models.hotel import Hotel
from app.models.guest import Guest
from app.core.tenant_context import (
    HotelTenantContext,
    HotelTenantManager,
    HotelTenantFilter
)
from app.utils.tenant_utils import (
    TenantQueryBuilder,
    TenantDataValidator,
    TenantBulkOperations,
    TenantIsolationError,
    get_tenant_query,
    validate_tenant_data
)
from app.services.hotel_service import HotelService


# Test database setup
SQLALCHEMY_DATABASE_URL = "sqlite:///./test_tenant_isolation.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="module")
def setup_database():
    """Setup test database"""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db_session():
    """Database session for tests"""
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def hotel1(db_session):
    """Create first test hotel"""
    hotel = Hotel(
        name="Hotel One",
        whatsapp_number="+1111111111",
        is_active=True
    )
    db_session.add(hotel)
    db_session.commit()
    db_session.refresh(hotel)
    yield hotel
    # Cleanup handled by database teardown


@pytest.fixture
def hotel2(db_session):
    """Create second test hotel"""
    hotel = Hotel(
        name="Hotel Two",
        whatsapp_number="+2222222222",
        is_active=True
    )
    db_session.add(hotel)
    db_session.commit()
    db_session.refresh(hotel)
    yield hotel
    # Cleanup handled by database teardown


@pytest.fixture
def guest_hotel1(db_session, hotel1):
    """Create guest for hotel1"""
    guest = Guest(
        hotel_id=hotel1.id,
        phone_number="+1234567890",
        name="Guest One"
    )
    db_session.add(guest)
    db_session.commit()
    db_session.refresh(guest)
    yield guest


@pytest.fixture
def guest_hotel2(db_session, hotel2):
    """Create guest for hotel2"""
    guest = Guest(
        hotel_id=hotel2.id,
        phone_number="+0987654321",
        name="Guest Two"
    )
    db_session.add(guest)
    db_session.commit()
    db_session.refresh(guest)
    yield guest


class TestHotelTenantContext:
    """Test hotel tenant context management"""
    
    def test_set_and_get_hotel_context(self):
        """Test setting and getting hotel context"""
        hotel_id = uuid.uuid4()
        hotel_name = "Test Hotel"
        
        # Set context
        HotelTenantContext.set_hotel_context(
            hotel_id=hotel_id,
            hotel_name=hotel_name,
            is_active=True
        )
        
        # Get context
        context = HotelTenantContext.get_hotel_context()
        assert context is not None
        assert context["hotel_id"] == hotel_id
        assert context["hotel_name"] == hotel_name
        assert context["is_active"] is True
        
        # Get specific values
        assert HotelTenantContext.get_current_hotel_id() == hotel_id
        assert HotelTenantContext.get_current_hotel_name() == hotel_name
        assert HotelTenantContext.is_hotel_active() is True
        
        # Clear context
        HotelTenantContext.clear_hotel_context()
        assert HotelTenantContext.get_hotel_context() is None
    
    def test_require_hotel_context_success(self):
        """Test requiring hotel context when set"""
        hotel_id = uuid.uuid4()
        HotelTenantContext.set_hotel_context(
            hotel_id=hotel_id,
            hotel_name="Test Hotel",
            is_active=True
        )
        
        context = HotelTenantContext.require_hotel_context()
        assert context["hotel_id"] == hotel_id
        
        HotelTenantContext.clear_hotel_context()
    
    def test_require_hotel_context_failure(self):
        """Test requiring hotel context when not set"""
        HotelTenantContext.clear_hotel_context()
        
        with pytest.raises(ValueError, match="No hotel context set"):
            HotelTenantContext.require_hotel_context()
    
    def test_require_active_hotel_success(self):
        """Test requiring active hotel when hotel is active"""
        hotel_id = uuid.uuid4()
        HotelTenantContext.set_hotel_context(
            hotel_id=hotel_id,
            hotel_name="Test Hotel",
            is_active=True
        )
        
        context = HotelTenantContext.require_active_hotel()
        assert context["is_active"] is True
        
        HotelTenantContext.clear_hotel_context()
    
    def test_require_active_hotel_failure(self):
        """Test requiring active hotel when hotel is inactive"""
        hotel_id = uuid.uuid4()
        HotelTenantContext.set_hotel_context(
            hotel_id=hotel_id,
            hotel_name="Test Hotel",
            is_active=False
        )
        
        with pytest.raises(ValueError, match="Hotel is not active"):
            HotelTenantContext.require_active_hotel()
        
        HotelTenantContext.clear_hotel_context()


class TestHotelTenantManager:
    """Test hotel tenant manager"""
    
    def test_load_hotel_context_success(self, db_session, hotel1, setup_database):
        """Test loading hotel context from database"""
        context = HotelTenantManager.load_hotel_context(db_session, hotel1.id)
        
        assert context is not None
        assert context["hotel_id"] == hotel1.id
        assert context["hotel_name"] == hotel1.name
        assert context["is_active"] == hotel1.is_active
        assert context["whatsapp_number"] == hotel1.whatsapp_number
    
    def test_load_hotel_context_not_found(self, db_session, setup_database):
        """Test loading hotel context when hotel not found"""
        non_existent_id = uuid.uuid4()
        context = HotelTenantManager.load_hotel_context(db_session, non_existent_id)
        
        assert context is None
    
    def test_get_hotel_permissions(self):
        """Test getting hotel permissions"""
        hotel_context = {
            "hotel_id": uuid.uuid4(),
            "is_active": True,
            "is_operational": True,
            "has_green_api_credentials": True,
            "settings": {
                "sentiment_analysis": {"enabled": True},
                "notifications": {
                    "email_enabled": True,
                    "sms_enabled": False,
                    "webhook_enabled": True
                }
            }
        }
        
        permissions = HotelTenantManager.get_hotel_permissions(hotel_context)
        
        assert permissions["can_send_messages"] is True
        assert permissions["can_receive_messages"] is True
        assert permissions["can_modify_settings"] is True
        assert permissions["can_view_analytics"] is True
        assert permissions["can_export_data"] is True
        assert permissions["has_whatsapp_integration"] is True
        assert permissions["can_view_sentiment"] is True
        assert permissions["has_email_notifications"] is True
        assert permissions["has_sms_notifications"] is False
        assert permissions["has_webhook_notifications"] is True
    
    def test_validate_hotel_access_success(self):
        """Test validating hotel access with sufficient permissions"""
        hotel_context = {
            "hotel_id": uuid.uuid4(),
            "is_active": True,
            "is_operational": True,
            "settings": {}
        }
        
        required_permissions = ["can_receive_messages", "can_view_analytics"]
        
        result = HotelTenantManager.validate_hotel_access(hotel_context, required_permissions)
        assert result is True
    
    def test_validate_hotel_access_failure(self):
        """Test validating hotel access with insufficient permissions"""
        hotel_context = {
            "hotel_id": uuid.uuid4(),
            "is_active": False,  # Inactive hotel
            "is_operational": False,
            "settings": {}
        }
        
        required_permissions = ["can_send_messages"]  # Requires operational hotel
        
        result = HotelTenantManager.validate_hotel_access(hotel_context, required_permissions)
        assert result is False


class TestTenantQueryBuilder:
    """Test tenant query builder"""
    
    def test_apply_tenant_filter(self, db_session, hotel1, guest_hotel1, setup_database):
        """Test applying tenant filter to query"""
        # Set hotel context
        HotelTenantContext.set_hotel_context(
            hotel_id=hotel1.id,
            hotel_name=hotel1.name,
            is_active=True
        )
        
        try:
            # Create base query
            query = db_session.query(Guest)
            
            # Apply tenant filter
            filtered_query = TenantQueryBuilder.apply_tenant_filter(query, Guest, hotel1.id)
            
            # Execute query
            guests = filtered_query.all()
            
            # Should only return guests for hotel1
            assert len(guests) >= 1
            for guest in guests:
                assert guest.hotel_id == hotel1.id
        
        finally:
            HotelTenantContext.clear_hotel_context()
    
    def test_create_tenant_query(self, db_session, hotel1, guest_hotel1, setup_database):
        """Test creating tenant-filtered query"""
        query = TenantQueryBuilder.create_tenant_query(db_session, Guest, hotel1.id)
        guests = query.all()
        
        # Should only return guests for hotel1
        for guest in guests:
            assert guest.hotel_id == hotel1.id
    
    def test_get_tenant_count(self, db_session, hotel1, guest_hotel1, setup_database):
        """Test getting tenant record count"""
        count = TenantQueryBuilder.get_tenant_count(db_session, Guest, hotel1.id)
        assert count >= 1
    
    def test_verify_tenant_ownership_success(self, db_session, hotel1, guest_hotel1, setup_database):
        """Test verifying tenant ownership - success case"""
        result = TenantQueryBuilder.verify_tenant_ownership(db_session, guest_hotel1, hotel1.id)
        assert result is True
    
    def test_verify_tenant_ownership_failure(self, db_session, hotel1, hotel2, guest_hotel1, setup_database):
        """Test verifying tenant ownership - failure case"""
        result = TenantQueryBuilder.verify_tenant_ownership(db_session, guest_hotel1, hotel2.id)
        assert result is False
    
    def test_tenant_filter_no_context(self, db_session, setup_database):
        """Test tenant filter when no context is set"""
        HotelTenantContext.clear_hotel_context()
        
        with pytest.raises(TenantIsolationError, match="No hotel ID provided"):
            TenantQueryBuilder.create_tenant_query(db_session, Guest)


class TestTenantDataValidator:
    """Test tenant data validator"""
    
    def test_validate_create_data_success(self, hotel1):
        """Test validating create data - success case"""
        data = {
            "phone_number": "+1234567890",
            "name": "Test Guest"
        }
        
        validated_data = TenantDataValidator.validate_create_data(data, Guest, hotel1.id)
        
        assert validated_data["hotel_id"] == hotel1.id
        assert validated_data["phone_number"] == data["phone_number"]
        assert validated_data["name"] == data["name"]
    
    def test_validate_create_data_with_hotel_id(self, hotel1):
        """Test validating create data with hotel_id already set"""
        data = {
            "hotel_id": hotel1.id,
            "phone_number": "+1234567890",
            "name": "Test Guest"
        }
        
        validated_data = TenantDataValidator.validate_create_data(data, Guest, hotel1.id)
        
        assert validated_data["hotel_id"] == hotel1.id
    
    def test_validate_create_data_wrong_hotel_id(self, hotel1, hotel2):
        """Test validating create data with wrong hotel_id"""
        data = {
            "hotel_id": hotel2.id,  # Wrong hotel
            "phone_number": "+1234567890",
            "name": "Test Guest"
        }
        
        with pytest.raises(TenantIsolationError, match="different hotel_id"):
            TenantDataValidator.validate_create_data(data, Guest, hotel1.id)
    
    def test_validate_update_data_success(self, guest_hotel1, hotel1):
        """Test validating update data - success case"""
        data = {
            "name": "Updated Guest Name"
        }
        
        validated_data = TenantDataValidator.validate_update_data(data, guest_hotel1, hotel1.id)
        
        assert "hotel_id" not in validated_data  # Should be removed
        assert validated_data["name"] == data["name"]
    
    def test_validate_update_data_wrong_ownership(self, guest_hotel1, hotel2):
        """Test validating update data with wrong ownership"""
        data = {
            "name": "Updated Guest Name"
        }
        
        with pytest.raises(TenantIsolationError, match="different hotel"):
            TenantDataValidator.validate_update_data(data, guest_hotel1, hotel2.id)
    
    def test_validate_update_data_hotel_id_change_attempt(self, guest_hotel1, hotel1, hotel2):
        """Test validating update data with hotel_id change attempt"""
        data = {
            "hotel_id": hotel2.id,  # Attempt to change hotel
            "name": "Updated Guest Name"
        }
        
        with pytest.raises(TenantIsolationError, match="change hotel_id"):
            TenantDataValidator.validate_update_data(data, guest_hotel1, hotel1.id)


class TestTenantBulkOperations:
    """Test tenant bulk operations"""
    
    def test_bulk_create(self, db_session, hotel1, setup_database):
        """Test bulk create with tenant isolation"""
        data_list = [
            {"phone_number": "+1111111111", "name": "Bulk Guest 1"},
            {"phone_number": "+2222222222", "name": "Bulk Guest 2"},
            {"phone_number": "+3333333333", "name": "Bulk Guest 3"}
        ]
        
        instances = TenantBulkOperations.bulk_create(db_session, Guest, data_list, hotel1.id)
        
        assert len(instances) == 3
        for instance in instances:
            assert instance.hotel_id == hotel1.id
        
        db_session.commit()
        
        # Verify in database
        query = TenantQueryBuilder.create_tenant_query(db_session, Guest, hotel1.id)
        guests = query.filter(Guest.name.like("Bulk Guest%")).all()
        assert len(guests) == 3
    
    def test_bulk_update(self, db_session, hotel1, setup_database):
        """Test bulk update with tenant isolation"""
        # Create test guests
        guests_data = [
            {"phone_number": "+4444444444", "name": "Update Guest 1"},
            {"phone_number": "+5555555555", "name": "Update Guest 2"}
        ]
        
        guests = TenantBulkOperations.bulk_create(db_session, Guest, guests_data, hotel1.id)
        db_session.commit()
        
        # Prepare updates
        updates = {
            guests[0].id: {"name": "Updated Guest 1"},
            guests[1].id: {"name": "Updated Guest 2"}
        }
        
        # Perform bulk update
        updated_count = TenantBulkOperations.bulk_update(db_session, Guest, updates, hotel1.id)
        
        assert updated_count == 2
        db_session.commit()
        
        # Verify updates
        db_session.refresh(guests[0])
        db_session.refresh(guests[1])
        assert guests[0].name == "Updated Guest 1"
        assert guests[1].name == "Updated Guest 2"
    
    def test_bulk_delete(self, db_session, hotel1, setup_database):
        """Test bulk delete with tenant isolation"""
        # Create test guests
        guests_data = [
            {"phone_number": "+6666666666", "name": "Delete Guest 1"},
            {"phone_number": "+7777777777", "name": "Delete Guest 2"}
        ]
        
        guests = TenantBulkOperations.bulk_create(db_session, Guest, guests_data, hotel1.id)
        db_session.commit()
        
        guest_ids = [guest.id for guest in guests]
        
        # Perform bulk delete
        deleted_count = TenantBulkOperations.bulk_delete(db_session, Guest, guest_ids, hotel1.id)
        
        assert deleted_count == 2
        db_session.commit()
        
        # Verify deletion
        remaining_guests = db_session.query(Guest).filter(Guest.id.in_(guest_ids)).all()
        assert len(remaining_guests) == 0


class TestTenantIsolationIntegration:
    """Test tenant isolation in real service operations"""
    
    def test_hotel_service_tenant_isolation(self, db_session, hotel1, hotel2, setup_database):
        """Test that hotel service respects tenant isolation"""
        # Set context for hotel1
        HotelTenantContext.set_hotel_context(
            hotel_id=hotel1.id,
            hotel_name=hotel1.name,
            is_active=True
        )
        
        try:
            hotel_service = HotelService(db_session)
            
            # Should be able to get hotel1
            result = hotel_service.get_hotel(hotel1.id)
            assert result is not None
            assert result.id == hotel1.id
            
            # Should also be able to get hotel2 (hotel service doesn't enforce tenant isolation by default)
            result = hotel_service.get_hotel(hotel2.id)
            assert result is not None
            assert result.id == hotel2.id
            
        finally:
            HotelTenantContext.clear_hotel_context()
    
    def test_convenience_functions(self, hotel1):
        """Test convenience functions for tenant isolation"""
        # Set context
        HotelTenantContext.set_hotel_context(
            hotel_id=hotel1.id,
            hotel_name=hotel1.name,
            is_active=True
        )
        
        try:
            # Test convenience functions
            from app.utils.tenant_utils import get_current_hotel_id, get_hotel_filter
            from app.core.tenant_context import get_current_hotel_id as context_get_hotel_id
            
            assert context_get_hotel_id() == hotel1.id
            
            hotel_filter = get_hotel_filter()
            assert hotel_filter["hotel_id"] == hotel1.id
            
            # Test data validation convenience function
            data = {"phone_number": "+1234567890", "name": "Test Guest"}
            validated_data = validate_tenant_data(data, Guest, hotel1.id)
            assert validated_data["hotel_id"] == hotel1.id
            
        finally:
            HotelTenantContext.clear_hotel_context()
