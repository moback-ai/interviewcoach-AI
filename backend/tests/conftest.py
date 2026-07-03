import os
import sys
from unittest.mock import patch

import pytest

BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)

import common.runtime_config as runtime_config


@pytest.fixture(autouse=True)
def _isolate_app_bootstrap():
    runtime_config._CONFIG.setdefault(
        "API_FAILURES_LOG_FILE", "/tmp/ic-test-api-failures.log"
    )
    with patch("app._ensure_app_schemas_once"):
        yield
