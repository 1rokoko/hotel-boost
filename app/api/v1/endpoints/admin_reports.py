"""
Admin reports endpoints
"""

import uuid
from datetime import datetime
from typing import Dict, Any, Optional, List
from fastapi import APIRouter, Depends, HTTPException, status, Query, BackgroundTasks
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
import structlog

from app.database import get_db
from app.api.v1.endpoints.admin_auth import get_current_admin_user
from app.schemas.admin_reports import (
    ReportRequest,
    ReportResponse,
    ReportListResponse,
    ReportExportRequest,
    ReportExportResponse
)
from app.services.admin_reports_service import (
    AdminReportsService,
    get_admin_reports_service
)
from app.models.admin_user import AdminPermission
from app.core.admin_security import AdminSecurity, AdminAuthorizationError

logger = structlog.get_logger(__name__)

router = APIRouter()


def require_permission(permission: AdminPermission):
    """Dependency to require specific permission"""
    def check_permission(
        current_user = Depends(get_current_admin_user)
    ):
        try:
            reports_service = reportsService(db)
            AdminSecurity.validate_admin_access(current_user, permission)
            return current_user
        except AdminAuthorizationError as e:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=str(e)
            )
    return check_permission


@router.post("/generate", response_model=ReportResponse)
async def generate_report(
    report_request: ReportRequest,
    background_tasks: BackgroundTasks,
    current_user = Depends(require_permission(AdminPermission.GENERATE_REPORTS)),
    db: Session = Depends(get_db)
):
    """
    Generate a new report
    
    Creates a report based on the specified parameters. Large reports
    are processed in the background.
    """
    try:
        # Validate hotel access if hotel_id is specified
        if report_request.hotel_id and not current_user.can_access_hotel(report_request.hotel_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this hotel"
            )
        
        report = await reports_service.generate_report(
            report_request=report_request,
            generating_user=current_user,
            background_tasks=background_tasks
        )
        
        logger.info(
            "Report generation initiated",
            user_id=str(current_user.id),
            report_id=str(report.id),
            report_type=report_request.report_type
        )
        
        return report
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error("Error generating report", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate report"
        )


@router.get("/", response_model=ReportListResponse)
async def list_reports(
    report_type: Optional[str] = Query(None, description="Filter by report type"),
    hotel_id: Optional[uuid.UUID] = Query(None, description="Filter by hotel ID"),
    status: Optional[str] = Query(None, description="Filter by report status"),
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(20, ge=1, le=100, description="Items per page"),
    current_user = Depends(require_permission(AdminPermission.VIEW_ANALYTICS)),
    db: Session = Depends(get_db)
):
    """
    List reports with filtering and pagination
    """
    try:
        # Validate hotel access if hotel_id is specified
        if hotel_id and not current_user.can_access_hotel(hotel_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this hotel"
            )
        
        reports, total = await reports_service.list_reports(
            requesting_user=current_user,
            report_type=report_type,
            hotel_id=hotel_id,
            status=status,
            page=page,
            per_page=per_page
        )
        
        total_pages = (total + per_page - 1) // per_page
        
        return ReportListResponse(
            reports=reports,
            total=total,
            page=page,
            per_page=per_page,
            total_pages=total_pages
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error listing reports", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list reports"
        )


@router.get("/{report_id}", response_model=ReportResponse)
async def get_report(
    report_id: uuid.UUID,
    current_user = Depends(require_permission(AdminPermission.VIEW_ANALYTICS)),
    db: Session = Depends(get_db)
):
    """
    Get report by ID
    """
    try:
        report = await reports_service.get_report(
            report_id=report_id,
            requesting_user=current_user
        )
        
        if not report:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Report not found"
            )
        
        return report
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error getting report", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get report"
        )


