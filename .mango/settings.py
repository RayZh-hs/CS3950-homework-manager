"""
Minimal project configuration for Canvas homework workflows.

Keep this file focused on course-specific configuration and custom hooks.
General API/client/workflow logic lives in other `.mango/` scripts.
"""

from __future__ import annotations

import base64
import html
import re
import subprocess
import urllib.parse
from pathlib import Path
from typing import List

import _agent_config
import _utility

# -----------------------------------------------------------------------------
# Required base configuration
# -----------------------------------------------------------------------------

OC_BASE_URL = "https://oc.sjtu.edu.cn/"
OC_API_BASE_URL = urllib.parse.urljoin(OC_BASE_URL, "api/v1/")
OC_COURSE_ID = 88632
OC_API_KEY = _utility.get_oc_api_key().strip().strip('"').strip("'")

# Local storage root under repository root: `<repo>/<HOMEWORK_ROOT_DIR>/...`
HOMEWORK_ROOT_DIR = "homework"

REPO_ROOT = Path(__file__).resolve().parents[1]
LITERALS_DIR = Path(__file__).resolve().parent / "literals"
PROMPT_TEMPLATE_PATH = LITERALS_DIR / "prompt.md"
PREAMBLE_PATH = LITERALS_DIR / "preamble.tex"
MAIN_TEX_NAME = "main.tex"
MAIN_PDF_NAME = "main.pdf"


def _render_prompt(
    *,
    template: str,
    preamble_path: Path,
    preamble_content: str,
    pdf_name: str,
    pdf_base64: str,
) -> str:
    replacements = {
        "{{ preamble_path }}": preamble_path.resolve().as_posix(),
        "{{ preamble_content }}": preamble_content,
        "{{ assignment_pdf_name }}": pdf_name,
        "{{ assignment_pdf_base64 }}": pdf_base64,
    }
    rendered = template
    for key, value in replacements.items():
        rendered = rendered.replace(key, value)
    return rendered


def _inject_absolute_preamble(latex: str, preamble_path: Path) -> str:
    abs_path = preamble_path.resolve().as_posix()
    preamble_line = f"\\input{{{abs_path}}}"

    latex = re.sub(
        r"\\input\{[^}]*preamble[^}]*\}",
        preamble_line,
        latex,
        flags=re.IGNORECASE,
    )
    latex = re.sub(
        r"\\usepackage\{[^}]*preamble[^}]*\}",
        preamble_line,
        latex,
        flags=re.IGNORECASE,
    )

    if preamble_line in latex:
        return latex

    if "\\begin{document}" in latex:
        return latex.replace("\\begin{document}", f"{preamble_line}\n\\begin{{document}}", 1)

    return f"{preamble_line}\n{latex}"


def _call_homework_agent(prompt: str) -> tuple[str, _agent_config.AgentConfig]:
    config = _agent_config.resolve_agent_config()
    payload = {
        "model": config.model,
        "input": [
            {
                "role": "user",
                "content": [
                    {"type": "input_text", "text": prompt},
                ],
            }
        ],
    }
    response = _utility.post_json(
        config.endpoint,
        payload,
        api_key=config.api_key,
        timeout=config.timeout,
    )
    return _utility.extract_agent_text(response), config


def _build_main_tex(homework_dir: Path, latex_body: str) -> Path:
    latex = _inject_absolute_preamble(latex_body, PREAMBLE_PATH)
    tex_path = homework_dir / MAIN_TEX_NAME
    tex_path.write_text(latex, encoding="utf-8")
    return tex_path


# -----------------------------------------------------------------------------
# Assignment/homework filtering and matching
# -----------------------------------------------------------------------------

def choose_homework_assignments(assignments: List[dict]) -> List[dict]:
    """
    Filter/reshape assignments that should be treated as homeworks.
    Default: include all assignments.
    """
    return assignments


def match_homework_query(assignment: dict, query: str) -> bool:
    """
    Determine whether one assignment matches a CLI query.
    Default supports:
      - exact numeric assignment id
      - case-insensitive substring match on assignment name
    """
    query = query.strip()
    if not query:
        return False

    a_id = str(assignment.get("id", ""))
    if query.isdigit() and query == a_id:
        return True

    name = str(assignment.get("name", "")).lower()
    return query.lower() in name


# -----------------------------------------------------------------------------
# Fetch behavior hooks
# -----------------------------------------------------------------------------

