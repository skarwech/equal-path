"""Config loaders fail loudly: duplicates, wrong types, empty files, invalid locks."""

import pytest

from equal_path.config import (
    load_anchors,
    load_rules,
    load_thresholds,
    thresholds_are_frozen,
    thresholds_digest,
    write_lock,
)
from equal_path.paths import THRESHOLDS_FILE


@pytest.fixture
def thresholds_text():
    return THRESHOLDS_FILE.read_text(encoding="utf-8")


def _write(tmp_path, name, text):
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


def test_duplicate_key_rejected(tmp_path, thresholds_text):
    path = _write(tmp_path, "t.yaml", thresholds_text + "\nmin_denominator: 1\n")
    with pytest.raises(ValueError, match="duplicate key 'min_denominator'"):
        load_thresholds(path)


@pytest.mark.parametrize(
    "line,value",
    [
        ("min_denominator: 30", "min_denominator: true"),
        ("min_denominator: 30", 'min_denominator: "30"'),
        ("stage_coverage_target: 0.70", "stage_coverage_target: true"),
        ("min_practical_gap_pp: 3.0", "min_practical_gap_pp: .inf"),
        ("min_practical_gap_pp: 3.0", "min_practical_gap_pp: .nan"),
    ],
)
def test_lax_coercion_rejected(tmp_path, thresholds_text, line, value):
    assert line in thresholds_text
    path = _write(tmp_path, "t.yaml", thresholds_text.replace(line, value))
    with pytest.raises(ValueError):
        load_thresholds(path)


@pytest.mark.parametrize("loader", [load_rules, load_anchors])
@pytest.mark.parametrize("content", ["", "{}\n", "just a string\n"])
def test_list_files_must_hold_a_list(tmp_path, loader, content):
    with pytest.raises(ValueError, match="list"):
        loader(_write(tmp_path, "x.yaml", content))


def test_unreadable_yaml_is_value_error(tmp_path):
    with pytest.raises(ValueError):
        load_rules(_write(tmp_path, "x.yaml", "- id: [unclosed\n"))


def test_write_lock_refuses_invalid_file(tmp_path, thresholds_text):
    source = _write(tmp_path, "t.yaml", thresholds_text.replace("min_denominator: 30", "min_denominator: -1"))
    lock = tmp_path / "t.lock"
    with pytest.raises(ValueError):
        write_lock(lock, source)
    assert not lock.exists()


def test_write_lock_round_trip(tmp_path, thresholds_text):
    source = _write(tmp_path, "t.yaml", thresholds_text)
    lock = tmp_path / "t.lock"
    digest = write_lock(lock, source)
    assert lock.read_text(encoding="utf-8").strip() == digest
    assert thresholds_are_frozen(source, lock)


def test_draft_status_is_never_locked(tmp_path, thresholds_text):
    source = _write(tmp_path, "t.yaml", thresholds_text.replace("status: frozen", "status: draft"))
    lock = tmp_path / "t.lock"
    with pytest.raises(ValueError, match="draft"):
        write_lock(lock, source)
    assert not lock.exists()
    assert not thresholds_are_frozen(source, lock)


def test_freeze_stamps_the_actual_time(tmp_path, thresholds_text):
    from equal_path.config import freeze

    source = _write(tmp_path, "t.yaml", thresholds_text)
    lock = tmp_path / "t.lock"
    freeze(source, lock, when="2030-01-02T03:04:05+00:00")
    assert load_thresholds(source).frozen_at == "2030-01-02T03:04:05+00:00"
    assert thresholds_are_frozen(source, lock)


def test_edit_after_lock_is_not_frozen(tmp_path, thresholds_text):
    source = _write(tmp_path, "t.yaml", thresholds_text)
    lock = tmp_path / "t.lock"
    write_lock(lock, source)
    source.write_text(thresholds_text.replace("min_denominator: 30", "min_denominator: 31"), encoding="utf-8")
    assert not thresholds_are_frozen(source, lock)


def test_missing_lock_is_not_frozen(tmp_path):
    assert not thresholds_are_frozen(THRESHOLDS_FILE, tmp_path / "absent.lock")


def test_digest_ignores_line_ending_style(tmp_path, thresholds_text):
    lf = _write(tmp_path, "lf.yaml", thresholds_text)
    crlf = tmp_path / "crlf.yaml"
    crlf.write_bytes(thresholds_text.replace("\n", "\r\n").encode("utf-8"))
    assert thresholds_digest(lf) == thresholds_digest(crlf)
