from __future__ import annotations

from collections.abc import Iterable

from query_cli.application.ports import SearchProvider
from query_cli.domain.errors import UnknownProviderError


def get_search_providers(provider_ids: Iterable[str], *, timeout: float) -> list[SearchProvider]:
    from query_cli.adapters.acl import AclAnthologyProvider
    from query_cli.adapters.arxiv import ArxivProvider

    registry: dict[str, SearchProvider] = {
        "acl": AclAnthologyProvider(timeout=timeout),
        "arxiv": ArxivProvider(timeout=timeout),
    }
    requested = list(provider_ids)
    if "all" in requested:
        requested = list(registry)

    providers = []
    seen = set()
    for provider_id in requested:
        if provider_id in seen:
            continue
        seen.add(provider_id)
        try:
            providers.append(registry[provider_id])
        except KeyError as exc:
            known = ", ".join(sorted([*registry, "all"]))
            raise UnknownProviderError(f"unknown provider '{provider_id}'. Known providers: {known}") from exc
    return providers
