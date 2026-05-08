import asyncio
import threading

import pytest

from query_cli.application.services import search_research, search_research_async
from query_cli.domain import SearchResult
from query_cli.domain.errors import ProviderSearchError, SearchNetworkError


class FakeProvider:
    def __init__(self, provider_id, results=None, error=None):
        self.provider_id = provider_id
        self.results = results or []
        self.error = error

    def search(self, query):
        if self.error:
            raise self.error
        return self.results


class AsyncFakeProvider:
    def __init__(self, provider_id, results=None, error=None, delay=0.0):
        self.provider_id = provider_id
        self.results = results or []
        self.error = error
        self.delay = delay
        self.seen_query = None

    async def search_async(self, query):
        self.seen_query = query
        if self.delay:
            await asyncio.sleep(self.delay)
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


def test_search_research_async_preserves_provider_order_after_concurrent_search():
    results = asyncio.run(
        search_research_async(
            "xai nlp",
            [
                AsyncFakeProvider(
                    "slow",
                    [
                        SearchResult(
                            title="A1", url="https://example.test/a1", source="A"
                        ),
                        SearchResult(
                            title="A2", url="https://example.test/a2", source="A"
                        ),
                    ],
                    delay=0.02,
                ),
                AsyncFakeProvider(
                    "fast",
                    [
                        SearchResult(
                            title="B1", url="https://example.test/b1", source="B"
                        ),
                    ],
                ),
            ],
            limit=3,
        )
    )

    assert [result.title for result in results] == ["A1", "B1", "A2"]


def test_search_research_async_continues_when_one_provider_fails():
    results = asyncio.run(
        search_research_async(
            "xai nlp",
            [
                AsyncFakeProvider("broken", error=RuntimeError("offline")),
                AsyncFakeProvider(
                    "ok",
                    [
                        SearchResult(
                            title="Paper",
                            url="https://example.test/paper",
                            source="OK",
                        )
                    ],
                ),
            ],
            limit=5,
        )
    )

    assert [result.title for result in results] == ["Paper"]


def test_search_research_async_returns_partial_results_when_provider_times_out():
    results = asyncio.run(
        search_research_async(
            "xai nlp",
            [
                AsyncFakeProvider("slow", delay=0.2),
                AsyncFakeProvider(
                    "ok",
                    [
                        SearchResult(
                            title="Paper",
                            url="https://example.test/paper",
                            source="OK",
                        )
                    ],
                ),
            ],
            limit=5,
            provider_timeout=0.01,
        )
    )

    assert [result.title for result in results] == ["Paper"]


def test_search_research_async_marks_all_provider_timeouts_as_network_failures():
    with pytest.raises(ProviderSearchError) as exc_info:
        asyncio.run(
            search_research_async(
                "xai nlp",
                [AsyncFakeProvider("slow", delay=0.2)],
                limit=5,
                provider_timeout=0.01,
            )
        )

    assert exc_info.value.network_failure is True
    assert "slow: timed out after 0.01s" in str(exc_info.value)


def test_search_research_async_marks_all_network_failures():
    with pytest.raises(ProviderSearchError) as exc_info:
        asyncio.run(
            search_research_async(
                "xai nlp",
                [
                    AsyncFakeProvider(
                        "offline", error=SearchNetworkError("rate limited")
                    )
                ],
                limit=5,
            )
        )

    assert exc_info.value.network_failure is True
    assert "offline: rate limited" in str(exc_info.value)


def test_search_research_async_bridges_sync_only_provider_in_thread():
    main_thread_id = threading.get_ident()
    seen = {}

    class SyncOnlyProvider:
        provider_id = "sync-only"

        def search(self, query):
            seen["query"] = query
            seen["thread_id"] = threading.get_ident()
            return [
                SearchResult(
                    title="Threaded Paper",
                    url="https://example.test/threaded",
                    source="Sync",
                )
            ]

    results = asyncio.run(
        search_research_async("xai nlp", [SyncOnlyProvider()], limit=5)
    )

    assert [result.title for result in results] == ["Threaded Paper"]
    assert seen["query"].text == "xai nlp"
    assert seen["thread_id"] != main_thread_id


def test_search_research_async_propagates_cancellation():
    class CancelledProvider:
        provider_id = "cancelled"

        async def search_async(self, query):
            raise asyncio.CancelledError

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(search_research_async("xai nlp", [CancelledProvider()], limit=5))


def test_search_research_sync_wrapper_rejects_running_event_loop():
    async def call_sync_api_from_loop():
        return search_research("xai nlp", [FakeProvider("ok")], limit=5)

    with pytest.raises(RuntimeError, match="use await search_research_async"):
        asyncio.run(call_sync_api_from_loop())
