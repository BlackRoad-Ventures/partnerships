#!/usr/bin/env bash
# 💛 YellowLight Infrastructure System
# Infrastructure automation and deployment

# Color codes
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

# Helper function for logging
_yl_log() {
    local emoji="$1"
    local category="$2"
    local message="$3"
    echo -e "${YELLOW}[$(date -u +%Y-%m-%dT%H:%M:%SZ)]${NC} ${emoji} ${BLUE}[${category}]${NC} ${message}"
}

# ========================================
# DEPLOYMENT FUNCTIONS
# ========================================

deploy_to_railway() {
    local service="$1"
    local environment="${2:-production}"
    
    _yl_log "🚂" "RAILWAY" "Deploying ${service} to ${environment}..."
    
    if command -v railway &> /dev/null; then
        railway up --environment "$environment"
    else
        _yl_log "⚠️" "RAILWAY" "Railway CLI not installed. Install with: npm i -g @railway/cli"
        return 1
    fi
}

deploy_to_cloudflare() {
    local service="$1"
    local environment="${2:-production}"
    
    _yl_log "☁️" "CLOUDFLARE" "Deploying ${service} to ${environment}..."
    
    if [ -f "wrangler.toml" ]; then
        if command -v wrangler &> /dev/null; then
            wrangler publish --env "$environment"
        else
            _yl_log "⚠️" "CLOUDFLARE" "Wrangler CLI not installed. Install with: npm i -g wrangler"
            return 1
        fi
    elif [ -d "dist" ] || [ -d "build" ]; then
        if command -v wrangler &> /dev/null; then
            wrangler pages publish dist --project-name "$service"
        else
            _yl_log "⚠️" "CLOUDFLARE" "Wrangler CLI not installed. Install with: npm i -g wrangler"
            return 1
        fi
    else
        _yl_log "❌" "CLOUDFLARE" "No deployment configuration found"
        return 1
    fi
}

deploy_to_digitalocean() {
    local service="$1"
    local environment="${2:-production}"
    
    _yl_log "🌊" "DIGITALOCEAN" "Deploying ${service} to ${environment}..."
    
    if command -v doctl &> /dev/null; then
        # This is a placeholder - customize based on your DigitalOcean setup
        # Example options:
        # - App Platform: doctl apps create-deployment <app-id>
        # - Droplets: Use SSH to deploy via git pull or SCP
        # - Kubernetes: kubectl apply -f manifests/
        _yl_log "ℹ️" "DIGITALOCEAN" "Placeholder: Implement DigitalOcean deployment for your specific infrastructure"
        _yl_log "ℹ️" "DIGITALOCEAN" "Options: App Platform, Droplets, or Kubernetes"
        return 1
    else
        _yl_log "⚠️" "DIGITALOCEAN" "doctl CLI not installed. Install from: https://docs.digitalocean.com/reference/doctl/"
        return 1
    fi
}

# ========================================
# HEALTH CHECK FUNCTIONS
# ========================================

health_check() {
    local url="$1"
    local expected_status="${2:-200}"
    
    _yl_log "🏥" "HEALTH" "Checking ${url}..."
    
    if command -v curl &> /dev/null; then
        local status=$(curl -s -o /dev/null -w "%{http_code}" "$url")
        
        if [ "$status" = "$expected_status" ]; then
            _yl_log "✅" "HEALTH" "Healthy (HTTP ${status})"
            return 0
        else
            _yl_log "❌" "HEALTH" "Unhealthy (HTTP ${status}, expected ${expected_status})"
            return 1
        fi
    else
        _yl_log "⚠️" "HEALTH" "curl not installed"
        return 1
    fi
}

