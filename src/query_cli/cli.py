from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Sequence
from typing import TextIO

from .application.services import search_research
from .bootstrap import get_search_providers
from .domain import SearchResult
from .domain.errors import ProviderSearchError, SearchError, SearchNetworkError

EXIT_SUCCESS = 0
EXIT_USAGE = 1
EXIT_NETWORK = 2
PROVIDER_CHOICES = (
    "acl",
    "arxiv",
    "arxiv-web",
    "pubmed",
    "semantic-scholar",
    "semantic-scholar-web",
    "openreview",
    "all",
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="query-cli",
        description="Search supported research websites from the shell.",
        epilog=(
            "examples:\n"
            "  query-cli search 'xai driven nlp' --provider acl --limit 5\n"
            "  query-cli search 'explainable NLP' --provider arxiv --limit 5\n"
            "  query-cli search 'explainable NLP' --provider all --format json"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    search = subparsers.add_parser("search", help="search supported research websites")
    search.add_argument("query", help="research query text")
    search.add_argument(
        "--provider",
        action="append",
        choices=PROVIDER_CHOICES,
        default=None,
        help="research website provider; repeatable; defaults to acl",
    )
    search.add_argument(
        "--limit", type=int, default=10, help="maximum number of results"
    )
    search.add_argument(
        "--since-year",
        type=int,
        default=None,
        help="only return results from this year or newer",
    )
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
    search.add_argument(
        "--verbose", action="store_true", help="print diagnostic details to stderr"
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    return run(argv, stdout=sys.stdout, stderr=sys.stderr)


def run(
    argv: Sequence[str] | None = None,
    *,
    stdout: TextIO,
    stderr: TextIO,
    environ: dict[str, str] | None = None,
) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    env = os.environ if environ is None else environ

    if args.command == "search":
        return run_search(args, stdout=stdout, stderr=stderr, environ=env)

    parser.error("unknown command")
    return EXIT_USAGE


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
        providers = get_search_providers(provider_ids, timeout=timeout, environ=environ)
        if args.verbose:
            providers_text = ", ".join(provider.provider_id for provider in providers)
            print(f"searching providers: {providers_text}", file=stderr)
        results = search_research(
            args.query,
            providers,
            limit=args.limit,
            since_year=args.since_year,
            provider_timeout=timeout,
        )
    except ValueError as exc:
        print(f"error: {exc}", file=stderr)
        return EXIT_USAGE
    except SearchNetworkError as exc:
        print(f"network error: {exc}", file=stderr)
        return EXIT_NETWORK
    except ProviderSearchError as exc:
        if exc.network_failure:
            print(f"network error: {exc}", file=stderr)
            return EXIT_NETWORK
        print(f"search error: {exc}", file=stderr)
        return EXIT_USAGE
    except SearchError as exc:
        print(f"search error: {exc}", file=stderr)
        return EXIT_USAGE
    except Exception as exc:
        print(f"search error: {exc}", file=stderr)
        return EXIT_NETWORK

    if args.verbose:
        print(f"results returned: {len(results)}", file=stderr)

    if args.format == "json":
        print(
            json.dumps([result.to_dict() for result in results], ensure_ascii=False),
            file=stdout,
        )
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
