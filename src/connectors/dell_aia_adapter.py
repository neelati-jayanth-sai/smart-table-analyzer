"""Dell AIA Gateway LLM adapter (OpenAI-compatible chat completions)."""

from __future__ import annotations

import json
import logging
import os
import time
from typing import Any

import requests

from src.utils.tokens import get_token_counter

from .llm_adapter import LLMAdapter

logger = logging.getLogger(__name__)


class DellAIAAdapter(LLMAdapter):
    """Chat-completions adapter with OAuth2 client-credentials auth.

    Tools are passed through in OpenAI function-calling form; `generate` returns
    `{"content": str, "tool_calls": [{"name": ..., "arguments": {...}}]}`.
    """

    def __init__(
        self,
        base_url: str,
        model: str,
        client_id: str | None = None,
        client_secret: str | None = None,
        token_endpoint: str | None = None,
        api_key: str | None = None,
        verify_ssl: bool = True,
        timeout: int = 120,
        temperature: float = 0.0,
        max_retries: int = 3,
    ):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.client_id = client_id
        self.client_secret = client_secret
        self.token_endpoint = token_endpoint or f"{self.base_url.rstrip('/v1')}/oauth/token"
        self.verify_ssl = verify_ssl
        self.timeout = timeout
        self.temperature = temperature
        self.max_retries = max_retries
        self.last_usage: dict[str, Any] = {}

        self._token = api_key
        self._token_expiry = float("inf") if api_key else 0.0
        self._counter = get_token_counter(model)

    @classmethod
    def from_env(cls) -> "DellAIAAdapter":
        base_url = os.getenv("LLM_BASE_URL")
        if not base_url:
            raise ValueError("LLM_BASE_URL is not set")
        return cls(
            base_url=base_url,
            model=os.getenv("LLM_MODEL", "gpt-oss-120b"),
            client_id=os.getenv("LLM_CLIENT_ID"),
            client_secret=os.getenv("LLM_CLIENT_SECRET"),
            token_endpoint=os.getenv("LLM_TOKEN_ENDPOINT"),
            api_key=os.getenv("LLM_API_KEY"),
            verify_ssl=os.getenv("LLM_VERIFY_SSL", "true").lower() != "false",
            timeout=int(os.getenv("LLM_TIMEOUT_SECONDS", "120")),
            temperature=float(os.getenv("LLM_TEMPERATURE", "0.0")),
        )

    # ------------------------------------------------------------------ auth

    def _access_token(self) -> str | None:
        if self._token and time.time() < self._token_expiry:
            return self._token
        if not (self.client_id and self.client_secret):
            return self._token

        response = requests.post(
            self.token_endpoint,
            data={
                "grant_type": "client_credentials",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=30,
            verify=self.verify_ssl,
        )
        response.raise_for_status()
        payload = response.json()
        self._token = payload["access_token"]
        # Refresh a minute early so a long call cannot straddle expiry.
        self._token_expiry = time.time() + max(int(payload.get("expires_in", 3600)) - 60, 60)
        return self._token

    # ------------------------------------------------------------ generation

    def generate(
        self, messages: list[dict[str, str]], tools: list[dict] | None = None
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        last_error: Exception | None = None
        for attempt in range(self.max_retries):
            try:
                return self._post(payload)
            except Exception as exc:  # network/gateway flakiness is expected
                last_error = exc
                logger.warning(
                    "LLM call failed (attempt %d/%d): %s", attempt + 1, self.max_retries, exc
                )
                if attempt < self.max_retries - 1:
                    time.sleep(2**attempt)
        raise RuntimeError(f"LLM request failed after {self.max_retries} attempts: {last_error}")

    def _post(self, payload: dict[str, Any]) -> dict[str, Any]:
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        token = self._access_token()
        if token:
            headers["Authorization"] = f"Bearer {token}"

        response = requests.post(
            f"{self.base_url}/chat/completions",
            headers=headers,
            json=payload,
            timeout=self.timeout,
            verify=self.verify_ssl,
        )
        response.raise_for_status()
        body = response.json()

        self.last_usage = body.get("usage", {})
        message = (body.get("choices") or [{}])[0].get("message", {}) or {}
        return {
            "content": message.get("content") or "",
            "tool_calls": _parse_tool_calls(message.get("tool_calls")),
        }

    def token_count(self, messages: list[dict]) -> int:
        return self._counter.count_messages(messages)


def _parse_tool_calls(raw: list[dict] | None) -> list[dict[str, Any]]:
    """Normalize OpenAI tool_calls into {'name', 'arguments'} dicts."""
    calls: list[dict[str, Any]] = []
    for call in raw or []:
        function = call.get("function") or {}
        arguments = function.get("arguments")
        if isinstance(arguments, str):
            try:
                arguments = json.loads(arguments)
            except json.JSONDecodeError:
                arguments = {}
        calls.append({"name": function.get("name"), "arguments": arguments or {}})
    return calls
