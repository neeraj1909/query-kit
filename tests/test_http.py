import asyncio

import httpx
import pytest

from query_cli.adapters.http import (
    AsyncProviderHttpClient,
    ProviderHttpClient,
    build_headers,
    ensure_success,
    parse_json_response,
    parse_xml_text,
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


def test_provider_http_client_maps_blank_request_errors_with_context():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("", request=request)

    client = ProviderHttpClient(
        provider_id="test-blank-error",
        base_url="https://example.test/",
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(SearchNetworkError) as exc_info:
        client.get("slow")

    message = str(exc_info.value)
    assert "GET https://example.test/slow" in message
    assert "ReadTimeout" in message


def test_async_provider_http_client_gets_and_posts_with_mock_transport():
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append((request.method, str(request.url), request.content))
        return httpx.Response(200, json={"ok": True})

    async def run():
        client = AsyncProviderHttpClient(
            provider_id="test-async-get-post",
            base_url="https://example.test/api/",
            transport=httpx.MockTransport(handler),
        )
        get_response = await client.get("papers", params={"q": "xai"})
        post_response = await client.post("papers", json={"q": "xai"})
        return get_response, post_response

    get_response, post_response = asyncio.run(run())

    assert get_response.json() == {"ok": True}
    assert post_response.json() == {"ok": True}
    assert seen == [
        ("GET", "https://example.test/api/papers?q=xai", b""),
        ("POST", "https://example.test/api/papers", b'{"q":"xai"}'),
    ]


def test_async_provider_http_client_enforces_min_interval_per_host():
    seen = []
    now = [10.0]
    sleeps = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        return httpx.Response(200, json={"ok": True})

    def clock():
        return now[0]

    async def sleeper(seconds):
        sleeps.append(seconds)
        now[0] += seconds

    async def run():
        client = AsyncProviderHttpClient(
            provider_id="test-async-min-interval",
            base_url="https://example.test/",
            transport=httpx.MockTransport(handler),
            min_interval=3.0,
            clock=clock,
            sleeper=sleeper,
        )
        await client.get("one")
        now[0] = 11.0
        await client.get("two")

    asyncio.run(run())

    assert seen == ["https://example.test/one", "https://example.test/two"]
    assert sleeps == [2.0]


def test_async_provider_http_client_retries_retry_after_status():
    statuses = [
        httpx.Response(503, headers={"Retry-After": "1.5"}, json={"ok": False}),
        httpx.Response(200, json={"ok": True}),
    ]
    sleeps = []

    def handler(request: httpx.Request) -> httpx.Response:
        return statuses.pop(0)

    async def sleeper(seconds):
        sleeps.append(seconds)

    async def run():
        client = AsyncProviderHttpClient(
            provider_id="test-async-retry-after",
            base_url="https://example.test/",
            transport=httpx.MockTransport(handler),
            retries=1,
            retry_backoff=0.25,
            sleeper=sleeper,
        )
        return await client.get("retry")

    response = asyncio.run(run())

    assert response.status_code == 200
    assert sleeps == [1.5]


def test_async_provider_http_client_maps_request_errors():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("offline", request=request)

    async def run():
        client = AsyncProviderHttpClient(
            provider_id="test-async-error",
            base_url="https://example.test/",
            transport=httpx.MockTransport(handler),
        )
        await client.get("offline")

    with pytest.raises(SearchNetworkError, match="offline"):
        asyncio.run(run())


def test_async_provider_http_client_maps_blank_request_errors_with_context():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("", request=request)

    async def run():
        client = AsyncProviderHttpClient(
            provider_id="test-async-blank-error",
            base_url="https://example.test/",
            transport=httpx.MockTransport(handler),
        )
        await client.get("slow")

    with pytest.raises(SearchNetworkError) as exc_info:
        asyncio.run(run())

    message = str(exc_info.value)
    assert "GET https://example.test/slow" in message
    assert "ReadTimeout" in message


def test_ensure_success_maps_rate_limit_to_network_error():
    with pytest.raises(SearchNetworkError, match="HTTP 429"):
        ensure_success(httpx.Response(429))


def test_parse_json_response_maps_malformed_json():
    with pytest.raises(ProviderParseError, match="invalid JSON"):
        parse_json_response(httpx.Response(200, text="{"))


def test_parse_xml_text_maps_malformed_xml():
    with pytest.raises(ProviderParseError, match="invalid XML"):
        parse_xml_text("<feed>")
