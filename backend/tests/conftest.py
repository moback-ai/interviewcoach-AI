import os
import sys
from unittest.mock import patch

import pytest

# Ensure runtime config env fallback is enabled at test collection time
os.environ.setdefault("RUNTIME_CONFIG_ALLOW_ENV", "true")
os.environ.setdefault("DOMAIN", "localhost:5000")

BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)

import common.runtime_config as runtime_config

runtime_config._CONFIG.setdefault("DOMAIN", "localhost:5000")
runtime_config._CONFIG.setdefault(
    "API_FAILURES_LOG_FILE", "/tmp/ic-test-api-failures.log"
)


@pytest.fixture(autouse=True)
def _isolate_app_bootstrap():
    with patch("app._ensure_app_schemas_once"):
        yield
