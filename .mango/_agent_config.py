"""
Resolve agent configuration from environment variables.

Supports manual settings via OC_AGENT_* and inference via OC_INFER_AGENT_FROM.
If both are present, manual settings win and a warning is emitted.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

import _utility


@dataclass(frozen=True)
class AgentConfig:
    endpoint: str
    api_key: str
    model: str
    timeout: int
    auth_header: str = "Authorization"
    auth_prefix: str = "Bearer "
    user_agent: str = ""


_MANUAL_KEYS = {"OC_AGENT_ENDPOINT", "OC_AGENT_API_KEY", "OC_AGENT_MODEL", "OC_AGENT_TIMEOUT"}


def _has_manual_settings(env: dict) -> bool:
    return any(env.get(key) for key in _MANUAL_KEYS)


def _infer_from_codex() -> AgentConfig:
    codex_dir = Path.home() / ".codex"
    config_path = codex_dir / "config.toml"
    auth_path = codex_dir / "auth.json"

    config_text = _utility.load_text(config_path)
    auth_text = _utility.load_text(auth_path)

    model_provider = _match_toml_value(config_text, "model_provider") or ""
    model = _match_toml_value(config_text, "model") or "gpt-4o-mini"
    wire_api = _match_provider_value(config_text, model_provider, "wire_api") or "responses"
    base_url = _match_provider_value(config_text, model_provider, "base_url") or "https://api.openai.com/v1/"
    print(f"Inferred model provider: {model_provider}, model: {model}, endpoint: {base_url}{wire_api}")
    requires_openai_auth = _match_provider_value(config_text, model_provider, "requires_openai_auth")
    requires_openai_auth = (requires_openai_auth or "").strip().lower() in {"true", "1", "yes"}

    endpoint = f"{base_url.rstrip('/')}/{wire_api.lstrip('/')}"
    timeout = int(_utility.get_env("OC_AGENT_TIMEOUT", "180"))

    api_key = ""
    auth_mode = ""
    if auth_text:
        try:
            auth_payload = json.loads(auth_text)
            if isinstance(auth_payload, dict):
                api_key = str(auth_payload.get("OPENAI_API_KEY", "") or "")
                api_key = _strip_quotes(api_key).replace("\n", "").strip()
                auth_mode = str(auth_payload.get("auth_mode", "") or "")
        except json.JSONDecodeError:
            api_key = ""

    if not api_key:
        api_key = _utility.get_env("OC_AGENT_API_KEY", _utility.get_env("OPENAI_API_KEY", ""))

    auth_header = "Authorization"
    auth_prefix = "Bearer "
    user_agent = _utility.get_env("OC_AGENT_USER_AGENT", "codex-cli")
    if auth_mode.lower() == "apikey" and not requires_openai_auth:
        auth_header = "api-key"
        auth_prefix = ""

    return AgentConfig(
        endpoint=endpoint,
        api_key=api_key,
        model=model,
        timeout=timeout,
        auth_header=auth_header,
        auth_prefix=auth_prefix,
        user_agent=user_agent,
    )


def _match_toml_value(text: str, key: str) -> str | None:
    if not text:
        return None
    pattern = re.compile(rf"^\s*{re.escape(key)}\s*=\s*(.+?)\s*$", re.MULTILINE)
    match = pattern.search(text)
    if not match:
        return None
    raw = match.group(1).strip()
    return _strip_quotes(raw)


def _match_provider_value(text: str, provider: str, key: str) -> str | None:
    if not text or not provider:
        return None
    section_pattern = re.compile(
        rf"^\s*\[model_providers\.{re.escape(provider)}\]\s*$",
        re.MULTILINE,
    )
    section_match = section_pattern.search(text)
    if not section_match:
        return None
    section_start = section_match.end()
    next_section = re.search(r"^\s*\[.+?\]\s*$", text[section_start:], re.MULTILINE)
    section_text = text[section_start : section_start + next_section.start()] if next_section else text[section_start:]
    return _match_toml_value(section_text, key)


def _strip_quotes(value: str) -> str:
    text = value.strip()
    if (text.startswith("\"") and text.endswith("\"")) or (text.startswith("'") and text.endswith("'")):
        return text[1:-1].strip()
    return text


def resolve_agent_config() -> AgentConfig:
    env = _utility.get_env_variables()
    infer_source = _utility.get_env("OC_INFER_AGENT_FROM", "").strip().lower()

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
        user_agent = _utility.get_env("OC_AGENT_USER_AGENT", "")
        if not endpoint:
            endpoint = "https://api.openai.com/v1/responses"
        return AgentConfig(
            endpoint=endpoint,
            api_key=api_key,
            model=model,
            timeout=timeout,
            user_agent=user_agent,
        )

    if infer_source == "codex":
        return _infer_from_codex()

    if infer_source:
        raise ValueError(f"Unsupported OC_INFER_AGENT_FROM value: {infer_source}")

    raise ValueError(
        "Agent configuration missing. Set OC_AGENT_* or OC_INFER_AGENT_FROM."
    )
