"""
Admin system settings endpoints
"""

import uuid
from typing import Dict, Any, Optional, List
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
import structlog

from app.database import get_db
from app.api.v1.endpoints.admin_auth import get_current_admin_user
from app.schemas.admin_settings import (
    SystemSettingsResponse,
    SystemSettingsUpdate,
    SettingValue,
    SettingsHistoryResponse
)
from app.services.admin_settings_service import (
    AdminSettingsService,
    get_admin_settings_service
)
from app.models.admin_user import AdminPermission
from app.core.admin_security import AdminSecurity, AdminAuthorizationError

logger = structlog.get_logger(__name__)

router = APIRouter()


def require_permission(permission: AdminPermission):
    """Dependency to require specific permission"""
    async def check_permission(
        current_user = Depends(get_current_admin_user)
    ):
        try:
        settings_service = settingsService(db)
            AdminSecurity.validate_admin_access(current_user, permission)
            return current_user
        except AdminAuthorizationError as e:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=str(e)
            )
    return check_permission


@router.get("/", response_model=SystemSettingsResponse)
async def get_system_settings(
    category: Optional[str] = Query(None, description="Filter by settings category"),
    current_user = Depends(require_permission(AdminPermission.MANAGE_SYSTEM)),
    db: Session = Depends(get_db)
):
    """
    Get system settings
    
    Returns all system settings or filtered by category.
    """
    try:
        settings = await settings_service.get_system_settings(category=category)
        
        logger.info(
            "System settings retrieved",
            user_id=str(current_user.id),
            category=category
        )
        
        return settings
        
    except Exception as e:
        logger.error("Error getting system settings", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve system settings"
        )


@router.put("/", response_model=SystemSettingsResponse)
async def update_system_settings(
    settings_data: SystemSettingsUpdate,
    current_user = Depends(require_permission(AdminPermission.MANAGE_SYSTEM)),
    db: Session = Depends(get_db)
):
    """
    Update system settings
    
    Updates multiple system settings in a single request.
    """
    try:
        updated_settings = await settings_service.update_system_settings(
            settings_data=settings_data,
            updating_user=current_user
        )
        
        logger.info(
            "System settings updated",
            user_id=str(current_user.id),
            settings_count=len(settings_data.settings)
        )
        
        return updated_settings
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error("Error updating system settings", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update system settings"
        )


@router.get("/{setting_key}", response_model=SettingValue)
async def get_setting(
    setting_key: str,
    current_user = Depends(require_permission(AdminPermission.MANAGE_SYSTEM)),
    db: Session = Depends(get_db)
):
    """
    Get specific system setting by key
    """
    try:
        setting = await settings_service.get_setting(setting_key)
        
        if not setting:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Setting not found"
            )
        
        return setting
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error getting setting", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve setting"
        )


@router.put("/{setting_key}", response_model=SettingValue)
async def update_setting(
    setting_key: str,
    setting_value: SettingValue,
    current_user = Depends(require_permission(AdminPermission.MANAGE_SYSTEM)),
    db: Session = Depends(get_db)
):
    """
    Update specific system setting
    """
    try:
        updated_setting = await settings_service.update_setting(
            setting_key=setting_key,
            setting_value=setting_value,
            updating_user=current_user
        )
        
        if not updated_setting:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Setting not found"
            )
        
        logger.info(
            "System setting updated",
            user_id=str(current_user.id),
            setting_key=setting_key
        )
        
        return updated_setting
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error updating setting", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update setting"
        )


@router.delete("/{setting_key}")
async def delete_setting(
    setting_key: str,
    current_user = Depends(require_permission(AdminPermission.MANAGE_SYSTEM)),
    db: Session = Depends(get_db)
):
    """
    Delete system setting
    """
    try:
        success = await settings_service.delete_setting(
            setting_key=setting_key,
            deleting_user=current_user
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Setting not found"
            )
        
        logger.info(
            "System setting deleted",
            user_id=str(current_user.id),
            setting_key=setting_key
        )
        
        return {"message": "Setting deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error deleting setting", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete setting"
        )


