#!/bin/bash

# WhatsApp Hotel Bot Rollback Script
# Usage: ./scripts/rollback.sh <environment> [revision]
# Example: ./scripts/rollback.sh production
# Example: ./scripts/rollback.sh production 5

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Usage function
usage() {
    echo "Usage: $0 <environment> [revision]"
    echo ""
    echo "Arguments:"
    echo "  environment  Target environment (staging, production)"
    echo "  revision     Specific revision to rollback to (optional)"
    echo ""
    echo "Examples:"
    echo "  $0 staging                    # Rollback to previous revision"
    echo "  $0 production 5               # Rollback to revision 5"
    echo "  $0 production --to-revision=3 # Rollback to revision 3"
    exit 1
}

# Validate arguments
if [ $# -lt 1 ] || [ $# -gt 2 ]; then
    log_error "Invalid number of arguments"
    usage
fi

ENVIRONMENT="$1"
REVISION="${2:-}"

# Validate environment
if [[ ! "$ENVIRONMENT" =~ ^(staging|production)$ ]]; then
    log_error "Invalid environment: $ENVIRONMENT"
    log_error "Supported environments: staging, production"
    exit 1
fi

# Set environment-specific variables
case "$ENVIRONMENT" in
    staging)
        NAMESPACE="hotel-bot-staging"
        ;;
    production)
        NAMESPACE="hotel-bot"
        ;;
esac

log_info "Starting rollback for $ENVIRONMENT environment"
log_info "Namespace: $NAMESPACE"

# Check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites..."
    
    # Check if kubectl is installed
    if ! command -v kubectl &> /dev/null; then
        log_error "kubectl is not installed or not in PATH"
        exit 1
    fi
    
    # Check if kubectl is configured
    if ! kubectl cluster-info &> /dev/null; then
        log_error "kubectl is not configured or cluster is not accessible"
        exit 1
    fi
    
    # Check if namespace exists
    if ! kubectl get namespace "$NAMESPACE" &> /dev/null; then
        log_error "Namespace $NAMESPACE does not exist"
        exit 1
    fi
    
    log_success "Prerequisites check passed"
}

# Show current deployment status
show_current_status() {
    log_info "Current deployment status:"
    echo ""
    
    # Show current deployments
    kubectl get deployments -n "$NAMESPACE" -l app=whatsapp-hotel-bot
    echo ""
    
    # Show current pods
    kubectl get pods -n "$NAMESPACE" -l app=whatsapp-hotel-bot
    echo ""
}

# Show rollout history
show_rollout_history() {
    log_info "Rollout history for deployments:"
    echo ""
    
    # API deployment history
    log_info "API Deployment History:"
    kubectl rollout history deployment/whatsapp-hotel-bot-api -n "$NAMESPACE"
    echo ""
    
    # Celery worker deployment history
    log_info "Celery Worker Deployment History:"
    kubectl rollout history deployment/whatsapp-hotel-bot-celery-worker -n "$NAMESPACE"
    echo ""
    
    # Celery beat deployment history
    log_info "Celery Beat Deployment History:"
    kubectl rollout history deployment/whatsapp-hotel-bot-celery-beat -n "$NAMESPACE"
    echo ""
}

# Confirm rollback
confirm_rollback() {
    if [ "$ENVIRONMENT" = "production" ]; then
        log_warning "You are about to rollback PRODUCTION environment!"
        echo ""
        read -p "Are you sure you want to continue? (yes/no): " -r
        if [[ ! $REPLY =~ ^[Yy][Ee][Ss]$ ]]; then
            log_info "Rollback cancelled by user"
            exit 0
        fi
    fi
}

# Perform rollback
perform_rollback() {
    log_info "Performing rollback..."
    
    local rollback_args=""
    if [ -n "$REVISION" ]; then
        rollback_args="--to-revision=$REVISION"
        log_info "Rolling back to revision: $REVISION"
    else
        log_info "Rolling back to previous revision"
    fi
    
    # Rollback API deployment
    log_info "Rolling back API deployment..."
    if kubectl rollout undo deployment/whatsapp-hotel-bot-api -n "$NAMESPACE" $rollback_args; then
        log_success "API deployment rollback initiated"
    else
        log_error "Failed to rollback API deployment"
        return 1
    fi
    
    # Rollback Celery worker deployment
    log_info "Rolling back Celery worker deployment..."
    if kubectl rollout undo deployment/whatsapp-hotel-bot-celery-worker -n "$NAMESPACE" $rollback_args; then
        log_success "Celery worker deployment rollback initiated"
    else
        log_error "Failed to rollback Celery worker deployment"
        return 1
    fi
    
    # Rollback Celery beat deployment
    log_info "Rolling back Celery beat deployment..."
    if kubectl rollout undo deployment/whatsapp-hotel-bot-celery-beat -n "$NAMESPACE" $rollback_args; then
        log_success "Celery beat deployment rollback initiated"
    else
        log_error "Failed to rollback Celery beat deployment"
        return 1
    fi
}

