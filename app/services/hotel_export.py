"""
Hotel export service for exporting hotel configurations and data
"""

import csv
import json
import uuid
from typing import Dict, Any, List, Optional, Union, IO
from io import StringIO, BytesIO
from dataclasses import dataclass
from enum import Enum
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
import structlog

from app.models.hotel import Hotel
from app.services.hotel_service import HotelService
from app.schemas.hotel import HotelSearchParams
from app.utils.audit_logger import get_audit_logger, AuditAction, AuditResource
from app.core.tenant_context import get_current_hotel_id
from app.core.logging import get_logger

logger = get_logger(__name__)


class ExportFormat(Enum):
    """Supported export formats"""
    CSV = "csv"
    JSON = "json"
    EXCEL = "excel"


class ExportScope(Enum):
    """Export scope options"""
    SINGLE_HOTEL = "single_hotel"  # Export single hotel
    MULTIPLE_HOTELS = "multiple_hotels"  # Export multiple hotels
    ALL_HOTELS = "all_hotels"  # Export all hotels
    TENANT_HOTELS = "tenant_hotels"  # Export hotels for current tenant


@dataclass
class ExportResult:
    """Result of export operation"""
    success: bool
    record_count: int
    file_content: Union[str, bytes]
    file_name: str
    content_type: str
    file_size_bytes: int
    processing_time_seconds: float
    errors: List[str]
    warnings: List[str]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary (excluding file content)"""
        return {
            "success": self.success,
            "record_count": self.record_count,
            "file_name": self.file_name,
            "content_type": self.content_type,
            "file_size_bytes": self.file_size_bytes,
            "processing_time_seconds": self.processing_time_seconds,
            "errors": self.errors,
            "warnings": self.warnings
        }


class HotelExportService:
    """Service for exporting hotel data in various formats"""
    
    def __init__(self, db: Session):
        """
        Initialize hotel export service
        
        Args:
            db: Database session
        """
        self.db = db
        self.hotel_service = HotelService(db)
        self.audit_logger = get_audit_logger(db)
        self.logger = logger.bind(service="hotel_export_service")
    
    def export_hotels(
        self,
        export_format: ExportFormat,
        scope: ExportScope = ExportScope.ALL_HOTELS,
        hotel_ids: Optional[List[uuid.UUID]] = None,
        search_params: Optional[HotelSearchParams] = None,
        include_sensitive_data: bool = False,
        exported_by: Optional[str] = None,
        custom_fields: Optional[List[str]] = None
    ) -> ExportResult:
        """
        Export hotels in specified format
        
        Args:
            export_format: Export format
            scope: Export scope
            hotel_ids: Specific hotel IDs to export (for MULTIPLE_HOTELS scope)
            search_params: Search parameters for filtering hotels
            include_sensitive_data: Whether to include sensitive data (tokens, etc.)
            exported_by: User performing the export
            custom_fields: Custom fields to include in export
            
        Returns:
            ExportResult: Export operation result
        """
        import time
        start_time = time.time()
        
        try:
            # Get hotels to export
            hotels = self._get_hotels_for_export(scope, hotel_ids, search_params)
            
            if not hotels:
                return ExportResult(
                    success=False,
                    record_count=0,
                    file_content="",
                    file_name="",
                    content_type="",
                    file_size_bytes=0,
                    processing_time_seconds=time.time() - start_time,
                    errors=["No hotels found for export"],
                    warnings=[]
                )
            
            # Convert hotels to export data
            export_data = self._prepare_export_data(
                hotels,
                include_sensitive_data,
                custom_fields
            )
            
            # Generate file content
            if export_format == ExportFormat.CSV:
                file_content, content_type = self._generate_csv(export_data)
            elif export_format == ExportFormat.JSON:
                file_content, content_type = self._generate_json(export_data)
            else:
                raise ValueError(f"Unsupported export format: {export_format}")
            
            # Generate file name
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            file_name = f"hotels_export_{timestamp}.{export_format.value}"
            
            # Calculate file size
            file_size = len(file_content.encode('utf-8')) if isinstance(file_content, str) else len(file_content)
            
            processing_time = time.time() - start_time
            
            # Log export operation
            self.audit_logger.log_data_export(
                hotel_id=get_current_hotel_id(),
                export_type="hotel_data",
                exported_by=exported_by,
                record_count=len(hotels),
                file_format=export_format.value
            )
            
            self.logger.info(
                "Hotel export completed",
                format=export_format.value,
                scope=scope.value,
                record_count=len(hotels),
                file_size=file_size,
                processing_time=processing_time
            )
            
            return ExportResult(
                success=True,
                record_count=len(hotels),
                file_content=file_content,
                file_name=file_name,
                content_type=content_type,
                file_size_bytes=file_size,
                processing_time_seconds=processing_time,
                errors=[],
                warnings=[]
            )
            
        except Exception as e:
            processing_time = time.time() - start_time
            self.logger.error("Hotel export failed", error=str(e), processing_time=processing_time)
            
            return ExportResult(
                success=False,
                record_count=0,
                file_content="",
                file_name="",
                content_type="",
                file_size_bytes=0,
                processing_time_seconds=processing_time,
                errors=[f"Export failed: {str(e)}"],
                warnings=[]
            )
    
    def export_single_hotel(
        self,
        hotel_id: uuid.UUID,
        export_format: ExportFormat,
        include_sensitive_data: bool = False,
        exported_by: Optional[str] = None
    ) -> ExportResult:
        """
        Export a single hotel
        
        Args:
            hotel_id: Hotel UUID
            export_format: Export format
            include_sensitive_data: Whether to include sensitive data
            exported_by: User performing the export
            
        Returns:
            ExportResult: Export operation result
        """
        return self.export_hotels(
            export_format=export_format,
            scope=ExportScope.SINGLE_HOTEL,
            hotel_ids=[hotel_id],
            include_sensitive_data=include_sensitive_data,
            exported_by=exported_by
        )
    
    def _get_hotels_for_export(
        self,
        scope: ExportScope,
        hotel_ids: Optional[List[uuid.UUID]],
        search_params: Optional[HotelSearchParams]
    ) -> List[Hotel]:
        """Get hotels based on export scope"""
        try:
            if scope == ExportScope.SINGLE_HOTEL or scope == ExportScope.MULTIPLE_HOTELS:
                if not hotel_ids:
                    raise ValueError("Hotel IDs required for single/multiple hotel export")
                
                hotels = []
                for hotel_id in hotel_ids:
                    hotel = self.db.query(Hotel).filter(Hotel.id == hotel_id).first()
                    if hotel:
                        hotels.append(hotel)
                
                return hotels
            
            elif scope == ExportScope.ALL_HOTELS:
                if search_params:
                    # Use search parameters
                    result = self.hotel_service.search_hotels(search_params)
                    # Convert response objects back to model objects
                    hotel_ids = [uuid.UUID(h.id) for h in result.hotels]
                    return self.db.query(Hotel).filter(Hotel.id.in_(hotel_ids)).all()
                else:
                    return self.db.query(Hotel).all()
            
            elif scope == ExportScope.TENANT_HOTELS:
                current_hotel_id = get_current_hotel_id()
                if current_hotel_id:
                    # For tenant scope, export only the current hotel
                    hotel = self.db.query(Hotel).filter(Hotel.id == current_hotel_id).first()
                    return [hotel] if hotel else []
                else:
                    return []
            
            else:
                raise ValueError(f"Unsupported export scope: {scope}")
                
        except SQLAlchemyError as e:
            self.logger.error("Failed to get hotels for export", error=str(e))
            raise
    
    def _prepare_export_data(
        self,
        hotels: List[Hotel],
        include_sensitive_data: bool,
        custom_fields: Optional[List[str]]
    ) -> List[Dict[str, Any]]:
        """Prepare hotel data for export"""
        export_data = []
        
        for hotel in hotels:
            hotel_dict = {
                "id": str(hotel.id),
                "name": hotel.name,
                "whatsapp_number": hotel.whatsapp_number,
                "is_active": hotel.is_active,
                "created_at": hotel.created_at.isoformat() if hotel.created_at else None,
                "updated_at": hotel.updated_at.isoformat() if hotel.updated_at else None,
                "has_green_api_credentials": hotel.has_green_api_credentials,
                "is_operational": hotel.is_operational
            }
            
            # Include sensitive data if requested
            if include_sensitive_data:
                hotel_dict.update({
                    "green_api_instance_id": hotel.green_api_instance_id,
                    "green_api_token": hotel.green_api_token,
                    "green_api_webhook_token": hotel.green_api_webhook_token
                })
            
            # Include settings
            if hotel.settings:
                hotel_dict["settings"] = hotel.settings
            
            # Include custom fields if specified
            if custom_fields:
                for field in custom_fields:
                    if hasattr(hotel, field):
                        value = getattr(hotel, field)
                        # Convert UUID and datetime objects to strings
                        if isinstance(value, uuid.UUID):
                            value = str(value)
                        elif hasattr(value, 'isoformat'):
                            value = value.isoformat()
                        hotel_dict[field] = value
            
            export_data.append(hotel_dict)
        
        return export_data
    
    def _generate_csv(self, export_data: List[Dict[str, Any]]) -> tuple[str, str]:
        """Generate CSV content"""
        if not export_data:
            return "", "text/csv"
        
        output = StringIO()
        
        # Get all possible field names
        all_fields = set()
        for record in export_data:
            all_fields.update(record.keys())
        
        # Sort fields for consistent output
        fieldnames = sorted(all_fields)
        
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        
        for record in export_data:
            # Convert complex objects to JSON strings for CSV
            csv_record = {}
            for key, value in record.items():
                if isinstance(value, (dict, list)):
                    csv_record[key] = json.dumps(value)
                else:
                    csv_record[key] = value
            
            writer.writerow(csv_record)
        
        return output.getvalue(), "text/csv"
    
    def _generate_json(self, export_data: List[Dict[str, Any]]) -> tuple[str, str]:
        """Generate JSON content"""
        export_structure = {
            "export_info": {
                "timestamp": datetime.utcnow().isoformat(),
                "format": "json",
                "record_count": len(export_data)
            },
            "hotels": export_data
        }
        
        return json.dumps(export_structure, indent=2, default=str), "application/json"
    
    def get_export_template(self, export_format: ExportFormat) -> str:
        """
        Get export template showing available fields
        
        Args:
            export_format: Format type
            
        Returns:
            str: Template content
        """
        template_data = [{
            "id": "hotel-uuid-here",
            "name": "Example Hotel",
            "whatsapp_number": "+1234567890",
            "is_active": True,
            "created_at": "2023-01-01T00:00:00",
            "updated_at": "2023-01-01T00:00:00",
            "has_green_api_credentials": True,
            "is_operational": True,
            "green_api_instance_id": "instance123",
            "green_api_token": "token123",
            "green_api_webhook_token": "webhook123",
            "settings": {
                "notifications": {
                    "email_enabled": True
                }
            }
        }]
        
        if export_format == ExportFormat.CSV:
            content, _ = self._generate_csv(template_data)
            return content
        elif export_format == ExportFormat.JSON:
            content, _ = self._generate_json(template_data)
            return content
        else:
            raise ValueError(f"Template not available for format: {export_format}")
    
    def get_available_fields(self) -> List[Dict[str, Any]]:
        """
        Get list of available fields for export
        
        Returns:
            List[Dict[str, Any]]: Field information
        """
        return [
            {"name": "id", "type": "string", "description": "Hotel unique identifier", "sensitive": False},
            {"name": "name", "type": "string", "description": "Hotel name", "sensitive": False},
            {"name": "whatsapp_number", "type": "string", "description": "WhatsApp phone number", "sensitive": False},
            {"name": "is_active", "type": "boolean", "description": "Whether hotel is active", "sensitive": False},
            {"name": "created_at", "type": "datetime", "description": "Creation timestamp", "sensitive": False},
            {"name": "updated_at", "type": "datetime", "description": "Last update timestamp", "sensitive": False},
            {"name": "has_green_api_credentials", "type": "boolean", "description": "Whether Green API credentials are configured", "sensitive": False},
            {"name": "is_operational", "type": "boolean", "description": "Whether hotel can send/receive messages", "sensitive": False},
            {"name": "green_api_instance_id", "type": "string", "description": "Green API instance ID", "sensitive": True},
            {"name": "green_api_token", "type": "string", "description": "Green API token", "sensitive": True},
            {"name": "green_api_webhook_token", "type": "string", "description": "Green API webhook token", "sensitive": True},
            {"name": "settings", "type": "object", "description": "Hotel configuration settings", "sensitive": False}
        ]


# Dependency injection helper
def get_hotel_export_service(db: Session) -> HotelExportService:
    """
    Get hotel export service instance
    
    Args:
        db: Database session
        
    Returns:
        HotelExportService: Hotel export service instance
    """
    return HotelExportService(db)
