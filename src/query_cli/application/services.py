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
    results: list[SearchResult] = []
    seen: set[tuple[str, str]] = set()

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

        for result in provider_results:
            if result.dedupe_key in seen:
                continue
            seen.add(result.dedupe_key)
            results.append(result)
            if len(results) >= limit:
                return results

    if failures and not results:
        raise ProviderSearchError("all", "; ".join(failures), network_failure=network_failure)
    return results
