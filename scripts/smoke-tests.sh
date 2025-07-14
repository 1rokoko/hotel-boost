#!/bin/bash

# WhatsApp Hotel Bot Smoke Tests
# Usage: ./scripts/smoke-tests.sh <environment>
# Example: ./scripts/smoke-tests.sh production

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

# Test results
TESTS_PASSED=0
TESTS_FAILED=0
FAILED_TESTS=()

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

log_test_pass() {
    echo -e "${GREEN}[PASS]${NC} $1"
    ((TESTS_PASSED++))
}

log_test_fail() {
    echo -e "${RED}[FAIL]${NC} $1"
    ((TESTS_FAILED++))
    FAILED_TESTS+=("$1")
}

# Usage function
usage() {
    echo "Usage: $0 <environment>"
    echo ""
    echo "Arguments:"
    echo "  environment  Target environment (staging, production)"
    echo ""
    echo "Examples:"
    echo "  $0 staging"
    echo "  $0 production"
    exit 1
}

# Validate arguments
if [ $# -ne 1 ]; then
    log_error "Invalid number of arguments"
    usage
fi

ENVIRONMENT="$1"

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
        BASE_URL="https://staging.hotel-bot.example.com"
        ;;
    production)
        NAMESPACE="hotel-bot"
        BASE_URL="https://hotel-bot.example.com"
        ;;
esac

log_info "Running smoke tests for $ENVIRONMENT environment"
log_info "Namespace: $NAMESPACE"
log_info "Base URL: $BASE_URL"

# Test helper functions
test_http_endpoint() {
    local endpoint="$1"
    local expected_status="${2:-200}"
    local test_name="$3"
    
    log_info "Testing: $test_name"
    
    local response
    local status_code
    
    if response=$(curl -s -w "%{http_code}" "$endpoint" --max-time 30); then
        status_code="${response: -3}"
        response_body="${response%???}"
        
        if [ "$status_code" = "$expected_status" ]; then
            log_test_pass "$test_name (HTTP $status_code)"
            return 0
        else
            log_test_fail "$test_name (Expected HTTP $expected_status, got $status_code)"
            return 1
        fi
    else
        log_test_fail "$test_name (Connection failed)"
        return 1
    fi
}

test_json_response() {
    local endpoint="$1"
    local expected_field="$2"
    local test_name="$3"
    
    log_info "Testing: $test_name"
    
    local response
    
    if response=$(curl -s "$endpoint" --max-time 30); then
        if echo "$response" | jq -e ".$expected_field" > /dev/null 2>&1; then
            log_test_pass "$test_name (JSON field '$expected_field' present)"
            return 0
        else
            log_test_fail "$test_name (JSON field '$expected_field' missing)"
            return 1
        fi
    else
        log_test_fail "$test_name (Connection failed)"
        return 1
    fi
}

test_kubernetes_resource() {
    local resource_type="$1"
    local resource_name="$2"
    local test_name="$3"
    
    log_info "Testing: $test_name"
    
    if kubectl get "$resource_type" "$resource_name" -n "$NAMESPACE" > /dev/null 2>&1; then
        log_test_pass "$test_name ($resource_type/$resource_name exists)"
        return 0
    else
        log_test_fail "$test_name ($resource_type/$resource_name not found)"
        return 1
    fi
}

test_pod_status() {
    local label_selector="$1"
    local test_name="$2"
    
    log_info "Testing: $test_name"
    
    local ready_pods
    local total_pods
    
    ready_pods=$(kubectl get pods -n "$NAMESPACE" -l "$label_selector" --field-selector=status.phase=Running -o name | wc -l)
    total_pods=$(kubectl get pods -n "$NAMESPACE" -l "$label_selector" -o name | wc -l)
    
    if [ "$ready_pods" -gt 0 ] && [ "$ready_pods" -eq "$total_pods" ]; then
        log_test_pass "$test_name ($ready_pods/$total_pods pods running)"
        return 0
    else
        log_test_fail "$test_name ($ready_pods/$total_pods pods running)"
        return 1
    fi
}

# Test functions
test_kubernetes_resources() {
    log_info "=== Testing Kubernetes Resources ==="
    
    test_kubernetes_resource "namespace" "$NAMESPACE" "Namespace exists"
    test_kubernetes_resource "deployment" "whatsapp-hotel-bot-api" "API deployment exists"
    test_kubernetes_resource "deployment" "whatsapp-hotel-bot-celery-worker" "Celery worker deployment exists"
    test_kubernetes_resource "deployment" "whatsapp-hotel-bot-celery-beat" "Celery beat deployment exists"
    test_kubernetes_resource "service" "whatsapp-hotel-bot-api" "API service exists"
    test_kubernetes_resource "configmap" "whatsapp-hotel-bot-config" "ConfigMap exists"
    test_kubernetes_resource "secret" "whatsapp-hotel-bot-secrets" "Secrets exist"
}

