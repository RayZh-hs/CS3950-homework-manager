"""
_utility.py
----------------
Shared helpers for the canvas homework management system.
"""

from __future__ import annotations

import base64
import json
import os
import re
import subprocess
import urllib.error
import urllib.request
import warnings
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import _agent_config


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
    if value is None:
        return ""
    text = str(value).strip()
    if (text.startswith('"') and text.endswith('"')) or (
        text.startswith("'") and text.endswith("'")
    ):
        text = text[1:-1].strip()
    return text


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


def render_homework_prompt(
    *,
    template: str,
    preamble_path: Path,
    preamble_content: str,
    pdf_name: str,
    assignment_material: str,
) -> str:
    replacements = {
        "{{ preamble_path }}": preamble_path.resolve().as_posix(),
        "{{ preamble_content }}": preamble_content,
        "{{ assignment_pdf_name }}": pdf_name,
        "{{ assignment_material }}": assignment_material,
    }
    rendered = template
    for key, value in replacements.items():
        rendered = rendered.replace(key, value)
    return rendered


def request_homework_agent_text(
    prompt: str,
    pdf_path: Path | None = None,
) -> tuple[str, _agent_config.AgentConfig]:
    import _agent_config

    config = _agent_config.resolve_agent_config()
    content = []
    if pdf_path is not None:
        pdf_base64 = base64.b64encode(pdf_path.read_bytes()).decode("utf-8")
        content.append(
            {
                "type": "input_file",
                "filename": pdf_path.name,
                "file_data": pdf_base64,
            }
        )
    content.append({"type": "input_text", "text": prompt})
    payload = {
        "model": config.model,
        "stream": True,
        "input": [
            {
                "role": "user",
                "content": content,
            }
        ],
    }
    response = post_json(
        config.endpoint,
        payload,
        api_key=config.api_key,
        timeout=config.timeout,
        auth_header=config.auth_header,
        auth_prefix=config.auth_prefix,
        user_agent=config.user_agent,
    )
    return extract_agent_text(response), config


def extract_assignment_pdf_text(pdf_path: Path) -> str:
    cmd = ["pdftotext", "-layout", "-nopgbrk", str(pdf_path), "-"]
    completed = subprocess.run(
        cmd,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def should_retry_with_assignment_pdf_text(exc: urllib.error.HTTPError) -> bool:
    if exc.code != 400:
        return False
    error_body = exc.read().decode("utf-8", errors="replace")
    return "input[0].content[0].file_data" in error_body and "invalid_value" in error_body


def format_attached_assignment_pdf_material() -> str:
    return (
        "The assignment PDF is attached as an `input_file` in this request. "
        "Read that PDF directly before producing the LaTeX answer sheet."
    )


def format_extracted_assignment_pdf_material(pdf_text: str) -> str:
    return (
        "This provider rejected direct PDF input, so the assignment text extracted from the PDF is included below. "
        "Treat this extracted text as the source of truth.\n\n"
        f"```text\n{pdf_text}\n```"
    )


def write_homework_main_tex(
    homework_dir: Path,
    latex_body: str,
    *,
    preamble_path: Path,
    output_name: str = "main.tex",
    student_name: str = "",
) -> Path:
    latex = _inject_absolute_latex_preamble(latex_body, preamble_path)

    if student_name:
        author_line = f"\\author{{{student_name}}}"
        if re.search(r"\\author\{.*?\}", latex, flags=re.DOTALL):
            latex = re.sub(r"\\author\{.*?\}", author_line, latex, count=1, flags=re.DOTALL)
        elif "\\date" in latex:
            latex = latex.replace("\\date", f"{author_line}\n\\date", 1)
        elif "\\maketitle" in latex:
            latex = latex.replace("\\maketitle", f"{author_line}\n\\maketitle", 1)
        else:
            latex = f"{author_line}\n{latex}"

    tex_path = homework_dir / output_name
    tex_path.write_text(latex, encoding="utf-8")
    return tex_path


def post_json(
    url: str,
    payload: dict,
    *,
    api_key: str,
    timeout: int = 120,
    auth_header: str = "Authorization",
    auth_prefix: str = "Bearer ",
    user_agent: str = "",
) -> dict:
    if not api_key:
        raise ValueError("Missing API key for agent call")

    data = json.dumps(payload).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        auth_header: f"{auth_prefix}{api_key}",
    }
    if payload.get("stream") is True:
        headers["Accept"] = "text/event-stream"
    if user_agent:
        headers["User-Agent"] = user_agent
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8", errors="replace")
        content_type = (resp.headers.get("Content-Type") or "").lower()
    if "text/event-stream" in content_type:
        parsed = _parse_sse_response(raw)
    else:
        parsed = json.loads(raw) if raw else {}
    if not isinstance(parsed, dict):
        raise RuntimeError("Invalid agent response payload")
    return parsed


def _inject_absolute_latex_preamble(latex: str, preamble_path: Path) -> str:
    abs_path = preamble_path.resolve().as_posix()
    preamble_line = f"\\input{{{abs_path}}}"

    latex = re.sub(
        r"\\input\{[^}]*preamble[^}]*\}",
        lambda _: preamble_line,
        latex,
        flags=re.IGNORECASE,
    )
    latex = re.sub(
        r"\\usepackage\{[^}]*preamble[^}]*\}",
        lambda _: preamble_line,
        latex,
        flags=re.IGNORECASE,
    )

    if preamble_line in latex:
        return latex

    if "\\begin{document}" in latex:
        return latex.replace("\\begin{document}", f"{preamble_line}\n\\begin{{document}}", 1)

    return f"{preamble_line}\n{latex}"


def _parse_sse_response(raw: str) -> dict:
    latest_response: dict | None = None
    output_text_chunks: list[str] = []

    for line in raw.splitlines():
        if not line.startswith("data:"):
            continue
        chunk = line[5:].strip()
        if not chunk or chunk == "[DONE]":
            continue
        try:
            event = json.loads(chunk)
        except json.JSONDecodeError:
            continue
        if not isinstance(event, dict):
            continue

        response = event.get("response")
        if isinstance(response, dict):
            latest_response = response

        if event.get("type") == "response.output_text.delta":
            delta = event.get("delta")
            if isinstance(delta, str):
                output_text_chunks.append(delta)

        if event.get("type") == "response.completed" and isinstance(response, dict):
            return response

    if latest_response is not None:
        return latest_response

    if output_text_chunks:
        return {
            "output": [
                {
                    "content": [
                        {
                            "type": "output_text",
                            "text": "".join(output_text_chunks),
                        }
                    ]
                }
            ]
        }

    return {}


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
