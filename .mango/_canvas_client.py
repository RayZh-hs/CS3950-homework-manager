from __future__ import annotations

import json
import mimetypes
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path
from typing import Any

import settings


class CanvasClient:
    def __init__(self) -> None:
        self.api_base = settings.OC_API_BASE_URL
        self.course_id = settings.OC_COURSE_ID
        self.api_key = settings.OC_API_KEY

    def _auth_headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.api_key}"}

    def _request(
        self,
        method: str,
        url: str,
        *,
        query: dict[str, Any] | None = None,
        form: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        timeout: int = 60,
    ) -> tuple[Any, dict[str, str]]:
        if query:
            q = urllib.parse.urlencode(query, doseq=True)
            url = f"{url}{'&' if '?' in url else '?'}{q}"

        data = None
        req_headers = dict(self._auth_headers())
        if headers:
            req_headers.update(headers)

        if form is not None:
            encoded = urllib.parse.urlencode(form, doseq=True)
            data = encoded.encode("utf-8")
            req_headers.setdefault("Content-Type", "application/x-www-form-urlencoded")

        req = urllib.request.Request(url, data=data, headers=req_headers, method=method)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            text = raw.decode("utf-8", errors="replace") if raw else ""
            parsed: Any = None
            if text:
                try:
                    parsed = json.loads(text)
                except json.JSONDecodeError:
                    parsed = text
            return parsed, dict(resp.headers)

    def _get_paginated(self, path: str, query: dict[str, Any] | None = None) -> list[dict]:
        url = urllib.parse.urljoin(self.api_base, path)
        items: list[dict] = []
        next_url = url
        next_query = query or {}

        while next_url:
            parsed, headers = self._request("GET", next_url, query=next_query)
            next_query = None
            if isinstance(parsed, list):
                items.extend(parsed)
            elif parsed is not None:
                raise RuntimeError(f"Unexpected paginated response type: {type(parsed).__name__}")

            next_url = None
            link_header = headers.get("Link", "")
            if link_header:
                for chunk in link_header.split(","):
                    chunk = chunk.strip()
                    if 'rel="next"' in chunk:
                        left = chunk.find("<")
                        right = chunk.find(">")
                        if left != -1 and right != -1 and right > left:
                            next_url = chunk[left + 1 : right]
                            break

        return items

    def list_assignments(self) -> list[dict]:
        return self._get_paginated(
            f"courses/{self.course_id}/assignments",
            query={"per_page": 100, "include[]": ["submission"]},
        )

    def get_assignment(self, assignment_id: int) -> dict:
        data, _ = self._request(
            "GET",
            urllib.parse.urljoin(
                self.api_base,
                f"courses/{self.course_id}/assignments/{assignment_id}",
            ),
            query={"include[]": ["submission"]},
        )
        if not isinstance(data, dict):
            raise RuntimeError("Invalid assignment response")
        return data

    def get_file_metadata(self, file_api_endpoint: str) -> dict:
        data, _ = self._request("GET", file_api_endpoint)
        if not isinstance(data, dict):
            raise RuntimeError("Invalid file metadata response")
        return data

    def download_signed_file(self, signed_url: str) -> bytes:
        req = urllib.request.Request(signed_url, method="GET")
        with urllib.request.urlopen(req, timeout=120) as resp:
            return resp.read()

    def _build_multipart_body(self, fields: dict[str, Any], file_path: Path) -> tuple[bytes, str]:
        boundary = f"----mango-canvas-{uuid.uuid4().hex}"
        lines: list[bytes] = []

        for key, value in fields.items():
            lines.append(f"--{boundary}\r\n".encode("utf-8"))
            lines.append(
                f'Content-Disposition: form-data; name="{key}"\r\n\r\n'.encode("utf-8")
            )
            lines.append(str(value).encode("utf-8"))
            lines.append(b"\r\n")

        mime = mimetypes.guess_type(str(file_path))[0] or "application/octet-stream"
        lines.append(f"--{boundary}\r\n".encode("utf-8"))
        lines.append(
            (
                f'Content-Disposition: form-data; name="file"; '
                f'filename="{file_path.name}"\r\n'
            ).encode("utf-8")
        )
        lines.append(f"Content-Type: {mime}\r\n\r\n".encode("utf-8"))
        lines.append(file_path.read_bytes())
        lines.append(b"\r\n")
        lines.append(f"--{boundary}--\r\n".encode("utf-8"))

        body = b"".join(lines)
        return body, boundary

    def upload_submission_file(self, assignment_id: int, file_path: Path) -> int:
        init_url = urllib.parse.urljoin(
            self.api_base,
            f"courses/{self.course_id}/assignments/{assignment_id}/submissions/self/files",
        )
        init_form = {
            "name": file_path.name,
            "size": file_path.stat().st_size,
            "content_type": mimetypes.guess_type(str(file_path))[0] or "application/octet-stream",
            "on_duplicate": "rename",
        }
        init_data, _ = self._request("POST", init_url, form=init_form)
        if not isinstance(init_data, dict):
            raise RuntimeError("Invalid upload init response")

        upload_url = str(init_data.get("upload_url", ""))
        upload_params = init_data.get("upload_params", {})
        if not upload_url or not isinstance(upload_params, dict):
            raise RuntimeError("Missing upload URL/params")

        body, boundary = self._build_multipart_body(upload_params, file_path)
        upload_req = urllib.request.Request(
            upload_url,
            data=body,
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(upload_req, timeout=180) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
                headers = dict(resp.headers)
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Upload failed: {exc.code} {exc.reason} {raw}") from exc

        json_data: dict[str, Any] | None = None
        if raw:
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, dict):
                    json_data = parsed
            except json.JSONDecodeError:
                pass

        if json_data and isinstance(json_data.get("id"), int):
            return int(json_data["id"])

        location = headers.get("Location")
        if location:
            finalize, _ = self._request("GET", location)
            if isinstance(finalize, dict) and isinstance(finalize.get("id"), int):
                return int(finalize["id"])

        if json_data and isinstance(json_data.get("url"), str):
            finalize, _ = self._request("GET", str(json_data["url"]))
            if isinstance(finalize, dict) and isinstance(finalize.get("id"), int):
                return int(finalize["id"])

        raise RuntimeError("Cannot resolve uploaded file id from upload response")

    def submit_assignment_files(
        self,
        assignment_id: int,
        file_ids: list[int],
        comment: str | None = None,
    ) -> dict:
        if not file_ids:
            raise ValueError("file_ids cannot be empty")

        submit_url = urllib.parse.urljoin(
            self.api_base,
            f"courses/{self.course_id}/assignments/{assignment_id}/submissions",
        )
        form: dict[str, Any] = {
            "submission[submission_type]": "online_upload",
            "submission[file_ids][]": file_ids,
        }
        if comment:
            form["comment[text_comment]"] = comment

        data, _ = self._request("POST", submit_url, form=form)
        if not isinstance(data, dict):
            raise RuntimeError("Invalid submit response")
        return data
