"""Offline-critical launch settings, checked statically (fast, no server)."""

import shlex
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REQUIRED_FLAGS = {
    "--server.address": "127.0.0.1",
    "--server.enableStaticServing": "true",
    "--browser.gatherUsageStats": "false",
    "--server.headless": "true",
}


def _launcher_flags() -> dict:
    text = (ROOT / "scripts" / "run_app.sh").read_text(encoding="utf-8").replace("\\\n", " ")
    exec_line = next(line for line in text.splitlines() if line.strip().startswith("exec "))
    tokens = shlex.split(exec_line)
    return {tok: tokens[i + 1] for i, tok in enumerate(tokens[:-1]) if tok.startswith("--")}


def test_launcher_passes_offline_flags():
    flags = _launcher_flags()
    for flag, value in REQUIRED_FLAGS.items():
        assert flags.get(flag) == value, (flag, flags.get(flag))


def test_launcher_changes_to_project_root():
    assert 'cd "$(dirname "$0")/.."' in (ROOT / "scripts" / "run_app.sh").read_text(encoding="utf-8")


def test_project_streamlit_config_matches():
    config = tomllib.loads((ROOT / ".streamlit" / "config.toml").read_text(encoding="utf-8"))
    assert config["browser"]["gatherUsageStats"] is False
    assert config["server"]["address"] == "127.0.0.1"
    assert config["server"]["enableStaticServing"] is True


def test_preview_launch_uses_the_launcher():
    import json

    launch = json.loads((ROOT / ".claude" / "launch.json").read_text(encoding="utf-8"))
    config = launch["configurations"][0]
    # relative, or absolute when the preview tool starts outside the project; either way this repo's launcher
    (arg,) = config["runtimeArgs"]
    assert (ROOT / arg).resolve() == (ROOT / "scripts" / "run_app.sh").resolve()
