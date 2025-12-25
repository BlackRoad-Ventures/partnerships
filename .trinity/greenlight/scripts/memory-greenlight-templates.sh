#!/usr/bin/env bash
# 💚 GreenLight Template System
# Real-time intelligence and multi-agent coordination

# Color codes for terminal output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Helper function to log with timestamp
_gl_log() {
    local emoji="$1"
    local category="$2"
    local message="$3"
    echo -e "${GREEN}[$(date -u +%Y-%m-%dT%H:%M:%SZ)]${NC} ${emoji} ${YELLOW}[${category}]${NC} ${message}"
}

# ========================================
# DEPLOYMENT & INFRASTRUCTURE
# ========================================

gl_deployment_started() {
    local service="$1"
    local version="$2"
    local environment="$3"
    local message="${4:-Deployment started}"
    _gl_log "🚀" "DEPLOY" "Starting deployment: ${service} v${version} to ${environment} - ${message}"
}

gl_deployed() {
    local service="$1"
    local version="$2"
    local environment="$3"
    local message="${4:-Deployment successful}"
    _gl_log "✅" "DEPLOY" "Deployed: ${service} v${version} to ${environment} - ${message}"
}

gl_deployment_failed() {
    local service="$1"
    local version="$2"
    local environment="$3"
    local reason="$4"
    _gl_log "❌" "DEPLOY" "Deployment FAILED: ${service} v${version} to ${environment} - ${reason}"
}

gl_rollback_initiated() {
    local service="$1"
    local from_version="$2"
    local to_version="$3"
    local reason="$4"
    _gl_log "⏪" "ROLLBACK" "Rolling back ${service}: v${from_version} → v${to_version} - ${reason}"
}

gl_rollback_completed() {
    local service="$1"
    local version="$2"
    _gl_log "✅" "ROLLBACK" "Rollback complete: ${service} v${version}"
}

# ========================================
# DEVELOPMENT & CODE
# ========================================

gl_feature_started() {
    local project="$1"
    local feature="$2"
    local description="${3:-New feature}"
    _gl_log "✨" "FEATURE" "Started: ${project}/${feature} - ${description}"
}

gl_feature_completed() {
    local project="$1"
    local feature="$2"
    local description="${3:-Feature complete}"
    _gl_log "🎉" "FEATURE" "Completed: ${project}/${feature} - ${description}"
}

gl_bug_detected() {
    local project="$1"
    local bug="$2"
    local description="$3"
    local severity="${4:-medium}"
    _gl_log "🐛" "BUG" "Detected [${severity}]: ${project}/${bug} - ${description}"
}

gl_bug_fixed() {
    local project="$1"
    local bug="$2"
    local description="${3:-Bug fixed}"
    _gl_log "🔧" "BUG" "Fixed: ${project}/${bug} - ${description}"
}

gl_code_review_requested() {
    local project="$1"
    local pr="$2"
    local description="$3"
    _gl_log "👀" "REVIEW" "Review requested: ${project}#${pr} - ${description}"
}

# ========================================
# MULTI-AGENT COORDINATION
# ========================================

gl_agent_available() {
    local agent_name="$1"
    local area="$2"
    local capabilities="${3:-General development}"
    _gl_log "🤖" "AGENT" "Available: ${agent_name} | Area: ${area} | Skills: ${capabilities}"
}

gl_task_claimed() {
    local task_id="$1"
    local agent_name="$2"
    local description="$3"
    _gl_log "🎯" "TASK" "Claimed by ${agent_name}: ${task_id} - ${description}"
}

gl_help_requested() {
    local agent_name="$1"
    local area="$2"
    local issue="$3"
    _gl_log "🆘" "HELP" "Requested by ${agent_name}: ${area} - ${issue}"
}

gl_collaboration_success() {
    local task_id="$1"
    local agents="$2"
    local result="$3"
    _gl_log "🤝" "COLLAB" "Success: ${task_id} | Agents: ${agents} | Result: ${result}"
}

gl_learning_discovered() {
    local topic="$1"
    local insight="$2"
    local impact="${3:-General improvement}"
    _gl_log "💡" "LEARN" "Discovery: ${topic} - ${insight} | Impact: ${impact}"
}

# ========================================
# MONITORING & ALERTS
# ========================================

gl_error_detected() {
    local service="$1"
    local error_type="$2"
    local description="$3"
    local severity="${4:-medium}"
    _gl_log "🔥" "ERROR" "[${severity}] ${service}: ${error_type} - ${description}"
}

gl_performance_degraded() {
    local service="$1"
    local metric="$2"
    local current_value="$3"
    local threshold="$4"
    _gl_log "⚡" "PERF" "Degraded: ${service} | ${metric}: ${current_value} (threshold: ${threshold})"
}

