from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Callable, Sequence
from typing import TextIO

from .client import (
    QueryNetworkError,
    QueryResponseError,
    QueryResult,
    QueryServerError,
    submit_query,
)

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

    ask = subparsers.add_parser("ask", help="submit a query")
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
