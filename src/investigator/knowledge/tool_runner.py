"""LLM tool loop for list-then-fetch knowledge retrieval."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from src.context import ContextEngine, PromptProfile
from src.investigator.prompts import build_knowledge_prompt
from src.models.state import InvestigationState, KnowledgeReference
from .tool_definitions import fetch_knowledge_tool, list_knowledge_tool

if TYPE_CHECKING:
    from src.database import InvestigationDb
    from src.database.knowledge_store import KnowledgeStore


class KnowledgeToolRunner:
    MAX_TURNS = 3
    SOURCES = ("iceberg", "iomete", "runbooks")

    def __init__(
        self,
        llm,
        knowledge_store: "KnowledgeStore",
        db: "InvestigationDb",
        context_engine: ContextEngine,
    ):
        self.llm = llm
        self.knowledge = knowledge_store
        self.db = db
        self.context_engine = context_engine
        self._cache = {}  # (investigation_id, source, topic_path) -> content

    def run(self, state: InvestigationState) -> list[KnowledgeReference]:
        prompt = build_knowledge_prompt(self.context_engine.render(PromptProfile.KNOWLEDGE, state), state)
        available: list[str] = []
        for turn in range(self.MAX_TURNS):
            if turn == 0:
                tools = [list_knowledge_tool()]
                content = prompt
            else:
                tools = [fetch_knowledge_tool()]
                content = _augment_prompt_for_fetch(prompt, available)
            response = self.llm.generate(
                [{"role": "user", "content": content}],
                tools=tools,
            )
            if turn > 0:
                refs = self._process_fetches(response.get("tool_calls", []), state)
                if refs:
                    return refs
            listed = self._process_lists(response.get("tool_calls", []))
            if not listed:
                break
            available.extend(listed)
        return []

    def _normalize_source(self, value: str | None) -> tuple[str, str | None]:
        if not value:
            return "", None
        value_lower = value.lower()
        if value_lower in self.SOURCES:
            return value_lower, None
        return "", None

    def _process_lists(self, tool_calls: list) -> list[str]:
        results: list[str] = []
        for call in tool_calls or []:
            if call.get("name") != "list_knowledge":
                continue
            args = call.get("arguments", {})
            source = args.get("source") or args.get("topic")
            prefix = args.get("prefix")
            source, topic_prefix = self._normalize_source(source)
            prefix = prefix or topic_prefix
            if not source:
                continue
            for entry in self.knowledge.list(source, prefix):
                results.append(f"{source}/{entry['topic_path']}: {entry.get('description', '')}")
        return results

    def _process_fetches(self, tool_calls: list, state: dict[str, Any]) -> list[KnowledgeReference]:
        refs: list[KnowledgeReference] = []
        seen: set[tuple[str, str]] = set()
        investigation_id = state["investigation_id"]
        for call in tool_calls or []:
            if call.get("name") != "fetch_knowledge":
                continue
            args = call.get("arguments", {})
            source = args.get("source") or args.get("topic")
            topic_path = args.get("topic_path") or args.get("path") or args.get("topic")
            source, _ = self._normalize_source(source)
            if not source or not topic_path:
                continue
            prefix = f"{source}/"
            if topic_path.startswith(prefix):
                topic_path = topic_path[len(prefix):]
            if topic_path.endswith(".md"):
                topic_path = topic_path[:-3]
            key = (source, topic_path)
            if key in seen:
                continue
            seen.add(key)
            
            # Check cache first
            cache_key = (investigation_id, source, topic_path)
            if cache_key in self._cache:
                cached = self._cache[cache_key]
                refs.append(cached)
                continue
            
            entry = self.knowledge.fetch(source, topic_path)
            content = entry.get("content", "")
            if not content:
                continue
            version = entry.get("version", "")
            ref = {"source": source, "topic_path": topic_path, "version": version, "content": content}
            refs.append(ref)
            
            # Cache the result
            self._cache[cache_key] = ref
            
            self.db.record_knowledge_fetch(
                state["investigation_id"], state["check_count"], source, topic_path, version
            )
        return refs


def _augment_prompt_for_fetch(prompt: str, available: list[str]) -> str:
    if not available:
        return prompt
    entries = "\n".join(f"- {path}" for path in available[:100])
    return (
        f"{prompt}\n\n"
        f"Available knowledge entries:\n{entries}\n\n"
        "Call fetch_knowledge(source, topic_path) for the 1-3 most relevant entries. "
        "Use the exact topic_path from the list above."
    )
