"""
Resolve agent configuration from environment variables.

Supports manual settings via OC_AGENT_* and inference via OC_INFER_AGENT_FROM.
If both are present, manual settings win and a warning is emitted.
"""

from __future__ import annotations

from dataclasses import dataclass

import _utility


@dataclass(frozen=True)
class AgentConfig:
    endpoint: str
    api_key: str
    model: str
    timeout: int


_MANUAL_KEYS = {"OC_AGENT_ENDPOINT", "OC_AGENT_API_KEY", "OC_AGENT_MODEL", "OC_AGENT_TIMEOUT"}


def _has_manual_settings(env: dict) -> bool:
    return any(env.get(key) for key in _MANUAL_KEYS)


def _infer_from_codex() -> AgentConfig:
    api_key = _utility.get_env("OC_AGENT_API_KEY", _utility.get_env("OPENAI_API_KEY", ""))
    endpoint = "https://api.openai.com/v1/responses"
    model = "gpt-4o-mini"
    timeout = int(_utility.get_env("OC_AGENT_TIMEOUT", "180"))
    return AgentConfig(endpoint=endpoint, api_key=api_key, model=model, timeout=timeout)


def resolve_agent_config() -> AgentConfig:
    env = _utility.get_env_variables()
    infer_source = env.get("OC_INFER_AGENT_FROM", "").strip().lower()

    if infer_source and _has_manual_settings(env):
        _utility.warn(
            "Both OC_INFER_AGENT_FROM and manual OC_AGENT_* settings were found. "
            "Manual settings take precedence."
        )

    if _has_manual_settings(env):
        endpoint = _utility.get_env("OC_AGENT_ENDPOINT", "").strip()
        api_key = _utility.get_env("OC_AGENT_API_KEY", "")
        model = _utility.get_env("OC_AGENT_MODEL", "gpt-4o-mini")
        timeout = int(_utility.get_env("OC_AGENT_TIMEOUT", "180"))
        if not endpoint:
            endpoint = "https://api.openai.com/v1/responses"
        return AgentConfig(endpoint=endpoint, api_key=api_key, model=model, timeout=timeout)

    if infer_source == "codex":
        return _infer_from_codex()

    if infer_source:
        raise ValueError(f"Unsupported OC_INFER_AGENT_FROM value: {infer_source}")

    raise ValueError(
        "Agent configuration missing. Set OC_AGENT_* or OC_INFER_AGENT_FROM."
    )
