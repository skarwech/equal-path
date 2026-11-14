"""Copy session-bound original exports (config/snapshots.yaml) into data/raw/<family>/ with a manifest.

Usage: python3 scripts/register_snapshots.py <folder holding the original files>
"""

from __future__ import annotations

import hashlib
import json
import logging
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from equal_path.config import _read_list  # noqa: E402
from equal_path.paths import CONFIG_DIR, DATA_DIR  # noqa: E402


def main(folder: Path) -> int:
    entries = _read_list(CONFIG_DIR / "snapshots.yaml")
    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    manifests: dict[str, list] = {}
    for entry in entries:
        source = folder / entry["original_name"]
        if not source.is_file():
            logging.error("missing snapshot %s", source)
            return 1
        target = DATA_DIR / "raw" / entry["family"] / entry["file"]
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        payload = target.read_bytes()
        manifests.setdefault(entry["family"], []).append({
            "file": entry["file"], "source_id": entry["source_id"], "url": entry["url"],
            "method": "SNAPSHOT", "capture": entry["capture"], "registered_at": stamp,
            "bytes": len(payload), "sha256": hashlib.sha256(payload).hexdigest(),
        })
    for family, manifest in manifests.items():
        (DATA_DIR / "raw" / family / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
        logging.info("%s: %d snapshot files registered", family, len(manifest))
    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    sys.exit(main(Path(sys.argv[1])))
