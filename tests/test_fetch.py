"""Generic raw-data fetcher: every download lands in data/raw/<family>/ with a manifest."""

import hashlib
import json

import pytest

from equal_path.fetch import Download, fetch_family, load_downloads


def _ok(payloads):
    def opener(download):
        return payloads[download.url]
    return opener


def test_fetch_writes_files_and_manifest(tmp_path):
    downloads = [
        Download(family="demo", file="a.json", url="https://x/a", source_id="S_A", kind="json"),
        Download(family="demo", file="b.csv", url="https://x/b", source_id="S_B", kind="csv"),
    ]
    target = tmp_path / "raw" / "demo"
    fetch_family(downloads, target, opener=_ok({"https://x/a": b'{"k": 1}', "https://x/b": b"a;b\n1;2\n"}), now="2026-11-14T00:00:00+00:00")
    manifest = json.loads((target / "manifest.json").read_text(encoding="utf-8"))
    assert [e["file"] for e in manifest] == ["a.json", "b.csv"]
    assert manifest[0]["sha256"] == hashlib.sha256(b'{"k": 1}').hexdigest()
    assert manifest[0]["source_id"] == "S_A" and manifest[0]["retrieved_at"] == "2026-11-14T00:00:00+00:00"


def test_failed_download_leaves_previous_files_untouched(tmp_path):
    target = tmp_path / "raw" / "demo"
    target.mkdir(parents=True)
    (target / "a.json").write_text("old", encoding="utf-8")

    def broken(download):
        raise OSError("network down")

    downloads = [Download(family="demo", file="a.json", url="https://x/a", source_id="S_A", kind="json")]
    with pytest.raises(OSError):
        fetch_family(downloads, target, opener=broken, now="t")
    assert (target / "a.json").read_text(encoding="utf-8") == "old"


def test_json_kind_rejects_html_error_pages(tmp_path):
    downloads = [Download(family="demo", file="a.json", url="https://x/a", source_id="S_A", kind="json")]
    with pytest.raises(ValueError, match="a.json"):
        fetch_family(downloads, tmp_path / "demo", opener=_ok({"https://x/a": b"<html>404</html>"}), now="t")


def test_download_config_is_valid_and_sources_resolve():
    from equal_path.sources import source_ids

    downloads = load_downloads()
    assert len({(d.family, d.file) for d in downloads}) == len(downloads)
    assert {d.source_id for d in downloads} <= source_ids()
    assert all(d.url.startswith("https://") for d in downloads)
