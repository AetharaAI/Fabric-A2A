"""
Distillation Prompts: Templates for Step 11 (Checkpoint Compression)

These are the prompts that convert raw working memory into structured
continuation state. This is the most important intelligence in the system.

The key insight: Logs are archaeology. State is navigation.
Step 11 must produce NAVIGATION, not ARCHAEOLOGY.
"""


DISTILLATION_SYSTEM_PROMPT = """You are a state distillation engine. Your purpose is to compress
an agent's working memory into the minimum structured state needed to continue execution.

CRITICAL RULES:
1. Be CONCISE. Output must be under 400 tokens.
2. Focus on WHAT TO DO NEXT, not what was done.
3. Include only facts the next episode NEEDS to continue.
4. Summarize tool outputs - never copy them verbatim.
5. Track errors and blockers explicitly.
6. Preserve dependency chains.
"""


DISTILLATION_USER_TEMPLATE = """Compress this episode's working memory into continuation state.

## OBJECTIVE
{objective}

## PREVIOUS STATE
{previous_checkpoint}

## WORKING MEMORY (this episode)
{working_memory}

## OUTPUT FORMAT
Respond with ONLY this JSON (no markdown, no explanation):
{{
    "objective": "the original objective (unchanged)",
    "progress": [
        "completed item 1",
        "completed item 2"
    ],
    "state": {{
        "key_fact_1": "value",
        "key_fact_2": "value"
    }},
    "next_action": "the single most important next step",
    "dependencies": [
        "what the next action needs"
    ],
    "errors": [
        "any unresolved errors or blockers"
    ]
}}"""


DISTILLATION_WITH_SUBTASKS_TEMPLATE = """Compress this episode's working memory into continuation state.
This objective has multiple subtasks. Track progress on each.

## OBJECTIVE
{objective}

## SUBTASKS
{subtasks}

## PREVIOUS STATE
{previous_checkpoint}

## WORKING MEMORY (this episode)
{working_memory}

## OUTPUT FORMAT
Respond with ONLY this JSON (no markdown, no explanation):
{{
    "objective": "the original objective",
    "progress": [
        "completed item 1",
        "completed item 2"
    ],
    "subtask_status": {{
        "subtask_1": "complete|in_progress|blocked|not_started",
        "subtask_2": "complete|in_progress|blocked|not_started"
    }},
    "state": {{
        "key_fact_1": "value"
    }},
    "next_action": "the single most important next step",
    "current_subtask": "which subtask to work on next",
    "dependencies": [],
    "errors": []
}}"""


# =============================================================================
# EXAMPLE: What good vs bad distillation looks like
# =============================================================================

EXAMPLE_BAD_DISTILLATION = """
❌ BAD - This is archaeology, not navigation:

{
    "objective": "Deploy Docker stack",
    "progress": [
        "Ran 'docker build -t aether-base .' and got output: Successfully built abc123...",
        "Ran 'docker-compose up redis' and got output: Creating network... Creating redis_1...",
        "Ran 'docker-compose up postgres' and got: Starting postgres_1... done",
        "Tried nginx config but got error: nginx: [emerg] unknown directive..."
    ],
    "state": {
        "docker_build_output": "Successfully built abc123def456...",
        "redis_logs": "1:C 01 Jan 2025 00:00:00.000 # Redis version=7.0.0...",
        "postgres_logs": "PostgreSQL 16.1 on x86_64..."
    },
    "next_action": "Fix the nginx error",
    "dependencies": [],
    "errors": ["nginx config error"]
}

This wastes tokens on raw output nobody needs.
"""

EXAMPLE_GOOD_DISTILLATION = """
✅ GOOD - This is navigation:

{
    "objective": "Deploy Docker stack",
    "progress": [
        "Docker base image built successfully",
        "Redis container running",
        "PostgreSQL container running"
    ],
    "state": {
        "containers_running": ["redis", "postgres"],
        "containers_pending": ["nginx", "aether-agent"],
        "docker_compose_path": "./docker-compose.yml",
        "blocking_issue": "nginx.conf has invalid directive on line 42"
    },
    "next_action": "Fix nginx.conf line 42 invalid directive, then start nginx container",
    "dependencies": ["nginx.conf must be valid before container start"],
    "errors": ["nginx.conf syntax error - unknown directive on line 42"]
}

Compact. Actionable. Everything the next episode needs to continue.
"""
