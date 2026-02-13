"""
Real-World Integration: LLM-Powered Agent with Checkpoint Engine
=================================================================

This is the template for plugging the checkpoint engine into an actual
LLM-powered agent using vLLM, OpenAI-compatible APIs, or any inference backend.

Copy this file, fill in YOUR_MODEL and YOUR_TOOLS, and you have infinite execution.
"""

import json
import logging
import os
from typing import Any, Optional

import requests  # or use openai, httpx, etc.

from aether_checkpoint import CheckpointEngine, MemoryConfig
from aether_checkpoint.config import StorageBackend
from aether_checkpoint.loop import LoopEvent

logger = logging.getLogger("aether_agent")


# =============================================================================
# YOUR TOOL REGISTRY
# =============================================================================

# Register all the tools your agent can use.
# The checkpoint engine doesn't care what tools you have - it just calls execute_tool.

TOOL_REGISTRY = {
    "bash": {
        "description": "Execute a bash command",
        "handler": lambda input: _run_bash(input["command"]),
    },
    "read_file": {
        "description": "Read a file's contents",
        "handler": lambda input: _read_file(input["path"]),
    },
    "write_file": {
        "description": "Write content to a file",
        "handler": lambda input: _write_file(input["path"], input["content"]),
    },
    "web_search": {
        "description": "Search the web",
        "handler": lambda input: _web_search(input["query"]),
    },
    # Add your tools here...
}

# Tool implementations (replace with your actual implementations)
def _run_bash(command: str) -> str:
    import subprocess
    result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=60)
    return result.stdout + result.stderr

def _read_file(path: str) -> str:
    with open(path) as f:
        return f.read()

def _write_file(path: str, content: str) -> str:
    with open(path, "w") as f:
        f.write(content)
    return f"Written to {path}"

def _web_search(query: str) -> str:
    return f"[Search results for: {query}]"  # Replace with real search


# =============================================================================
# LLM AGENT IMPLEMENTATION
# =============================================================================

