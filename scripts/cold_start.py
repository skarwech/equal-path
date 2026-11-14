"""Cold start (spec F8 offline mode): a fresh Python process renders the app with the network blocked.

Prints the seconds and writes evidence/step8/cold_start.json; exits non-zero above 10 s or on an exception.
"""

import json
import sys
import time

STARTED = time.perf_counter()   # before any project or Streamlit import

from pathlib import Path  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from streamlit.testing.v1 import AppTest  # noqa: E402

from equal_path.hardening import block_network  # noqa: E402
from equal_path.paths import EVIDENCE_DIR, ROOT  # noqa: E402

LIMIT_SECONDS = 10.0

if __name__ == "__main__":
    with block_network():
        at = AppTest.from_file(str(ROOT / "app" / "streamlit_app.py"), default_timeout=60).run()
    seconds = round(time.perf_counter() - STARTED, 2)
    report = {"cold_start_seconds_offline": seconds, "limit_seconds": LIMIT_SECONDS, "exceptions": len(at.exception),
              "method": "fresh Python process incl. imports; network blocked; Streamlit AppTest full render incl. data load"}
    if len(sys.argv) < 2 or sys.argv[1] != "--no-write":
        out = EVIDENCE_DIR / "step8" / "cold_start.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(report))
    sys.exit(0 if seconds < LIMIT_SECONDS and not at.exception else 1)
