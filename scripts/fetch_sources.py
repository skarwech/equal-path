"""Download every source family listed in config/downloads.yaml into data/raw/<family>/.

Usage: python3 scripts/fetch_sources.py [family ...]   (no argument = all families)
Run once while online; build_observations.py then works offline from the saved files.
"""

from __future__ import annotations

import logging
import sys
from itertools import groupby
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from equal_path.fetch import fetch_family, load_downloads  # noqa: E402
from equal_path.paths import DATA_DIR  # noqa: E402

log = logging.getLogger("fetch_sources")


def main(families: list[str]) -> int:
    downloads = sorted(load_downloads(), key=lambda d: d.family)
    status = 0
    for family, items in groupby(downloads, key=lambda d: d.family):
        if families and family not in families:
            continue
        try:
            manifest = fetch_family(list(items), DATA_DIR / "raw" / family)
            log.info("%s: %d files", family, len(manifest))
        except (OSError, ValueError) as exc:
            log.error("%s failed, previous files kept: %s", family, exc)
            status = 1
    return status


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    sys.exit(main(sys.argv[1:]))
