ACL SETUSER fabric_admin on >admin_secure_password_123 ~* +@all
ACL SETUSER fabric_mcp on >mcp_system_password_456 ~agent:* +@all -@dangerous
ACL SETUSER percy on >percy_agent_secret_789 ~agent:percy:* ~shared:* +@all -@dangerous
ACL SETUSER coder on >coder_agent_secret_abc ~agent:coder:* ~shared:* +@all -@dangerous
ACL SETUSER memory on >memory_agent_secret_def ~agent:memory:* ~shared:* +@all -@dangerous
ACL SETUSER vision on >vision_agent_secret_ghi ~agent:vision:* ~shared:* +@all -@dangerous
ACL SETUSER monitoring on >monitoring_readonly_123 ~metrics:* +@read
ACL SETUSER backup on >backup_service_456 ~* +@read +@connection
ACL SETUSER default off
ACL SAVE



ACL SETUSER fabric_admin on >admin_secure_password_123 ~* +@all &*
ACL SETUSER fabric_mcp on >mcp_system_password_456 +@stream +@pubsub +@connection &*
ACL SETUSER percy on >percy_agent_secret_789 +@stream +@pubsub +@connection &agent.percy.* &shared.broadcast &shared.direct.percy
ACL SETUSER coder on >coder_agent_secret_abc +@stream +@pubsub +@connection &agent.coder.* &shared.broadcast &shared.direct.coder
ACL SETUSER memory on >memory_agent_secret_def +@stream +@pubsub +@connection &agent.memory.* &shared.broadcast &shared.direct.memory
ACL SETUSER vision on >vision_agent_secret_ghi +@stream +@pubsub +@connection &agent.vision.* &shared.broadcast &shared.direct.vision
ACL SETUSER monitoring on >monitoring_readonly_123 +@read +@pubsub &metrics.*
ACL SETUSER backup on >backup_service_456 +@read +@connection +@server
ACL SETUSER default off



# Redis ACL File for Fabric Agent Infrastructure
# 
# Copy this to /opt/redis/users.acl on your R64 node
# Then customize passwords (use strong passwords in production!)
#
# ACL commands reference:
#   on = enabled, off = disabled
#   >password = password required
#   ~pattern = key pattern access
#   +command = allow command, -command = deny command
#   +@category = allow category (e.g., +@string, +@hash)

# =============================================================================
# Admin User (Full Access)
# =============================================================================
user fabric_admin on >admin_secure_password_123 ~* +@all &*

# =============================================================================
# Fabric MCP Server (System User)
# =============================================================================
# Can read/write all agent streams, publish to all topics and channels
user fabric_mcp on >mcp_system_password_456 ~agent:* +@stream +@pubsub +@read -@dangerous &*

# =============================================================================
# Agent-Specific Users (Isolated)
# =============================================================================

# Percy Agent - Reasoning and planning
# Can access: agent:percy:* streams, &shared:* pub/sub, &agent.percy.* channels
user percy on >percy_agent_secret_789 ~agent:percy:* ~shared:* +@stream +@pubsub +@read -@dangerous &shared:* &agent.percy:*

# Coder Agent - Code generation
user coder on >coder_agent_secret_abc ~agent:coder:* ~shared:* +@stream +@pubsub +@read -@dangerous &shared:* &agent.coder:*

# Memory Agent - Long-term memory
user memory on >memory_agent_secret_def ~agent:memory:* ~shared:* +@stream +@pubsub +@read -@dangerous &shared:* &agent.memory:*

# Vision Agent - Image processing
user vision on >vision_agent_secret_ghi ~agent:vision:* ~shared:* +@stream +@pubsub +@read -@dangerous &shared:* &agent.vision:*

# =============================================================================
# Service Accounts (Limited Scope)
# =============================================================================

# Monitoring service - read-only access to metrics
user monitoring on >monitoring_readonly_123 ~metrics:* +@read

# Backup service - read access for backups
user backup on >backup_service_456 ~* +@read +@connection +@server

# =============================================================================
# Default User (Deny All)
# =============================================================================
# New connections without auth get rejected
user default off

