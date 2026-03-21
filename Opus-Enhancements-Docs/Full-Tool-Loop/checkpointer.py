"""
Checkpointer — State Distillation Engine
=========================================

This is the critical piece: Step N+1 in your loop.

Instead of dumping raw tool outputs (archaeology), the checkpointer
distills working memory into structured continuation state (navigation).

Two modes:
    1. LLM-powered distillation — uses the model itself to summarize
    2. Rule-based distillation — deterministic extraction (no LLM call needed)

You can mix both: rule-based for structured data, LLM for open-ended summaries.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Optional
from abc import ABC, abstractmethod

from .memory import WorkingMemory, EpisodicMemory, EpisodeCheckpoint


@dataclass
class CheckpointState:
    """
    The compressed state that gets persisted and rehydrated.
    
    This is what replaces 10,000 tokens of raw history with
    ~200 tokens of distilled navigation state.
    """
    objective: str
    progress_items: list[str]
    current_state: dict[str, Any]
    next_actions: list[str]
    dependencies: list[str]
    warnings: list[str] = field(default_factory=list)
    raw_token_count: int = 0
    compressed_token_count: int = 0

    @property
    def compression_ratio(self) -> float:
        if self.raw_token_count == 0:
            return 0
        return 1 - (self.compressed_token_count / self.raw_token_count)


class DistillationStrategy(ABC):
    """Base class for state distillation strategies."""

    @abstractmethod
    async def distill(
        self,
        working_memory: WorkingMemory,
        objective: str,
        previous_checkpoint: Optional[EpisodeCheckpoint] = None,
    ) -> CheckpointState:
        """Compress working memory into checkpoint state."""
        ...


class RuleBasedDistillation(DistillationStrategy):
    """
    Deterministic distillation — no LLM call required.
    
    Fast, cheap, predictable. Good for structured tool outputs
    where you know the format ahead of time.
    """

    def __init__(
        self,
        success_indicators: list[str] = None,
        failure_indicators: list[str] = None,
    ):
        self.success_indicators = success_indicators or ["success", "completed", "created", "done"]
        self.failure_indicators = failure_indicators or ["error", "failed", "exception", "timeout"]

    async def distill(
        self,
        working_memory: WorkingMemory,
        objective: str,
        previous_checkpoint: Optional[EpisodeCheckpoint] = None,
    ) -> CheckpointState:
        progress = []
        warnings = []
        state = {}
        next_actions = []
        dependencies = []

        for entry in working_memory.entries:
            output_str = json.dumps(entry.tool_output, default=str).lower()

            # Classify result
            is_success = any(ind in output_str for ind in self.success_indicators)
            is_failure = any(ind in output_str for ind in self.failure_indicators)

            if is_success:
                progress.append(
                    f"{entry.tool_name} (step {entry.step_number}): completed"
                )
            elif is_failure:
                warnings.append(
                    f"{entry.tool_name} (step {entry.step_number}): "
                    f"{str(entry.tool_output)[:200]}"
                )
            else:
                state[f"step_{entry.step_number}_{entry.tool_name}"] = (
                    str(entry.tool_output)[:300]
                )

        # Carry forward previous checkpoint context
        if previous_checkpoint:
            for dep in previous_checkpoint.dependencies:
                if dep not in dependencies:
                    dependencies.append(dep)

        # Estimate compressed size
        compressed_str = json.dumps({
            "progress": progress, "state": state,
            "next": next_actions, "warnings": warnings,
        })

        return CheckpointState(
            objective=objective,
            progress_items=progress,
            current_state=state,
            next_actions=next_actions,
            dependencies=dependencies,
            warnings=warnings,
            raw_token_count=working_memory.token_count,
            compressed_token_count=len(compressed_str) // 4,
        )


class LLMDistillation(DistillationStrategy):
    """
    LLM-powered distillation — uses the model to summarize.
    
    More expensive but much better at extracting meaning from
    unstructured tool outputs. Pass in any LLM callable.
    """

    # The prompt that tells the model HOW to compress state.
    # This is the secret sauce — it forces structured output.
    DISTILLATION_PROMPT = """You are a state compression engine. Your job is to distill 
working memory from an AI agent's execution episode into minimal continuation state.

OBJECTIVE: {objective}

PREVIOUS CHECKPOINT (if any):
{previous_state}

CURRENT WORKING MEMORY:
{working_memory}

