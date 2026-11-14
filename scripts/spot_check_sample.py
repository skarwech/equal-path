"""Draw the F0 spot-check sample: 10 unit-level cells from the built store, with a logged seed.

Stratified so every source family whose publisher page can be opened in a browser appears.
Writes evidence/spotcheck_sample.csv; the result column is filled in after checking each
cell against the publisher's live page (screenshots in evidence/spotcheck/).
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pandas as pd  # noqa: E402

from equal_path.observations import load_observations  # noqa: E402
from equal_path.paths import EVIDENCE_DIR  # noqa: E402

SEED = 20261114
QUOTA = {"S_CR_SCREENING_STATS": 3, "S_CIF2024_REPORT": 2, "S_LUNG_REPORT_2019_2023": 2, "S_SOTKANET": 2, "S_STATFIN": 1}


def main() -> int:
    store = load_observations()
    units = store[(store.geo_level == "unit") & store.value.notna()]
    picks = [units[units.source_id == source].sample(n=n, random_state=SEED) for source, n in QUOTA.items()]
    sample = pd.concat(picks).reset_index(drop=True)
    sample.insert(0, "check_id", [f"SC{i + 1:02d}" for i in range(len(sample))])
    sample = sample.assign(seed=SEED, live_value="", result="")
    out = EVIDENCE_DIR / "spotcheck_sample.csv"
    sample.to_csv(out, index=False)
    print(sample[["check_id", "indicator_id", "county_id", "period", "subgroup", "value", "numerator", "denominator", "locator"]].to_string())
    return 0


if __name__ == "__main__":
    sys.exit(main())
