"""Integration: the launcher serves the map topojson locally from ANY working directory,
binds to localhost only and makes no telemetry or public-IP calls."""

import os
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
LAUNCHER = ROOT / "scripts" / "run_app.sh"

pytestmark = pytest.mark.integration


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@pytest.fixture(scope="module")
def server(tmp_path_factory):
    port = _free_port()
    cwd = tmp_path_factory.mktemp("elsewhere")  # deliberately NOT the project root
    log_path = cwd / "server.log"
    env = {**os.environ, "PORT": str(port), "PYTHON": sys.executable}
    with log_path.open("w") as log:
        process = subprocess.Popen(["bash", str(LAUNCHER)], cwd=cwd, env=env, stdout=log, stderr=subprocess.STDOUT)
    base = f"http://127.0.0.1:{port}"
    try:
        deadline = time.time() + 40
        while time.time() < deadline:
            try:
                urllib.request.urlopen(f"{base}/_stcore/health", timeout=1).read()
                break
            except OSError:
                time.sleep(0.3)
        else:
            pytest.fail("server did not start:\n" + log_path.read_text())
        yield base, log_path
    finally:
        process.terminate()
        process.wait(timeout=10)


def test_topojson_served_as_json_from_any_cwd(server):
    base, _ = server
    with urllib.request.urlopen(f"{base}/app/static/topojson/world_110m.json", timeout=5) as response:
        assert response.headers.get_content_type() == "application/json"
        assert response.read(15).startswith(b'{"type":"Topol')


def _non_loopback_ip():
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
            probe.connect(("192.0.2.1", 9))  # TEST-NET-1; UDP connect sends nothing
            address = probe.getsockname()[0]
    except OSError:
        return None
    return None if address.startswith("127.") else address


def test_binds_localhost_only(server):
    base, log_path = server
    port = int(base.rsplit(":", 1)[1])
    assert f"URL: http://127.0.0.1:{port}" in log_path.read_text()
    address = _non_loopback_ip()
    if address is None:
        pytest.skip("no non-loopback interface to probe")
    with pytest.raises(OSError):
        socket.create_connection((address, port), timeout=2).close()


def test_no_telemetry_or_public_ip_lookup_in_log(server):
    _, log_path = server
    log = log_path.read_text()
    assert "Collecting usage statistics" not in log
    assert "External URL" not in log and "Network URL" not in log
