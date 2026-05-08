from __future__ import annotations

import os

import httpx

from query_cli.adapters.http import (
    AsyncProviderHttpClient,
    ProviderHttpClient,
    async_transport_for,
    ensure_success,
    parse_json_response,
)
from query_cli.domain import SearchQuery, SearchResult
from query_cli.domain.errors import ProviderParseError

GRAPH_API_BASE_URL = "https://api.semanticscholar.org/graph/v1/"
SEARCH_FIELDS = "title,authors,year,venue,abstract,url"


class SemanticScholarProvider:
    provider_id = "semantic-scholar"

    def __init__(
        self,
        *,
        base_url: str = GRAPH_API_BASE_URL,
        timeout: float = 30.0,
        transport: httpx.BaseTransport | None = None,
        async_transport: httpx.AsyncBaseTransport | None = None,
        api_key: str | None = None,
        min_interval: float = 1.0,
        retries: int = 2,
    ) -> None:
        self.api_key = (
            api_key
            if api_key is not None
            else os.environ.get("QUERY_CLI_SEMANTIC_SCHOLAR_API_KEY")
        )
        headers = {"x-api-key": self.api_key} if self.api_key else None
        self.http = ProviderHttpClient(
            provider_id=self.provider_id,
            base_url=base_url,
            timeout=timeout,
            transport=transport,
            headers=headers,
            min_interval=min_interval,
            retries=retries,
            retry_backoff=1.0,
        )
        self.async_http = AsyncProviderHttpClient(
            provider_id=self.provider_id,
            base_url=base_url,
            timeout=timeout,
            transport=async_transport_for(transport, async_transport),
            headers=headers,
            min_interval=min_interval,
            retries=retries,
            retry_backoff=1.0,
        )

    def search(self, query: SearchQuery) -> list[SearchResult]:
        response = self.http.get("paper/search", params=build_search_params(query))
        ensure_success(response)
        data = parse_json_response(response)
        return parse_semantic_scholar_results(
            data, limit=query.limit, since_year=query.since_year
        )

    async def search_async(self, query: SearchQuery) -> list[SearchResult]:
        response = await self.async_http.get(
            "paper/search", params=build_search_params(query)
        )
        ensure_success(response)
        data = parse_json_response(response)
        return parse_semantic_scholar_results(
            data, limit=query.limit, since_year=query.since_year
        )


def build_search_params(query: SearchQuery) -> dict[str, str]:
    params = {
        "query": semantic_scholar_query_text(query.text),
        "limit": str(query.limit),
        "fields": SEARCH_FIELDS,
    }
    if query.since_year is not None:
        params["year"] = f"{query.since_year}-"
        params["publicationDateOrYear"] = f"{query.since_year}:"
    return params


def semantic_scholar_query_text(value: str) -> str:
    # Semantic Scholar docs say hyphenated query terms yield no matches.
    return clean_text(value.replace("-", " "))


def parse_semantic_scholar_results(
    data: object,
    *,
    limit: int,
    since_year: int | None = None,
) -> list[SearchResult]:
    if not isinstance(data, dict) or not isinstance(data.get("data"), list):
        raise ProviderParseError("malformed Semantic Scholar search response")

    results: list[SearchResult] = []
    for record in data["data"]:
        if not isinstance(record, dict):
            continue
        title = clean_text(record.get("title"))
        url = clean_text(record.get("url")) or semantic_scholar_url(
            record.get("paperId")
        )
        if not title or not url:
            continue
        year = parse_year(record.get("year"))
        if since_year is not None and year is not None and year < since_year:
            continue
        results.append(
            SearchResult(
                title=title,
                url=url,
                source="Semantic Scholar",
                authors=parse_authors(record.get("authors")),
                year=year,
                venue=clean_text(record.get("venue")) or None,
                abstract=clean_text(record.get("abstract")) or None,
            )
        )
        if len(results) >= limit:
            break
    return results


def parse_authors(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    authors: list[str] = []
    for author in value:
        if isinstance(author, dict):
            name = clean_text(author.get("name"))
            if name:
                authors.append(name)
    return tuple(authors)


def semantic_scholar_url(paper_id: object) -> str:
    paper_id_text = clean_text(paper_id)
    if not paper_id_text:
        return ""
    return f"https://www.semanticscholar.org/paper/{paper_id_text}"


def clean_text(value: object) -> str:
    if value is None:
        return ""
    return " ".join(str(value).split())


def parse_year(value: object) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
