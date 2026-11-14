"""Write the offline analyst cache (data/processed/briefings.json): one validated briefing per county.

Uses Claude when the anthropic SDK and credentials are available, otherwise the deterministic template.
Rerun after any data change; tests/test_hardening.py fails while the cache is stale.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from equal_path.actions import run_actions  # noqa: E402
from equal_path.hardening import BRIEFINGS_FILE, build_briefing_cache  # noqa: E402

if __name__ == "__main__":
    cache = build_briefing_cache(run_actions())
    sources = sorted({e["source"] for e in cache.values()})
    print(f"cached {len(cache)} briefings ({', '.join(sources)}) -> {BRIEFINGS_FILE}")
