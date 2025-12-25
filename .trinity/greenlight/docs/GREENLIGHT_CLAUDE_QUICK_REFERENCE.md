# 💚 GreenLight - Project & Collaboration System

## Overview

GreenLight is BlackRoad's unified intelligence and collaboration system, providing real-time event tracking, multi-agent coordination, and context propagation across the entire ecosystem.

## Core Capabilities

### 14 Integration Layers

1. **Memory Layer** - Persistent intelligence storage
2. **NATS Layer** - Real-time event distribution
3. **Slack Layer** - Team communication
4. **Linear Layer** - Issue tracking
5. **GitHub Layer** - Code and CI/CD
6. **Notion Layer** - Documentation
7. **Redis Layer** - Fast data access
8. **Postgres Layer** - Structured data
9. **Anthropic Layer** - Claude integration
10. **Railway Layer** - Infrastructure hosting
11. **Cloudflare Layer** - CDN and security
12. **Context Propagation** - Learning across agents
13. **Analytics & Observability** - Production visibility
14. **AI Agent Coordination** - Multi-Claude teamwork

### 103 Template Functions

GreenLight provides logging templates for every aspect of software development and operations:

#### Deployment & Infrastructure
- `gl_deployment_started` - Track deployment start
- `gl_deployed` - Successful deployment
- `gl_deployment_failed` - Failed deployment
- `gl_rollback_initiated` - Rollback started
- `gl_rollback_completed` - Rollback finished

#### Development & Code
- `gl_feature_started` - New feature development
- `gl_feature_completed` - Feature ready
- `gl_bug_detected` - Bug discovered
- `gl_bug_fixed` - Bug resolved
- `gl_code_review_requested` - PR review needed

#### Multi-Agent Coordination
- `gl_agent_available` - Agent ready for work
- `gl_task_claimed` - Agent takes task
- `gl_help_requested` - Agent needs assistance
- `gl_collaboration_success` - Joint completion
- `gl_learning_discovered` - New insight shared

#### Monitoring & Alerts
- `gl_error_detected` - System error
- `gl_performance_degraded` - Slowness detected
- `gl_service_unhealthy` - Health check failed
- `gl_incident_declared` - Major incident
- `gl_incident_resolved` - Incident closed

### 200+ Emoji States

Visual language for unified communication:
- 🚀 Deployment
- 🐛 Bug
- ✨ Feature
- 🔥 Critical
- ⚡ Performance
- 🤖 AI/Agent
- 🎯 Task
- 💡 Learning
- And 190+ more...

## Usage Examples

### Basic Event Logging

```bash
# Source the templates
source .trinity/greenlight/scripts/memory-greenlight-templates.sh

# Log a deployment
gl_deployed "partnerships" "v1.0.0" "production" "Initial release"

# Log an error
gl_error_detected "partnerships" "api_timeout" "Connection timeout after 30s" "high"

# Log feature completion
gl_feature_completed "partnerships" "trinity-integration" "Trinity system fully integrated"
```

### Multi-Agent Coordination

```bash
# Agent announces availability
gl_agent_available "claude-partnerships" "partnerships" "Venture management, partnership tracking"

# Agent claims a task
gl_task_claimed "feature-123" "claude-partnerships" "Implement partnership dashboard"

# Agent discovers insight
gl_learning_discovered "partnership-tracking" "Use Linear for milestone tracking" "Improved visibility"

# Report collaboration success
gl_collaboration_success "feature-123" "claude-partnerships,claude-frontend" "Dashboard completed"
```

### Announcements

```bash
# Announce work in progress
gl_announce "partnerships" "Trinity Integration" "1) Setup structure 2) Add docs 3) Test" "Infrastructure upgrade"

# Announce completion
gl_announce "partnerships" "Trinity Complete" "All systems operational" "Ready for production"
```

## Event Flow

1. **Local Logging** - Template functions create standardized logs
2. **NATS Distribution** - Events published to message bus
3. **Multi-Channel Routing** - Delivered to Slack, Linear, Notion, etc.
4. **Context Storage** - Saved to memory layer for Claude access
5. **Learning Propagation** - Insights shared across all agents

## Benefits

### For Individual Agents
- ✅ Standardized logging patterns
- ✅ Easy-to-use template functions
- ✅ Automatic multi-channel distribution
- ✅ Context persistence

### For Multi-Agent Teams
- ✅ Real-time visibility of all activities
- ✅ Coordinated task claiming
- ✅ Shared learning and insights
- ✅ Conflict prevention

### For Operations
- ✅ Unified event stream
- ✅ Historical analysis
- ✅ Performance tracking
- ✅ Incident management

## Configuration

GreenLight works out of the box with sensible defaults. For advanced configuration:

```bash
# Set custom NATS server
export GREENLIGHT_NATS_URL="nats://custom-server:4222"

# Set custom log level
export GREENLIGHT_LOG_LEVEL="debug"

# Enable specific integrations
export GREENLIGHT_SLACK_ENABLED="true"
export GREENLIGHT_LINEAR_ENABLED="true"
```

## Best Practices

### When to Log
- ✅ At the start and end of significant operations
- ✅ When errors or anomalies occur
- ✅ When making important decisions
- ✅ When discovering new insights
- ✅ When coordinating with other agents

### What to Include
- ✅ Clear, descriptive messages
- ✅ Relevant context (service, version, environment)
- ✅ Severity level for errors
- ✅ Links to related resources
- ✅ Agent identifier for coordination

### What to Avoid
- ❌ Logging sensitive data (secrets, PII)
- ❌ Excessive logging of trivial events
- ❌ Inconsistent message formats
- ❌ Vague or unclear descriptions

## Full Function Reference

See `memory-greenlight-templates.sh` for the complete list of 103 template functions.

Run `show_help` after sourcing the script to see all available commands.

---

**"We don't just log events. We share understanding."** 💚✨
