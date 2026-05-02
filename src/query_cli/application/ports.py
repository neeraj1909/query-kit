from __future__ import annotations

from typing import Protocol

from query_cli.domain import SearchQuery, SearchResult


class SearchProvider(Protocol):
    provider_id: str

    def search(self, query: SearchQuery) -> list[SearchResult]: ...
