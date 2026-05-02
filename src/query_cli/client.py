from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import urljoin

import httpx


class QueryClientError(Exception):
    """Base class for query client failures."""


class QueryNetworkError(QueryClientError):
    pass


class QueryServerError(QueryClientError):
    def __init__(self, status_code: int, message: str, url: str | None = None) -> None:
        self.status_code = status_code
        self.url = url
        super().__init__(message)


class QueryResponseError(QueryClientError):
    pass


@dataclass(frozen=True)
class QueryResult:
    data: dict[str, Any]
    text: str


def submit_query(
    query: str,
    *,
    base_url: str,
    api_key: str | None = None,
    timeout: float = 30.0,
    endpoint_path: str = "/query",
    transport: httpx.BaseTransport | None = None,
) -> QueryResult:
    url = build_url(base_url, endpoint_path)
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    try:
        with httpx.Client(timeout=timeout, transport=transport) as client:
            response = client.post(url, headers=headers, json={"query": query})
    except httpx.RequestError as exc:
        raise QueryNetworkError(str(exc)) from exc

    if response.is_error:
        raise QueryServerError(response.status_code, format_server_error(response), str(response.url))

    try:
        payload = response.json()
    except ValueError as exc:
        raise QueryResponseError("Response was not valid JSON") from exc

    if not isinstance(payload, dict):
        raise QueryResponseError("Response JSON must be an object")

    return normalize_response(payload)


def build_url(base_url: str, endpoint_path: str) -> str:
    return urljoin(base_url.rstrip("/") + "/", endpoint_path.lstrip("/"))


def normalize_response(payload: dict[str, Any]) -> QueryResult:
    if "result" in payload:
        return QueryResult(data=payload, text=format_value(payload["result"]))
    if "answer" in payload:
        return QueryResult(data=payload, text=format_value(payload["answer"]))
    if "results" in payload:
        return QueryResult(data=payload, text=format_value(payload["results"]))
    raise QueryResponseError("Response must contain one of: result, answer, results")


def format_value(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "\n".join(format_value(item) for item in value)
    return str(value)


def format_server_error(response: httpx.Response) -> str:
    content_type = response.headers.get("content-type", "")
    if "html" in content_type.lower() or looks_like_html(response.text):
        message = f"Server returned HTTP {response.status_code} from {response.url}"
        if "aclanthology.org" in str(response.url):
            return (
                f"{message}. This looks like an HTML website, not a compatible /query API. "
                "For ACL Anthology, use: query-cli search \"...\" --provider acl"
            )
        return f"{message}. Response looked like HTML, not the expected JSON API response."

    detail = response.text.strip()
    if detail:
        return f"Server returned HTTP {response.status_code}: {detail[:500]}"
    return f"Server returned HTTP {response.status_code}"


def looks_like_html(text: str) -> bool:
    prefix = text.lstrip()[:100].lower()
    return prefix.startswith("<!doctype html") or prefix.startswith("<html")
