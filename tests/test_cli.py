from io import StringIO

import pytest

from query_cli.cli import EXIT_NETWORK, EXIT_SUCCESS, EXIT_USAGE, resolve_timeout, run
from query_cli.domain.errors import SearchNetworkError


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


def test_run_search_prints_json(monkeypatch):
    from query_cli.domain import SearchResult

    class FakeProvider:
        provider_id = "acl"

        def search(self, query):
            return [SearchResult(title="Paper title", url="https://example.test/paper", source="ACL Anthology")]

    monkeypatch.setattr("query_cli.cli.get_search_providers", lambda provider_ids, timeout: [FakeProvider()])
    stdout = StringIO()
    stderr = StringIO()
    code = run(
        ["search", "xai driven nlp", "--format", "json"],
        stdout=stdout,
        stderr=stderr,
        environ={},
    )

    assert code == EXIT_SUCCESS
    assert '"title": "Paper title"' in stdout.getvalue()
    assert '"source": "ACL Anthology"' in stdout.getvalue()


def test_run_search_reports_network_errors(monkeypatch):
    class FakeProvider:
        provider_id = "acl"

        def search(self, query):
            raise SearchNetworkError("offline")

    monkeypatch.setattr("query_cli.cli.get_search_providers", lambda provider_ids, timeout: [FakeProvider()])
    stdout = StringIO()
    stderr = StringIO()
    code = run(
        ["search", "xai driven nlp"],
        stdout=stdout,
        stderr=stderr,
        environ={},
    )

    assert code == EXIT_NETWORK
    assert stdout.getvalue() == ""
    assert "network error: acl: offline" in stderr.getvalue()


def test_run_search_verbose_prints_provider_diagnostics(monkeypatch):
    from query_cli.domain import SearchResult

    class FakeProvider:
        provider_id = "acl"

        def search(self, query):
            return [SearchResult(title="Paper title", url="https://example.test/paper", source="ACL Anthology")]

    monkeypatch.setattr("query_cli.cli.get_search_providers", lambda provider_ids, timeout: [FakeProvider()])
    stdout = StringIO()
    stderr = StringIO()
    code = run(
        ["search", "xai driven nlp", "--verbose"],
        stdout=stdout,
        stderr=stderr,
        environ={},
    )

    assert code == EXIT_SUCCESS
    assert "searching providers: acl" in stderr.getvalue()
    assert "results returned: 1" in stderr.getvalue()


def test_resolve_timeout_defaults_and_env():
    assert resolve_timeout(None, None) == 30.0
    assert resolve_timeout(None, "12.5") == 12.5
    assert resolve_timeout("2", "12.5") == 2.0


@pytest.mark.parametrize("value", ["0", "-1"])
def test_resolve_timeout_requires_positive_value(value):
    with pytest.raises(ValueError, match="greater than 0"):
        resolve_timeout(value, None)
