from __future__ import annotations

import re
from html import unescape
from urllib.parse import urljoin

import httpx

from query_cli.adapters.http import (
    AsyncProviderHttpClient,
    ProviderHttpClient,
    async_transport_for,
    ensure_success,
)
from query_cli.domain import SearchQuery, SearchResult

ARXIV_WEB_BASE_URL = "https://arxiv.org/search/"
RESULT_SPLIT_RE = re.compile(r'<li\s+class=["\']arxiv-result["\'][^>]*>', re.I)
TAG_RE = re.compile(r"<[^>]+>")
WHITESPACE_RE = re.compile(r"\s+")


class ArxivWebProvider:
    provider_id = "arxiv-web"

    def __init__(
        self,
        *,
        base_url: str = ARXIV_WEB_BASE_URL,
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
        response = self.http.get("", params=build_arxiv_web_params(query))
        ensure_success(response)
        return parse_arxiv_search_html(
            response.text, limit=query.limit, since_year=query.since_year
        )

    async def search_async(self, query: SearchQuery) -> list[SearchResult]:
        response = await self.async_http.get("", params=build_arxiv_web_params(query))
        ensure_success(response)
        return parse_arxiv_search_html(
            response.text, limit=query.limit, since_year=query.since_year
        )


def build_arxiv_web_params(query: SearchQuery) -> dict[str, str]:
    return {
        "query": query.text,
        "searchtype": "all",
        "source": "header",
        "abstracts": "show",
        "size": str(max(50, min(query.limit, 200))),
    }


def parse_arxiv_search_html(
    html_text: str, *, limit: int, since_year: int | None = None
) -> list[SearchResult]:
    results: list[SearchResult] = []
    for chunk in RESULT_SPLIT_RE.split(html_text)[1:]:
        result_html = chunk.split("</li>", 1)[0]
        result = parse_arxiv_result_html(result_html)
        if result is None:
            continue
        if since_year is not None and result.year is not None and result.year < since_year:
            continue
        results.append(result)
        if len(results) >= limit:
            break
    return results


def parse_arxiv_result_html(result_html: str) -> SearchResult | None:
    url = first_match(
        r'<p[^>]*class=["\'][^"\']*list-title[^"\']*["\'][^>]*>.*?'
        r'<a\s+href=["\']([^"\']+/abs/[^"\']+)["\']',
        result_html,
    )
    title = text_from_first_match(
        r'<p[^>]*class=["\'][^"\']*(?<![\\w-])title(?![\\w-])[^"\']*["\'][^>]*>(.*?)</p>',
        result_html,
    )
    if not title or not url:
        return None

    authors = parse_authors(
        first_match(
            r'<p[^>]*class=["\'][^"\']*authors[^"\']*["\'][^>]*>(.*?)</p>',
            result_html,
        )
    )
    abstract = parse_abstract(result_html)
    year = parse_year(
        text_from_first_match(
            r'<p[^>]*class=["\'][^"\']*is-size-7[^"\']*["\'][^>]*>(.*?)</p>',
            result_html,
        )
    )
    return SearchResult(
        title=title,
        url=urljoin("https://arxiv.org", url),
        source="arXiv Web",
        authors=authors,
        year=year,
        venue="arXiv",
        abstract=abstract or None,
    )


def parse_authors(authors_html: str) -> tuple[str, ...]:
    authors_text = html_to_text(authors_html)
    authors_text = re.sub(r"^Authors:\s*", "", authors_text)
    authors = [author.strip() for author in authors_text.split(",")]
    return tuple(author for author in authors if author)


def parse_abstract(result_html: str) -> str:
    full_html = first_match(
        r'<span[^>]*class=["\'][^"\']*abstract-full[^"\']*["\'][^>]*>(.*?)'
        r'<a\s+class=["\']is-size-7["\']',
        result_html,
    )
    if full_html:
        return clean_abstract_text(html_to_text(full_html))

    short_html = first_match(
        r'<span[^>]*class=["\'][^"\']*abstract-short[^"\']*["\'][^>]*>(.*?)'
        r'<a\s+class=["\']is-size-7["\']',
        result_html,
    )
    if short_html:
        return clean_abstract_text(html_to_text(short_html))

    abstract_html = first_match(
        r'<p[^>]*class=["\'][^"\']*abstract[^"\']*["\'][^>]*>(.*?)</p>',
        result_html,
    )
    return clean_abstract_text(html_to_text(abstract_html))


def clean_abstract_text(value: str) -> str:
    value = re.sub(r"^Abstract\s*:\s*", "", value)
    value = value.replace("▽ More", "").replace("△ Less", "")
    value = value.replace("More", "").replace("Less", "")
    return clean_text(value)


def text_from_first_match(pattern: str, value: str) -> str:
    return html_to_text(first_match(pattern, value))


def first_match(pattern: str, value: str) -> str:
    match = re.search(pattern, value, flags=re.I | re.S)
    return match.group(1) if match else ""


def html_to_text(value: str) -> str:
    if not value:
        return ""
    text = TAG_RE.sub(" ", value)
    return clean_text(unescape(text))


def clean_text(value: str) -> str:
    return WHITESPACE_RE.sub(" ", value).strip()


def parse_year(value: str) -> int | None:
    submitted = re.search(r"Submitted\s+\d{1,2}\s+\w+,\s+(\d{4})", value)
    if submitted:
        return int(submitted.group(1))
    year = re.search(r"\b(19\d{2}|20\d{2})\b", value)
    return int(year.group(1)) if year else None
