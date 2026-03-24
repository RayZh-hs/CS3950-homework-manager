"""
_utility.py
----------------
Shared helpers for the canvas homework management system.
"""

from __future__ import annotations

import json
import os
import re
import urllib.request
import warnings
from pathlib import Path


def get_env_variables() -> dict:
    # Append .env to the list of environment variable files to load
    dir_of_script = os.path.dirname(os.path.abspath(__file__))
    env_files = [".env", os.path.join(dir_of_script, ".env")]
    for env_file in env_files:
        try:
            with open(env_file, encoding="utf-8") as f:
                for line in f:
                    if line.strip() and not line.startswith("#"):
                        key, value = line.strip().split("=", 1)
                        os.environ[key] = value
        except FileNotFoundError:
            pass
    # Return the loaded environment variables as a dictionary
    return {key: os.environ[key] for key in os.environ}


def get_env(name: str, default: str | None = None, *, required: bool = False) -> str:
    env_vars = get_env_variables()
    value = env_vars.get(name, default)
    if required and (value is None or str(value).strip() == ""):
        raise ValueError(f"Missing required environment variable: {name}")
    return "" if value is None else str(value)


def warn(message: str) -> None:
    warnings.warn(message, RuntimeWarning, stacklevel=2)


def get_oc_api_key() -> str:
    api_key = get_env("OC_API_KEY", "")
    if api_key:
        return api_key
    raise ValueError(
        "OC_API_KEY not found in environment variables. "
        "Please set it in a .env file or as an environment variable."
    )


def load_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def post_json(url: str, payload: dict, *, api_key: str, timeout: int = 120) -> dict:
    if not api_key:
        raise ValueError("Missing API key for agent call")

    data = json.dumps(payload).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8", errors="replace")
    parsed = json.loads(raw) if raw else {}
    if not isinstance(parsed, dict):
        raise RuntimeError("Invalid agent response payload")
    return parsed


def extract_agent_text(payload: dict) -> str:
    if "output" in payload and isinstance(payload["output"], list):
        chunks: list[str] = []
        for item in payload["output"]:
            if not isinstance(item, dict):
                continue
            for content in item.get("content", []) or []:
                if isinstance(content, dict) and content.get("type") in {"output_text", "text"}:
                    text = content.get("text") or ""
                    chunks.append(str(text))
        if chunks:
            return "\n".join(chunks).strip()

    if "choices" in payload and isinstance(payload["choices"], list):
        texts: list[str] = []
        for choice in payload["choices"]:
            if not isinstance(choice, dict):
                continue
            message = choice.get("message") or {}
            content = message.get("content")
            if isinstance(content, str):
                texts.append(content)
        if texts:
            return "\n".join(texts).strip()

    return ""


def extract_latex_code_block(text: str) -> str | None:
    match = re.search(r"```(?:latex|tex)?\s*(.*?)```", text, re.DOTALL | re.IGNORECASE)
    if not match:
        return None
    return match.group(1).strip()
