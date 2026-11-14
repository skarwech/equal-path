"""Trust panel inputs: figures come from the actual test run, never hard-coded text."""

from __future__ import annotations

import hashlib
import json
import logging
import xml.etree.ElementTree as ET  # noqa: S405 (parses our own pytest report only)
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from equal_path.paths import TEST_REPORT

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class TestSummary:
    __test__ = False  # not a pytest test class

    total: int
    failed: int
    skipped: int
    passed: int
    timestamp: str

    @property
    def all_green(self) -> bool:
        return self.failed == 0 and self.total > 0


def _suite_counts(suite: ET.Element) -> tuple[int, int, int]:
    total = int(suite.get("tests"))  # type: ignore[arg-type]  (None -> TypeError, handled)
    failed = int(suite.get("failures", "0")) + int(suite.get("errors", "0"))
    skipped = int(suite.get("skipped", "0"))
    if min(total, failed, skipped) < 0 or failed + skipped > total:
        raise ValueError(f"inconsistent counts in suite {suite.get('name')!r}")
    return total, failed, skipped


def read_test_summary(path: Path = TEST_REPORT) -> TestSummary | None:
    """Summarise a pytest --junitxml report across ALL suites; None if absent or malformed."""
    if not path.exists():
        return None
    try:
        root = ET.parse(path).getroot()  # noqa: S314 (trusted local file)
        suites = [root] if root.tag == "testsuite" else list(root.iter("testsuite"))
        counts = [_suite_counts(suite) for suite in suites]
    except (ET.ParseError, OSError, TypeError, ValueError) as exc:
        log.warning("unusable test report %s: %s", path, exc)
        return None
    if not counts:
        return None
    total, failed, skipped = (sum(column) for column in zip(*counts))
    return TestSummary(
        total=total,
        failed=failed,
        skipped=skipped,
        passed=total - failed - skipped,
        timestamp=max((suite.get("timestamp", "") for suite in suites), default=""),
    )


JUNK_NAMES = frozenset({".DS_Store", "Thumbs.db"})
JUNK_SUFFIXES = (".pyc", ".swp", ".swo", "~")


def _is_tracked(path: Path) -> bool:
    if "__pycache__" in path.parts or path.name in JUNK_NAMES:
        return False
    return not path.name.endswith(JUNK_SUFFIXES) and not (path.name.startswith(".") and path.suffix in (".swp", ".swo"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _watched_files(watched: Iterable[Path], root: Path) -> dict[str, str]:
    files = {}
    for folder in watched:
        candidates = [folder] if folder.is_file() else sorted(folder.rglob("*"))
        for path in candidates:
            if path.is_file() and _is_tracked(path):
                files[path.relative_to(root).as_posix()] = _sha256(path)
    return files


def is_full_reported_run(
    report: Path,
    from_testpaths: bool,
    keyword: str,
    markexpr: str,
    collectonly: bool,
    xmlpath: str | None,
) -> bool:
    """True only for the default full suite writing the badge's own report."""
    if not from_testpaths or keyword or markexpr or collectonly or not xmlpath:
        return False
    return Path(xmlpath).resolve() == report.resolve()


def write_fingerprint(target: Path, watched: Iterable[Path], root: Path, report: Path, full_run: bool) -> None:
    """Bind the run to its report and to every watched file's content.

    Partial runs and runs without a report record `full_run: false`, which the app
    always shows as stale, so a subset or failed-to-report run can never look current.
    """
    try:
        payload = {
            "full_run": full_run and report.exists(),
            "report_sha256": _sha256(report) if report.exists() else None,
            "files": _watched_files(watched, root),
        }
    except OSError as exc:
        log.warning("cannot fingerprint test inputs: %s", exc)
        payload = {"full_run": False, "report_sha256": None, "files": {}}
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=1, sort_keys=True), encoding="utf-8")


def fingerprint_is_current(target: Path, watched: Iterable[Path], root: Path, report: Path) -> bool:
    """True only if the last full run produced this exact report and no watched file changed."""
    try:
        recorded = json.loads(target.read_text(encoding="utf-8"))
        return (
            recorded.get("full_run") is True
            and recorded.get("report_sha256") == _sha256(report)
            and recorded.get("files") == _watched_files(watched, root)
        )
    except (OSError, ValueError, AttributeError):
        return False


def input_stamp(paths: Iterable[Path]) -> tuple:
    """Cheap change key (name, mtime, size) for cache invalidation; missing files count too."""
    stamp = []
    for path in paths:
        try:
            info = path.stat()
            stamp.append((str(path), info.st_mtime_ns, info.st_size))
        except OSError:
            stamp.append((str(path), None, None))
    return tuple(stamp)