@router.get("/{setting_key}/history", response_model=SettingsHistoryResponse)
async def get_setting_history(
    setting_key: str,
    limit: int = Query(50, ge=1, le=100, description="Number of history entries to return"),
    current_user = Depends(require_permission(AdminPermission.MANAGE_SYSTEM)),
    db: Session = Depends(get_db)
):
    """
    Get setting change history
    """
    try:
        history = await settings_service.get_setting_history(
            setting_key=setting_key,
            limit=limit
        )
        
        return history
        
    except Exception as e:
        logger.error("Error getting setting history", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve setting history"
        )


@router.post("/validate")
async def validate_settings(
    settings_data: SystemSettingsUpdate,
    current_user = Depends(require_permission(AdminPermission.MANAGE_SYSTEM)),
    db: Session = Depends(get_db)
):
    """
    Validate system settings without saving
    
    Useful for testing configuration changes before applying them.
    """
    try:
        validation_result = await settings_service.validate_settings(settings_data)
        
        return {
            "valid": validation_result.is_valid,
            "errors": validation_result.errors,
            "warnings": validation_result.warnings,
            "affected_services": validation_result.affected_services
        }
        
    except Exception as e:
        logger.error("Error validating settings", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to validate settings"
        )


@router.post("/reset")
async def reset_settings_to_default(
    category: Optional[str] = Query(None, description="Reset specific category only"),
    current_user = Depends(require_permission(AdminPermission.MANAGE_SYSTEM)),
    db: Session = Depends(get_db)
):
    """
    Reset system settings to default values
    
    WARNING: This will reset settings to their default values.
    """
    try:
        reset_count = await settings_service.reset_to_defaults(
            category=category,
            resetting_user=current_user
        )
        
        logger.warning(
            "System settings reset to defaults",
            user_id=str(current_user.id),
            category=category,
            reset_count=reset_count
        )
        
        return {
            "message": f"Reset {reset_count} settings to default values",
            "category": category,
            "reset_count": reset_count
        }
        
    except Exception as e:
        logger.error("Error resetting settings", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to reset settings"
        )


@router.get("/categories/list")
async def list_setting_categories(
    current_user = Depends(require_permission(AdminPermission.MANAGE_SYSTEM)),
    db: Session = Depends(get_db)
):
    """
    List all available setting categories
    """
    try:
        categories = await settings_service.get_setting_categories()
        
        return {
            "categories": categories,
            "total": len(categories)
        }
        
    except Exception as e:
        logger.error("Error listing setting categories", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list setting categories"
        )


@router.post("/backup")
async def backup_settings(
    current_user = Depends(require_permission(AdminPermission.MANAGE_SYSTEM)),
    db: Session = Depends(get_db)
):
    """
    Create backup of current system settings
    """
    try:
        backup_info = await settings_service.create_settings_backup(
            creating_user=current_user
        )
        
        logger.info(
            "System settings backup created",
            user_id=str(current_user.id),
            backup_id=backup_info["backup_id"]
        )
        
        return backup_info
        
    except Exception as e:
        logger.error("Error creating settings backup", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create settings backup"
        )


@router.post("/restore/{backup_id}")
async def restore_settings(
    backup_id: str,
    current_user = Depends(require_permission(AdminPermission.MANAGE_SYSTEM)),
    db: Session = Depends(get_db)
):
    """
    Restore system settings from backup
    """
    try:
        restore_info = await settings_service.restore_settings_backup(
            backup_id=backup_id,
            restoring_user=current_user
        )
        
        logger.warning(
            "System settings restored from backup",
            user_id=str(current_user.id),
            backup_id=backup_id,
            restored_count=restore_info["restored_count"]
        )
        
        return restore_info
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error("Error restoring settings", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to restore settings"
        )
