"""Prompt builders for investigation graph nodes."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from src.context import MAX_PROMPT_TOKENS, PromptContext
from src.utils.errors import get_error_guidance
from src.utils.tokens import get_token_counter

_token_counter = get_token_counter()
logger = logging.getLogger(__name__)

# Directory containing prompt templates
PROMPTS_DIR = Path(__file__).parent / "templates"


def _load_prompt_template(template_name: str) -> str:
    """Load a prompt template from the prompts directory."""
    template_path = PROMPTS_DIR / template_name
    if not template_path.exists():
        raise FileNotFoundError(f"Prompt template not found: {template_path}")
    return template_path.read_text(encoding="utf-8")


def _check_prompt_budget(prompt: str, prompt_name: str = "prompt", state: dict[str, Any] | None = None) -> int:
    """Check prompt budget and log context usage.
    
    Returns the token count for the prompt.
    Optionally tracks usage in the investigation state.
    """
    token_count = _token_counter.count(prompt)
    usage_pct = (token_count / MAX_PROMPT_TOKENS) * 100
    
    logger.info(
        f"[Context Tracking] {prompt_name}: {token_count:,} tokens / {MAX_PROMPT_TOKENS:,} max ({usage_pct:.1f}% usage)"
    )
    
    # Track usage in state if provided
    if state is not None:
        if "context_usage" not in state:
            state["context_usage"] = {}
        state["context_usage"][prompt_name] = {
            "tokens": token_count,
            "max_tokens": MAX_PROMPT_TOKENS,
            "usage_pct": round(usage_pct, 2)
        }
    
    if token_count > MAX_PROMPT_TOKENS:
        raise ValueError(f"Prompt exceeds {MAX_PROMPT_TOKENS} token budget: {token_count:,} tokens")
    
    return token_count


def build_decide_prompt(prompt_context: PromptContext, state: dict[str, Any] | None = None) -> str:
    baseline = prompt_context.baseline_summary
    empty_note = ""
    if baseline.get("is_empty"):
        empty_note = (
            "\nNOTE: The table appears to be empty (0 rows, 0 data files). "
            "Ask exactly one question to confirm whether this is expected, then stop.\n"
        )
    
    template = _load_prompt_template("decide_prompt.txt")
    prompt = template.format(
        table_name=prompt_context.table_name,
        overall_score=baseline.get('overall', 'N/A'),
        weakest_dimensions=json.dumps(baseline.get('weakest', [])),
        partition_info=json.dumps(prompt_context.partition_info),
        prior_findings=json.dumps(prompt_context.findings_summary),
        check_num=prompt_context.check_count + 1,
        max_checks=prompt_context.max_checks,
        empty_note=empty_note,
        column_analysis=json.dumps(prompt_context.column_analysis, default=str),
        query_patterns=json.dumps(prompt_context.query_patterns, default=str),
    )
    _check_prompt_budget(prompt, "decide_prompt", state)
    return prompt


def build_knowledge_prompt(prompt_context: PromptContext, state: dict[str, Any] | None = None) -> str:
    template = _load_prompt_template("knowledge_prompt.txt")
    prompt = template.format(
        question=prompt_context.current_question,
        check_type=prompt_context.current_check_type or 'general'
    )
    _check_prompt_budget(prompt, "knowledge_prompt", state)
    return prompt


def build_query_prompt(prompt_context: PromptContext, state: dict[str, Any] | None = None) -> str:
    partition = prompt_context.partition_info
    partition_note = ""
    if not partition.get("partition_queryable"):
        partition_note = (
            "\nNOTE: This table does not expose a 'partition' column in its .partitions metadata. "
            "Do NOT try to SELECT or GROUP BY a 'partition' column. Use only the columns listed above.\n"
        )
    previous_error = prompt_context.previous_error
    error_guidance = ""
    if previous_error:
        specific_guidance = get_error_guidance(previous_error)
        error_guidance = f"\nERROR: {previous_error}\n{specific_guidance}\n"
    
    template = _load_prompt_template("query_prompt.txt")
    prompt = template.format(
        question=prompt_context.current_question,
        check_type=prompt_context.current_check_type or 'general',
        table_name=prompt_context.table_name,
        partition_info=json.dumps(partition),
        metadata_text=prompt_context.metadata_text,
        partition_note=partition_note,
        error_guidance=error_guidance,
        table_properties=json.dumps(prompt_context.table_properties),
        column_analysis=json.dumps(prompt_context.column_analysis),
        partition_analysis=json.dumps(prompt_context.partition_analysis),
        query_patterns=json.dumps(prompt_context.query_patterns),
        knowledge_text=prompt_context.knowledge_text,
        previous_error=prompt_context.previous_error
    )
    _check_prompt_budget(prompt, "query_prompt", state)
    return prompt


def build_analysis_prompt(prompt_context: PromptContext, state: dict[str, Any] | None = None) -> str:
    template = _load_prompt_template("analysis_prompt.txt")
    critic_feedback_section = ""
    if state and state.get("critic_feedback"):
        critic_feedback_section = (
            "CRITIC FEEDBACK FROM PREVIOUS ATTEMPT:\n"
            "Your previous draft was rejected. Fix the following issues:\n"
            f"{state['critic_feedback']}\n"
        )
        
    prompt = template.format(
        question=prompt_context.current_question,
        check_num=prompt_context.check_count,
        check_type=prompt_context.current_check_type or "general",
        query_result=json.dumps(prompt_context.query_result_summary, default=str),
        knowledge_text=prompt_context.knowledge_text,
        evidence_ids=prompt_context.knowledge_evidence_ids,
        column_analysis=json.dumps(prompt_context.column_analysis, default=str),
        partition_analysis=json.dumps(prompt_context.partition_analysis, default=str),
        query_patterns=json.dumps(prompt_context.query_patterns, default=str),
        measured_signals=json.dumps(prompt_context.baseline_summary.get("signals", []), default=str),
        critic_feedback_section=critic_feedback_section,
        table_name=prompt_context.table_name,
    )
    _check_prompt_budget(prompt, "analysis_prompt", state)
    return prompt


def build_critic_prompt(prompt_context: PromptContext, draft_finding: dict[str, Any], state: dict[str, Any] | None = None) -> str:
    template = _load_prompt_template("critic_prompt.txt")
    prompt = template.format(
        draft_finding=json.dumps(draft_finding, default=str, indent=2),
        query_result=json.dumps(prompt_context.query_result_summary, default=str),
        knowledge_text=prompt_context.knowledge_text,
        table_name=prompt_context.table_name,
    )
    _check_prompt_budget(prompt, "critic_prompt", state)
    return prompt