# Wait for rollback to complete
wait_for_rollback() {
    log_info "Waiting for rollback to complete..."
    
    # Wait for API deployment
    if ! kubectl rollout status deployment/whatsapp-hotel-bot-api -n "$NAMESPACE" --timeout=600s; then
        log_error "API deployment rollback failed"
        return 1
    fi
    
    # Wait for Celery worker deployment
    if ! kubectl rollout status deployment/whatsapp-hotel-bot-celery-worker -n "$NAMESPACE" --timeout=300s; then
        log_error "Celery worker deployment rollback failed"
        return 1
    fi
    
    # Wait for Celery beat deployment
    if ! kubectl rollout status deployment/whatsapp-hotel-bot-celery-beat -n "$NAMESPACE" --timeout=300s; then
        log_error "Celery beat deployment rollback failed"
        return 1
    fi
    
    log_success "All deployments rolled back successfully"
}

# Verify rollback health
verify_rollback() {
    log_info "Verifying rollback health..."
    
    # Wait a bit for the service to be fully ready
    sleep 10
    
    # Test health endpoint using kubectl port-forward in background
    kubectl port-forward service/whatsapp-hotel-bot-api 8080:8000 -n "$NAMESPACE" &
    PORT_FORWARD_PID=$!
    
    # Wait for port-forward to establish
    sleep 5
    
    # Test health endpoint
    if curl -f http://localhost:8080/health > /dev/null 2>&1; then
        log_success "Health check passed after rollback"
        HEALTH_CHECK_PASSED=true
    else
        log_error "Health check failed after rollback"
        HEALTH_CHECK_PASSED=false
    fi
    
    # Clean up port-forward
    kill $PORT_FORWARD_PID 2>/dev/null || true
    
    if [ "$HEALTH_CHECK_PASSED" = false ]; then
        log_error "Rollback verification failed"
        return 1
    fi
}

# Show post-rollback status
show_post_rollback_status() {
    log_info "Post-rollback status:"
    echo ""
    
    # Show current deployments
    kubectl get deployments -n "$NAMESPACE" -l app=whatsapp-hotel-bot
    echo ""
    
    # Show current pods
    kubectl get pods -n "$NAMESPACE" -l app=whatsapp-hotel-bot
    echo ""
    
    # Show current images
    log_info "Current images:"
    kubectl get deployments -n "$NAMESPACE" -l app=whatsapp-hotel-bot -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.spec.template.spec.containers[0].image}{"\n"}{end}'
    echo ""
}

# Emergency rollback (skip confirmations)
emergency_rollback() {
    log_warning "EMERGENCY ROLLBACK MODE"
    log_info "Skipping confirmations and performing immediate rollback"
    
    check_prerequisites
    perform_rollback
    wait_for_rollback
    verify_rollback
    show_post_rollback_status
    
    log_success "Emergency rollback completed"
}

# Main rollback function
main() {
    log_info "=== WhatsApp Hotel Bot Rollback ==="
    log_info "Environment: $ENVIRONMENT"
    log_info "Namespace: $NAMESPACE"
    if [ -n "$REVISION" ]; then
        log_info "Target revision: $REVISION"
    fi
    echo ""
    
    # Check for emergency mode
    if [[ "${EMERGENCY:-}" == "true" ]]; then
        emergency_rollback
        return
    fi
    
    # Execute rollback steps
    check_prerequisites
    show_current_status
    show_rollout_history
    confirm_rollback
    perform_rollback
    wait_for_rollback
    verify_rollback
    show_post_rollback_status
    
    log_success "=== Rollback completed successfully ==="
}

# Error handling
trap 'log_error "Rollback failed at line $LINENO"' ERR

# Handle emergency mode
if [[ "${1:-}" == "--emergency" ]]; then
    export EMERGENCY=true
    shift
    ENVIRONMENT="${1:-production}"
    REVISION="${2:-}"
fi

# Run main function
main "$@"
