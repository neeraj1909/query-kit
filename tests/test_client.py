import httpx
import pytest

from query_cli.client import (
    QueryNetworkError,
    QueryResponseError,
    QueryServerError,
    build_url,
    submit_query,
)


def test_build_url_handles_slashes():
    assert build_url("https://example.test/api/", "/query") == "https://example.test/api/query"


def test_submit_query_sends_expected_request():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["method"] = request.method
        seen["url"] = str(request.url)
        seen["auth"] = request.headers.get("Authorization")
        seen["accept"] = request.headers.get("Accept")
        seen["payload"] = request.content
        return httpx.Response(200, json={"result": "ok"})

    result = submit_query(
        "hello",
        base_url="https://example.test/api",
        api_key="secret",
        timeout=5,
        transport=httpx.MockTransport(handler),
    )

    assert result.text == "ok"
    assert result.data == {"result": "ok"}
    assert seen == {
        "method": "POST",
        "url": "https://example.test/api/query",
        "auth": "Bearer secret",
        "accept": "application/json",
        "payload": b'{"query":"hello"}',
    }


def test_submit_query_omits_auth_header_without_api_key():
    def handler(request: httpx.Request) -> httpx.Response:
        assert "Authorization" not in request.headers
        return httpx.Response(200, json={"answer": "ok"})

    result = submit_query(
        "hello",
        base_url="https://example.test",
        transport=httpx.MockTransport(handler),
    )

    assert result.text == "ok"


def test_submit_query_formats_results_list():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"results": ["one", "two"]})

    result = submit_query(
        "hello",
        base_url="https://example.test",
        transport=httpx.MockTransport(handler),
    )

    assert result.text == "one\ntwo"


def test_submit_query_maps_network_errors():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("no route", request=request)

    with pytest.raises(QueryNetworkError, match="no route"):
        submit_query(
            "hello",
            base_url="https://example.test",
            transport=httpx.MockTransport(handler),
        )


def test_submit_query_maps_server_errors():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="boom")

    with pytest.raises(QueryServerError, match="HTTP 500: boom") as exc_info:
        submit_query(
            "hello",
            base_url="https://example.test",
            transport=httpx.MockTransport(handler),
        )

    assert exc_info.value.status_code == 500


def test_submit_query_rejects_invalid_json():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="not json")

    with pytest.raises(QueryResponseError, match="not valid JSON"):
        submit_query(
            "hello",
            base_url="https://example.test",
            transport=httpx.MockTransport(handler),
        )


def test_submit_query_rejects_unexpected_response_shape():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"message": "ok"})

    with pytest.raises(QueryResponseError, match="result, answer, results"):
        submit_query(
            "hello",
            base_url="https://example.test",
            transport=httpx.MockTransport(handler),
        )
