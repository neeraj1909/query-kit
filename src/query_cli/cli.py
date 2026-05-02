from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Callable, Sequence
from typing import TextIO

from .application.services import search_research
from .bootstrap import get_search_providers
from .client import (
    QueryNetworkError,
    QueryResponseError,
    QueryResult,
    QueryServerError,
    submit_query,
)
from .domain import SearchResult
from .domain.errors import SearchError

EXIT_SUCCESS = 0
EXIT_USAGE = 1
EXIT_NETWORK = 2
EXIT_SERVER = 3
EXIT_RESPONSE = 4

ClientCallable = Callable[..., QueryResult]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="query-cli",
        description="Submit queries to a configurable HTTP API.",
        epilog=(
            "examples:\n"
            "  query-cli ask 'hello' --base-url http://localhost:8000\n"
            "  QUERY_CLI_BASE_URL=http://localhost:8000 query-cli ask 'hello'\n"
            "  query-cli ask 'hello' --format json"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    ask = subparsers.add_parser("ask", help="submit a query to a compatible /query API")
    ask.add_argument("query", help="query text to submit")
    ask.add_argument("--base-url", help="API base URL; defaults to QUERY_CLI_BASE_URL")
    ask.add_argument("--api-key", help="bearer token; defaults to QUERY_CLI_API_KEY")
    ask.add_argument(
        "--timeout",
        help="request timeout in seconds; defaults to QUERY_CLI_TIMEOUT or 30",
    )
    ask.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="output format",
    )
    ask.add_argument("--verbose", action="store_true", help="print diagnostic details to stderr")

    search = subparsers.add_parser("search", help="search supported research websites")
    search.add_argument("query", help="research query text")
    search.add_argument(
        "--provider",
        action="append",
        choices=("acl", "arxiv", "all"),
        default=None,
        help="research website provider; repeatable; defaults to acl",
    )
    search.add_argument("--limit", type=int, default=10, help="maximum number of results")
    search.add_argument(
        "--timeout",
        help="request timeout in seconds; defaults to QUERY_CLI_TIMEOUT or 30",
    )
    search.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="output format",
    )
    search.add_argument("--verbose", action="store_true", help="print diagnostic details to stderr")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    return run(argv, stdout=sys.stdout, stderr=sys.stderr)


def run(
    argv: Sequence[str] | None = None,
    *,
    stdout: TextIO,
    stderr: TextIO,
    client: ClientCallable = submit_query,
    environ: dict[str, str] | None = None,
) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    env = os.environ if environ is None else environ

    if args.command == "ask":
        return run_ask(args, stdout=stdout, stderr=stderr, client=client, environ=env)
    if args.command == "search":
        return run_search(args, stdout=stdout, stderr=stderr, environ=env)

    parser.error("unknown command")
    return EXIT_USAGE


def run_ask(
    args: argparse.Namespace,
    *,
    stdout: TextIO,
    stderr: TextIO,
    client: ClientCallable,
    environ: os._Environ[str] | dict[str, str],
) -> int:
    base_url = args.base_url or environ.get("QUERY_CLI_BASE_URL")
    api_key = args.api_key or environ.get("QUERY_CLI_API_KEY")

    if not base_url:
        print("error: --base-url or QUERY_CLI_BASE_URL is required", file=stderr)
        return EXIT_USAGE

    try:
        timeout = resolve_timeout(args.timeout, environ.get("QUERY_CLI_TIMEOUT"))
    except ValueError as exc:
        print(f"error: {exc}", file=stderr)
        return EXIT_USAGE

    if args.verbose:
        print(f"POST {base_url.rstrip('/')}/query", file=stderr)

    try:
        result = client(
            args.query,
            base_url=base_url,
            api_key=api_key,
            timeout=timeout,
        )
    except QueryNetworkError as exc:
        print(f"network error: {exc}", file=stderr)
        return EXIT_NETWORK
    except QueryServerError as exc:
        print(str(exc), file=stderr)
        return EXIT_SERVER
    except QueryResponseError as exc:
        print(f"response error: {exc}", file=stderr)
        return EXIT_RESPONSE

    if args.format == "json":
        print(json.dumps(result.data, ensure_ascii=False), file=stdout)
    else:
        print(result.text, file=stdout)
    return EXIT_SUCCESS


def run_search(
    args: argparse.Namespace,
    *,
    stdout: TextIO,
    stderr: TextIO,
    environ: os._Environ[str] | dict[str, str],
) -> int:
    try:
        timeout = resolve_timeout(args.timeout, environ.get("QUERY_CLI_TIMEOUT"))
        provider_ids = args.provider or ["acl"]
        providers = get_search_providers(provider_ids, timeout=timeout)
        if args.verbose:
            providers_text = ", ".join(provider.provider_id for provider in providers)
            print(f"searching providers: {providers_text}", file=stderr)
        results = search_research(args.query, providers, limit=args.limit)
    except ValueError as exc:
        print(f"error: {exc}", file=stderr)
        return EXIT_USAGE
    except SearchError as exc:
        print(f"search error: {exc}", file=stderr)
        return EXIT_USAGE
    except QueryNetworkError as exc:
        print(f"network error: {exc}", file=stderr)
        return EXIT_NETWORK
    except Exception as exc:
        print(f"search error: {exc}", file=stderr)
        return EXIT_NETWORK

    if args.verbose:
        print(f"results returned: {len(results)}", file=stderr)

    if args.format == "json":
        print(json.dumps([result.to_dict() for result in results], ensure_ascii=False), file=stdout)
    else:
        print(format_search_results(results), file=stdout)
    return EXIT_SUCCESS


def format_search_results(results: list[SearchResult]) -> str:
    if not results:
        return "No results found."
    return "\n\n".join(result.to_text() for result in results)


def resolve_timeout(flag_value: str | None, env_value: str | None) -> float:
    value = flag_value if flag_value is not None else env_value
    if value is None or value == "":
        return 30.0

    try:
        timeout = float(value)
    except ValueError as exc:
        raise ValueError("timeout must be a number") from exc

    if timeout <= 0:
        raise ValueError("timeout must be greater than 0")
    return timeout
