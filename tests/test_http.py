import httpx
import pytest

from query_cli.adapters.http import (
    ProviderHttpClient,
    build_headers,
    ensure_success,
    parse_json_response,
)
from query_cli.domain.errors import ProviderParseError, SearchNetworkError


def test_build_headers_uses_configured_user_agent(monkeypatch):
    monkeypatch.setenv("QUERY_CLI_USER_AGENT", "query-cli-test/1.0")

    assert build_headers() == {"User-Agent": "query-cli-test/1.0"}


def test_build_headers_keeps_provider_user_agent(monkeypatch):
    monkeypatch.setenv("QUERY_CLI_USER_AGENT", "query-cli-test/1.0")

    assert build_headers({"User-Agent": "provider/1.0"}) == {
        "User-Agent": "provider/1.0"
    }


def test_provider_http_client_enforces_min_interval_per_host():
    seen = []
    now = [10.0]
    sleeps = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        return httpx.Response(200, json={"ok": True})

    def clock():
        return now[0]

    def sleeper(seconds):
        sleeps.append(seconds)
        now[0] += seconds

    client = ProviderHttpClient(
        provider_id="test-min-interval",
        base_url="https://example.test/",
        transport=httpx.MockTransport(handler),
        min_interval=3.0,
        clock=clock,
        sleeper=sleeper,
    )

    client.get("one")
    now[0] = 11.0
    client.get("two")

    assert seen == ["https://example.test/one", "https://example.test/two"]
    assert sleeps == [2.0]


def test_provider_http_client_retries_transient_status():
    statuses = [503, 200]
    sleeps = []

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(statuses.pop(0), json={"ok": True})

    client = ProviderHttpClient(
        provider_id="test-retry",
        base_url="https://example.test/",
        transport=httpx.MockTransport(handler),
        retries=1,
        retry_backoff=0.25,
        sleeper=sleeps.append,
    )

    response = client.get("retry")

    assert response.status_code == 200
    assert sleeps == [0.25]


def test_ensure_success_maps_rate_limit_to_network_error():
    with pytest.raises(SearchNetworkError, match="HTTP 429"):
        ensure_success(httpx.Response(429))


def test_parse_json_response_maps_malformed_json():
    with pytest.raises(ProviderParseError, match="invalid JSON"):
        parse_json_response(httpx.Response(200, text="{"))
