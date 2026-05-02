from __future__ import annotations

import gzip
import re
from html.parser import HTMLParser
from urllib.parse import urljoin

import httpx

from query_cli.domain import SearchQuery, SearchResult


class AclAnthologyProvider:
    provider_id = "acl"

    def __init__(
        self,
        *,
        base_url: str = "https://aclanthology.org/",
        timeout: float = 30.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.base_url = base_url
        self.timeout = timeout
        self.transport = transport

    def search(self, query: SearchQuery) -> list[SearchResult]:
        try:
            with httpx.Client(timeout=self.timeout, transport=self.transport, follow_redirects=True) as client:
                response = client.get(urljoin(self.base_url, "anthology.bib.gz"))
            response.raise_for_status()
        except httpx.RequestError as exc:
            from query_cli.client import QueryNetworkError

            raise QueryNetworkError(str(exc)) from exc
        return search_acl_bibtex(response.content, query=query, limit=query.limit)


def search_acl_bibtex(content: bytes, *, query: SearchQuery, limit: int) -> list[SearchResult]:
    text = gzip.decompress(content).decode("utf-8", errors="replace")
    terms = [term.casefold() for term in query.text.split() if term.strip()]
    results = []
    for entry in iter_bib_entries(text):
        title = clean_bib_value(entry.get("title", ""))
        abstract = clean_bib_value(entry.get("abstract", ""))
        haystack = f"{title} {abstract}".casefold()
        if terms and not all(term in haystack for term in terms):
            continue
        year = parse_year(clean_bib_value(entry.get("year", "")))
        if query.since_year is not None and year is not None and year < query.since_year:
            continue
        url = clean_bib_value(entry.get("url", ""))
        if not url:
            continue
        authors = tuple(
            author.strip()
            for author in clean_bib_value(entry.get("author", "")).replace("\n", " ").split(" and ")
            if author.strip()
        )
        results.append(
            SearchResult(
                title=title,
                url=url,
                source="ACL Anthology",
                authors=authors,
                year=year,
                venue=clean_bib_value(entry.get("booktitle", "")) or None,
                abstract=abstract or None,
            )
        )
        if len(results) >= limit:
            break
    return results


def iter_bib_entries(text: str):
    for chunk in re.split(r"\n@", text):
        if not chunk.strip() or chunk.lstrip().startswith("%"):
            continue
        body = "@" + chunk if not chunk.startswith("@") else chunk
        yield dict(re.findall(r"\n\s*([A-Za-z]+)\s*=\s*[\{\"](.*?)[\}\"],?\s*(?=\n\s*[A-Za-z]+\s*=|\n\})", body, re.DOTALL))


def clean_bib_value(value: str) -> str:
    value = re.sub(r"[{}]", "", value)
    value = re.sub(r"\\['`\"^~=.]\s*([A-Za-z])", r"\1", value)
    return " ".join(value.split())


def parse_year(value: str) -> int | None:
    try:
        return int(value)
    except ValueError:
        return None


def parse_acl_results(html: str, *, base_url: str, limit: int) -> list[SearchResult]:
    parser = AclSearchParser(base_url=base_url)
    parser.feed(html)
    return parser.results[:limit]


class AclSearchParser(HTMLParser):
    def __init__(self, *, base_url: str) -> None:
        super().__init__()
        self.base_url = base_url
        self.results: list[SearchResult] = []
        self._current_href: str | None = None
        self._current_text: list[str] = []
        self._capture_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if self._current_href is not None:
            self._capture_depth += 1
            return

        if tag != "a":
            return

        attrs_dict = dict(attrs)
        href = attrs_dict.get("href")
        if href and looks_like_paper_href(href):
            self._current_href = href
            self._current_text = []
            self._capture_depth = 1

    def handle_data(self, data: str) -> None:
        if self._current_href is not None:
            self._current_text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if self._current_href is None:
            return

        self._capture_depth -= 1
        if self._capture_depth > 0:
            return

        title = " ".join("".join(self._current_text).split())
        href = self._current_href
        self._current_href = None
        self._current_text = []

        if not title or should_skip_title(title):
            return

        url = urljoin(self.base_url, href)
        result = SearchResult(title=title, url=url, source="ACL Anthology")
        if result.dedupe_key not in {existing.dedupe_key for existing in self.results}:
            self.results.append(result)


def looks_like_paper_href(href: str) -> bool:
    clean = href.strip("/")
    if not clean or "/" in clean:
        return False
    if clean.startswith(("anthology", "events", "volumes", "people", "search", "info", "posts")):
        return False
    return any(char.isdigit() for char in clean) and any(char.isalpha() for char in clean)


def should_skip_title(title: str) -> bool:
    lowered = title.casefold()
    return lowered in {"pdf", "bib", "abs", "doi", "github"} or len(title) < 8
