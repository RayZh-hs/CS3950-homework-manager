from __future__ import annotations

import json
import re
import sys
import urllib.parse
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import settings
from _canvas_client import CanvasClient

REPO_ROOT = Path(__file__).resolve().parents[1]
HOMEWORK_ROOT = REPO_ROOT / settings.HOMEWORK_ROOT_DIR


@dataclass
class HomeworkRef:
    assignment: dict
    homework_dir: Path
    meta_file: Path


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", name).strip("-").lower()
    return slug or "homework"


def _assignment_dir_name(assignment: dict) -> str:
    return f"{assignment['id']}-{_slugify(str(assignment.get('name', 'homework')))}"


def _assignment_due_key(assignment: dict) -> tuple[int, str]:
    due = assignment.get("due_at")
    if not due:
        return (1, "")
    return (0, str(due))


def _decode_canvas_filename(name: str) -> str:
    return urllib.parse.unquote_plus(name).strip().replace("/", "_")


def _load_meta(meta_file: Path) -> dict:
    if not meta_file.exists():
        return {}
    try:
        return json.loads(meta_file.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_meta(meta_file: Path, payload: dict) -> None:
    meta_file.parent.mkdir(parents=True, exist_ok=True)
    meta_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _homework_ref(assignment: dict) -> HomeworkRef:
    homework_dir = HOMEWORK_ROOT / _assignment_dir_name(assignment)
    meta_file = homework_dir / ".hwmeta.json"
    return HomeworkRef(assignment=assignment, homework_dir=homework_dir, meta_file=meta_file)


def _fmt_time(ts: str | None) -> str:
    if not ts:
        return "-"
    return ts.replace("T", " ").replace("Z", " UTC")


def _is_submitted(assignment: dict) -> bool:
    submission = assignment.get("submission")
    if isinstance(submission, dict) and submission.get("submitted_at"):
        return True
    return bool(assignment.get("has_submitted_submissions"))


def _resolve_assignment(assignments: list[dict], query: str) -> dict:
    # 1) exact id
    if query.isdigit():
        for a in assignments:
            if str(a.get("id")) == query:
                return a

    # 2) custom matcher from settings
    matches = [a for a in assignments if settings.match_homework_query(a, query)]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        matches.sort(key=_assignment_due_key)
        print(f"Ambiguous query '{query}'. Candidates:", file=sys.stderr)
        for a in matches:
            print(f"  {a.get('id')}: {a.get('name')}", file=sys.stderr)
        raise SystemExit(2)

    raise SystemExit(f"Cannot find homework matching: {query}")


def list_homeworks() -> int:
    client = CanvasClient()
    assignments = settings.choose_homework_assignments(client.list_assignments())
    assignments = sorted(assignments, key=_assignment_due_key)

    HOMEWORK_ROOT.mkdir(parents=True, exist_ok=True)

    if not assignments:
        print("No homework assignments found.")
        return 0

    for a in assignments:
        ref = _homework_ref(a)
        downloaded = "Y" if ref.meta_file.exists() else "N"
        submitted = "Y" if _is_submitted(a) else "N"
        due = _fmt_time(a.get("due_at"))
        print(
            f"[{downloaded}|{submitted}] "
            f"{a.get('id')}: {a.get('name')} | due: {due}"
        )

    return 0


def fetch_homework(query: str) -> int:
    client = CanvasClient()
    assignments = settings.choose_homework_assignments(client.list_assignments())
    assignment = _resolve_assignment(assignments, query)
    ref = _homework_ref(assignment)
    ref.homework_dir.mkdir(parents=True, exist_ok=True)

    endpoints = settings.extract_homework_file_api_endpoints(assignment)
    downloaded_paths: list[Path] = []

    for endpoint in endpoints:
        meta = client.get_file_metadata(endpoint)
        raw_name = (
            meta.get("display_name")
            or meta.get("filename")
            or f"file_{meta.get('id', 'unknown')}"
        )
        local_name = _decode_canvas_filename(str(raw_name))
        signed_url = str(meta.get("url", "")).replace("\n", "").strip()
        if not signed_url:
            continue

        data = client.download_signed_file(signed_url)
        path = ref.homework_dir / local_name
        path.write_bytes(data)
        downloaded_paths.append(path)
        print(f"Downloaded: {path}")

    post_fetch = settings.post_fetch_homework(assignment, ref.homework_dir, downloaded_paths)

    old_meta = _load_meta(ref.meta_file)
    new_meta = {
        **old_meta,
        "assignment_id": assignment.get("id"),
        "assignment_name": assignment.get("name"),
        "due_at": assignment.get("due_at"),
        "downloaded_at": datetime.now(timezone.utc).isoformat(),
        "downloaded_files": [p.name for p in downloaded_paths],
        "post_fetch": post_fetch,
    }
    _save_meta(ref.meta_file, new_meta)

    print(f"Homework ready at: {ref.homework_dir}")
    return 0


def _validate_artifacts(paths: Iterable[Path], homework_dir: Path) -> list[Path]:
    valid: list[Path] = []
    for p in paths:
        p = p if p.is_absolute() else (homework_dir / p)
        if p.exists() and p.is_file():
            valid.append(p)
    return valid


def submit_homework(query: str) -> int:
    client = CanvasClient()
    assignments = settings.choose_homework_assignments(client.list_assignments())
    assignment = _resolve_assignment(assignments, query)
    ref = _homework_ref(assignment)

    if not ref.homework_dir.exists():
        raise SystemExit(
            f"Homework directory does not exist. Fetch first: {ref.homework_dir}"
        )

    settings.build_homework(assignment, ref.homework_dir)
    artifacts = _validate_artifacts(
        settings.get_submission_artifacts(assignment, ref.homework_dir),
        ref.homework_dir,
    )

    if not artifacts:
        raise SystemExit(
            "No submission artifacts found. "
            "Customize `get_submission_artifacts()` in settings.py."
        )

    uploaded_ids: list[int] = []
    for file_path in artifacts:
        file_id = client.upload_submission_file(int(assignment["id"]), file_path)
        uploaded_ids.append(file_id)
        print(f"Uploaded: {file_path.name} -> file_id={file_id}")

    comment = settings.get_submission_comment(assignment, ref.homework_dir)
    submit_resp = client.submit_assignment_files(
        int(assignment["id"]),
        uploaded_ids,
        comment=comment,
    )

    old_meta = _load_meta(ref.meta_file)
    new_meta = {
        **old_meta,
        "last_submit_at": datetime.now(timezone.utc).isoformat(),
        "last_submitted_files": [p.name for p in artifacts],
        "last_submitted_file_ids": uploaded_ids,
        "last_submit_response": submit_resp,
    }
    _save_meta(ref.meta_file, new_meta)

    print("Submission finished.")
    return 0
