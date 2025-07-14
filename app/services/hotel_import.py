"""
Hotel import service for importing hotel data from CSV/JSON
"""

import csv
import json
import uuid
from typing import Dict, Any, List, Optional, Union, IO, Tuple
from io import StringIO, BytesIO
from dataclasses import dataclass
from enum import Enum
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
import structlog

from app.models.hotel import Hotel
from app.schemas.hotel import HotelCreate
from app.services.hotel_service import HotelService, HotelServiceError, HotelAlreadyExistsError
from app.services.hotel_validator import HotelValidator, ValidationResult
from app.utils.audit_logger import get_audit_logger, AuditAction, AuditResource
from app.core.logging import get_logger

logger = get_logger(__name__)


class ImportFormat(Enum):
    """Supported import formats"""
    CSV = "csv"
    JSON = "json"
    EXCEL = "excel"


class ImportMode(Enum):
    """Import modes"""
    CREATE_ONLY = "create_only"  # Only create new hotels
    UPDATE_ONLY = "update_only"  # Only update existing hotels
    CREATE_OR_UPDATE = "create_or_update"  # Create new or update existing
    REPLACE = "replace"  # Replace all existing data


@dataclass
class ImportResult:
    """Result of import operation"""
    success: bool
    total_records: int
    created_count: int
    updated_count: int
    skipped_count: int
    error_count: int
    errors: List[Dict[str, Any]]
    warnings: List[Dict[str, Any]]
    processing_time_seconds: float
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "success": self.success,
            "total_records": self.total_records,
            "created_count": self.created_count,
            "updated_count": self.updated_count,
            "skipped_count": self.skipped_count,
            "error_count": self.error_count,
            "errors": self.errors,
            "warnings": self.warnings,
            "processing_time_seconds": self.processing_time_seconds
        }


