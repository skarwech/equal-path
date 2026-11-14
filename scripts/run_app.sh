#!/usr/bin/env bash
# Launch Equal Path offline-safe from ANY working directory.
# Flags are passed explicitly so behaviour never depends on which
# .streamlit/config.toml happens to be in the caller's cwd.
set -euo pipefail
cd "$(dirname "$0")/.."
exec "${PYTHON:-python3}" -m streamlit run app/streamlit_app.py \
  --server.headless true \
  --server.address 127.0.0.1 \
  --server.port "${PORT:-8501}" \
  --server.enableStaticServing true \
  --browser.gatherUsageStats false