@router.delete("/{report_id}")
async def delete_report(
    report_id: uuid.UUID,
    current_user = Depends(require_permission(AdminPermission.GENERATE_REPORTS)),
    db: Session = Depends(get_db)
):
    """
    Delete report
    """
    try:
        success = await reports_service.delete_report(
            report_id=report_id,
            deleting_user=current_user
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Report not found"
            )
        
        logger.info(
            "Report deleted",
            user_id=str(current_user.id),
            report_id=str(report_id)
        )
        
        return {"message": "Report deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error deleting report", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete report"
        )


@router.post("/{report_id}/export", response_model=ReportExportResponse)
async def export_report(
    report_id: uuid.UUID,
    export_request: ReportExportRequest,
    background_tasks: BackgroundTasks,
    current_user = Depends(require_permission(AdminPermission.EXPORT_DATA)),
    db: Session = Depends(get_db)
):
    """
    Export report in specified format
    """
    try:
        export_info = await reports_service.export_report(
            report_id=report_id,
            export_request=export_request,
            exporting_user=current_user,
            background_tasks=background_tasks
        )
        
        if not export_info:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Report not found"
            )
        
        logger.info(
            "Report export initiated",
            user_id=str(current_user.id),
            report_id=str(report_id),
            format=export_request.format
        )
        
        return export_info
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error exporting report", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to export report"
        )


@router.get("/{report_id}/download")
async def download_report(
    report_id: uuid.UUID,
    format: str = Query(..., regex="^(pdf|csv|excel|json)$", description="Download format"),
    current_user = Depends(require_permission(AdminPermission.EXPORT_DATA)),
    db: Session = Depends(get_db)
):
    """
    Download report file
    """
    try:
        file_stream, filename, media_type = await reports_service.download_report(
            report_id=report_id,
            format=format,
            requesting_user=current_user
        )
        
        if not file_stream:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Report file not found"
            )
        
        logger.info(
            "Report downloaded",
            user_id=str(current_user.id),
            report_id=str(report_id),
            format=format
        )
        
        return StreamingResponse(
            file_stream,
            media_type=media_type,
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error downloading report", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to download report"
        )


@router.get("/templates/list")
async def list_report_templates(
    current_user = Depends(require_permission(AdminPermission.VIEW_ANALYTICS)),
    db: Session = Depends(get_db)
):
    """
    List available report templates
    """
    try:
        templates = await reports_service.get_report_templates()
        
        return {
            "templates": templates,
            "total": len(templates)
        }
        
    except Exception as e:
        logger.error("Error listing report templates", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list report templates"
        )


@router.post("/schedule")
async def schedule_report(
    report_request: ReportRequest,
    schedule_config: Dict[str, Any],
    current_user = Depends(require_permission(AdminPermission.GENERATE_REPORTS)),
    db: Session = Depends(get_db)
):
    """
    Schedule recurring report generation
    """
    try:
        # Validate hotel access if hotel_id is specified
        if report_request.hotel_id and not current_user.can_access_hotel(report_request.hotel_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this hotel"
            )
        
        scheduled_report = await reports_service.schedule_report(
            report_request=report_request,
            schedule_config=schedule_config,
            scheduling_user=current_user
        )
        
        logger.info(
            "Report scheduled",
            user_id=str(current_user.id),
            scheduled_report_id=str(scheduled_report["id"]),
            report_type=report_request.report_type
        )
        
        return scheduled_report
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error("Error scheduling report", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to schedule report"
        )


@router.get("/scheduled/list")
async def list_scheduled_reports(
    current_user = Depends(require_permission(AdminPermission.GENERATE_REPORTS)),
    db: Session = Depends(get_db)
):
    """
    List scheduled reports
    """
    try:
        scheduled_reports = await reports_service.list_scheduled_reports(
            requesting_user=current_user
        )
        
        return {
            "scheduled_reports": scheduled_reports,
            "total": len(scheduled_reports)
        }
        
    except Exception as e:
        logger.error("Error listing scheduled reports", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list scheduled reports"
        )