database_check() {
    local connection_string="$1"
    
    _yl_log "🗄️" "DATABASE" "Checking database connection..."
    
    # Extract database type from connection string
    if [[ "$connection_string" == postgresql://* ]] || [[ "$connection_string" == postgres://* ]]; then
        if command -v psql &> /dev/null; then
            if psql "$connection_string" -c "SELECT 1" &> /dev/null; then
                _yl_log "✅" "DATABASE" "PostgreSQL connection successful"
                return 0
            else
                _yl_log "❌" "DATABASE" "PostgreSQL connection failed"
                return 1
            fi
        else
            _yl_log "⚠️" "DATABASE" "psql not installed"
            return 1
        fi
    else
        _yl_log "ℹ️" "DATABASE" "Database type not recognized or not supported"
        return 1
    fi
}

service_status() {
    local service="$1"
    
    _yl_log "📊" "STATUS" "Checking ${service} status..."
    
    # Check if service is running locally
    if pgrep -f "$service" > /dev/null; then
        _yl_log "✅" "STATUS" "${service} is running"
        return 0
    else
        _yl_log "❌" "STATUS" "${service} is not running"
        return 1
    fi
}

# ========================================
# ROLLBACK FUNCTIONS
# ========================================

rollback_service() {
    local service="$1"
    local version="$2"
    
    _yl_log "⏪" "ROLLBACK" "Rolling back ${service} to version ${version}..."
    
    # Source GreenLight to log the event
    if [ -f ".trinity/greenlight/scripts/memory-greenlight-templates.sh" ]; then
        source .trinity/greenlight/scripts/memory-greenlight-templates.sh
        gl_rollback_initiated "$service" "current" "$version" "Manual rollback"
    fi
    
    _yl_log "ℹ️" "ROLLBACK" "Implement rollback for your deployment platform"
    
    # Placeholder for actual rollback logic
    # This would depend on your deployment platform
    
    return 0
}

rollback_database() {
    local backup_id="$1"
    
    _yl_log "⏪" "ROLLBACK" "Rolling back database to backup ${backup_id}..."
    _yl_log "⚠️" "ROLLBACK" "Database rollbacks should be done carefully!"
    _yl_log "ℹ️" "ROLLBACK" "Implement database rollback for your setup"
    
    return 1
}

# ========================================
# MONITORING FUNCTIONS
# ========================================

check_metrics() {
    local service="$1"
    
    _yl_log "📈" "METRICS" "Checking metrics for ${service}..."
    
    # CPU and memory usage
    if command -v top &> /dev/null; then
        local pid=$(pgrep -f "$service" | head -1)
        if [ -n "$pid" ]; then
            _yl_log "ℹ️" "METRICS" "Process ID: ${pid}"
            # Add actual metrics collection here
        else
            _yl_log "⚠️" "METRICS" "Service not found"
        fi
    fi
}

view_logs() {
    local service="$1"
    local lines="${2:-50}"
    
    _yl_log "📝" "LOGS" "Viewing last ${lines} lines for ${service}..."
    
    # Check common log locations
    if [ -f "/var/log/${service}.log" ]; then
        tail -n "$lines" "/var/log/${service}.log"
    elif [ -f "logs/${service}.log" ]; then
        tail -n "$lines" "logs/${service}.log"
    else
        _yl_log "⚠️" "LOGS" "Log file not found"
    fi
}

alert_status() {
    local service="$1"
    
    _yl_log "🔔" "ALERTS" "Checking alert status for ${service}..."
    _yl_log "ℹ️" "ALERTS" "Implement alert checking for your monitoring system"
}

# ========================================
# UTILITY FUNCTIONS
# ========================================

infrastructure_info() {
    echo ""
    _yl_log "ℹ️" "INFO" "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    _yl_log "ℹ️" "INFO" "YellowLight Infrastructure System"
    _yl_log "ℹ️" "INFO" "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    
    echo ""
    _yl_log "🔧" "INFO" "Installed Tools:"
    command -v railway &> /dev/null && echo "  ✅ Railway CLI" || echo "  ❌ Railway CLI"
    command -v wrangler &> /dev/null && echo "  ✅ Wrangler (Cloudflare)" || echo "  ❌ Wrangler (Cloudflare)"
    command -v doctl &> /dev/null && echo "  ✅ doctl (DigitalOcean)" || echo "  ❌ doctl (DigitalOcean)"
    command -v docker &> /dev/null && echo "  ✅ Docker" || echo "  ❌ Docker"
    command -v kubectl &> /dev/null && echo "  ✅ kubectl (Kubernetes)" || echo "  ❌ kubectl (Kubernetes)"
    
    echo ""
    _yl_log "ℹ️" "INFO" "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
}

show_help() {
    echo ""
    echo "💛 YellowLight Infrastructure System - Available Functions"
    echo ""
    echo "DEPLOYMENT:"
    echo "  deploy_to_railway <service> [environment]"
    echo "  deploy_to_cloudflare <service> [environment]"
    echo "  deploy_to_digitalocean <service> [environment]"
    echo ""
    echo "HEALTH CHECKS:"
    echo "  health_check <url> [expected_status]"
    echo "  database_check <connection_string>"
    echo "  service_status <service>"
    echo ""
    echo "ROLLBACKS:"
    echo "  rollback_service <service> <version>"
    echo "  rollback_database <backup_id>"
    echo ""
    echo "MONITORING:"
    echo "  check_metrics <service>"
    echo "  view_logs <service> [lines]"
    echo "  alert_status <service>"
    echo ""
    echo "UTILITIES:"
    echo "  infrastructure_info"
    echo "  show_help"
    echo ""
}

# Export functions
export -f deploy_to_railway deploy_to_cloudflare deploy_to_digitalocean
export -f health_check database_check service_status
export -f rollback_service rollback_database
export -f check_metrics view_logs alert_status
export -f infrastructure_info show_help

echo "💛 YellowLight Infrastructure System loaded"
echo "Run 'show_help' for available commands"
echo "Run 'infrastructure_info' for system information"
