from __future__ import annotations

from collections.abc import Iterable
from collections.abc import Mapping

from query_cli.application.ports import SearchProviderLike
from query_cli.domain.errors import UnknownProviderError


def get_search_providers(
    provider_ids: Iterable[str],
    *,
    timeout: float,
    environ: Mapping[str, str] | None = None,
) -> list[SearchProviderLike]:
    from query_cli.adapters.acl import AclAnthologyProvider
    from query_cli.adapters.arxiv import ArxivProvider
    from query_cli.adapters.arxiv_web import ArxivWebProvider
    from query_cli.adapters.openreview import OpenReviewProvider
    from query_cli.adapters.pubmed import PubMedProvider
    from query_cli.adapters.semantic_scholar import SemanticScholarProvider
    from query_cli.adapters.semantic_scholar_web import SemanticScholarWebProvider

    def env_value(name: str) -> str | None:
        if environ is None:
            return None
        return environ.get(name, "")

    registry: dict[str, SearchProviderLike] = {
        "acl": AclAnthologyProvider(timeout=timeout),
        "arxiv": ArxivProvider(timeout=timeout),
        "arxiv-web": ArxivWebProvider(timeout=timeout),
        "pubmed": PubMedProvider(
            timeout=timeout,
            api_key=env_value("QUERY_CLI_NCBI_API_KEY"),
            tool=env_value("QUERY_CLI_NCBI_TOOL"),
            email=env_value("QUERY_CLI_NCBI_EMAIL"),
        ),
        "semantic-scholar": SemanticScholarProvider(
            timeout=timeout,
            api_key=env_value("QUERY_CLI_SEMANTIC_SCHOLAR_API_KEY"),
        ),
        "semantic-scholar-web": SemanticScholarWebProvider(timeout=timeout),
        "openreview": OpenReviewProvider(timeout=timeout),
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
            raise UnknownProviderError(
                f"unknown provider '{provider_id}'. Known providers: {known}"
            ) from exc
    return providers