def extract_homework_file_api_endpoints(assignment: dict) -> List[str]:
    """
    Parse assignment description HTML to extract Canvas file API endpoints.

    Expected endpoint format:
      https://.../api/v1/courses/<course_id>/files/<file_id>
    """
    description = assignment.get("description") or ""
    endpoint_pattern = re.compile(r'data-api-endpoint="([^"]+/files/\d+)"')
    endpoints = endpoint_pattern.findall(description)

    # Fallback: if data-api-endpoint missing, convert href to API endpoint.
    if not endpoints:
        href_pattern = re.compile(r'href="([^"]*/courses/\d+/files/\d+[^\"]*)"')
        for href in href_pattern.findall(description):
            clean = html.unescape(href)
            m = re.search(r"/courses/(\d+)/files/(\d+)", clean)
            if m:
                c_id, f_id = m.groups()
                endpoints.append(f"{OC_API_BASE_URL}courses/{c_id}/files/{f_id}")

    # Ordered de-duplication
    seen = set()
    ordered = []
    for ep in endpoints:
        if ep not in seen:
            seen.add(ep)
            ordered.append(ep)
    return ordered


def post_fetch_homework(
    assignment: dict,
    homework_dir: Path,
    downloaded_files: List[Path],
) -> dict | None:
    """
    Optional hook after download finishes.

        Default: no-op.

        Customize this hook to run extra setup after files are downloaded.
    """
    pdf_files = [p for p in downloaded_files if p.suffix.lower() == ".pdf"]
    if not pdf_files:
        return {"status": "skipped", "reason": "no-pdf"}

    pdf_path = pdf_files[0]
    pdf_bytes = pdf_path.read_bytes()
    pdf_base64 = base64.b64encode(pdf_bytes).decode("utf-8")

    template = _utility.load_text(PROMPT_TEMPLATE_PATH)
    if not template.strip():
        return {"status": "skipped", "reason": "missing-prompt-template"}

    preamble_content = _utility.load_text(PREAMBLE_PATH)
    prompt = _render_prompt(
        template=template,
        preamble_path=PREAMBLE_PATH,
        preamble_content=preamble_content,
        pdf_name=pdf_path.name,
        pdf_base64=pdf_base64,
    )

    agent_text, agent_config = _call_homework_agent(prompt)
    if not agent_text:
        return {"status": "failed", "reason": "empty-agent-response"}

    latex_body = _utility.extract_latex_code_block(agent_text)
    if not latex_body:
        return {"status": "failed", "reason": "no-latex-code-block"}

    tex_path = _build_main_tex(homework_dir, latex_body)
    return {
        "status": "ok",
        "agent_model": agent_config.model,
        "pdf": pdf_path.name,
        "tex": tex_path.name,
    }


# -----------------------------------------------------------------------------
# Submission hooks
# -----------------------------------------------------------------------------

def build_homework(assignment: dict, homework_dir: Path) -> None:
    """
    Optional build step before submission.
    Default: no-op.

    Customize here if you need to run LaTeX/Make/CMake/other build tooling.
    """
    tex_path = homework_dir / MAIN_TEX_NAME
    if not tex_path.exists():
        return None

    output_pdf = homework_dir / MAIN_PDF_NAME
    cmd = [
        _utility.get_env("LATEX_COMMAND", "pdflatex"),
        "-interaction=nonstopmode",
        "-halt-on-error",
        f"-output-directory={homework_dir}",
        str(tex_path),
    ]
    subprocess.run(cmd, check=True, cwd=homework_dir)

    if not output_pdf.exists():
        raise RuntimeError("LaTeX build did not produce main.pdf")
    return None


def get_submission_artifacts(assignment: dict, homework_dir: Path) -> List[Path]:
    """
    Return files to submit.

    Default strategy:
      1) if `<homework_dir>/submit/` exists, submit all files inside it.
      2) otherwise submit `main.pdf` if present.
      3) otherwise return empty list.
    """
    submit_dir = homework_dir / "submit"
    if submit_dir.exists() and submit_dir.is_dir():
        return sorted([p for p in submit_dir.iterdir() if p.is_file()])

    main_pdf = homework_dir / MAIN_PDF_NAME
    if main_pdf.exists() and main_pdf.is_file():
        return [main_pdf]

    return []


def get_submission_comment(assignment: dict, homework_dir: Path) -> str | None:
    """
    Optional submission comment.
    """
    return None
