"""Generic raw-data fetcher driven by config/downloads.yaml.

Each family is written to a staging folder and swapped in only when every file in it
downloaded and passed its format check, so a failed run never mixes old and new files.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
import urllib.request
from pathlib import Path
from typing import Callable, Iterable, Literal

from pydantic import BaseModel, ConfigDict

from equal_path.config import _read_list
from equal_path.paths import CONFIG_DIR

DOWNLOADS_FILE = CONFIG_DIR / "downloads.yaml"
USER_AGENT = "equal-path-pipeline/0.1"


class Download(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    family: str
    file: str
    url: str
    source_id: str
    kind: Literal["json", "csv", "xlsx", "html", "pdf", "text"]
    method: Literal["GET", "POST"] = "GET"
    body: str | None = None  # JSON body for POST APIs (PxWeb)
    note: str = ""


def load_downloads(path: Path = DOWNLOADS_FILE) -> tuple[Download, ...]:
    if not path.exists():
        return ()
    return tuple(Download.model_validate(item) for item in _read_list(path))


def http_open(download: Download, timeout: int = 120) -> bytes:
    data = download.body.encode("utf-8") if download.body else None
    headers = {"User-Agent": USER_AGENT}
    if data:
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(download.url, data=data, headers=headers, method=download.method)
    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310 (configured https URLs)
        if response.status != 200:
            raise OSError(f"HTTP {response.status} for {download.url}")
        return response.read()


def _check(download: Download, payload: bytes) -> None:
    head = payload[:200].lstrip().lower()
    if download.kind == "json":
        try:
            json.loads(payload)
        except ValueError as exc:
            raise ValueError(f"{download.file}: not JSON ({exc})") from exc
    elif download.kind == "pdf" and not payload.startswith(b"%PDF"):
        raise ValueError(f"{download.file}: not a PDF")
    elif download.kind == "xlsx" and not payload.startswith(b"PK"):
        raise ValueError(f"{download.file}: not an xlsx file")
    elif download.kind == "csv" and head.startswith((b"<!doctype", b"<html")):
        raise ValueError(f"{download.file}: HTML instead of CSV")


def fetch_family(
    downloads: Iterable[Download],
    target: Path,
    opener: Callable[[Download], bytes] = http_open,
    now: str | None = None,
) -> list[dict]:
    """Download every file of one family into `target` atomically and write manifest.json."""
    from datetime import datetime, timezone

    stamp = now or datetime.now(timezone.utc).isoformat(timespec="seconds")
    target.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f"{target.name}_", dir=target.parent))
    try:
        manifest = []
        for download in downloads:
            payload = opener(download)
            _check(download, payload)
            (staging / download.file).write_bytes(payload)
            manifest.append({
                "file": download.file, "source_id": download.source_id, "url": download.url,
                "method": download.method, "retrieved_at": stamp, "bytes": len(payload),
                "sha256": hashlib.sha256(payload).hexdigest(),
            })
        (staging / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
        if target.exists():
            shutil.rmtree(target)
        staging.rename(target)
        return manifest
    finally:
        if staging.exists():
            shutil.rmtree(staging)