class LLMAgent:
    """Real LLM-powered agent that satisfies the AgentProtocol.

    Works with any OpenAI-compatible API (vLLM, Ollama, OpenAI, etc.)
    """

    def __init__(
        self,
        api_base: str = "http://localhost:8000/v1",  # Your vLLM / inference endpoint
        model: str = "apriel-1.5-15b-thinker",       # Your model
        api_key: str = "not-needed",                   # For vLLM, usually not needed
    ):
        self.api_base = api_base.rstrip("/")
        self.model = model
        self.api_key = api_key

    def decide_action(self, system_prompt: str, messages: list[dict]) -> dict:
        """Call the LLM to decide the next action.

        The LLM receives the system prompt (with checkpoint context) and
        message history, and returns a structured tool call.
        """
        # Build the tool descriptions for the prompt
        tool_descriptions = "\n".join(
            f"- {name}: {info['description']}" for name, info in TOOL_REGISTRY.items()
        )

        full_system = f"""{system_prompt}

## AVAILABLE TOOLS
{tool_descriptions}

## RESPONSE FORMAT
Respond with a JSON object:
{{
    "tool": "tool_name",
    "input": {{"param": "value"}},
    "reasoning": "why this action"
}}

If the objective is complete, respond with:
{{"tool": "__DONE__", "input": {{}}, "reasoning": "objective achieved because..."}}
"""

        # Call the LLM
        api_messages = [{"role": "system", "content": full_system}] + messages

        try:
            response = requests.post(
                f"{self.api_base}/chat/completions",
                json={
                    "model": self.model,
                    "messages": api_messages,
                    "temperature": 0.2,
                    "max_tokens": 1024,
                },
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=60,
            )
            response.raise_for_status()
            data = response.json()

            content = data["choices"][0]["message"]["content"]
            tokens_used = data.get("usage", {}).get("total_tokens", 0)

            # Parse the JSON response
            action = json.loads(content)
            action["tokens_used"] = tokens_used
            return action

        except (requests.RequestException, json.JSONDecodeError, KeyError) as e:
            logger.error(f"LLM call failed: {e}")
            # On failure, return a safe no-op that will trigger error recovery
            return {
                "tool": "__DONE__",
                "input": {},
                "reasoning": f"LLM call failed: {e}",
                "tokens_used": 0,
            }

    def execute_tool(self, tool_name: str, tool_input: dict) -> Any:
        """Execute a tool from the registry."""
        if tool_name not in TOOL_REGISTRY:
            raise ValueError(f"Unknown tool: {tool_name}. Available: {list(TOOL_REGISTRY.keys())}")

        handler = TOOL_REGISTRY[tool_name]["handler"]
        return handler(tool_input)

    def distill_checkpoint(
        self,
        objective: str,
        working_memory_text: str,
        previous_checkpoint: Optional[str],
    ) -> dict:
        """Use the LLM to distill working memory into a structured checkpoint.

        This is the intelligence of Step 11 - the model compresses its own
        experience into navigation state, not just logs.
        """
        distillation_prompt = f"""You are a state distillation system. Your job is to compress
the working memory from an execution episode into structured continuation state.

OBJECTIVE: {objective}

{"PREVIOUS CHECKPOINT:" + chr(10) + previous_checkpoint if previous_checkpoint else "This is the first episode."}

WORKING MEMORY FROM THIS EPISODE:
{working_memory_text}

Respond with ONLY a JSON object in this exact format:
{{
    "objective": "the original objective",
    "progress": ["list of completed steps/achievements"],
    "state": {{"key": "value pairs describing current state"}},
    "next_action": "what should be done next",
    "dependencies": ["what the next action depends on"],
    "errors": ["any errors or blockers encountered"]
}}

RULES:
- Be concise. This must fit in ~400 tokens.
- Focus on NAVIGATION (what's next) not ARCHAEOLOGY (what happened).
- Include only facts needed to continue execution.
- Do NOT include raw tool outputs. Summarize results.
"""

        try:
            response = requests.post(
                f"{self.api_base}/chat/completions",
                json={
                    "model": self.model,
                    "messages": [{"role": "user", "content": distillation_prompt}],
                    "temperature": 0.1,
                    "max_tokens": 500,
                },
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=30,
            )
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
            return json.loads(content)

        except Exception as e:
            logger.error(f"Distillation failed: {e}")
            # Fallback: mechanical extraction
            return {
                "objective": objective,
                "progress": ["Episode completed but distillation failed"],
                "state": {"distillation_error": str(e)},
                "next_action": "Retry previous episode's work",
                "dependencies": [],
                "errors": [str(e)],
            }


# =============================================================================
# MAIN: Run the agent with infinite execution
# =============================================================================

def main():
    logging.basicConfig(level=logging.INFO)

    # === CONFIGURATION ===
    # Auto-configure based on your model's context window
    config = MemoryConfig.for_model("apriel-1.5-15b-thinker")

    # Override with production backends when ready
    # config.working_memory_backend = StorageBackend.REDIS
    # config.episodic_memory_backend = StorageBackend.POSTGRES
    # config.semantic_memory_backend = StorageBackend.WEAVIATE
    # config.redis_url = "redis://localhost:6379/0"
    # config.postgres_url = "postgresql://localhost:5432/aether_checkpoints"
    # config.weaviate_url = "http://localhost:8080"

    # === AGENT ===
    agent = LLMAgent(
        api_base=os.getenv("VLLM_API_BASE", "http://localhost:8000/v1"),
        model=os.getenv("MODEL_NAME", "apriel-1.5-15b-thinker"),
    )

    # === EVENT HANDLER (optional monitoring) ===
    def on_event(event: LoopEvent):
        emoji = {
            "step": "📍", "checkpoint": "💾", "rehydrate": "🔄",
            "complete": "✅", "error": "❌", "safety_stop": "🛑",
        }.get(event.event_type, "📌")
        print(f"{emoji} [{event.event_type}] Episode {event.episode}: {event.data}")

    # === RUN ===
    engine = CheckpointEngine(
        agent=agent,
        config=config,
        on_event=on_event,
    )

    objective = input("Enter objective: ")
    result = engine.run(objective)

    print(f"\n{'='*60}")
    print("EXECUTION COMPLETE")
    print(f"{'='*60}")
    print(result.to_continuation_prompt())


if __name__ == "__main__":
    main()
