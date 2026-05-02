from __future__ import annotations

import re
from datetime import datetime, timezone

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

OPENREVIEW_API_BASE_URL = "https://api2.openreview.net/"


class OpenReviewProvider:
    provider_id = "openreview"

    def __init__(
        self,
        *,
        base_url: str = OPENREVIEW_API_BASE_URL,
        timeout: float = 30.0,
        transport: httpx.BaseTransport | None = None,
        async_transport: httpx.AsyncBaseTransport | None = None,
        min_interval: float = 1.0,
        retries: int = 1,
    ) -> None:
        self.http = ProviderHttpClient(
            provider_id=self.provider_id,
            base_url=base_url,
            timeout=timeout,
            transport=transport,
            min_interval=min_interval,
            retries=retries,
        )
        self.async_http = AsyncProviderHttpClient(
            provider_id=self.provider_id,
            base_url=base_url,
            timeout=timeout,
            transport=async_transport_for(transport, async_transport),
            min_interval=min_interval,
            retries=retries,
        )

    def search(self, query: SearchQuery) -> list[SearchResult]:
        response = self.http.get(
            "notes/search",
            params={
                "term": query.text,
                "limit": str(query.limit),
            },
        )
        ensure_success(response)
        data = parse_json_response(response)
        return parse_openreview_notes(
            data, limit=query.limit, since_year=query.since_year
        )

    async def search_async(self, query: SearchQuery) -> list[SearchResult]:
        response = await self.async_http.get(
            "notes/search",
            params={
                "term": query.text,
                "limit": str(query.limit),
            },
        )
        ensure_success(response)
        data = parse_json_response(response)
        return parse_openreview_notes(
            data, limit=query.limit, since_year=query.since_year
        )


def parse_openreview_notes(
    data: object,
    *,
    limit: int,
    since_year: int | None = None,
) -> list[SearchResult]:
    if not isinstance(data, dict) or not isinstance(data.get("notes"), list):
        raise ProviderParseError("malformed OpenReview notes response")

    results: list[SearchResult] = []
    for note in data["notes"]:
        if not isinstance(note, dict):
            continue
        content = note.get("content")
        if not isinstance(content, dict):
            continue
        title = clean_text(content_value(content, "title"))
        note_id = clean_text(note.get("forum")) or clean_text(note.get("id"))
        if not title or not note_id:
            continue
        year = parse_openreview_year(note, content)
        if since_year is not None and year is not None and year < since_year:
            continue
        results.append(
            SearchResult(
                title=title,
                url=f"https://openreview.net/forum?id={note_id}",
                source="OpenReview",
                authors=parse_authors(content_value(content, "authors")),
                year=year,
                venue=clean_text(content_value(content, "venue"))
                or clean_text(content_value(content, "venueid"))
                or None,
                abstract=clean_text(content_value(content, "abstract"))
                or clean_text(content_value(content, "TLDR"))
                or None,
            )
        )
        if len(results) >= limit:
            break
    return results


def content_value(content: dict[str, object], key: str) -> object:
    value = content.get(key)
    if isinstance(value, dict) and "value" in value:
        return value["value"]
    return value


def parse_authors(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(cleaned for author in value if (cleaned := clean_text(author)))


def parse_openreview_year(
    note: dict[str, object], content: dict[str, object]
) -> int | None:
    year = parse_year(content_value(content, "year"))
    if year is not None:
        return year
    for key in ("venue", "venueid", "_bibtex"):
        year = parse_year_from_text(clean_text(content_value(content, key)))
        if year is not None:
            return year
    for key in ("pdate", "tmdate", "cdate"):
        year = parse_epoch_millis_year(note.get(key))
        if year is not None:
            return year
    return None


def parse_epoch_millis_year(value: object) -> int | None:
    try:
        timestamp_ms = int(value)
    except (TypeError, ValueError):
        return None
    if timestamp_ms <= 0:
        return None
    return datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc).year


def parse_year_from_text(value: str) -> int | None:
    match = re.search(r"\b(19\d{2}|20\d{2})\b", value)
    if not match:
        return None
    return int(match.group(1))


def clean_text(value: object) -> str:
    if value is None:
        return ""
    return " ".join(str(value).split())


def parse_year(value: object) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
