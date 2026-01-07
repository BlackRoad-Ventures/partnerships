#!/usr/bin/env bash
# 💛 Trinity-Codex Integration
# Access to 8,789+ reusable components across BlackRoad ecosystem

# Color codes
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

CODEX_REPO="blackroad-os/blackroad-os-codex"
CODEX_URL="https://github.com/${CODEX_REPO}"

_codex_log() {
    local emoji="$1"
    local message="$2"
    echo -e "${YELLOW}[CODEX]${NC} ${emoji} ${message}"
}

# Check if codex is available locally
codex_available() {
    if [ -d "../blackroad-os-codex" ]; then
        return 0
    elif [ -d "../../blackroad-os-codex" ]; then
        return 0
    else
        return 1
    fi
}

# Get codex path
get_codex_path() {
    if [ -d "../blackroad-os-codex" ]; then
        echo "../blackroad-os-codex"
    elif [ -d "../../blackroad-os-codex" ]; then
        echo "../../blackroad-os-codex"
    else
        echo ""
    fi
}

# Initialize codex
codex_init() {
    _codex_log "🔧" "Initializing BlackRoad Codex integration..."
    
    if codex_available; then
        local codex_path=$(get_codex_path)
        _codex_log "✅" "Codex found at: ${codex_path}"
        return 0
    else
        _codex_log "⚠️" "Codex not found locally"
        _codex_log "ℹ️" "Clone from: ${CODEX_URL}"
        _codex_log "ℹ️" "Recommended location: ../blackroad-os-codex"
        return 1
    fi
}

# Search for components
codex_search() {
    local query="$1"
    
    if [ -z "$query" ]; then
        _codex_log "❌" "Usage: codex_search <query>"
        return 1
    fi
    
    _codex_log "🔍" "Searching for: ${query}"
    
    if codex_available; then
        local codex_path=$(get_codex_path)
        
        # Search in Python files
        _codex_log "📄" "Python components:"
        grep -r --include="*.py" -l "$query" "$codex_path" 2>/dev/null | head -5
        
        # Search in TypeScript files
        _codex_log "📄" "TypeScript components:"
        grep -r --include="*.ts" -l "$query" "$codex_path" 2>/dev/null | head -5
        
        # Search in documentation
        _codex_log "📄" "Documentation:"
        grep -r --include="*.md" -l "$query" "$codex_path" 2>/dev/null | head -5
        
    else
        _codex_log "⚠️" "Codex not available. Run 'codex_init' first"
        return 1
    fi
}

# Extract a component
codex_extract() {
    local component="$1"
    local destination="${2:-.}"
    
    if [ -z "$component" ]; then
        _codex_log "❌" "Usage: codex_extract <component> [destination]"
        return 1
    fi
    
    _codex_log "📦" "Extracting component: ${component}"
    _codex_log "📍" "Destination: ${destination}"
    
    if codex_available; then
        local codex_path=$(get_codex_path)
        
        # Find the component file
        local component_file=$(find "$codex_path" -name "*${component}*" -type f | head -1)
        
        if [ -n "$component_file" ]; then
            cp "$component_file" "$destination/"
            _codex_log "✅" "Extracted: $(basename $component_file)"
        else
            _codex_log "❌" "Component not found: ${component}"
            return 1
        fi
    else
        _codex_log "⚠️" "Codex not available. Run 'codex_init' first"
        return 1
    fi
}

# Verify a component
codex_verify() {
    local component="$1"
    
    if [ -z "$component" ]; then
        _codex_log "❌" "Usage: codex_verify <component>"
        return 1
    fi
    
    _codex_log "🔍" "Verifying component: ${component}"
    
    if codex_available; then
        local codex_path=$(get_codex_path)
        
        # Check if verification script exists
        if [ -f "$codex_path/blackroad-codex-verification.py" ]; then
            python3 "$codex_path/blackroad-codex-verification.py" "$component"
        else
            _codex_log "⚠️" "Verification script not found"
            _codex_log "ℹ️" "Manual verification recommended"
        fi
    else
        _codex_log "⚠️" "Codex not available. Run 'codex_init' first"
        return 1
    fi
}

# List component categories
codex_categories() {
    _codex_log "📚" "Component Categories in BlackRoad Codex:"
    echo ""
    echo "  🔐 Authentication - JWT, OAuth, session management"
    echo "  🌐 API Clients - HTTP, GraphQL, WebSocket"
    echo "  🗄️ Database - Migrations, models, queries"
    echo "  🏗️ Infrastructure - Docker, K8s, CI/CD"
    echo "  🎨 UI Components - React, Vue, Svelte"
    echo "  🛠️ Utilities - Helpers, validators, formatters"
    echo "  📋 Templates - Project scaffolding"
    echo "  🔍 Search - Indexing, search engines"
    echo "  📊 Analytics - Tracking, metrics"
    echo "  🔔 Notifications - Email, push, SMS"
    echo ""
    echo "Total: 8,789+ components across 56 repositories"
    echo ""
}

# Get codex statistics
codex_stats() {
    _codex_log "📊" "BlackRoad Codex Statistics:"
    echo ""
    echo "  Total Components: 8,789+"
    echo "  Repositories: 56"
    echo "  Languages: Python, TypeScript, JavaScript, Go, Rust"
    echo "  Last Updated: December 2025"
    echo "  Lines of Code: 500,000+"
    echo ""
    
    if codex_available; then
        local codex_path=$(get_codex_path)
        _codex_log "✅" "Codex available locally at: ${codex_path}"
        
        echo ""
        echo "  Local Statistics:"
        echo "  Python files: $(find "$codex_path" -name "*.py" 2>/dev/null | wc -l)"
        echo "  TypeScript files: $(find "$codex_path" -name "*.ts" 2>/dev/null | wc -l)"
        echo "  JavaScript files: $(find "$codex_path" -name "*.js" 2>/dev/null | wc -l)"
    else
        _codex_log "⚠️" "Codex not available locally"
    fi
    echo ""
}

# Show help
codex_help() {
    echo ""
    echo "🔗 Trinity-Codex Integration - Available Functions"
    echo ""
    echo "INITIALIZATION:"
    echo "  codex_init                - Check and initialize Codex integration"
    echo ""
    echo "SEARCH & DISCOVERY:"
    echo "  codex_search <query>      - Search for components"
    echo "  codex_categories          - List component categories"
    echo "  codex_stats              - Show Codex statistics"
    echo ""
    echo "COMPONENT MANAGEMENT:"
    echo "  codex_extract <comp> [dest] - Extract component to destination"
    echo "  codex_verify <component>    - Verify component integrity"
    echo ""
    echo "UTILITIES:"
    echo "  codex_help               - Show this help"
    echo ""
}

# Export functions
export -f codex_available get_codex_path
export -f codex_init codex_search codex_extract codex_verify
export -f codex_categories codex_stats codex_help

echo "🔗 Trinity-Codex Integration loaded"
echo "Run 'codex_help' for available commands"
echo "Run 'codex_init' to initialize"
