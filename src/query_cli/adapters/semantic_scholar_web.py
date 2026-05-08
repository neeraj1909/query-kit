from __future__ import annotations

import re
from typing import Any
from urllib.parse import quote

import httpx

from query_cli.adapters.http import (
    AsyncProviderHttpClient,
    ProviderHttpClient,
    async_transport_for,
    ensure_success,
    parse_json_response,
)
from query_cli.domain import SearchQuery, SearchResult

SEMANTIC_SCHOLAR_WEB_BASE_URL = "https://www.semanticscholar.org/"
WHITESPACE_RE = re.compile(r"\s+")


class SemanticScholarWebProvider:
    """Public Semantic Scholar web-search provider.

    This provider mirrors the browser-visible public search endpoint used by the
    Semantic Scholar search page. It intentionally uses ordinary HTTP only: no
    cdp/Chrome dependency, no copied cookies, no copied auth headers, and no
    browser fingerprint headers. If Semantic Scholar's WAF challenges direct
    non-browser HTTP, the shared HTTP diagnostics surface that limitation.
    """

    provider_id = "semantic-scholar-web"

    def __init__(
        self,
        *,
        base_url: str = SEMANTIC_SCHOLAR_WEB_BASE_URL,
        timeout: float = 30.0,
        transport: httpx.BaseTransport | None = None,
        async_transport: httpx.AsyncBaseTransport | None = None,
        min_interval: float = 3.0,
        retries: int = 1,
    ) -> None:
        self.http = ProviderHttpClient(
            provider_id=self.provider_id,
            base_url=base_url,
            timeout=timeout,
            transport=transport,
            min_interval=min_interval,
            retries=retries,
            retry_backoff=1.0,
        )
        self.async_http = AsyncProviderHttpClient(
            provider_id=self.provider_id,
            base_url=base_url,
            timeout=timeout,
            transport=async_transport_for(transport, async_transport),
            min_interval=min_interval,
            retries=retries,
            retry_backoff=1.0,
        )

    def search(self, query: SearchQuery) -> list[SearchResult]:
        response = self.http.post(
            "api/1/search",
            json=build_semantic_scholar_web_payload(query),
        )
        ensure_success(response)
        data = parse_json_response(response)
        return parse_semantic_scholar_web_search_json(
            data,
            limit=query.limit,
            since_year=query.since_year,
        )

    async def search_async(self, query: SearchQuery) -> list[SearchResult]:
        response = await self.async_http.post(
            "api/1/search",
            json=build_semantic_scholar_web_payload(query),
        )
        ensure_success(response)
        data = parse_json_response(response)
        return parse_semantic_scholar_web_search_json(
            data,
            limit=query.limit,
            since_year=query.since_year,
        )


def build_semantic_scholar_web_payload(query: SearchQuery) -> dict[str, Any]:
    return {
        "authors": [],
        "coAuthors": [],
        "cues": [
            "CitedByLibraryPaperCue",
            "CitesYourPaperCue",
            "CitesLibraryPaperCue",
        ],
        "fieldsOfStudy": [],
        "getQuerySuggestions": False,
        "hydrateWithDdb": True,
        "includeBadges": True,
        "includePdfVisibility": True,
        "includeTldrs": True,
        "page": 1,
        "pageSize": min(max(query.limit, 1), 100),
        "performTitleMatch": True,
        "queryString": query.text,
        "requireViewablePdf": False,
        "sort": "relevance",
        "venues": [],
        "yearFilter": None,
    }


def parse_semantic_scholar_web_search_json(
    data: Any,
    *,
    limit: int,
    since_year: int | None = None,
) -> list[SearchResult]:
    if not isinstance(data, dict):
        return []
    raw_results = data.get("results")
    if not isinstance(raw_results, list):
        return []

    results: list[SearchResult] = []
    for raw_result in raw_results:
        if not isinstance(raw_result, dict):
            continue
        result = parse_semantic_scholar_web_result(raw_result)
        if result is None:
            continue
        if since_year is not None and result.year is not None and result.year < since_year:
            continue
        results.append(result)
        if len(results) >= limit:
            break
    return results


def parse_semantic_scholar_web_result(result: dict[str, Any]) -> SearchResult | None:
    title = text_value(result.get("title"))
    paper_id = clean_text(str(result.get("id") or ""))
    if not title or not paper_id:
        return None

    year = parse_year(text_value(result.get("year")))
    venue = text_value(result.get("venue")) or None
    abstract = text_value(result.get("paperAbstract"))
    if not abstract:
        abstract = text_value(result.get("tldr"))
    if not abstract:
        abstract = clean_text(str(result.get("paperAbstractTruncated") or ""))

    return SearchResult(
        title=title,
        url=semantic_scholar_paper_url(result, paper_id=paper_id),
        source="Semantic Scholar Web",
        authors=parse_authors(result),
        year=year,
        venue=venue,
        abstract=abstract or None,
    )


def semantic_scholar_paper_url(result: dict[str, Any], *, paper_id: str) -> str:
    slug = clean_text(str(result.get("slug") or ""))
    if slug:
        return f"https://www.semanticscholar.org/paper/{quote(slug, safe='')}/{paper_id}"
    return f"https://www.semanticscholar.org/paper/{paper_id}"


def parse_authors(result: dict[str, Any]) -> tuple[str, ...]:
    names = parse_nested_author_pairs(result.get("authors"))
    if not names:
        names = parse_structured_authors(result.get("structuredAuthors"))
    return tuple(dict.fromkeys(names))


def parse_nested_author_pairs(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    names: list[str] = []
    for author_entry in value:
        candidates = author_entry if isinstance(author_entry, list) else [author_entry]
        name = ""
        for candidate in reversed(candidates):
            if isinstance(candidate, dict):
                name = text_value(candidate) or clean_text(str(candidate.get("name") or ""))
            elif isinstance(candidate, str):
                name = clean_text(candidate)
            if name:
                break
        if name:
            names.append(name)
    return names


def parse_structured_authors(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    names: list[str] = []
    for author in value:
        if not isinstance(author, dict):
            continue
        parts = [
            clean_text(str(author.get("firstName") or "")),
            clean_text(" ".join(str(part) for part in author.get("middleNames") or [])),
            clean_text(str(author.get("lastName") or "")),
        ]
        name = clean_text(" ".join(part for part in parts if part))
        if name:
            names.append(name)
    return names


def text_value(value: Any) -> str:
    if isinstance(value, dict):
        text = value.get("text")
        if isinstance(text, str):
            return clean_text(text)
        name = value.get("name")
        if isinstance(name, str):
            return clean_text(name)
    if isinstance(value, str):
        return clean_text(value)
    return ""


def clean_text(value: str) -> str:
    return WHITESPACE_RE.sub(" ", value).strip()


def parse_year(value: str) -> int | None:
    match = re.search(r"\b(19\d{2}|20\d{2})\b", value)
    return int(match.group(1)) if match else None
