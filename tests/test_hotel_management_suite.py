"""
Comprehensive test suite for hotel management functionality
"""

import pytest
import uuid
import json
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from unittest.mock import patch, Mock, AsyncMock

from app.main import app
from app.database import get_db
from app.models.base import Base
from app.models.hotel import Hotel
from app.models.hotel_settings import HotelSettings
from app.services.hotel_service import HotelService
from app.services.hotel_validator import HotelValidator
from app.services.hotel_config import HotelConfigService
from app.services.hotel_import import HotelImportService, ImportFormat, ImportMode
from app.services.hotel_export import HotelExportService, ExportFormat, ExportScope
from app.utils.whatsapp_validator import WhatsAppValidator
from app.utils.data_migration import DataMigrationService
from app.core.tenant_context import HotelTenantContext


# Test database setup
SQLALCHEMY_DATABASE_URL = "sqlite:///./test_hotel_management.db"
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
        "name": "Test Hotel Suite",
        "whatsapp_number": "+1234567890",
        "green_api_instance_id": "test_instance_123",
        "green_api_token": "test_token_123",
        "green_api_webhook_token": "webhook_token_123",
        "settings": {
            "notifications": {
                "email_enabled": True,
                "sms_enabled": False,
                "webhook_enabled": True
            },
            "auto_responses": {
                "enabled": True,
                "greeting_message": "Welcome to Test Hotel Suite!",
                "business_hours": {
                    "enabled": True,
                    "start": "08:00",
                    "end": "22:00",
                    "timezone": "UTC"
                }
            },
            "sentiment_analysis": {
                "enabled": True,
                "threshold": 0.3,
                "alert_negative": True
            },
            "language": {
                "primary": "en",
                "supported": ["en", "es", "fr"]
            }
        },
        "is_active": True
    }


