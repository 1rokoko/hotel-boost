"""
Monitoring endpoints for Green API
"""

from typing import Dict, Any, List, Optional
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
import structlog

from app.middleware.green_api_middleware import get_green_api_metrics
from app.services.green_api_monitoring import (
    get_alert_manager, get_health_checker,
    AlertRule, AlertSeverity, AlertType
)

logger = structlog.get_logger(__name__)

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


class AlertRuleCreate(BaseModel):
    """Schema for creating alert rules"""
    name: str
    alert_type: str
    severity: str
    threshold: float
    duration: int
    enabled: bool = True
    cooldown: int = 300
    description: str = ""
    tags: List[str] = []


class AlertRuleUpdate(BaseModel):
    """Schema for updating alert rules"""
    threshold: Optional[float] = None
    duration: Optional[int] = None
    enabled: Optional[bool] = None
    cooldown: Optional[int] = None
    description: Optional[str] = None
    tags: Optional[List[str]] = None


@router.get("/dashboard", response_class=HTMLResponse)
def monitoring_dashboard(request: Request):
    """
    Green API Monitoring Dashboard

    Returns an HTML dashboard for monitoring Green API operations
    """
    return templates.TemplateResponse("monitoring_dashboard.html", {"request": request})


@router.get("/metrics")
def get_green_api_metrics_endpoint():
    """
    Get current Green API metrics
    
    Returns comprehensive metrics including:
    - Request statistics
    - Response times
    - Error rates
    - Rate limiting
    - Webhook statistics
    - Message statistics
    - Per-instance metrics
    """
    try:
        metrics = get_green_api_metrics().get_metrics()
        
        logger.info("Green API metrics retrieved", 
                   total_requests=metrics['requests']['total'])
        
        return {
            "status": "success",
            "data": metrics,
            "timestamp": metrics.get('timestamp')
        }
        
    except Exception as e:
        logger.error("Error retrieving Green API metrics", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to retrieve metrics")


@router.get("/health")
async def get_green_api_health():
    """
    Get Green API health status
    
    Returns health status for all Green API instances including:
    - Overall health summary
    - Per-instance health details
    - Error rates and response times
    """
    try:
        health_checker = get_health_checker()
        
        # Get health for all instances
        health_results = await health_checker.check_all_instances()
        
        # Get summary
        health_summary = health_checker.get_health_summary()
        
        logger.info("Green API health checked", 
                   overall_status=health_summary['overall_status'],
                   total_instances=health_summary['total_instances'])
        
        return {
            "status": "success",
            "data": {
                "summary": health_summary,
                "instances": health_results
            }
        }
        
    except Exception as e:
        logger.error("Error checking Green API health", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to check health")


@router.get("/health/{instance_id}")
async def get_instance_health(instance_id: str):
    """
    Get health status for a specific Green API instance
    """
    try:
        health_checker = get_health_checker()
        health_result = await health_checker.check_instance_health(instance_id)
        
        logger.info("Instance health checked", 
                   instance_id=instance_id,
                   status=health_result['status'])
        
        return {
            "status": "success",
            "data": health_result
        }
        
    except Exception as e:
        logger.error("Error checking instance health", 
                    instance_id=instance_id, 
                    error=str(e))
        raise HTTPException(status_code=500, detail="Failed to check instance health")


@router.get("/alerts")
def get_alerts(
    active_only: bool = Query(False, description="Return only active alerts"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of alerts to return")
):
    """
    Get alerts information
    
    Returns:
    - Active alerts if active_only=True
    - Alert history if active_only=False
    - Alert rules configuration
    """
    try:
        alert_manager = get_alert_manager()
        
        if active_only:
            alerts = alert_manager.get_active_alerts()
            data_key = "active_alerts"
        else:
            alerts = alert_manager.get_alert_history(limit)
            data_key = "alert_history"
        
        rules = alert_manager.get_rules()
        
        logger.info("Alerts retrieved", 
                   active_only=active_only,
                   alert_count=len(alerts))
        
        return {
            "status": "success",
            "data": {
                data_key: alerts,
                "rules": rules,
                "active_count": len(alert_manager.get_active_alerts())
            }
        }
        
    except Exception as e:
        logger.error("Error retrieving alerts", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to retrieve alerts")


@router.post("/alerts/rules")
def create_alert_rule(rule_data: AlertRuleCreate):
    """
    Create a new alert rule
    """
    try:
        # Validate alert type and severity
        try:
            alert_type = AlertType(rule_data.alert_type)
            severity = AlertSeverity(rule_data.severity)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=f"Invalid alert type or severity: {str(e)}")
        
        # Create alert rule
        rule = AlertRule(
            name=rule_data.name,
            alert_type=alert_type,
            severity=severity,
            threshold=rule_data.threshold,
            duration=rule_data.duration,
            enabled=rule_data.enabled,
            cooldown=rule_data.cooldown,
            description=rule_data.description,
            tags=rule_data.tags
        )
        
        alert_manager = get_alert_manager()
        alert_manager.add_rule(rule)
        
        logger.info("Alert rule created", 
                   rule_name=rule_data.name,
                   alert_type=rule_data.alert_type)
        
        return {
            "status": "success",
            "message": f"Alert rule '{rule_data.name}' created successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error creating alert rule", 
                    rule_name=rule_data.name, 
                    error=str(e))
        raise HTTPException(status_code=500, detail="Failed to create alert rule")


@router.put("/alerts/rules/{rule_name}")
def update_alert_rule(rule_name: str, rule_data: AlertRuleUpdate):
    """
    Update an existing alert rule
    """
    try:
        alert_manager = get_alert_manager()
        
        # Find the rule
        rule = None
        for r in alert_manager.rules:
            if r.name == rule_name:
                rule = r
                break
        
        if not rule:
            raise HTTPException(status_code=404, detail=f"Alert rule '{rule_name}' not found")
        
        # Update rule properties
        if rule_data.threshold is not None:
            rule.threshold = rule_data.threshold
        if rule_data.duration is not None:
            rule.duration = rule_data.duration
        if rule_data.enabled is not None:
            rule.enabled = rule_data.enabled
        if rule_data.cooldown is not None:
            rule.cooldown = rule_data.cooldown
        if rule_data.description is not None:
            rule.description = rule_data.description
        if rule_data.tags is not None:
            rule.tags = rule_data.tags
        
        logger.info("Alert rule updated", rule_name=rule_name)
        
        return {
            "status": "success",
            "message": f"Alert rule '{rule_name}' updated successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error updating alert rule", 
                    rule_name=rule_name, 
                    error=str(e))
        raise HTTPException(status_code=500, detail="Failed to update alert rule")


@router.delete("/alerts/rules/{rule_name}")
def delete_alert_rule(rule_name: str):
    """
    Delete an alert rule
    """
    try:
        alert_manager = get_alert_manager()
        
        # Check if rule exists
        rule_exists = any(rule.name == rule_name for rule in alert_manager.rules)
        if not rule_exists:
            raise HTTPException(status_code=404, detail=f"Alert rule '{rule_name}' not found")
        
        alert_manager.remove_rule(rule_name)
        
        logger.info("Alert rule deleted", rule_name=rule_name)
        
        return {
            "status": "success",
            "message": f"Alert rule '{rule_name}' deleted successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error deleting alert rule", 
                    rule_name=rule_name, 
                    error=str(e))
        raise HTTPException(status_code=500, detail="Failed to delete alert rule")


@router.post("/alerts/rules/{rule_name}/enable")
def enable_alert_rule(rule_name: str):
    """
    Enable an alert rule
    """
    try:
        alert_manager = get_alert_manager()
        alert_manager.enable_rule(rule_name)
        
        logger.info("Alert rule enabled", rule_name=rule_name)
        
        return {
            "status": "success",
            "message": f"Alert rule '{rule_name}' enabled"
        }
        
    except Exception as e:
        logger.error("Error enabling alert rule", 
                    rule_name=rule_name, 
                    error=str(e))
        raise HTTPException(status_code=500, detail="Failed to enable alert rule")


@router.post("/alerts/rules/{rule_name}/disable")
def disable_alert_rule(rule_name: str):
    """
    Disable an alert rule
    """
    try:
        alert_manager = get_alert_manager()
        alert_manager.disable_rule(rule_name)
        
        logger.info("Alert rule disabled", rule_name=rule_name)
        
        return {
            "status": "success",
            "message": f"Alert rule '{rule_name}' disabled"
        }
        
    except Exception as e:
        logger.error("Error disabling alert rule", 
                    rule_name=rule_name, 
                    error=str(e))
        raise HTTPException(status_code=500, detail="Failed to disable alert rule")


@router.post("/metrics/reset")
def reset_metrics():
    """
    Reset Green API metrics
    
    This endpoint resets all collected metrics to zero.
    Use with caution as this will clear historical data.
    """
    try:
        metrics = get_green_api_metrics()
        metrics.reset_metrics()
        
        logger.warning("Green API metrics reset")
        
        return {
            "status": "success",
            "message": "Green API metrics have been reset"
        }
        
    except Exception as e:
        logger.error("Error resetting metrics", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to reset metrics")


@router.get("/status")
def get_monitoring_status():
    """
    Get overall monitoring system status
    
    Returns a summary of the monitoring system including:
    - Metrics collection status
    - Alert system status
    - Health checker status
    """
    try:
        metrics = get_green_api_metrics().get_metrics()
        alert_manager = get_alert_manager()
        health_checker = get_health_checker()
        
        # Get monitoring status
        status = {
            "metrics": {
                "total_requests": metrics['requests']['total'],
                "error_rate": metrics['requests']['error_rate'],
                "last_updated": "real-time"
            },
            "alerts": {
                "total_rules": len(alert_manager.rules),
                "enabled_rules": len([r for r in alert_manager.rules if r.enabled]),
                "active_alerts": len(alert_manager.get_active_alerts())
            },
            "health": health_checker.get_health_summary(),
            "system_status": "operational"
        }
        
        return {
            "status": "success",
            "data": status
        }
        
    except Exception as e:
        logger.error("Error getting monitoring status", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to get monitoring status")


# Export router
__all__ = ['router']
