"""Build data/processed/observations.parquet from the saved raw files (offline).

Runs every loader, validates the combined store against the catalog, the 22 units and the
source registry, and refuses to write anything if a single problem is found.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pandas as pd  # noqa: E402

from equal_path.config import load_indicator_catalog  # noqa: E402
from equal_path.geography import UNIT_CODES  # noqa: E402
from equal_path.loaders import cif_report, cr_app, distance, lung_report, screening, sotkanet, statfin  # noqa: E402
from equal_path.observations import status_problems  # noqa: E402
from equal_path.paths import OBSERVATIONS_FILE  # noqa: E402
from equal_path.sources import source_ids  # noqa: E402
from equal_path.spine import KEY, validate_observations  # noqa: E402

LOADERS = (screening, cr_app, cif_report, lung_report, sotkanet, statfin, distance)
log = logging.getLogger("build_observations")


def main() -> int:
    frames = []
    for loader in LOADERS:
        try:
            frame = loader.load()
        except (OSError, ValueError, KeyError) as exc:
            log.error("%s failed: %s", loader.__name__, exc)
            return 1
        log.info("%-32s %5d rows", loader.__name__, len(frame))
        frames.append(frame)
    store = pd.concat(frames, ignore_index=True).sort_values(list(KEY)).reset_index(drop=True)
    catalog = {i.id: i.model_dump() for i in load_indicator_catalog()}
    problems = validate_observations(store, catalog=catalog, unit_codes=UNIT_CODES, source_ids=source_ids())
    problems += status_problems(store, load_indicator_catalog())  # e.g. a renamed source column dropped rows
    if problems:
        for problem in problems[:40]:
            log.error(problem)
        log.error("%d problems; store NOT written", len(problems))
        return 1
    OBSERVATIONS_FILE.parent.mkdir(parents=True, exist_ok=True)
    store.to_parquet(OBSERVATIONS_FILE, index=False)
    log.info("wrote %d rows, %d indicators -> %s", len(store), store.indicator_id.nunique(), OBSERVATIONS_FILE.name)
    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    sys.exit(main())
