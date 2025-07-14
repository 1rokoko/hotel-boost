"""
Unit tests for trigger API endpoints
"""

import pytest
import uuid
from datetime import datetime
from unittest.mock import Mock, patch
from fastapi.testclient import TestClient
from fastapi import status

from app.main import app
from app.services.trigger_service import (
    TriggerNotFoundError,
    TriggerValidationError,
    TriggerTemplateError
)
from app.schemas.trigger import TriggerResponse, TriggerListResponse
from app.schemas.trigger_config import TriggerStatistics


class TestTriggerAPI:
    """Test cases for Trigger API endpoints"""
    
    @pytest.fixture
    def client(self):
        """Test client"""
        return TestClient(app)
    
    @pytest.fixture
    def mock_hotel_id(self):
        """Mock hotel ID"""
        return uuid.uuid4()
    
    @pytest.fixture
    def sample_trigger_response(self, mock_hotel_id):
        """Sample trigger response"""
        return TriggerResponse(
            id=uuid.uuid4(),
            hotel_id=mock_hotel_id,
            name="Welcome Message",
            trigger_type="TIME_BASED",
            message_template="Welcome to {{ hotel.name }}!",
            conditions={
                "time_based": {
                    "schedule_type": "hours_after_checkin",
                    "hours_after": 2
                }
            },
            is_active=True,
            priority=1,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
    
    def test_create_trigger_success(self, client, mock_hotel_id, sample_trigger_response):
        """Test successful trigger creation"""
        trigger_data = {
            "name": "Welcome Message",
            "trigger_type": "TIME_BASED",
            "message_template": "Welcome to {{ hotel.name }}!",
            "conditions": {
                "time_based": {
                    "schedule_type": "hours_after_checkin",
                    "hours_after": 2
                }
            },
            "is_active": True,
            "priority": 1
        }
        
        with patch('app.api.v1.endpoints.triggers.get_current_tenant_id') as mock_tenant, \
             patch('app.api.v1.endpoints.triggers.get_trigger_service') as mock_service:
            
            mock_tenant.return_value = mock_hotel_id
            mock_service.return_value.create_trigger.return_value = sample_trigger_response
            
            response = client.post("/api/v1/triggers/", json=trigger_data)
            
            assert response.status_code == status.HTTP_201_CREATED
            data = response.json()
            assert data["name"] == "Welcome Message"
            assert data["trigger_type"] == "TIME_BASED"
    
    def test_create_trigger_validation_error(self, client, mock_hotel_id):
        """Test trigger creation with validation error"""
        trigger_data = {
            "name": "Invalid Trigger",
            "trigger_type": "TIME_BASED",
            "message_template": "{{ invalid syntax",
            "conditions": {
                "time_based": {
                    "schedule_type": "hours_after_checkin",
                    "hours_after": 2
                }
            }
        }
        
        with patch('app.api.v1.endpoints.triggers.get_current_tenant_id') as mock_tenant, \
             patch('app.api.v1.endpoints.triggers.get_trigger_service') as mock_service:
            
            mock_tenant.return_value = mock_hotel_id
            mock_service.return_value.create_trigger.side_effect = TriggerValidationError("Invalid template")
            
            response = client.post("/api/v1/triggers/", json=trigger_data)
            
            assert response.status_code == status.HTTP_400_BAD_REQUEST
            assert "Validation error" in response.json()["detail"]
    
    def test_get_trigger_success(self, client, mock_hotel_id, sample_trigger_response):
        """Test successful trigger retrieval"""
        trigger_id = sample_trigger_response.id
        
        with patch('app.api.v1.endpoints.triggers.get_current_tenant_id') as mock_tenant, \
             patch('app.api.v1.endpoints.triggers.get_trigger_service') as mock_service:
            
            mock_tenant.return_value = mock_hotel_id
            mock_service.return_value.get_trigger.return_value = sample_trigger_response
            
            response = client.get(f"/api/v1/triggers/{trigger_id}")
            
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["id"] == str(trigger_id)
            assert data["name"] == "Welcome Message"
    
    def test_get_trigger_not_found(self, client, mock_hotel_id):
        """Test trigger retrieval with non-existent trigger"""
        trigger_id = uuid.uuid4()
        
        with patch('app.api.v1.endpoints.triggers.get_current_tenant_id') as mock_tenant, \
             patch('app.api.v1.endpoints.triggers.get_trigger_service') as mock_service:
            
            mock_tenant.return_value = mock_hotel_id
            mock_service.return_value.get_trigger.side_effect = TriggerNotFoundError("Not found")
            
            response = client.get(f"/api/v1/triggers/{trigger_id}")
            
            assert response.status_code == status.HTTP_404_NOT_FOUND
            assert "Trigger not found" in response.json()["detail"]
    
    def test_update_trigger_success(self, client, mock_hotel_id, sample_trigger_response):
        """Test successful trigger update"""
        trigger_id = sample_trigger_response.id
        update_data = {
            "name": "Updated Welcome Message",
            "is_active": False
        }
        
        # Update the response to reflect changes
        updated_response = sample_trigger_response.copy()
        updated_response.name = "Updated Welcome Message"
        updated_response.is_active = False
        
        with patch('app.api.v1.endpoints.triggers.get_current_tenant_id') as mock_tenant, \
             patch('app.api.v1.endpoints.triggers.get_trigger_service') as mock_service:
            
            mock_tenant.return_value = mock_hotel_id
            mock_service.return_value.update_trigger.return_value = updated_response
            
            response = client.put(f"/api/v1/triggers/{trigger_id}", json=update_data)
            
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["name"] == "Updated Welcome Message"
            assert data["is_active"] is False
    
    def test_delete_trigger_success(self, client, mock_hotel_id):
        """Test successful trigger deletion"""
        trigger_id = uuid.uuid4()
        
        with patch('app.api.v1.endpoints.triggers.get_current_tenant_id') as mock_tenant, \
             patch('app.api.v1.endpoints.triggers.get_trigger_service') as mock_service:
            
            mock_tenant.return_value = mock_hotel_id
            mock_service.return_value.delete_trigger.return_value = True
            
            response = client.delete(f"/api/v1/triggers/{trigger_id}")
            
            assert response.status_code == status.HTTP_204_NO_CONTENT
    
    def test_list_triggers_success(self, client, mock_hotel_id, sample_trigger_response):
        """Test successful trigger listing"""
        trigger_list = TriggerListResponse(
            triggers=[sample_trigger_response],
            total=1,
            page=1,
            size=20
        )
        
        with patch('app.api.v1.endpoints.triggers.get_current_tenant_id') as mock_tenant, \
             patch('app.api.v1.endpoints.triggers.get_trigger_service') as mock_service:
            
            mock_tenant.return_value = mock_hotel_id
            mock_service.return_value.list_triggers.return_value = trigger_list
            
            response = client.get("/api/v1/triggers/")
            
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["total"] == 1
            assert len(data["triggers"]) == 1
            assert data["triggers"][0]["name"] == "Welcome Message"
    
    def test_list_triggers_with_filters(self, client, mock_hotel_id):
        """Test trigger listing with filters"""
        with patch('app.api.v1.endpoints.triggers.get_current_tenant_id') as mock_tenant, \
             patch('app.api.v1.endpoints.triggers.get_trigger_service') as mock_service:
            
            mock_tenant.return_value = mock_hotel_id
            mock_service.return_value.list_triggers.return_value = TriggerListResponse(
                triggers=[], total=0, page=1, size=20
            )
            
            response = client.get(
                "/api/v1/triggers/",
                params={
                    "trigger_type": "TIME_BASED",
                    "is_active": True,
                    "page": 1,
                    "size": 10
                }
            )
            
            assert response.status_code == status.HTTP_200_OK
            
            # Verify service was called with correct parameters
            mock_service.return_value.list_triggers.assert_called_once()
            call_kwargs = mock_service.return_value.list_triggers.call_args.kwargs
            assert call_kwargs["trigger_type"] == "TIME_BASED"
            assert call_kwargs["is_active"] is True
            assert call_kwargs["page"] == 1
            assert call_kwargs["size"] == 10
    
    def test_test_trigger_success(self, client, mock_hotel_id, sample_trigger_response):
        """Test successful trigger testing"""
        trigger_id = sample_trigger_response.id
        test_data = {
            "guest_data": {
                "name": "John Doe",
                "preferences": {"room_type": "suite"}
            },
            "dry_run": True
        }
        
        with patch('app.api.v1.endpoints.triggers.get_current_tenant_id') as mock_tenant, \
             patch('app.api.v1.endpoints.triggers.get_trigger_service') as mock_service, \
             patch('app.api.v1.endpoints.triggers.get_trigger_engine') as mock_engine:
            
            mock_tenant.return_value = mock_hotel_id
            mock_service.return_value.get_trigger.return_value = sample_trigger_response
            mock_engine.return_value.execute_trigger.return_value = {
                "success": True,
                "rendered_message": "Welcome to Test Hotel, John Doe!"
            }
            
            response = client.post(f"/api/v1/triggers/{trigger_id}/test", json=test_data)
            
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["success"] is True
            assert data["conditions_met"] is True
            assert "Welcome to Test Hotel" in data["rendered_message"]
    
    def test_get_trigger_statistics_success(self, client, mock_hotel_id):
        """Test successful trigger statistics retrieval"""
        stats = TriggerStatistics(
            total_triggers=10,
            active_triggers=8,
            inactive_triggers=2,
            triggers_by_type={"TIME_BASED": 5, "EVENT_BASED": 3, "CONDITION_BASED": 2},
            executions_last_24h=25,
            success_rate=95.0,
            avg_execution_time_ms=150.5
        )
        
        with patch('app.api.v1.endpoints.triggers.get_current_tenant_id') as mock_tenant, \
             patch('app.api.v1.endpoints.triggers.get_trigger_service') as mock_service:
            
            mock_tenant.return_value = mock_hotel_id
            mock_service.return_value.get_trigger_statistics.return_value = stats
            
            response = client.get("/api/v1/triggers/statistics")
            
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["total_triggers"] == 10
            assert data["active_triggers"] == 8
            assert data["success_rate"] == 95.0
    
    def test_validate_template_success(self, client, mock_hotel_id):
        """Test successful template validation"""
        template_data = {
            "template": "Welcome to {{ hotel.name }}, {{ guest.name }}!"
        }
        
        with patch('app.api.v1.endpoints.triggers.get_current_tenant_id') as mock_tenant, \
             patch('app.utils.template_renderer.TemplateRenderer') as mock_renderer_class:
            
            mock_tenant.return_value = mock_hotel_id
            mock_renderer = Mock()
            mock_renderer_class.return_value = mock_renderer
            mock_renderer.validate_template.return_value = Mock(
                is_valid=True,
                variables=[],
                errors=[],
                warnings=[]
            )
            
            response = client.post("/api/v1/triggers/validate-template", json=template_data)
            
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["is_valid"] is True
    
    def test_validate_template_invalid(self, client, mock_hotel_id):
        """Test template validation with invalid template"""
        template_data = {
            "template": "{{ invalid syntax"
        }
        
        with patch('app.api.v1.endpoints.triggers.get_current_tenant_id') as mock_tenant, \
             patch('app.utils.template_renderer.TemplateRenderer') as mock_renderer_class:
            
            mock_tenant.return_value = mock_hotel_id
            mock_renderer = Mock()
            mock_renderer_class.return_value = mock_renderer
            mock_renderer.validate_template.return_value = Mock(
                is_valid=False,
                variables=[],
                errors=["Unclosed variable expression"],
                warnings=[]
            )
            
            response = client.post("/api/v1/triggers/validate-template", json=template_data)
            
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["is_valid"] is False
            assert len(data["errors"]) > 0
    
    def test_bulk_operation_success(self, client, mock_hotel_id):
        """Test successful bulk operation"""
        operation_data = {
            "trigger_ids": [str(uuid.uuid4()), str(uuid.uuid4())],
            "operation": "activate"
        }
        
        with patch('app.api.v1.endpoints.triggers.get_current_tenant_id') as mock_tenant, \
             patch('app.api.v1.endpoints.triggers.get_trigger_service') as mock_service:
            
            mock_tenant.return_value = mock_hotel_id
            mock_service.return_value.update_trigger.return_value = Mock()
            
            response = client.post("/api/v1/triggers/bulk-operation", json=operation_data)
            
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["total_processed"] == 2
            assert len(data["successful"]) == 2
            assert len(data["failed"]) == 0
    
    def test_bulk_operation_partial_failure(self, client, mock_hotel_id):
        """Test bulk operation with partial failures"""
        trigger_ids = [str(uuid.uuid4()), str(uuid.uuid4())]
        operation_data = {
            "trigger_ids": trigger_ids,
            "operation": "delete"
        }
        
        with patch('app.api.v1.endpoints.triggers.get_current_tenant_id') as mock_tenant, \
             patch('app.api.v1.endpoints.triggers.get_trigger_service') as mock_service:
            
            mock_tenant.return_value = mock_hotel_id
            
            # First call succeeds, second fails
            mock_service.return_value.delete_trigger.side_effect = [
                True,
                TriggerNotFoundError("Not found")
            ]
            
            response = client.post("/api/v1/triggers/bulk-operation", json=operation_data)
            
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["total_processed"] == 2
            assert len(data["successful"]) == 1
            assert len(data["failed"]) == 1
