"""Regression test for the openml-python client-side timeout gap (Phase 6,
see STATUS.md's Notes: a real OpenML outage once left a call hanging
silently for ~53 minutes since neither openml-python nor a bare `requests`
call times out by default, and `socket.setdefaulttimeout()` does not
rescue this). Uses a real hung TCP listener rather than mocking
`requests` internals, so it fails if a future urllib3/requests upgrade
changes how an absent timeout behaves.
"""

import socket
import threading
import time

import pytest
import requests

from caml.benchmarks.openml import install_default_http_timeout


@pytest.fixture(autouse=True)
def _restore_requests_session_request():
    original = requests.Session.request
    yield
    requests.Session.request = original


def _hung_server() -> int:
    """A local TCP server that accepts connections but never responds,
    mirroring the real incident (server accepted the connection, then
    stayed silent for ~53 minutes before eventually returning a 504)."""
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.bind(("127.0.0.1", 0))
    port = srv.getsockname()[1]
    srv.listen(1)

    def accept_and_hang():
        conn, _ = srv.accept()
        time.sleep(30)
        conn.close()

    threading.Thread(target=accept_and_hang, daemon=True).start()
    return port


def test_default_timeout_bounds_a_silently_hung_connection():
    port = _hung_server()
    install_default_http_timeout(seconds=1)

    start = time.monotonic()
    with pytest.raises(requests.exceptions.RequestException):
        requests.get(f"http://127.0.0.1:{port}/")
    elapsed = time.monotonic() - start

    assert elapsed < 10, f"expected the request to fail fast, took {elapsed:.1f}s"


def test_explicit_caller_timeout_is_not_overridden():
    """A caller-supplied timeout must win over the installed default --
    otherwise a legitimately long-running call (e.g. a large dataset
    download) could get cut short by an unrelated default."""
    port = _hung_server()
    install_default_http_timeout(seconds=999)

    start = time.monotonic()
    with pytest.raises(requests.exceptions.RequestException):
        requests.get(f"http://127.0.0.1:{port}/", timeout=1)
    elapsed = time.monotonic() - start

    assert elapsed < 10, f"caller's explicit timeout=1 should have won, took {elapsed:.1f}s"
