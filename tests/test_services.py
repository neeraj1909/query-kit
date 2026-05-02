import pytest

from query_cli.application.services import search_research
from query_cli.domain import SearchResult
from query_cli.domain.errors import ProviderSearchError


class FakeProvider:
    def __init__(self, provider_id, results=None, error=None):
        self.provider_id = provider_id
        self.results = results or []
        self.error = error

    def search(self, query):
        if self.error:
            raise self.error
        return self.results


def test_search_research_deduplicates_and_applies_global_limit():
    duplicate = SearchResult(
        title="Same Paper", url="https://example.test/paper", source="A"
    )
    results = search_research(
        "xai nlp",
        [
            FakeProvider(
                "a",
                [
                    duplicate,
                    SearchResult(
                        title="Second", url="https://example.test/2", source="A"
                    ),
                ],
            ),
            FakeProvider(
                "b",
                [
                    SearchResult(
                        title="Same Paper", url="https://example.test/paper", source="B"
                    )
                ],
            ),
        ],
        limit=2,
    )

    assert [result.title for result in results] == ["Same Paper", "Second"]


def test_search_research_continues_when_one_provider_fails():
    results = search_research(
        "xai nlp",
        [
            FakeProvider("broken", error=RuntimeError("offline")),
            FakeProvider(
                "ok",
                [
                    SearchResult(
                        title="Paper", url="https://example.test/paper", source="OK"
                    )
                ],
            ),
        ],
        limit=5,
    )

    assert [result.title for result in results] == ["Paper"]


def test_search_research_round_robins_provider_results_before_limit():
    results = search_research(
        "xai nlp",
        [
            FakeProvider(
                "a",
                [
                    SearchResult(title="A1", url="https://example.test/a1", source="A"),
                    SearchResult(title="A2", url="https://example.test/a2", source="A"),
                ],
            ),
            FakeProvider(
                "b",
                [
                    SearchResult(title="B1", url="https://example.test/b1", source="B"),
                    SearchResult(title="B2", url="https://example.test/b2", source="B"),
                ],
            ),
        ],
        limit=3,
    )

    assert [result.title for result in results] == ["A1", "B1", "A2"]


def test_search_research_raises_when_all_providers_fail():
    with pytest.raises(ProviderSearchError, match="broken: offline"):
        search_research(
            "xai nlp",
            [FakeProvider("broken", error=RuntimeError("offline"))],
            limit=5,
        )