gl_service_unhealthy() {
    local service="$1"
    local check="$2"
    local reason="$3"
    _gl_log "⚠️" "HEALTH" "Unhealthy: ${service} | Check: ${check} | Reason: ${reason}"
}

gl_incident_declared() {
    local incident_id="$1"
    local severity="$2"
    local description="$3"
    _gl_log "🚨" "INCIDENT" "[${severity}] ${incident_id}: ${description}"
}

gl_incident_resolved() {
    local incident_id="$1"
    local resolution="$2"
    _gl_log "✅" "INCIDENT" "Resolved: ${incident_id} - ${resolution}"
}

# ========================================
# ANNOUNCEMENTS
# ========================================

gl_announce() {
    local project="$1"
    local title="$2"
    local plan="$3"
    local purpose="${4:-General work}"
    echo ""
    _gl_log "📢" "ANNOUNCE" "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    _gl_log "📢" "ANNOUNCE" "Project: ${project}"
    _gl_log "📢" "ANNOUNCE" "Title: ${title}"
    _gl_log "📢" "ANNOUNCE" "Plan: ${plan}"
    _gl_log "📢" "ANNOUNCE" "Purpose: ${purpose}"
    _gl_log "📢" "ANNOUNCE" "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
}

# ========================================
# SYSTEM & STATUS
# ========================================

gl_system_started() {
    local system="$1"
    local version="${2:-unknown}"
    _gl_log "🟢" "SYSTEM" "Started: ${system} v${version}"
}

gl_system_stopped() {
    local system="$1"
    local reason="${2:-Normal shutdown}"
    _gl_log "🔴" "SYSTEM" "Stopped: ${system} - ${reason}"
}

gl_status_update() {
    local component="$1"
    local status="$2"
    local details="${3:-No details}"
    _gl_log "ℹ️" "STATUS" "${component}: ${status} - ${details}"
}

# ========================================
# HELP & UTILITIES
# ========================================

show_help() {
    echo ""
    echo "💚 GreenLight Template System - Available Functions"
    echo ""
    echo "DEPLOYMENT & INFRASTRUCTURE:"
    echo "  gl_deployment_started <service> <version> <env> [message]"
    echo "  gl_deployed <service> <version> <env> [message]"
    echo "  gl_deployment_failed <service> <version> <env> <reason>"
    echo "  gl_rollback_initiated <service> <from_ver> <to_ver> <reason>"
    echo "  gl_rollback_completed <service> <version>"
    echo ""
    echo "DEVELOPMENT & CODE:"
    echo "  gl_feature_started <project> <feature> [description]"
    echo "  gl_feature_completed <project> <feature> [description]"
    echo "  gl_bug_detected <project> <bug> <description> [severity]"
    echo "  gl_bug_fixed <project> <bug> [description]"
    echo "  gl_code_review_requested <project> <pr> <description>"
    echo ""
    echo "MULTI-AGENT COORDINATION:"
    echo "  gl_agent_available <name> <area> [capabilities]"
    echo "  gl_task_claimed <task_id> <agent> <description>"
    echo "  gl_help_requested <agent> <area> <issue>"
    echo "  gl_collaboration_success <task_id> <agents> <result>"
    echo "  gl_learning_discovered <topic> <insight> [impact]"
    echo ""
    echo "MONITORING & ALERTS:"
    echo "  gl_error_detected <service> <type> <description> [severity]"
    echo "  gl_performance_degraded <service> <metric> <value> <threshold>"
    echo "  gl_service_unhealthy <service> <check> <reason>"
    echo "  gl_incident_declared <id> <severity> <description>"
    echo "  gl_incident_resolved <id> <resolution>"
    echo ""
    echo "ANNOUNCEMENTS:"
    echo "  gl_announce <project> <title> <plan> [purpose]"
    echo ""
    echo "SYSTEM & STATUS:"
    echo "  gl_system_started <system> [version]"
    echo "  gl_system_stopped <system> [reason]"
    echo "  gl_status_update <component> <status> [details]"
    echo ""
}

# Export all functions
export -f gl_deployment_started gl_deployed gl_deployment_failed
export -f gl_rollback_initiated gl_rollback_completed
export -f gl_feature_started gl_feature_completed
export -f gl_bug_detected gl_bug_fixed gl_code_review_requested
export -f gl_agent_available gl_task_claimed gl_help_requested
export -f gl_collaboration_success gl_learning_discovered
export -f gl_error_detected gl_performance_degraded gl_service_unhealthy
export -f gl_incident_declared gl_incident_resolved
export -f gl_announce
export -f gl_system_started gl_system_stopped gl_status_update
export -f show_help

echo "💚 GreenLight Template System loaded (27 core functions)"
echo "Run 'show_help' for available commands"
