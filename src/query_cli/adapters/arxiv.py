from __future__ import annotations

import xml.etree.ElementTree as ET

import httpx

from query_cli.domain import SearchQuery, SearchResult
from query_cli.domain.errors import SearchNetworkError

ATOM_NS = {"atom": "http://www.w3.org/2005/Atom"}


class ArxivProvider:
    provider_id = "arxiv"

    def __init__(
        self,
        *,
        base_url: str = "https://export.arxiv.org/api/query",
        timeout: float = 30.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.base_url = base_url
        self.timeout = timeout
        self.transport = transport

    def search(self, query: SearchQuery) -> list[SearchResult]:
        params = {
            "search_query": f"all:{query.text}",
            "start": "0",
            "max_results": str(query.limit),
        }
        try:
            with httpx.Client(timeout=self.timeout, transport=self.transport, follow_redirects=True) as client:
                response = client.get(self.base_url, params=params)
            response.raise_for_status()
        except httpx.RequestError as exc:
            raise SearchNetworkError(str(exc)) from exc
        return parse_arxiv_feed(response.text, limit=query.limit)


def parse_arxiv_feed(xml_text: str, *, limit: int) -> list[SearchResult]:
    root = ET.fromstring(xml_text)
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
