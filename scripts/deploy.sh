#!/bin/bash

# WhatsApp Hotel Bot Deployment Script
# Usage: ./scripts/deploy.sh <environment> <image_tag>
# Example: ./scripts/deploy.sh production ghcr.io/org/whatsapp-hotel-bot:v1.0.0

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
K8S_DIR="${PROJECT_ROOT}/k8s"

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
    echo "Usage: $0 <environment> <image_tag>"
    echo ""
    echo "Arguments:"
    echo "  environment  Target environment (staging, production)"
    echo "  image_tag    Docker image tag to deploy"
    echo ""
    echo "Examples:"
    echo "  $0 staging ghcr.io/org/whatsapp-hotel-bot:develop"
    echo "  $0 production ghcr.io/org/whatsapp-hotel-bot:v1.0.0"
    exit 1
}

# Validate arguments
if [ $# -ne 2 ]; then
    log_error "Invalid number of arguments"
    usage
fi

ENVIRONMENT="$1"
IMAGE_TAG="$2"

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
        REPLICAS_API=2
        REPLICAS_WORKER=1
        ;;
    production)
        NAMESPACE="hotel-bot"
        REPLICAS_API=3
        REPLICAS_WORKER=2
        ;;
esac

log_info "Starting deployment to $ENVIRONMENT environment"
log_info "Image tag: $IMAGE_TAG"
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
        log_warning "Namespace $NAMESPACE does not exist, creating it..."
        kubectl create namespace "$NAMESPACE"
        kubectl label namespace "$NAMESPACE" name="$NAMESPACE"
    fi
    
    log_success "Prerequisites check passed"
}

# Create or update secrets
deploy_secrets() {
    log_info "Deploying secrets..."
    
    # Check if secrets file exists
    if [ ! -f "${K8S_DIR}/secrets-${ENVIRONMENT}.yaml" ]; then
        log_error "Secrets file not found: ${K8S_DIR}/secrets-${ENVIRONMENT}.yaml"
        log_error "Please create environment-specific secrets file"
        exit 1
    fi
    
    kubectl apply -f "${K8S_DIR}/secrets-${ENVIRONMENT}.yaml" -n "$NAMESPACE"
    log_success "Secrets deployed"
}

# Deploy ConfigMaps
deploy_configmaps() {
    log_info "Deploying ConfigMaps..."
    
    # Apply base ConfigMaps
    kubectl apply -f "${K8S_DIR}/configmap.yaml" -n "$NAMESPACE"
    
    # Apply environment-specific ConfigMaps if they exist
    if [ -f "${K8S_DIR}/configmap-${ENVIRONMENT}.yaml" ]; then
        kubectl apply -f "${K8S_DIR}/configmap-${ENVIRONMENT}.yaml" -n "$NAMESPACE"
    fi
    
    log_success "ConfigMaps deployed"
}

# Deploy services
deploy_services() {
    log_info "Deploying services..."
    kubectl apply -f "${K8S_DIR}/service.yaml" -n "$NAMESPACE"
    log_success "Services deployed"
}

# Deploy ingress
deploy_ingress() {
    log_info "Deploying ingress..."
    
    # Apply base ingress
    kubectl apply -f "${K8S_DIR}/ingress.yaml" -n "$NAMESPACE"
    
    # Apply environment-specific ingress if it exists
    if [ -f "${K8S_DIR}/ingress-${ENVIRONMENT}.yaml" ]; then
        kubectl apply -f "${K8S_DIR}/ingress-${ENVIRONMENT}.yaml" -n "$NAMESPACE"
    fi
    
    log_success "Ingress deployed"
}

# Update deployment with new image
update_deployment() {
    log_info "Updating deployment with image: $IMAGE_TAG"
    
    # Create temporary deployment file with updated image and replicas
    TEMP_DEPLOYMENT=$(mktemp)
    
    # Update image tag and replicas in deployment
    sed -e "s|image: whatsapp-hotel-bot:latest|image: $IMAGE_TAG|g" \
        -e "s|replicas: 3|replicas: $REPLICAS_API|g" \
        -e "s|replicas: 2|replicas: $REPLICAS_WORKER|g" \
        "${K8S_DIR}/deployment.yaml" > "$TEMP_DEPLOYMENT"
    
    # Apply the updated deployment
    kubectl apply -f "$TEMP_DEPLOYMENT" -n "$NAMESPACE"
    
    # Clean up temporary file
    rm "$TEMP_DEPLOYMENT"
    
    log_success "Deployment updated"
}

# Wait for deployment to be ready
wait_for_deployment() {
    log_info "Waiting for deployment to be ready..."
    
    # Wait for API deployment
    if ! kubectl rollout status deployment/whatsapp-hotel-bot-api -n "$NAMESPACE" --timeout=600s; then
        log_error "API deployment failed to become ready"
        return 1
    fi
    
    # Wait for Celery worker deployment
    if ! kubectl rollout status deployment/whatsapp-hotel-bot-celery-worker -n "$NAMESPACE" --timeout=300s; then
        log_error "Celery worker deployment failed to become ready"
        return 1
    fi
    
    # Wait for Celery beat deployment
    if ! kubectl rollout status deployment/whatsapp-hotel-bot-celery-beat -n "$NAMESPACE" --timeout=300s; then
        log_error "Celery beat deployment failed to become ready"
        return 1
    fi
    
    log_success "All deployments are ready"
}

# Verify deployment health
verify_deployment() {
    log_info "Verifying deployment health..."
    
    # Get service endpoint
    SERVICE_IP=$(kubectl get service whatsapp-hotel-bot-api -n "$NAMESPACE" -o jsonpath='{.spec.clusterIP}')
    
    # Wait a bit for the service to be fully ready
    sleep 10
    
    # Test health endpoint using kubectl port-forward in background
    kubectl port-forward service/whatsapp-hotel-bot-api 8080:8000 -n "$NAMESPACE" &
    PORT_FORWARD_PID=$!
    
    # Wait for port-forward to establish
    sleep 5
    
    # Test health endpoint
    if curl -f http://localhost:8080/health > /dev/null 2>&1; then
        log_success "Health check passed"
        HEALTH_CHECK_PASSED=true
    else
        log_error "Health check failed"
        HEALTH_CHECK_PASSED=false
    fi
    
    # Clean up port-forward
    kill $PORT_FORWARD_PID 2>/dev/null || true
    
    if [ "$HEALTH_CHECK_PASSED" = false ]; then
        return 1
    fi
}

# Main deployment function
main() {
    log_info "=== WhatsApp Hotel Bot Deployment ==="
    log_info "Environment: $ENVIRONMENT"
    log_info "Image: $IMAGE_TAG"
    log_info "Namespace: $NAMESPACE"
    echo ""
    
    # Execute deployment steps
    check_prerequisites
    deploy_secrets
    deploy_configmaps
    deploy_services
    deploy_ingress
    update_deployment
    wait_for_deployment
    verify_deployment
    
    log_success "=== Deployment completed successfully ==="
    
    # Display deployment information
    echo ""
    log_info "Deployment Information:"
    kubectl get pods -n "$NAMESPACE" -l app=whatsapp-hotel-bot
    echo ""
    kubectl get services -n "$NAMESPACE"
    echo ""
    kubectl get ingress -n "$NAMESPACE"
}

# Error handling
trap 'log_error "Deployment failed at line $LINENO"' ERR

# Run main function
main "$@"
