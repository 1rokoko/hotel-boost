"""
Data migration utilities for hotel data migration and transformation
"""

import uuid
import json
from typing import Dict, Any, List, Optional, Union, Callable
from dataclasses import dataclass
from enum import Enum
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import text
import structlog

from app.models.hotel import Hotel
from app.services.hotel_service import HotelService
from app.services.hotel_import import HotelImportService, ImportFormat, ImportMode
from app.services.hotel_export import HotelExportService, ExportFormat, ExportScope
from app.utils.audit_logger import get_audit_logger, AuditAction, AuditResource
from app.core.logging import get_logger

logger = get_logger(__name__)


class MigrationType(Enum):
    """Types of data migration"""
    SCHEMA_UPDATE = "schema_update"
    DATA_TRANSFORMATION = "data_transformation"
    TENANT_MIGRATION = "tenant_migration"
    BACKUP_RESTORE = "backup_restore"
    VERSION_UPGRADE = "version_upgrade"


class MigrationStatus(Enum):
    """Migration status"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


@dataclass
class MigrationResult:
    """Result of migration operation"""
    success: bool
    migration_id: str
    migration_type: MigrationType
    records_processed: int
    records_migrated: int
    records_failed: int
    start_time: datetime
    end_time: datetime
    duration_seconds: float
    errors: List[str]
    warnings: List[str]
    rollback_data: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "success": self.success,
            "migration_id": self.migration_id,
            "migration_type": self.migration_type.value,
            "records_processed": self.records_processed,
            "records_migrated": self.records_migrated,
            "records_failed": self.records_failed,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat(),
            "duration_seconds": self.duration_seconds,
            "errors": self.errors,
            "warnings": self.warnings,
            "has_rollback_data": self.rollback_data is not None
        }


class DataMigrationService:
    """Service for managing hotel data migrations"""
    
    def __init__(self, db: Session):
        """
        Initialize data migration service
        
        Args:
            db: Database session
        """
        self.db = db
        self.hotel_service = HotelService(db)
        self.import_service = HotelImportService(db)
        self.export_service = HotelExportService(db)
        self.audit_logger = get_audit_logger(db)
        self.logger = logger.bind(service="data_migration_service")
    
    def migrate_hotel_settings_schema(
        self,
        migration_function: Callable[[Dict[str, Any]], Dict[str, Any]],
        dry_run: bool = True,
        batch_size: int = 100
    ) -> MigrationResult:
        """
        Migrate hotel settings schema
        
        Args:
            migration_function: Function to transform settings
            dry_run: If True, only validate without applying changes
            batch_size: Number of records to process in each batch
            
        Returns:
            MigrationResult: Migration operation result
        """
        migration_id = str(uuid.uuid4())
        start_time = datetime.utcnow()
        
        try:
            self.logger.info(
                "Starting hotel settings schema migration",
                migration_id=migration_id,
                dry_run=dry_run,
                batch_size=batch_size
            )
            
            # Get all hotels
            hotels = self.db.query(Hotel).all()
            total_records = len(hotels)
            migrated_count = 0
            failed_count = 0
            errors = []
            warnings = []
            rollback_data = {} if not dry_run else None
            
            # Process in batches
            for i in range(0, total_records, batch_size):
                batch = hotels[i:i + batch_size]
                
                for hotel in batch:
                    try:
                        # Store original settings for rollback
                        if not dry_run and rollback_data is not None:
                            rollback_data[str(hotel.id)] = hotel.settings
                        
                        # Apply migration function
                        if hotel.settings:
                            old_settings = hotel.settings.copy()
                            new_settings = migration_function(old_settings)
                            
                            # Validate that migration function returned valid data
                            if not isinstance(new_settings, dict):
                                raise ValueError("Migration function must return a dictionary")
                            
                            # Apply changes if not dry run
                            if not dry_run:
                                hotel.settings = new_settings
                                migrated_count += 1
                            else:
                                # In dry run, just count as migrated if no errors
                                migrated_count += 1
                            
                            # Log the change
                            self.logger.debug(
                                "Hotel settings migrated",
                                hotel_id=str(hotel.id),
                                old_settings_keys=list(old_settings.keys()),
                                new_settings_keys=list(new_settings.keys()),
                                dry_run=dry_run
                            )
                        
                    except Exception as e:
                        failed_count += 1
                        error_msg = f"Failed to migrate hotel {hotel.id}: {str(e)}"
                        errors.append(error_msg)
                        self.logger.error(
                            "Hotel settings migration failed for hotel",
                            hotel_id=str(hotel.id),
                            error=str(e)
                        )
                
                # Commit batch if not dry run
                if not dry_run:
                    try:
                        self.db.commit()
                    except SQLAlchemyError as e:
                        self.db.rollback()
                        error_msg = f"Failed to commit batch: {str(e)}"
                        errors.append(error_msg)
                        self.logger.error("Batch commit failed", error=str(e))
            
            end_time = datetime.utcnow()
            duration = (end_time - start_time).total_seconds()
            success = failed_count == 0
            
            result = MigrationResult(
                success=success,
                migration_id=migration_id,
                migration_type=MigrationType.SCHEMA_UPDATE,
                records_processed=total_records,
                records_migrated=migrated_count,
                records_failed=failed_count,
                start_time=start_time,
                end_time=end_time,
                duration_seconds=duration,
                errors=errors,
                warnings=warnings,
                rollback_data=rollback_data
            )
            
            # Log migration completion
            self.audit_logger.log_audit(
                action=AuditAction.UPDATE,
                resource=AuditResource.SYSTEM,
                resource_id=migration_id,
                resource_name="Hotel Settings Schema Migration",
                success=success,
                details={
                    "migration_type": MigrationType.SCHEMA_UPDATE.value,
                    "dry_run": dry_run,
                    "records_processed": total_records,
                    "records_migrated": migrated_count,
                    "records_failed": failed_count
                }
            )
            
            self.logger.info(
                "Hotel settings schema migration completed",
                migration_id=migration_id,
                success=success,
                records_processed=total_records,
                records_migrated=migrated_count,
                records_failed=failed_count,
                duration_seconds=duration
            )
            
            return result
            
        except Exception as e:
            end_time = datetime.utcnow()
            duration = (end_time - start_time).total_seconds()
            
            self.logger.error(
                "Hotel settings schema migration failed",
                migration_id=migration_id,
                error=str(e),
                duration_seconds=duration
            )
            
            return MigrationResult(
                success=False,
                migration_id=migration_id,
                migration_type=MigrationType.SCHEMA_UPDATE,
                records_processed=0,
                records_migrated=0,
                records_failed=1,
                start_time=start_time,
                end_time=end_time,
                duration_seconds=duration,
                errors=[f"Migration failed: {str(e)}"],
                warnings=[],
                rollback_data=None
            )
    
    def rollback_migration(
        self,
        migration_result: MigrationResult
    ) -> MigrationResult:
        """
        Rollback a migration using stored rollback data
        
        Args:
            migration_result: Original migration result with rollback data
            
        Returns:
            MigrationResult: Rollback operation result
        """
        if not migration_result.rollback_data:
            raise ValueError("No rollback data available for this migration")
        
        rollback_id = str(uuid.uuid4())
        start_time = datetime.utcnow()
        
        try:
            self.logger.info(
                "Starting migration rollback",
                original_migration_id=migration_result.migration_id,
                rollback_id=rollback_id
            )
            
            rollback_count = 0
            failed_count = 0
            errors = []
            
            for hotel_id_str, original_settings in migration_result.rollback_data.items():
                try:
                    hotel_id = uuid.UUID(hotel_id_str)
                    hotel = self.db.query(Hotel).filter(Hotel.id == hotel_id).first()
                    
                    if hotel:
                        hotel.settings = original_settings
                        rollback_count += 1
                    else:
                        failed_count += 1
                        errors.append(f"Hotel {hotel_id} not found for rollback")
                        
                except Exception as e:
                    failed_count += 1
                    errors.append(f"Failed to rollback hotel {hotel_id_str}: {str(e)}")
            
            # Commit rollback changes
            try:
                self.db.commit()
            except SQLAlchemyError as e:
                self.db.rollback()
                errors.append(f"Failed to commit rollback: {str(e)}")
                failed_count = len(migration_result.rollback_data)
                rollback_count = 0
            
            end_time = datetime.utcnow()
            duration = (end_time - start_time).total_seconds()
            success = failed_count == 0
            
            result = MigrationResult(
                success=success,
                migration_id=rollback_id,
                migration_type=MigrationType.SCHEMA_UPDATE,
                records_processed=len(migration_result.rollback_data),
                records_migrated=rollback_count,
                records_failed=failed_count,
                start_time=start_time,
                end_time=end_time,
                duration_seconds=duration,
                errors=errors,
                warnings=[],
                rollback_data=None
            )
            
            self.logger.info(
                "Migration rollback completed",
                original_migration_id=migration_result.migration_id,
                rollback_id=rollback_id,
                success=success,
                records_rolled_back=rollback_count,
                records_failed=failed_count
            )
            
            return result
            
        except Exception as e:
            end_time = datetime.utcnow()
            duration = (end_time - start_time).total_seconds()
            
            self.logger.error(
                "Migration rollback failed",
                original_migration_id=migration_result.migration_id,
                rollback_id=rollback_id,
                error=str(e)
            )
            
            return MigrationResult(
                success=False,
                migration_id=rollback_id,
                migration_type=MigrationType.SCHEMA_UPDATE,
                records_processed=0,
                records_migrated=0,
                records_failed=1,
                start_time=start_time,
                end_time=end_time,
                duration_seconds=duration,
                errors=[f"Rollback failed: {str(e)}"],
                warnings=[],
                rollback_data=None
            )
    
    def backup_hotel_data(
        self,
        backup_name: Optional[str] = None,
        include_sensitive_data: bool = False
    ) -> Dict[str, Any]:
        """
        Create a backup of all hotel data
        
        Args:
            backup_name: Optional backup name
            include_sensitive_data: Whether to include sensitive data
            
        Returns:
            Dict[str, Any]: Backup data
        """
        try:
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            backup_name = backup_name or f"hotel_backup_{timestamp}"
            
            # Export all hotels
            export_result = self.export_service.export_hotels(
                export_format=ExportFormat.JSON,
                scope=ExportScope.ALL_HOTELS,
                include_sensitive_data=include_sensitive_data
            )
            
            if not export_result.success:
                raise Exception(f"Failed to export hotel data: {export_result.errors}")
            
            # Parse the exported JSON
            export_data = json.loads(export_result.file_content)
            
            backup_data = {
                "backup_info": {
                    "name": backup_name,
                    "timestamp": datetime.utcnow().isoformat(),
                    "record_count": export_result.record_count,
                    "includes_sensitive_data": include_sensitive_data
                },
                "data": export_data
            }
            
            self.logger.info(
                "Hotel data backup created",
                backup_name=backup_name,
                record_count=export_result.record_count,
                includes_sensitive_data=include_sensitive_data
            )
            
            return backup_data
            
        except Exception as e:
            self.logger.error("Failed to create hotel data backup", error=str(e))
            raise
    
    def restore_hotel_data(
        self,
        backup_data: Dict[str, Any],
        restore_mode: ImportMode = ImportMode.CREATE_OR_UPDATE,
        dry_run: bool = True
    ) -> MigrationResult:
        """
        Restore hotel data from backup
        
        Args:
            backup_data: Backup data to restore
            restore_mode: How to handle existing data
            dry_run: If True, only validate without applying changes
            
        Returns:
            MigrationResult: Restore operation result
        """
        migration_id = str(uuid.uuid4())
        start_time = datetime.utcnow()
        
        try:
            # Validate backup data structure
            if "backup_info" not in backup_data or "data" not in backup_data:
                raise ValueError("Invalid backup data structure")
            
            backup_info = backup_data["backup_info"]
            hotels_data = backup_data["data"].get("hotels", [])
            
            self.logger.info(
                "Starting hotel data restore",
                migration_id=migration_id,
                backup_name=backup_info.get("name"),
                record_count=len(hotels_data),
                restore_mode=restore_mode.value,
                dry_run=dry_run
            )
            
            # Convert to JSON string for import service
            import_data = json.dumps({"hotels": hotels_data})
            
            # Use import service to restore data
            import_result = self.import_service.import_from_file(
                file_content=import_data,
                file_format=ImportFormat.JSON,
                import_mode=restore_mode,
                validate_only=dry_run
            )
            
            end_time = datetime.utcnow()
            duration = (end_time - start_time).total_seconds()
            
            result = MigrationResult(
                success=import_result.success,
                migration_id=migration_id,
                migration_type=MigrationType.BACKUP_RESTORE,
                records_processed=import_result.total_records,
                records_migrated=import_result.created_count + import_result.updated_count,
                records_failed=import_result.error_count,
                start_time=start_time,
                end_time=end_time,
                duration_seconds=duration,
                errors=[error.get("error", str(error)) for error in import_result.errors],
                warnings=[warning.get("warning", str(warning)) for warning in import_result.warnings],
                rollback_data=None
            )
            
            self.logger.info(
                "Hotel data restore completed",
                migration_id=migration_id,
                success=result.success,
                records_processed=result.records_processed,
                records_migrated=result.records_migrated,
                records_failed=result.records_failed
            )
            
            return result
            
        except Exception as e:
            end_time = datetime.utcnow()
            duration = (end_time - start_time).total_seconds()
            
            self.logger.error(
                "Hotel data restore failed",
                migration_id=migration_id,
                error=str(e)
            )
            
            return MigrationResult(
                success=False,
                migration_id=migration_id,
                migration_type=MigrationType.BACKUP_RESTORE,
                records_processed=0,
                records_migrated=0,
                records_failed=1,
                start_time=start_time,
                end_time=end_time,
                duration_seconds=duration,
                errors=[f"Restore failed: {str(e)}"],
                warnings=[],
                rollback_data=None
            )
    
    def validate_data_integrity(self) -> Dict[str, Any]:
        """
        Validate hotel data integrity
        
        Returns:
            Dict[str, Any]: Validation results
        """
        try:
            results = {
                "timestamp": datetime.utcnow().isoformat(),
                "total_hotels": 0,
                "issues": [],
                "warnings": [],
                "summary": {}
            }
            
            # Get all hotels
            hotels = self.db.query(Hotel).all()
            results["total_hotels"] = len(hotels)
            
            duplicate_numbers = []
            invalid_settings = []
            missing_credentials = []
            
            # Check for issues
            phone_numbers = {}
            for hotel in hotels:
                # Check for duplicate WhatsApp numbers
                if hotel.whatsapp_number in phone_numbers:
                    duplicate_numbers.append({
                        "whatsapp_number": hotel.whatsapp_number,
                        "hotel_ids": [phone_numbers[hotel.whatsapp_number], str(hotel.id)]
                    })
                else:
                    phone_numbers[hotel.whatsapp_number] = str(hotel.id)
                
                # Check settings validity
                if hotel.settings:
                    try:
                        json.dumps(hotel.settings)  # Test JSON serialization
                    except (TypeError, ValueError):
                        invalid_settings.append(str(hotel.id))
                
                # Check for missing credentials on active hotels
                if hotel.is_active and not hotel.has_green_api_credentials:
                    missing_credentials.append(str(hotel.id))
            
            # Compile results
            if duplicate_numbers:
                results["issues"].append({
                    "type": "duplicate_whatsapp_numbers",
                    "count": len(duplicate_numbers),
                    "details": duplicate_numbers
                })
            
            if invalid_settings:
                results["issues"].append({
                    "type": "invalid_settings",
                    "count": len(invalid_settings),
                    "hotel_ids": invalid_settings
                })
            
            if missing_credentials:
                results["warnings"].append({
                    "type": "missing_credentials_on_active_hotels",
                    "count": len(missing_credentials),
                    "hotel_ids": missing_credentials
                })
            
            results["summary"] = {
                "total_issues": len(results["issues"]),
                "total_warnings": len(results["warnings"]),
                "data_integrity_score": max(0, 100 - (len(results["issues"]) * 10) - (len(results["warnings"]) * 2))
            }
            
            self.logger.info(
                "Data integrity validation completed",
                total_hotels=results["total_hotels"],
                total_issues=results["summary"]["total_issues"],
                total_warnings=results["summary"]["total_warnings"],
                integrity_score=results["summary"]["data_integrity_score"]
            )
            
            return results
            
        except Exception as e:
            self.logger.error("Data integrity validation failed", error=str(e))
            raise


# Dependency injection helper
def get_data_migration_service(db: Session) -> DataMigrationService:
    """
    Get data migration service instance
    
    Args:
        db: Database session
        
    Returns:
        DataMigrationService: Data migration service instance
    """
    return DataMigrationService(db)


# Common migration functions
def migrate_settings_v1_to_v2(settings: Dict[str, Any]) -> Dict[str, Any]:
    """
    Example migration function: v1 to v2 settings schema
    
    Args:
        settings: Original settings
        
    Returns:
        Dict[str, Any]: Migrated settings
    """
    # Example: Add default values for new fields
    migrated = settings.copy()
    
    if "notifications" not in migrated:
        migrated["notifications"] = {
            "email_enabled": True,
            "sms_enabled": False,
            "webhook_enabled": False
        }
    
    if "auto_responses" not in migrated:
        migrated["auto_responses"] = {
            "enabled": True,
            "greeting_message": "Welcome to our hotel! How can we help you today?"
        }
    
    return migrated
