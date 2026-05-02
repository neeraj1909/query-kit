from __future__ import annotations

import xml.etree.ElementTree as ET
from collections.abc import Awaitable, Callable

import httpx

from query_cli.adapters.http import (
    AsyncProviderHttpClient,
    ProviderHttpClient,
    async_transport_for,
    ensure_success,
    parse_xml_text,
)
from query_cli.domain import SearchQuery, SearchResult

ATOM_NS = {"atom": "http://www.w3.org/2005/Atom"}


class ArxivProvider:
    provider_id = "arxiv"

    def __init__(
        self,
        *,
        base_url: str = "https://export.arxiv.org/api/query",
        timeout: float = 30.0,
        transport: httpx.BaseTransport | None = None,
        async_transport: httpx.AsyncBaseTransport | None = None,
        min_interval: float = 3.0,
        retries: int = 1,
        clock: Callable[[], float] | None = None,
        sleeper: Callable[[float], None] | None = None,
        async_sleeper: Callable[[float], Awaitable[None]] | None = None,
    ) -> None:
        kwargs = {}
        if clock is not None:
            kwargs["clock"] = clock
        if sleeper is not None:
            kwargs["sleeper"] = sleeper
        self.http = ProviderHttpClient(
            provider_id=self.provider_id,
            base_url=base_url,
            timeout=timeout,
            transport=transport,
            min_interval=min_interval,
            retries=retries,
            retry_backoff=1.0,
            **kwargs,
        )
        async_kwargs = {}
        if clock is not None:
            async_kwargs["clock"] = clock
        if async_sleeper is not None:
            async_kwargs["sleeper"] = async_sleeper
        self.async_http = AsyncProviderHttpClient(
            provider_id=self.provider_id,
            base_url=base_url,
            timeout=timeout,
            transport=async_transport_for(transport, async_transport),
            min_interval=min_interval,
            retries=retries,
            retry_backoff=1.0,
            **async_kwargs,
        )

    def search(self, query: SearchQuery) -> list[SearchResult]:
        params = {
            "search_query": build_arxiv_query(query),
            "start": "0",
            "max_results": str(query.limit),
            "sortBy": "lastUpdatedDate",
            "sortOrder": "descending",
        }
        response = self.http.get("", params=params)
        ensure_success(response)
        return parse_arxiv_feed(response.text, limit=query.limit)

    async def search_async(self, query: SearchQuery) -> list[SearchResult]:
        params = {
            "search_query": build_arxiv_query(query),
            "start": "0",
            "max_results": str(query.limit),
            "sortBy": "lastUpdatedDate",
            "sortOrder": "descending",
        }
        response = await self.async_http.get("", params=params)
        ensure_success(response)
        return parse_arxiv_feed(response.text, limit=query.limit)


def build_arxiv_query(query: SearchQuery) -> str:
    terms = [term for term in query.text.split() if term.strip()]
    search_query = " AND ".join(f"all:{term}" for term in terms)
    if query.since_year is None:
        return search_query
    return f"{search_query} AND submittedDate:[{query.since_year}01010000 TO *]"


def parse_arxiv_feed(xml_text: str, *, limit: int) -> list[SearchResult]:
    root = parse_xml_text(xml_text)
    results = []
    for entry in root.findall("atom:entry", ATOM_NS):
        title = text_of(entry, "atom:title")
        url = text_of(entry, "atom:id")
        if not title or not url:
            continue
        authors = tuple(
            text_of(author, "atom:name")
            for author in entry.findall("atom:author", ATOM_NS)
            if text_of(author, "atom:name")
        )
        published = text_of(entry, "atom:published")
        results.append(
            SearchResult(
                title=" ".join(title.split()),
                url=url.strip(),
                source="arXiv",
                authors=authors,
                year=parse_year(published),
                venue="arXiv",
                abstract=" ".join(text_of(entry, "atom:summary").split()) or None,
            )
        )
        if len(results) >= limit:
            break
    return results


def text_of(element: ET.Element, path: str) -> str:
    child = element.find(path, ATOM_NS)
    if child is None or child.text is None:
        return ""
    return child.text


def parse_year(value: str) -> int | None:
    if len(value) < 4:
        return None
    try:
        return int(value[:4])
    except ValueError:
        return None
