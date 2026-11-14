"""Download the raw geography files from Statistics Finland into data/raw/geo/.

Run once while online; everything downstream works offline from the saved files.
A manifest records URL, retrieval time, size and SHA-256 for each file.
"""

from __future__ import annotations

import hashlib
import json
import logging
import shutil
import sys
import tempfile
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from equal_path.geography_build import geojson_content_sha256  # noqa: E402

RAW_GEO = ROOT / "data" / "raw" / "geo"
CLASS_API = "https://data.stat.fi/api/classifications/v2"
WFS = "https://geo.stat.fi/geoserver/tilastointialueet/wfs"
QUERY = "content=data&meta=max&lang=fi&format=json"

DOWNLOADS: dict[str, tuple[str, str]] = {
    "hva_classification_2026.json": (
        "S_STATFI_HVA_CLASS_2026",
        f"{CLASS_API}/classifications/hyvinvointialue_1_20260101/classificationItems?{QUERY}",
    ),
    "yta_classification_2026.json": (
        "S_STATFI_YTA_CORR_2026",
        f"{CLASS_API}/classifications/yhteistyoalue_1_20260101/classificationItems?{QUERY}",
    ),
    "kunta_hva_2026.json": (
        "S_STATFI_HVA_CLASS_2026",
        f"{CLASS_API}/correspondenceTables/kunta_1_20260101%23hyvinvointialue_1_20260101/maps?{QUERY}",
    ),
    "kunta_yta_2026.json": (
        "S_STATFI_YTA_CORR_2026",
        f"{CLASS_API}/correspondenceTables/kunta_1_20260101%23yhteistyoalue_1_20260101/maps?{QUERY}",
    ),
    "hva_boundaries_4500k_2026.geojson": (
        "S_STATFI_HVA_BOUNDARIES_2026",
        f"{WFS}?service=WFS&version=2.0.0&request=GetFeature"
        "&typeName=tilastointialueet:hyvinvointialue4500k_2026"
        "&outputFormat=application/json&srsName=EPSG:4326",
    ),
}

log = logging.getLogger("fetch_geography")


def download(url: str, timeout: int = 90) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "equal-path-pipeline/0.1"})
    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310 (fixed https URLs)
        if response.status != 200:
            raise RuntimeError(f"HTTP {response.status} for {url}")
        return response.read()


def main() -> int:
    RAW_GEO.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix="geo_", dir=RAW_GEO.parent))
    try:
        if _download_all(staging) != 0:
            return 1
        if RAW_GEO.exists():
            shutil.rmtree(RAW_GEO)
        staging.rename(RAW_GEO)
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    return 0


def _download_all(target: Path) -> int:
    manifest = []
    for filename, (source_id, url) in DOWNLOADS.items():
        try:
            payload = download(url)
            json.loads(payload)  # fail fast on HTML error pages
        except Exception as exc:  # noqa: BLE001 (report every failure with context)
            log.error("download failed for %s: %s", filename, exc)
            return 1
        (target / filename).write_bytes(payload)
        entry = {
            "file": filename,
            "source_id": source_id,
            "url": url,
            "retrieved_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "bytes": len(payload),
            "sha256": hashlib.sha256(payload).hexdigest(),
        }
        if filename.endswith(".geojson"):
            # Raw bytes change on every request (timeStamp); this hash is re-checkable upstream.
            entry["content_sha256"] = geojson_content_sha256(json.loads(payload))
        manifest.append(entry)
        log.info("saved %s (%d bytes)", filename, len(payload))
    (target / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    sys.exit(main())
