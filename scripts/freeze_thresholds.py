"""Freeze config/thresholds.yaml: stamp frozen_at with the current time, then record its
SHA-256 in config/thresholds.lock.

Run only when the team deliberately changes a threshold; the lock diff makes the
change visible, so nobody can tune a threshold after seeing county results.
Refuses invalid files and files whose status is not 'frozen'.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from equal_path.config import freeze  # noqa: E402

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    try:
        logging.info("thresholds frozen: sha256=%s", freeze())
    except (OSError, ValueError) as exc:
        logging.error("refusing to freeze: %s", exc)
        sys.exit(1)
