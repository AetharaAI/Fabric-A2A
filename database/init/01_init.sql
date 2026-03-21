7\-- Fabric MCP Server - Database Initialization
-- This script creates the initial database schema

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Create enum types
DO $$ BEGIN
    CREATE TYPE agent_status AS ENUM ('online', 'offline', 'degraded', 'unknown');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE trust_tier AS ENUM ('local', 'org', 'public');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- Create tables first
CREATE TABLE IF NOT EXISTS agents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    status agent_status DEFAULT 'unknown',
    trust_tier trust_tier DEFAULT 'local',
    runtime VARCHAR(100),
    endpoint VARCHAR(500),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS capabilities (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    agent_id UUID REFERENCES agents(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    schema JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS tools (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    category VARCHAR(100),
    provider VARCHAR(100),
    enabled BOOLEAN DEFAULT true,
    config JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS health_checks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    agent_id UUID REFERENCES agents(id) ON DELETE CASCADE,
    status VARCHAR(50),
    latency_ms INTEGER,
    checked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS call_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    trace_id UUID,
    target_type VARCHAR(50),
    target_id UUID,
    request JSONB,
    response JSONB,
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_agents_status ON agents(status);
CREATE INDEX IF NOT EXISTS idx_agents_trust_tier ON agents(trust_tier);
CREATE INDEX IF NOT EXISTS idx_agents_runtime ON agents(runtime);
CREATE INDEX IF NOT EXISTS idx_capabilities_name ON capabilities(name);
CREATE INDEX IF NOT EXISTS idx_tools_category ON tools(category);
CREATE INDEX IF NOT EXISTS idx_tools_provider ON tools(provider);
CREATE INDEX IF NOT EXISTS idx_tools_enabled ON tools(enabled);
CREATE INDEX IF NOT EXISTS idx_health_checks_agent ON health_checks(agent_id, checked_at);
CREATE INDEX IF NOT EXISTS idx_call_logs_trace ON call_logs(trace_id, started_at);
CREATE INDEX IF NOT EXISTS idx_call_logs_target ON call_logs(target_type, target_id, started_at);

-- Add comments for documentation
COMMENT ON TABLE agents IS 'Registered AI agents in the Fabric network';
COMMENT ON TABLE capabilities IS 'Agent capabilities and their schemas';
COMMENT ON TABLE tools IS 'Built-in tools available in the Fabric server';
COMMENT ON TABLE call_logs IS 'Audit log of all calls for observability';
COMMENT ON TABLE health_checks IS 'Agent health check history';

-- Grant permissions (if not using superuser)
-- GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO fabric;
-- GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO fabric;