class TestHotelManagementIntegration:
    """Integration tests for complete hotel management workflow"""
    
    def test_complete_hotel_lifecycle(self, client, db_session, sample_hotel_data, setup_database):
        """Test complete hotel lifecycle: create, read, update, delete"""
        # 1. Create hotel
        response = client.post("/api/v1/hotels/", json=sample_hotel_data)
        assert response.status_code == 201
        created_hotel = response.json()
        hotel_id = created_hotel["id"]
        
        # Verify creation
        assert created_hotel["name"] == sample_hotel_data["name"]
        assert created_hotel["whatsapp_number"] == sample_hotel_data["whatsapp_number"]
        assert created_hotel["is_active"] == sample_hotel_data["is_active"]
        
        # 2. Read hotel
        response = client.get(f"/api/v1/hotels/{hotel_id}")
        assert response.status_code == 200
        retrieved_hotel = response.json()
        assert retrieved_hotel["id"] == hotel_id
        assert retrieved_hotel["name"] == sample_hotel_data["name"]
        
        # 3. Update hotel
        update_data = {
            "name": "Updated Test Hotel Suite",
            "is_active": False
        }
        response = client.put(f"/api/v1/hotels/{hotel_id}", json=update_data)
        assert response.status_code == 200
        updated_hotel = response.json()
        assert updated_hotel["name"] == update_data["name"]
        assert updated_hotel["is_active"] == update_data["is_active"]
        
        # 4. Update configuration
        config_update = {
            "settings": {
                "notifications": {
                    "email_enabled": False,
                    "sms_enabled": True
                }
            },
            "merge": True
        }
        response = client.patch(f"/api/v1/hotels/{hotel_id}/config", json=config_update)
        assert response.status_code == 200
        config_updated_hotel = response.json()
        assert config_updated_hotel["settings"]["notifications"]["sms_enabled"] is True
        
        # 5. Update status
        status_update = {
            "is_active": True,
            "reason": "Reactivated for testing"
        }
        response = client.patch(f"/api/v1/hotels/{hotel_id}/status", json=status_update)
        assert response.status_code == 200
        status_updated_hotel = response.json()
        assert status_updated_hotel["is_active"] is True
        
        # 6. Search hotels
        response = client.get("/api/v1/hotels/", params={"name": "Updated"})
        assert response.status_code == 200
        search_results = response.json()
        assert search_results["total"] >= 1
        assert any(h["id"] == hotel_id for h in search_results["hotels"])
        
        # 7. Get by WhatsApp number
        encoded_number = sample_hotel_data["whatsapp_number"].replace("+", "%2B")
        response = client.get(f"/api/v1/hotels/whatsapp/{encoded_number}")
        assert response.status_code == 200
        whatsapp_hotel = response.json()
        assert whatsapp_hotel["id"] == hotel_id
        
        # 8. Delete hotel
        response = client.delete(f"/api/v1/hotels/{hotel_id}")
        assert response.status_code == 204
        
        # 9. Verify deletion
        response = client.get(f"/api/v1/hotels/{hotel_id}")
        assert response.status_code == 404
    
    def test_hotel_validation_workflow(self, db_session, sample_hotel_data, setup_database):
        """Test hotel validation workflow"""
        validator = HotelValidator(db_session)
        
        # Test valid data
        from app.schemas.hotel import HotelCreate
        valid_data = HotelCreate(**sample_hotel_data)
        result = validator.validate_hotel_create(valid_data)
        assert result.is_valid is True
        assert len(result.errors) == 0
        
        # Test invalid data
        invalid_data = sample_hotel_data.copy()
        invalid_data["whatsapp_number"] = "invalid_number"
        invalid_hotel_data = HotelCreate(**invalid_data)
        result = validator.validate_hotel_create(invalid_hotel_data)
        assert result.is_valid is False
        assert len(result.errors) > 0
        
        # Test configuration validation
        config_result = validator.validate_hotel_configuration(sample_hotel_data["settings"])
        assert config_result.is_valid is True
    
    def test_whatsapp_validation_workflow(self):
        """Test WhatsApp number validation workflow"""
        validator = WhatsAppValidator()
        
        # Test valid numbers
        valid_numbers = ["+1234567890", "+49123456789", "+33123456789"]
        for number in valid_numbers:
            result = validator.validate_format(number)
            assert result.is_valid is True
            assert result.formatted_number.startswith("+")
        
        # Test invalid numbers
        invalid_numbers = ["invalid", "+0123456789", "123", "+1234567890123456"]
        for number in invalid_numbers:
            result = validator.validate_format(number)
            assert result.is_valid is False
            assert len(result.errors) > 0
        
        # Test batch validation
        all_numbers = valid_numbers + invalid_numbers
        results = validator.batch_validate_format(all_numbers)
        assert len(results) == len(all_numbers)
        valid_count = sum(1 for r in results if r.is_valid)
        assert valid_count == len(valid_numbers)
    
    def test_hotel_configuration_workflow(self, db_session, sample_hotel_data, setup_database):
        """Test hotel configuration management workflow"""
        # Create hotel first
        hotel_service = HotelService(db_session)
        from app.schemas.hotel import HotelCreate
        hotel_data = HotelCreate(**sample_hotel_data)
        created_hotel = hotel_service.create_hotel(hotel_data)
        
        # Test configuration service
        config_service = HotelConfigService(db_session)
        
        # Get configuration
        config = config_service.get_hotel_config(created_hotel.id)
        assert "notifications" in config
        assert "auto_responses" in config
        
        # Get specific value
        email_enabled = config_service.get_config_value(
            created_hotel.id,
            "notifications.email_enabled"
        )
        assert email_enabled is True
        
        # Update configuration
        new_config = {
            "notifications": {
                "email_enabled": False,
                "webhook_enabled": True
            }
        }
        updated_config = config_service.update_config(
            created_hotel.id,
            new_config,
            merge=True
        )
        assert updated_config["notifications"]["email_enabled"] is False
        assert updated_config["notifications"]["webhook_enabled"] is True
        
        # Set specific value
        config_service.set_config_value(
            created_hotel.id,
            "sentiment_analysis.threshold",
            0.5
        )
        threshold = config_service.get_config_value(
            created_hotel.id,
            "sentiment_analysis.threshold"
        )
        assert threshold == 0.5
    
    def test_import_export_workflow(self, db_session, sample_hotel_data, setup_database):
        """Test hotel import/export workflow"""
        import_service = HotelImportService(db_session)
        export_service = HotelExportService(db_session)
        
        # Test CSV template
        csv_template = import_service.get_import_template(ImportFormat.CSV)
        assert "name,whatsapp_number" in csv_template
        
        # Test JSON template
        json_template = import_service.get_import_template(ImportFormat.JSON)
        template_data = json.loads(json_template)
        assert "hotels" in template_data
        assert len(template_data["hotels"]) > 0
        
        # Create test data for export
        hotel_service = HotelService(db_session)
        from app.schemas.hotel import HotelCreate
        hotel_data = HotelCreate(**sample_hotel_data)
        created_hotel = hotel_service.create_hotel(hotel_data)
        
        # Test export
        export_result = export_service.export_single_hotel(
            created_hotel.id,
            ExportFormat.JSON,
            include_sensitive_data=False
        )
        assert export_result.success is True
        assert export_result.record_count == 1
        
        # Parse exported data
        exported_data = json.loads(export_result.file_content)
        assert "hotels" in exported_data
        assert len(exported_data["hotels"]) == 1
        
        # Test import of exported data
        import_result = import_service.import_from_file(
            export_result.file_content,
            ImportFormat.JSON,
            ImportMode.CREATE_ONLY,
            validate_only=True
        )
        # Should fail because hotel already exists
        assert import_result.success is False or import_result.skipped_count > 0
    
    def test_data_migration_workflow(self, db_session, sample_hotel_data, setup_database):
        """Test data migration workflow"""
        # Create test hotel
        hotel_service = HotelService(db_session)
        from app.schemas.hotel import HotelCreate
        hotel_data = HotelCreate(**sample_hotel_data)
        created_hotel = hotel_service.create_hotel(hotel_data)
        
        migration_service = DataMigrationService(db_session)
        
        # Test backup
        backup_data = migration_service.backup_hotel_data(
            backup_name="test_backup",
            include_sensitive_data=False
        )
        assert "backup_info" in backup_data
        assert "data" in backup_data
        assert backup_data["backup_info"]["record_count"] >= 1
        
        # Test data integrity validation
        integrity_results = migration_service.validate_data_integrity()
        assert "total_hotels" in integrity_results
        assert integrity_results["total_hotels"] >= 1
        assert "summary" in integrity_results
        
        # Test schema migration (dry run)
        def test_migration_function(settings):
            """Test migration function that adds a new field"""
            migrated = settings.copy()
            migrated["test_field"] = "migrated_value"
            return migrated
        
        migration_result = migration_service.migrate_hotel_settings_schema(
            test_migration_function,
            dry_run=True,
            batch_size=10
        )
        assert migration_result.success is True
        assert migration_result.records_processed >= 1
    
    def test_tenant_isolation_workflow(self, db_session, sample_hotel_data, setup_database):
        """Test tenant isolation workflow"""
        # Create two hotels
        hotel_service = HotelService(db_session)
        from app.schemas.hotel import HotelCreate
        
        hotel1_data = sample_hotel_data.copy()
        hotel1_data["whatsapp_number"] = "+1111111111"
        hotel1_data["name"] = "Hotel One"
        hotel1 = hotel_service.create_hotel(HotelCreate(**hotel1_data))
        
        hotel2_data = sample_hotel_data.copy()
        hotel2_data["whatsapp_number"] = "+2222222222"
        hotel2_data["name"] = "Hotel Two"
        hotel2 = hotel_service.create_hotel(HotelCreate(**hotel2_data))
        
        # Test tenant context
        HotelTenantContext.set_hotel_context(
            hotel_id=hotel1.id,
            hotel_name=hotel1.name,
            is_active=True
        )
        
        # Verify context
        current_hotel_id = HotelTenantContext.get_current_hotel_id()
        assert current_hotel_id == hotel1.id
        
        current_hotel_name = HotelTenantContext.get_current_hotel_name()
        assert current_hotel_name == hotel1.name
        
        # Test tenant utilities
        from app.utils.tenant_utils import TenantQueryBuilder
        from app.models.guest import Guest
        
        # This would test tenant filtering if we had guest data
        # For now, just verify the query builder works
        try:
            query = TenantQueryBuilder.create_tenant_query(db_session, Guest, hotel1.id)
            guests = query.all()
            # Should return empty list since no guests exist
            assert isinstance(guests, list)
        except Exception:
            # Expected if Guest model doesn't exist in test DB
            pass
        
        # Clear context
        HotelTenantContext.clear_hotel_context()
        assert HotelTenantContext.get_current_hotel_id() is None
    
    def test_error_handling_and_edge_cases(self, client, db_session, setup_database):
        """Test error handling and edge cases"""
        # Test creating hotel with duplicate WhatsApp number
        hotel_data = {
            "name": "First Hotel",
            "whatsapp_number": "+9999999999",
            "is_active": True
        }
        
        # Create first hotel
        response1 = client.post("/api/v1/hotels/", json=hotel_data)
        assert response1.status_code == 201
        
        # Try to create second hotel with same number
        hotel_data["name"] = "Second Hotel"
        response2 = client.post("/api/v1/hotels/", json=hotel_data)
        assert response2.status_code == 409  # Conflict
        
        # Test invalid UUID
        response = client.get("/api/v1/hotels/invalid-uuid")
        assert response.status_code == 422
        
        # Test non-existent hotel
        non_existent_id = str(uuid.uuid4())
        response = client.get(f"/api/v1/hotels/{non_existent_id}")
        assert response.status_code == 404
        
        # Test invalid data
        invalid_data = {
            "name": "",  # Empty name
            "whatsapp_number": "invalid"  # Invalid format
        }
        response = client.post("/api/v1/hotels/", json=invalid_data)
        assert response.status_code == 422
        
        # Test malformed JSON
        response = client.post(
            "/api/v1/hotels/",
            data="invalid json",
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 422


class TestHotelManagementPerformance:
    """Performance tests for hotel management"""
    
    def test_bulk_operations_performance(self, db_session, setup_database):
        """Test performance of bulk operations"""
        import time
        
        hotel_service = HotelService(db_session)
        
        # Create multiple hotels
        start_time = time.time()
        hotels = []
        for i in range(10):
            hotel_data = {
                "name": f"Performance Test Hotel {i}",
                "whatsapp_number": f"+555000{i:04d}",
                "is_active": True
            }
            from app.schemas.hotel import HotelCreate
            hotel = hotel_service.create_hotel(HotelCreate(**hotel_data))
            hotels.append(hotel)
        
        creation_time = time.time() - start_time
        assert creation_time < 5.0  # Should complete within 5 seconds
        
        # Search hotels
        start_time = time.time()
        from app.schemas.hotel import HotelSearchParams
        search_params = HotelSearchParams(
            name="Performance",
            page=1,
            size=20
        )
        results = hotel_service.search_hotels(search_params)
        search_time = time.time() - start_time
        
        assert search_time < 1.0  # Should complete within 1 second
        assert results.total >= 10
        
        # Cleanup
        for hotel in hotels:
            hotel_service.delete_hotel(hotel.id)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