test_pod_health() {
    log_info "=== Testing Pod Health ==="
    
    test_pod_status "app=whatsapp-hotel-bot,component=api" "API pods are running"
    test_pod_status "app=whatsapp-hotel-bot,component=celery-worker" "Celery worker pods are running"
    test_pod_status "app=whatsapp-hotel-bot,component=celery-beat" "Celery beat pod is running"
}

test_api_endpoints() {
    log_info "=== Testing API Endpoints ==="
    
    # Test basic endpoints
    test_http_endpoint "$BASE_URL/health" "200" "Health endpoint"
    test_http_endpoint "$BASE_URL/health/ready" "200" "Readiness endpoint"
    test_http_endpoint "$BASE_URL/" "200" "Root endpoint"
    test_http_endpoint "$BASE_URL/docs" "200" "API documentation"
    
    # Test API endpoints
    test_http_endpoint "$BASE_URL/api/v1/health" "200" "API v1 health endpoint"
    
    # Test JSON responses
    test_json_response "$BASE_URL/health" "status" "Health endpoint JSON structure"
    test_json_response "$BASE_URL/" "message" "Root endpoint JSON structure"
}

test_monitoring_endpoints() {
    log_info "=== Testing Monitoring Endpoints ==="
    
    # Test metrics endpoint (if enabled)
    if curl -s "$BASE_URL/metrics" --max-time 10 > /dev/null 2>&1; then
        log_test_pass "Metrics endpoint accessible"
    else
        log_warning "Metrics endpoint not accessible (may be disabled)"
    fi
}

test_database_connectivity() {
    log_info "=== Testing Database Connectivity ==="
    
    # Test database connectivity through API
    local db_test_endpoint="$BASE_URL/api/v1/health/database"
    
    if curl -s "$db_test_endpoint" --max-time 30 > /dev/null 2>&1; then
        log_test_pass "Database connectivity through API"
    else
        log_test_fail "Database connectivity through API"
    fi
}

test_external_dependencies() {
    log_info "=== Testing External Dependencies ==="
    
    # Test Redis connectivity through API
    local redis_test_endpoint="$BASE_URL/api/v1/health/redis"
    
    if curl -s "$redis_test_endpoint" --max-time 30 > /dev/null 2>&1; then
        log_test_pass "Redis connectivity through API"
    else
        log_test_fail "Redis connectivity through API"
    fi
}

test_security_headers() {
    log_info "=== Testing Security Headers ==="
    
    local headers
    headers=$(curl -s -I "$BASE_URL/" --max-time 30)
    
    if echo "$headers" | grep -i "x-frame-options" > /dev/null; then
        log_test_pass "X-Frame-Options header present"
    else
        log_test_fail "X-Frame-Options header missing"
    fi
    
    if echo "$headers" | grep -i "x-content-type-options" > /dev/null; then
        log_test_pass "X-Content-Type-Options header present"
    else
        log_test_fail "X-Content-Type-Options header missing"
    fi
}

test_performance() {
    log_info "=== Testing Performance ==="
    
    local response_time
    response_time=$(curl -s -w "%{time_total}" -o /dev/null "$BASE_URL/health" --max-time 30)
    
    if (( $(echo "$response_time < 2.0" | bc -l) )); then
        log_test_pass "Health endpoint response time acceptable (${response_time}s)"
    else
        log_test_fail "Health endpoint response time too slow (${response_time}s)"
    fi
}

# Main test execution
main() {
    log_info "=== WhatsApp Hotel Bot Smoke Tests ==="
    log_info "Environment: $ENVIRONMENT"
    log_info "Namespace: $NAMESPACE"
    log_info "Base URL: $BASE_URL"
    echo ""
    
    # Check prerequisites
    if ! command -v kubectl &> /dev/null; then
        log_error "kubectl is not installed or not in PATH"
        exit 1
    fi
    
    if ! command -v curl &> /dev/null; then
        log_error "curl is not installed or not in PATH"
        exit 1
    fi
    
    if ! command -v jq &> /dev/null; then
        log_error "jq is not installed or not in PATH"
        exit 1
    fi
    
    # Run test suites
    test_kubernetes_resources
    echo ""
    test_pod_health
    echo ""
    test_api_endpoints
    echo ""
    test_monitoring_endpoints
    echo ""
    test_database_connectivity
    echo ""
    test_external_dependencies
    echo ""
    test_security_headers
    echo ""
    test_performance
    echo ""
    
    # Print summary
    log_info "=== Test Summary ==="
    log_info "Tests passed: $TESTS_PASSED"
    log_info "Tests failed: $TESTS_FAILED"
    
    if [ $TESTS_FAILED -eq 0 ]; then
        log_success "All smoke tests passed!"
        exit 0
    else
        log_error "Some smoke tests failed:"
        for test in "${FAILED_TESTS[@]}"; do
            log_error "  - $test"
        done
        exit 1
    fi
}

# Run main function
main "$@"