Compress this into a JSON object with EXACTLY this structure:
{{
    "progress_items": ["list of things completed this episode"],
    "current_state": {{"key": "value pairs of important current state"}},
    "next_actions": ["ordered list of what to do next"],
    "dependencies": ["things that must exist or be true for next actions"],
    "warnings": ["any errors, blockers, or concerns"]
}}

RULES:
- Be CONCISE. Each item should be one short sentence max.
- Focus on STATE not HISTORY. What IS, not what WAS.
- Include only information needed to CONTINUE the task.
- Drop any completed work that doesn't affect next steps.
- Output ONLY valid JSON, nothing else."""

    def __init__(self, llm_callable: Callable):
        """
        Args:
            llm_callable: An async function that takes a prompt string
                          and returns a response string. This lets you
                          plug in ANY model — vLLM, OpenAI, Anthropic, local, etc.
                          
        Example:
            async def my_llm(prompt: str) -> str:
                response = await client.chat.completions.create(
                    model="your-model",
                    messages=[{"role": "user", "content": prompt}],
                )
                return response.choices[0].message.content
                
            distiller = LLMDistillation(llm_callable=my_llm)
        """
        self.llm_callable = llm_callable

    async def distill(
        self,
        working_memory: WorkingMemory,
        objective: str,
        previous_checkpoint: Optional[EpisodeCheckpoint] = None,
    ) -> CheckpointState:
        prev_state = "None (first episode)"
        if previous_checkpoint:
            prev_state = previous_checkpoint.to_rehydration_prompt()

        prompt = self.DISTILLATION_PROMPT.format(
            objective=objective,
            previous_state=prev_state,
            working_memory=working_memory.to_context_string(),
        )

        raw_response = await self.llm_callable(prompt)

        # Parse LLM response — handle markdown code fences
        cleaned = raw_response.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[-1]
        if cleaned.endswith("```"):
            cleaned = cleaned.rsplit("```", 1)[0]
        cleaned = cleaned.strip()

        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError:
            # Fallback: treat entire response as a progress summary
            data = {
                "progress_items": [cleaned[:500]],
                "current_state": {"raw_summary": cleaned[:1000]},
                "next_actions": ["Review distillation output and continue"],
                "dependencies": [],
                "warnings": ["LLM distillation returned non-JSON; used fallback"],
            }

        compressed_str = json.dumps(data)
        return CheckpointState(
            objective=objective,
            progress_items=data.get("progress_items", []),
            current_state=data.get("current_state", {}),
            next_actions=data.get("next_actions", []),
            dependencies=data.get("dependencies", []),
            warnings=data.get("warnings", []),
            raw_token_count=working_memory.token_count,
            compressed_token_count=len(compressed_str) // 4,
        )


class Checkpointer:
    """
    Main checkpointer that orchestrates distillation and persistence.
    
    This is Step N+1 in your loop — it takes the full working memory,
    compresses it, saves it, and returns the rehydration state.
    """

    def __init__(
        self,
        episodic_memory: EpisodicMemory,
        strategy: Optional[DistillationStrategy] = None,
    ):
        self.episodic = episodic_memory
        self.strategy = strategy or RuleBasedDistillation()
        self._checkpoint_count = 0

    async def checkpoint(
        self,
        working_memory: WorkingMemory,
        objective: str,
    ) -> EpisodeCheckpoint:
        """
        Execute a full checkpoint cycle:
        1. Load previous checkpoint for context continuity
        2. Distill current working memory into compressed state
        3. Persist the checkpoint
        4. Return the checkpoint for rehydration
        """
        # Get previous checkpoint for continuity
        previous = await self.episodic.get_latest(objective)

        # Distill working memory
        state = await self.strategy.distill(
            working_memory=working_memory,
            objective=objective,
            previous_checkpoint=previous,
        )

        # Merge progress with previous checkpoint
        all_results = state.progress_items.copy()
        if previous:
            # Carry forward key results from previous episodes
            all_results = previous.key_results + all_results

        # Create and persist checkpoint
        checkpoint = await self.episodic.create_checkpoint(
            objective=objective,
            progress_summary=f"Episode {self.episodic.episode_count}: "
                           f"{len(state.progress_items)} items completed, "
                           f"{len(state.warnings)} warnings",
            current_state=state.current_state,
            next_actions=state.next_actions,
            key_results=all_results,
            dependencies=state.dependencies,
            metadata={
                "compression_ratio": state.compression_ratio,
                "raw_tokens": state.raw_token_count,
                "compressed_tokens": state.compressed_token_count,
                "warnings": state.warnings,
            },
        )

        self._checkpoint_count += 1
        return checkpoint
