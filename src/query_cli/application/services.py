from __future__ import annotations

from collections.abc import Sequence

from query_cli.application.ports import SearchProvider
from query_cli.domain import SearchQuery, SearchResult
from query_cli.domain.errors import ProviderSearchError, SearchNetworkError


def search_research(
    query_text: str,
    providers: Sequence[SearchProvider],
    *,
    limit: int,
    since_year: int | None = None,
) -> list[SearchResult]:
    query = SearchQuery(text=query_text, since_year=since_year, limit=limit)
    provider_result_sets: list[list[SearchResult]] = []

    failures: list[str] = []
    network_failure = False
    for provider in providers:
        try:
            provider_results = provider.search(query)
        except SearchNetworkError as exc:
            failures.append(f"{provider.provider_id}: {exc}")
            network_failure = True
            continue
        except Exception as exc:
            failures.append(f"{provider.provider_id}: {exc}")
            continue

        provider_result_sets.append(provider_results)

    results = merge_provider_results(provider_result_sets, limit=limit)
    if failures and not results:
        raise ProviderSearchError(
            "all", "; ".join(failures), network_failure=network_failure
        )
    return results


def merge_provider_results(
    provider_result_sets: Sequence[Sequence[SearchResult]], *, limit: int
) -> list[SearchResult]:
    results: list[SearchResult] = []
    seen: set[tuple[str, str]] = set()
    max_results = max(
        (len(provider_results) for provider_results in provider_result_sets), default=0
    )
    for index in range(max_results):
        for provider_results in provider_result_sets:
            if index >= len(provider_results):
                continue
            result = provider_results[index]
            if result.dedupe_key in seen:
                continue
            seen.add(result.dedupe_key)
            results.append(result)
            if len(results) >= limit:
                return results
    return results
