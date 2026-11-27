import os

import pytest

from provider_api.server import FAULTS, start_server


@pytest.fixture(scope="session", autouse=True)
def provider_api():
    server, url = start_server()
    os.environ["PROVIDER_API_URL"] = url
    yield url
    server.shutdown()


@pytest.fixture(autouse=True)
def clean_state(tmp_path, monkeypatch):
    FAULTS.reset()
    monkeypatch.chdir(tmp_path)   # tools write data/ and reports/ relative to cwd
