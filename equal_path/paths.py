"""Filesystem locations, resolved from the project root so any working directory works."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = ROOT / "config"
DATA_DIR = ROOT / "data"
RAW_GEO_DIR = DATA_DIR / "raw" / "geo"
REFERENCE_DIR = DATA_DIR / "reference"
EVIDENCE_DIR = ROOT / "evidence"

THRESHOLDS_FILE = CONFIG_DIR / "thresholds.yaml"
THRESHOLDS_LOCK = CONFIG_DIR / "thresholds.lock"
SCOPE_FILE = CONFIG_DIR / "scope.yaml"
RULES_FILE = CONFIG_DIR / "rules.yaml"
ANCHORS_FILE = CONFIG_DIR / "anchors.yaml"
REFERENCE_TIMES_FILE = CONFIG_DIR / "reference_times.yaml"
INDICATORS_FILE = CONFIG_DIR / "indicators.yaml"

SOURCES_FILE = REFERENCE_DIR / "sources.csv"
UNITS_FILE = REFERENCE_DIR / "units.csv"
UNITS_GEOJSON = REFERENCE_DIR / "units.geojson"
OBSERVATIONS_FILE = DATA_DIR / "processed" / "observations.parquet"  # built in Step 2
TEST_REPORT = EVIDENCE_DIR / "test_report.xml"
TEST_FINGERPRINT = EVIDENCE_DIR / "test_inputs.json"
STALENESS_WATCHED = (
    ROOT / "equal_path", ROOT / "app", ROOT / "tests", ROOT / "scripts",
    CONFIG_DIR, REFERENCE_DIR, DATA_DIR / "raw", DATA_DIR / "processed", ROOT / "pyproject.toml", ROOT / ".streamlit",
)
APP_INPUTS = (
    THRESHOLDS_FILE, SCOPE_FILE, RULES_FILE, ANCHORS_FILE, REFERENCE_TIMES_FILE, INDICATORS_FILE,
    SOURCES_FILE, UNITS_FILE, UNITS_GEOJSON, OBSERVATIONS_FILE,
)
