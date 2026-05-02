from __future__ import annotations

import os
import time
import xml.etree.ElementTree as ET
from collections.abc import Callable, Collection, Mapping
from typing import Any
from urllib.parse import urljoin, urlsplit

import httpx

from query_cli.domain.errors import ProviderParseError, SearchNetworkError


class ProviderHttpClient:
    _last_request_at: dict[tuple[str, str], float] = {}

    def __init__(
        self,
        *,
        provider_id: str,
        base_url: str = "",
        timeout: float = 30.0,
        transport: httpx.BaseTransport | None = None,
        headers: Mapping[str, str] | None = None,
        min_interval: float = 0.0,
        retries: int = 0,
        retry_statuses: Collection[int] = (429, 500, 502, 503, 504),
        retry_backoff: float = 0.5,
        clock: Callable[[], float] = time.monotonic,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        self.provider_id = provider_id
        self.base_url = base_url
        self.timeout = timeout
        self.transport = transport
        self.headers = build_headers(headers)
        self.min_interval = min_interval
        self.retries = retries
        self.retry_statuses = set(retry_statuses)
        self.retry_backoff = retry_backoff
        self.clock = clock
        self.sleeper = sleeper

    def get(
        self, url: str, *, params: Mapping[str, object] | None = None
    ) -> httpx.Response:
        return self.request("GET", url, params=params)

    def post(
        self, url: str, *, json: Mapping[str, object] | None = None
    ) -> httpx.Response:
        return self.request("POST", url, json=json)

    def request(
        self,
        method: str,
        url: str,
        *,
        params: Mapping[str, object] | None = None,
        json: Mapping[str, object] | None = None,
    ) -> httpx.Response:
        absolute_url = urljoin(self.base_url, url)
        last_error: httpx.RequestError | None = None
        for attempt in range(self.retries + 1):
            self._wait_for_host(absolute_url)
            try:
                with httpx.Client(
                    timeout=self.timeout,
                    transport=self.transport,
                    follow_redirects=True,
                    headers=self.headers,
                ) as client:
                    response = client.request(
                        method, absolute_url, params=params, json=json
                    )
            except httpx.RequestError as exc:
                last_error = exc
                if attempt >= self.retries:
                    raise SearchNetworkError(str(exc)) from exc
                self._sleep_before_retry(None, attempt)
                continue
            if (
                response.status_code not in self.retry_statuses
                or attempt >= self.retries
            ):
                return response
            self._sleep_before_retry(response, attempt)

        if last_error is not None:
            raise SearchNetworkError(str(last_error)) from last_error
        raise SearchNetworkError("request failed")

    def _wait_for_host(self, url: str) -> None:
        if self.min_interval <= 0:
            return
        host = urlsplit(url).netloc
        if not host:
            return
        key = (self.provider_id, host)
        now = self.clock()
        last_request_at = self._last_request_at.get(key)
        if last_request_at is not None:
            wait_seconds = self.min_interval - (now - last_request_at)
            if wait_seconds > 0:
                self.sleeper(wait_seconds)
                now = self.clock()
        self._last_request_at[key] = now

    def _sleep_before_retry(
        self, response: httpx.Response | None, attempt: int
    ) -> None:
        retry_after = (
            parse_retry_after(response.headers.get("Retry-After"))
            if response is not None
            else None
        )
        delay = (
            retry_after
            if retry_after is not None
            else self.retry_backoff * (2**attempt)
        )
        if delay > 0:
            self.sleeper(delay)


def build_headers(headers: Mapping[str, str] | None = None) -> dict[str, str]:
    merged = dict(headers or {})
    user_agent = os.environ.get("QUERY_CLI_USER_AGENT", "").strip()
    if user_agent and not any(name.casefold() == "user-agent" for name in merged):
        merged["User-Agent"] = user_agent
    return merged


def ensure_success(response: httpx.Response) -> None:
    if response.status_code < 400:
        return
    if response.status_code == 429:
        raise SearchNetworkError("rate limited by upstream provider (HTTP 429)")
    raise SearchNetworkError(f"upstream provider returned HTTP {response.status_code}")


def parse_retry_after(value: str | None) -> float | None:
    if value is None:
        return None
    try:
        delay = float(value)
    except ValueError:
        return None
    return max(delay, 0.0)


def parse_json_response(response: httpx.Response) -> Any:
    try:
        return response.json()
    except ValueError as exc:
        raise ProviderParseError("invalid JSON response") from exc


def parse_xml_text(xml_text: str) -> ET.Element:
    try:
        return ET.fromstring(xml_text)
    except ET.ParseError as exc:
        raise ProviderParseError("invalid XML response") from exc
