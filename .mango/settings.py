"""
Minimal project configuration for Canvas homework workflows.

Keep this file focused on course-specific configuration and custom hooks.
General API/client/workflow logic lives in other `.mango/` scripts.
"""

from __future__ import annotations

import html
import re
import urllib.parse
from pathlib import Path
from typing import List

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
    return None


# -----------------------------------------------------------------------------
# Submission hooks
# -----------------------------------------------------------------------------

def build_homework(assignment: dict, homework_dir: Path) -> None:
    """
    Optional build step before submission.
    Default: no-op.

    Customize here if you need to run LaTeX/Make/CMake/other build tooling.
    """
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

    main_pdf = homework_dir / "main.pdf"
    if main_pdf.exists() and main_pdf.is_file():
        return [main_pdf]

    return []


def get_submission_comment(assignment: dict, homework_dir: Path) -> str | None:
    """
    Optional submission comment.
    """
    return None
