"""Tests for https://www canonical URL enforcement."""
import common.runtime_config as runtime_config

runtime_config._LOADED = True
runtime_config._CONFIG = {
    "DOMAIN": "https://www.ugaanlabs.ai",
    "FRONTEND_DOMAIN": "www.ugaanlabs.ai",
}

from common.canonical_url import (
    apex_host,
    canonical_host,
    canonical_redirect_url,
    effective_request_proto,
    normalize_public_origin,
)


def test_canonical_host_from_frontend_domain():
    assert canonical_host() == "www.ugaanlabs.ai"
    assert apex_host() == "ugaanlabs.ai"


def test_normalize_public_origin():
    assert normalize_public_origin() == "https://www.ugaanlabs.ai"


def test_redirect_apex_to_www_https():
    url = canonical_redirect_url("ugaanlabs.ai", "https", "/signup", b"")
    assert url == "https://www.ugaanlabs.ai/signup"


def test_redirect_http_www_to_https():
    url = canonical_redirect_url("www.ugaanlabs.ai", "http", "/api/health", b"")
    assert url == "https://www.ugaanlabs.ai/api/health"


def test_no_redirect_when_canonical():
    assert canonical_redirect_url("www.ugaanlabs.ai", "https", "/dashboard", b"") is None


def test_skip_alb_health_host():
    assert canonical_redirect_url(
        "interviewcoach-prod-alb-123.ap-south-1.elb.amazonaws.com",
        "http",
        "/api/health",
        b"",
    ) is None


def test_effective_proto_cloudfront_header():
    headers = {"CloudFront-Forwarded-Proto": "https", "X-Forwarded-Proto": "http"}
    assert effective_request_proto(headers, "http") == "https"
    assert canonical_redirect_url("www.ugaanlabs.ai", effective_request_proto(headers, "http"), "/api/health", b"") is None
