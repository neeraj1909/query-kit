from __future__ import annotations

from dataclasses import asdict, dataclass
from urllib.parse import urlsplit, urlunsplit


@dataclass(frozen=True)
class SearchQuery:
    text: str
    since_year: int | None = None
    limit: int = 10

    def __post_init__(self) -> None:
        if not self.text.strip():
            raise ValueError("query text is required")
        if self.limit <= 0:
            raise ValueError("limit must be greater than 0")
        if self.since_year is not None and self.since_year <= 0:
            raise ValueError("since-year must be greater than 0")


@dataclass(frozen=True)
class SearchResult:
    title: str
    url: str
    source: str
    authors: tuple[str, ...] = ()
    year: int | None = None
    venue: str | None = None
    abstract: str | None = None

    def __post_init__(self) -> None:
        if not self.title.strip():
            raise ValueError("result title is required")
        if not self.url.strip():
            raise ValueError("result URL is required")
        if not self.source.strip():
            raise ValueError("result source is required")

    @property
    def dedupe_key(self) -> tuple[str, str]:
        return (normalize_title(self.title), normalize_url(self.url))

    def to_dict(self) -> dict[str, object]:
        return asdict(self)

    def to_text(self) -> str:
        details = []
        if self.year is not None:
            details.append(str(self.year))
        if self.venue:
            details.append(self.venue)
        suffix = f" ({', '.join(details)})" if details else ""
        return f"{self.title}{suffix}\n{self.url}"


def normalize_title(title: str) -> str:
    return " ".join(title.casefold().split())


def normalize_url(url: str) -> str:
    parts = urlsplit(url.strip())
    return urlunsplit(
        (parts.scheme.lower(), parts.netloc.lower(), parts.path.rstrip("/"), "", "")
    )
