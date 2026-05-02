from io import StringIO

import pytest

from query_cli.cli import EXIT_NETWORK, EXIT_RESPONSE, EXIT_SERVER, EXIT_SUCCESS, EXIT_USAGE, resolve_timeout, run
from query_cli.client import QueryNetworkError, QueryResponseError, QueryResult, QueryServerError, format_server_error


def test_run_ask_uses_env_base_url_and_prints_text():
    calls = []

    def client(query, **kwargs):
        calls.append((query, kwargs))
        return QueryResult(data={"result": "hello back"}, text="hello back")

    stdout = StringIO()
    stderr = StringIO()
    code = run(
        ["ask", "hello"],
        stdout=stdout,
        stderr=stderr,
        client=client,
        environ={"QUERY_CLI_BASE_URL": "https://example.test"},
    )

    assert code == EXIT_SUCCESS
    assert stdout.getvalue() == "hello back\n"
    assert stderr.getvalue() == ""
    assert calls == [
        (
            "hello",
            {"base_url": "https://example.test", "api_key": None, "timeout": 30.0},
        )
    ]


def test_run_ask_flags_override_env():
    def client(query, **kwargs):
        return QueryResult(data={"result": kwargs}, text="ok")

    stdout = StringIO()
    stderr = StringIO()
    code = run(
        [
            "ask",
            "hello",
            "--base-url",
            "https://flag.test",
            "--api-key",
            "flag-token",
            "--timeout",
            "7",
        ],
        stdout=stdout,
        stderr=stderr,
        client=client,
        environ={
            "QUERY_CLI_BASE_URL": "https://env.test",
            "QUERY_CLI_API_KEY": "env-token",
            "QUERY_CLI_TIMEOUT": "3",
        },
    )

    assert code == EXIT_SUCCESS
    assert stdout.getvalue() == "ok\n"


def test_run_ask_prints_json_output():
    def client(query, **kwargs):
        return QueryResult(data={"results": ["one", "two"]}, text="one\ntwo")

    stdout = StringIO()
    stderr = StringIO()
    code = run(
        ["ask", "hello", "--base-url", "https://example.test", "--format", "json"],
        stdout=stdout,
        stderr=stderr,
        client=client,
        environ={},
    )

    assert code == EXIT_SUCCESS
    assert stdout.getvalue() == '{"results": ["one", "two"]}\n'


def test_run_ask_requires_base_url():
    stdout = StringIO()
    stderr = StringIO()
    code = run(["ask", "hello"], stdout=stdout, stderr=stderr, environ={})

    assert code == EXIT_USAGE
    assert stdout.getvalue() == ""
    assert "--base-url or QUERY_CLI_BASE_URL is required" in stderr.getvalue()


def test_run_ask_rejects_invalid_timeout():
    stdout = StringIO()
    stderr = StringIO()
    code = run(
        ["ask", "hello", "--base-url", "https://example.test", "--timeout", "nope"],
        stdout=stdout,
        stderr=stderr,
        environ={},
    )

    assert code == EXIT_USAGE
    assert "timeout must be a number" in stderr.getvalue()


@pytest.mark.parametrize(
    ("error", "expected_code", "expected_stderr"),
    [
        (QueryNetworkError("offline"), EXIT_NETWORK, "network error: offline"),
        (QueryServerError(503, "server busy"), EXIT_SERVER, "server busy"),
        (QueryResponseError("bad response"), EXIT_RESPONSE, "response error: bad response"),
    ],
)
def test_run_ask_maps_client_errors(error, expected_code, expected_stderr):
    def client(query, **kwargs):
        raise error

    stdout = StringIO()
    stderr = StringIO()
    code = run(
        ["ask", "hello", "--base-url", "https://example.test"],
        stdout=stdout,
        stderr=stderr,
        client=client,
        environ={},
    )

    assert code == expected_code
    assert stdout.getvalue() == ""
    assert expected_stderr in stderr.getvalue()


def test_run_verbose_prints_request_diagnostic():
    def client(query, **kwargs):
        return QueryResult(data={"result": "ok"}, text="ok")

    stdout = StringIO()
    stderr = StringIO()
    code = run(
        ["ask", "hello", "--base-url", "https://example.test/api", "--verbose"],
        stdout=stdout,
        stderr=stderr,
        client=client,
        environ={},
    )

    assert code == EXIT_SUCCESS
    assert "POST https://example.test/api/query" in stderr.getvalue()


def test_run_search_defaults_to_acl_and_prints_results(monkeypatch):
    from query_cli.domain import SearchResult

    class FakeProvider:
        provider_id = "acl"

        def search(self, query):
            return [SearchResult(title="Paper title", url="https://example.test/paper", source="ACL Anthology")]

    monkeypatch.setattr("query_cli.cli.get_search_providers", lambda provider_ids, timeout: [FakeProvider()])
    stdout = StringIO()
    stderr = StringIO()
    code = run(
        ["search", "xai driven nlp", "--limit", "1"],
        stdout=stdout,
        stderr=stderr,
        environ={},
    )

    assert code == EXIT_SUCCESS
    assert "Paper title" in stdout.getvalue()
    assert "https://example.test/paper" in stdout.getvalue()


def test_run_search_accepts_repeated_providers(monkeypatch):
    from query_cli.domain import SearchResult

    seen = {}

    class FakeProvider:
        provider_id = "acl"

        def search(self, query):
            return [SearchResult(title="Paper title", url="https://example.test/paper", source="ACL Anthology")]

    def fake_get_search_providers(provider_ids, timeout):
        seen["provider_ids"] = provider_ids
        return [FakeProvider()]

    monkeypatch.setattr("query_cli.cli.get_search_providers", fake_get_search_providers)
    stdout = StringIO()
    stderr = StringIO()
    code = run(
        ["search", "xai driven nlp", "--provider", "acl", "--provider", "arxiv"],
        stdout=stdout,
        stderr=stderr,
        environ={},
    )

    assert code == EXIT_SUCCESS
    assert seen["provider_ids"] == ["acl", "arxiv"]
    assert "Paper title" in stdout.getvalue()


def test_format_server_error_summarizes_acl_html():
    import httpx

    response = httpx.Response(
        404,
        headers={"content-type": "text/html"},
        text="<!doctype html><html><body>not found</body></html>",
        request=httpx.Request("POST", "https://aclanthology.org/query"),
    )

    message = format_server_error(response)

    assert "Server returned HTTP 404 from https://aclanthology.org/query" in message
    assert "query-cli search" in message
    assert "<!doctype html>" not in message


def test_resolve_timeout_defaults_and_env():
    assert resolve_timeout(None, None) == 30.0
    assert resolve_timeout(None, "12.5") == 12.5
    assert resolve_timeout("2", "12.5") == 2.0


@pytest.mark.parametrize("value", ["0", "-1"])
def test_resolve_timeout_requires_positive_value(value):
    with pytest.raises(ValueError, match="greater than 0"):
        resolve_timeout(value, None)