class HotelImportService:
    """Service for importing hotel data from various formats"""
    
    def __init__(self, db: Session):
        """
        Initialize hotel import service
        
        Args:
            db: Database session
        """
        self.db = db
        self.hotel_service = HotelService(db)
        self.validator = HotelValidator(db)
        self.audit_logger = get_audit_logger(db)
        self.logger = logger.bind(service="hotel_import_service")
    
    def import_from_file(
        self,
        file_content: Union[str, bytes, IO],
        file_format: ImportFormat,
        import_mode: ImportMode = ImportMode.CREATE_OR_UPDATE,
        validate_only: bool = False,
        imported_by: Optional[str] = None,
        batch_size: int = 100
    ) -> ImportResult:
        """
        Import hotels from file
        
        Args:
            file_content: File content (string, bytes, or file-like object)
            file_format: Format of the file
            import_mode: Import mode
            validate_only: If True, only validate without importing
            imported_by: User performing the import
            batch_size: Number of records to process in each batch
            
        Returns:
            ImportResult: Import operation result
        """
        import time
        start_time = time.time()
        
        try:
            # Parse file content
            if file_format == ImportFormat.CSV:
                records = self._parse_csv(file_content)
            elif file_format == ImportFormat.JSON:
                records = self._parse_json(file_content)
            else:
                raise ValueError(f"Unsupported import format: {file_format}")
            
            # Process records
            result = self._process_records(
                records,
                import_mode,
                validate_only,
                imported_by,
                batch_size
            )
            
            # Calculate processing time
            result.processing_time_seconds = time.time() - start_time
            
            # Log import operation
            self.audit_logger.log_data_import(
                hotel_id=None,  # System-level operation
                import_type="hotel_data",
                imported_by=imported_by,
                record_count=result.total_records,
                file_format=file_format.value,
                success=result.success
            )
            
            self.logger.info(
                "Hotel import completed",
                format=file_format.value,
                mode=import_mode.value,
                validate_only=validate_only,
                total_records=result.total_records,
                created=result.created_count,
                updated=result.updated_count,
                errors=result.error_count,
                processing_time=result.processing_time_seconds
            )
            
            return result
            
        except Exception as e:
            processing_time = time.time() - start_time
            self.logger.error("Hotel import failed", error=str(e), processing_time=processing_time)
            
            return ImportResult(
                success=False,
                total_records=0,
                created_count=0,
                updated_count=0,
                skipped_count=0,
                error_count=1,
                errors=[{"error": f"Import failed: {str(e)}", "record": None}],
                warnings=[],
                processing_time_seconds=processing_time
            )
    
    def _parse_csv(self, file_content: Union[str, bytes, IO]) -> List[Dict[str, Any]]:
        """Parse CSV file content"""
        if isinstance(file_content, bytes):
            file_content = file_content.decode('utf-8')
        
        if hasattr(file_content, 'read'):
            content = file_content.read()
            if isinstance(content, bytes):
                content = content.decode('utf-8')
        else:
            content = file_content
        
        # Parse CSV
        csv_reader = csv.DictReader(StringIO(content))
        records = []
        
        for row_num, row in enumerate(csv_reader, start=2):  # Start at 2 (header is row 1)
            # Clean empty values
            cleaned_row = {k: v.strip() if v else None for k, v in row.items() if k}
            cleaned_row['_row_number'] = row_num
            records.append(cleaned_row)
        
        return records
    
    def _parse_json(self, file_content: Union[str, bytes, IO]) -> List[Dict[str, Any]]:
        """Parse JSON file content"""
        if isinstance(file_content, bytes):
            file_content = file_content.decode('utf-8')
        
        if hasattr(file_content, 'read'):
            content = file_content.read()
            if isinstance(content, bytes):
                content = content.decode('utf-8')
        else:
            content = file_content
        
        # Parse JSON
        data = json.loads(content)
        
        # Handle different JSON structures
        if isinstance(data, list):
            records = data
        elif isinstance(data, dict):
            if 'hotels' in data:
                records = data['hotels']
            elif 'data' in data:
                records = data['data']
            else:
                records = [data]  # Single hotel object
        else:
            raise ValueError("Invalid JSON structure")
        
        # Add row numbers for tracking
        for i, record in enumerate(records):
            record['_row_number'] = i + 1
        
        return records
    
    def _process_records(
        self,
        records: List[Dict[str, Any]],
        import_mode: ImportMode,
        validate_only: bool,
        imported_by: Optional[str],
        batch_size: int
    ) -> ImportResult:
        """Process import records"""
        total_records = len(records)
        created_count = 0
        updated_count = 0
        skipped_count = 0
        error_count = 0
        errors = []
        warnings = []
        
        # Process in batches
        for i in range(0, total_records, batch_size):
            batch = records[i:i + batch_size]
            
            for record in batch:
                try:
                    result = self._process_single_record(
                        record,
                        import_mode,
                        validate_only,
                        imported_by
                    )
                    
                    if result['action'] == 'created':
                        created_count += 1
                    elif result['action'] == 'updated':
                        updated_count += 1
                    elif result['action'] == 'skipped':
                        skipped_count += 1
                    
                    if result.get('warnings'):
                        warnings.extend(result['warnings'])
                        
                except Exception as e:
                    error_count += 1
                    errors.append({
                        "error": str(e),
                        "record": record,
                        "row_number": record.get('_row_number')
                    })
                    self.logger.error(
                        "Failed to process record",
                        record=record,
                        error=str(e)
                    )
            
            # Commit batch if not validate_only
            if not validate_only:
                try:
                    self.db.commit()
                except SQLAlchemyError as e:
                    self.db.rollback()
                    self.logger.error("Failed to commit batch", error=str(e))
                    # Mark all records in batch as errors
                    error_count += len(batch) - error_count
                    errors.append({
                        "error": f"Batch commit failed: {str(e)}",
                        "record": None,
                        "batch_start": i + 1,
                        "batch_end": min(i + batch_size, total_records)
                    })
        
        success = error_count == 0
        
        return ImportResult(
            success=success,
            total_records=total_records,
            created_count=created_count,
            updated_count=updated_count,
            skipped_count=skipped_count,
            error_count=error_count,
            errors=errors,
            warnings=warnings,
            processing_time_seconds=0.0  # Will be set by caller
        )
    
    def _process_single_record(
        self,
        record: Dict[str, Any],
        import_mode: ImportMode,
        validate_only: bool,
        imported_by: Optional[str]
    ) -> Dict[str, Any]:
        """Process a single import record"""
        row_number = record.get('_row_number', 'unknown')
        
        try:
            # Convert record to hotel data
            hotel_data = self._convert_record_to_hotel_data(record)
            
            # Validate hotel data
            validation_result = self.validator.validate_hotel_create(hotel_data)
            
            if not validation_result.is_valid:
                raise ValueError(f"Validation failed: {', '.join(validation_result.errors)}")
            
            warnings = []
            if validation_result.warnings:
                warnings = [{"warning": w, "row_number": row_number} for w in validation_result.warnings]
            
            if validate_only:
                return {"action": "validated", "warnings": warnings}
            
            # Check if hotel exists
            existing_hotel = self.hotel_service.get_hotel_by_whatsapp_number(hotel_data.whatsapp_number)
            
            if existing_hotel:
                if import_mode == ImportMode.CREATE_ONLY:
                    return {"action": "skipped", "reason": "Hotel already exists", "warnings": warnings}
                elif import_mode in [ImportMode.UPDATE_ONLY, ImportMode.CREATE_OR_UPDATE, ImportMode.REPLACE]:
                    # Update existing hotel
                    from app.schemas.hotel import HotelUpdate
                    update_data = HotelUpdate(
                        name=hotel_data.name,
                        green_api_instance_id=hotel_data.green_api_instance_id,
                        green_api_token=hotel_data.green_api_token,
                        green_api_webhook_token=hotel_data.green_api_webhook_token,
                        settings=hotel_data.settings,
                        is_active=hotel_data.is_active
                    )
                    
                    updated_hotel = self.hotel_service.update_hotel(existing_hotel.id, update_data)
                    
                    # Log audit
                    self.audit_logger.log_hotel_updated(
                        hotel_id=existing_hotel.id,
                        hotel_name=updated_hotel.name,
                        updated_by=imported_by,
                        updated_fields=["imported_data"],
                        new_values=hotel_data.dict()
                    )
                    
                    return {"action": "updated", "hotel_id": str(existing_hotel.id), "warnings": warnings}
            else:
                if import_mode == ImportMode.UPDATE_ONLY:
                    return {"action": "skipped", "reason": "Hotel does not exist", "warnings": warnings}
                else:
                    # Create new hotel
                    new_hotel = self.hotel_service.create_hotel(hotel_data)
                    
                    # Log audit
                    self.audit_logger.log_hotel_created(
                        hotel_id=new_hotel.id,
                        hotel_name=new_hotel.name,
                        created_by=imported_by,
                        details={"source": "import"}
                    )
                    
                    return {"action": "created", "hotel_id": str(new_hotel.id), "warnings": warnings}
                    
        except (HotelAlreadyExistsError, HotelServiceError) as e:
            raise ValueError(f"Hotel service error: {str(e)}")
        except Exception as e:
            raise ValueError(f"Processing error: {str(e)}")
    
    def _convert_record_to_hotel_data(self, record: Dict[str, Any]) -> HotelCreate:
        """Convert import record to HotelCreate schema"""
        # Remove internal fields
        clean_record = {k: v for k, v in record.items() if not k.startswith('_')}
        
        # Handle settings field (might be JSON string)
        if 'settings' in clean_record and isinstance(clean_record['settings'], str):
            try:
                clean_record['settings'] = json.loads(clean_record['settings'])
            except json.JSONDecodeError:
                clean_record['settings'] = {}
        
        # Convert boolean fields
        for bool_field in ['is_active']:
            if bool_field in clean_record:
                value = clean_record[bool_field]
                if isinstance(value, str):
                    clean_record[bool_field] = value.lower() in ['true', '1', 'yes', 'on']
        
        # Create HotelCreate instance
        return HotelCreate(**clean_record)
    
    def get_import_template(self, format_type: ImportFormat) -> str:
        """
        Get import template for specified format
        
        Args:
            format_type: Format type
            
        Returns:
            str: Template content
        """
        if format_type == ImportFormat.CSV:
            return self._get_csv_template()
        elif format_type == ImportFormat.JSON:
            return self._get_json_template()
        else:
            raise ValueError(f"Template not available for format: {format_type}")
    
    def _get_csv_template(self) -> str:
        """Get CSV template"""
        headers = [
            "name",
            "whatsapp_number",
            "green_api_instance_id",
            "green_api_token",
            "green_api_webhook_token",
            "settings",
            "is_active"
        ]
        
        # Create CSV with headers and example row
        output = StringIO()
        writer = csv.writer(output)
        writer.writerow(headers)
        writer.writerow([
            "Example Hotel",
            "+1234567890",
            "instance123",
            "token123",
            "webhook123",
            '{"notifications": {"email_enabled": true}}',
            "true"
        ])
        
        return output.getvalue()
    
    def _get_json_template(self) -> str:
        """Get JSON template"""
        template = {
            "hotels": [
                {
                    "name": "Example Hotel",
                    "whatsapp_number": "+1234567890",
                    "green_api_instance_id": "instance123",
                    "green_api_token": "token123",
                    "green_api_webhook_token": "webhook123",
                    "settings": {
                        "notifications": {
                            "email_enabled": True
                        }
                    },
                    "is_active": True
                }
            ]
        }
        
        return json.dumps(template, indent=2)


# Dependency injection helper
def get_hotel_import_service(db: Session) -> HotelImportService:
    """
    Get hotel import service instance
    
    Args:
        db: Database session
        
    Returns:
        HotelImportService: Hotel import service instance
    """
    return HotelImportService(db)
