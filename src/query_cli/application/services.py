from __future__ import annotations

import asyncio
from dataclasses import dataclass
from collections.abc import Sequence

from query_cli.application.ports import SearchProviderLike
from query_cli.domain import SearchQuery, SearchResult
from query_cli.domain.errors import ProviderSearchError, SearchNetworkError


@dataclass(frozen=True)
class _ProviderFailure:
    provider_id: str
    message: str
    network_failure: bool = False


def search_research(
    query_text: str,
    providers: Sequence[SearchProviderLike],
    *,
    limit: int,
    since_year: int | None = None,
    provider_timeout: float | None = None,
) -> list[SearchResult]:
    if _running_event_loop_exists():
        raise RuntimeError(
            "search_research() cannot run inside an active event loop; "
            "use await search_research_async(...) instead"
        )
    return asyncio.run(
        search_research_async(
            query_text,
            providers,
            limit=limit,
            since_year=since_year,
            provider_timeout=provider_timeout,
        )
    )


async def search_research_async(
    query_text: str,
    providers: Sequence[SearchProviderLike],
    *,
    limit: int,
    since_year: int | None = None,
    provider_timeout: float | None = None,
) -> list[SearchResult]:
    query = SearchQuery(text=query_text, since_year=since_year, limit=limit)
    provider_outcomes = await asyncio.gather(
        *(
            _search_provider(provider, query, provider_timeout=provider_timeout)
            for provider in providers
        )
    )

    provider_result_sets: list[list[SearchResult]] = []
    failures: list[str] = []
    network_failure = False
    for outcome in provider_outcomes:
        if isinstance(outcome, _ProviderFailure):
            failures.append(f"{outcome.provider_id}: {outcome.message}")
            network_failure = network_failure or outcome.network_failure
            continue
        provider_result_sets.append(outcome)

    results = merge_provider_results(provider_result_sets, limit=limit)
    if failures and not results:
        raise ProviderSearchError(
            "all", "; ".join(failures), network_failure=network_failure
        )
    return results


async def _search_provider(
    provider: SearchProviderLike,
    query: SearchQuery,
    *,
    provider_timeout: float | None = None,
) -> list[SearchResult] | _ProviderFailure:
    try:
        search_coro = _call_provider(provider, query)
        if provider_timeout is not None:
            return await asyncio.wait_for(search_coro, timeout=provider_timeout)
        return await search_coro
    except TimeoutError:
        return _ProviderFailure(
            provider.provider_id,
            f"timed out after {provider_timeout:g}s",
            network_failure=True,
        )
    except SearchNetworkError as exc:
        return _ProviderFailure(provider.provider_id, str(exc), network_failure=True)
    except Exception as exc:
        return _ProviderFailure(provider.provider_id, str(exc))


async def _call_provider(
    provider: SearchProviderLike, query: SearchQuery
) -> list[SearchResult]:
    search_async = getattr(provider, "search_async", None)
    if callable(search_async):
        return await search_async(query)
    search = getattr(provider, "search")
    return await asyncio.to_thread(search, query)


def _running_event_loop_exists() -> bool:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return False
    return True


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
