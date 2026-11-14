"""Offline rehearsal (spec Step 7): render the demo counties with the network blocked, 5 times in a row.

Writes evidence/step8/rehearsal.json; exits non-zero unless the gate is met (>= 5 runs, no exceptions, no
validator rejections, every briefing from the offline cache).
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from equal_path.hardening import REHEARSAL_RUNS, rehearse  # noqa: E402
from equal_path.paths import EVIDENCE_DIR  # noqa: E402

if __name__ == "__main__":
    report = rehearse(runs=int(sys.argv[1]) if len(sys.argv) > 1 else REHEARSAL_RUNS)
    out = EVIDENCE_DIR / "step8" / "rehearsal.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "seconds"}), "max seconds", max(report["seconds"]))
    sys.exit(0 if report["gate_met"] else 1)
