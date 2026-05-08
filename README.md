# Query CLI

A small, independent Python CLI for searching public research sources from the shell.

It does not require a paid API, cloud account, hosted LLM, or project-specific backend. The CLI uses provider-specific adapters for supported research websites and normalizes results into a consistent text or JSON format.

## Requirements

- Python 3.10 or newer
- [`uv`](https://docs.astral.sh/uv/) for installation as a standalone tool

## Install From PyPI

After the package is published to PyPI, install the command-line tool with:

```bash
uv tool install query-kit
```

Confirm the executable is available:

```bash
query-cli --help
```

Use it as a Python library in another project with:

```bash
uv add query-kit
```

The PyPI distribution is named `query-kit`; the import package remains
`query_cli`, and the console command remains `query-cli`.

## Install From A Local Checkout

`uv tool install --force .` installs the project from the current directory only. If you do not already have the repository locally, clone it first, then run the install command from inside the checkout.

```bash
git clone git@github.com:neeraj1909/query-kit.git
cd query-kit
uv tool install --force .
```

`uv` does not have a `uv tool reinstall` command. To refresh an existing local install after pulling changes, run the same install command again from the repository root:

```bash
uv tool install --force .
```

After installation, confirm the executable is available:

```bash
query-cli --help
```

## Use

Search ACL Anthology directly:

```bash
query-cli search "xai driven nlp" --provider acl --limit 5
```

Search arXiv Atom API directly:

```bash
query-cli search "explainable NLP" --provider arxiv --limit 5
```

Search arXiv's public web search page when the Atom API is unavailable or rate-limited:

```bash
query-cli search "Devanagari OCR" --provider arxiv-web --limit 5
```

Search PubMed directly:

```bash
query-cli search "explainable NLP" --provider pubmed --limit 5
```

Search Semantic Scholar directly:

```bash
query-cli search "explainable NLP" --provider semantic-scholar --limit 5
```

Search OpenReview directly:

```bash
query-cli search "explainable NLP" --provider openreview --limit 5
```

Search more than one provider by repeating `--provider`:

```bash
query-cli search "explainable NLP" --provider acl --provider arxiv --provider pubmed --limit 10
```

Search all launch-ready providers:

```bash
query-cli search "explainable NLP" --provider all --limit 10
```

Filter by publication year when the provider supports it:

```bash
query-cli search "explainable NLP" --provider all --since-year 2024 --limit 10
```

Return normalized JSON results:

```bash
query-cli search "explainable NLP" --provider acl --limit 5 --format json
```

The earlier ACL Anthology query should be run with `search`:

```bash
query-cli search "list down xai driven nlp research papers in last 1 year" --provider acl --limit 5
```

Results are normalized into the same shape across providers, deduplicated by title/link, and limited after merging.

## Python API

Synchronous Python callers can use the same service that powers the CLI:

```python
from query_cli.application.services import search_research
from query_cli.bootstrap import get_search_providers

providers = get_search_providers(["arxiv", "pubmed"], timeout=30)
results = search_research("explainable nlp", providers, limit=10)
```

Async applications should use the native async service instead of calling the sync
wrapper inside an existing event loop:

```python
from query_cli.application.services import search_research_async
from query_cli.bootstrap import get_search_providers

providers = get_search_providers(["arxiv", "pubmed"], timeout=30)
results = await search_research_async("explainable nlp", providers, limit=10)
```

Built-in providers expose both `search(...)` and `search_async(...)`. The async
service calls provider `search_async(...)` methods concurrently and falls back to
running sync-only third-party providers in a worker thread.

## Search Workflow

When you run:

```bash
query-cli search "<keyword>" --provider <provider-name>
```

The CLI passes through these phases:

1. **Parse command**: `argparse` reads the query text, provider names, limit, timeout, format, and verbose flag.
2. **Resolve configuration**: the CLI resolves `--timeout` or `QUERY_CLI_TIMEOUT`, then defaults to `30` seconds if neither is set.
3. **Select providers**: `src/query_cli/bootstrap.py` maps provider names such as `acl`, `arxiv`, `pubmed`, `semantic-scholar`, `openreview`, or `all` to concrete provider adapters.
4. **Build domain query**: the application service creates a `SearchQuery` with the keyword text, optional `--since-year`, and result limit, then validates that the query is not empty and the limit is positive.
5. **Call provider adapters**: each selected adapter performs provider-specific HTTP and parsing work. The sync CLI enters one service-level event loop, then the service runs async-capable providers concurrently while preserving provider order for merging:
   - `acl` downloads ACL Anthology's public BibTeX export with abstracts and matches query terms against paper metadata.
   - `arxiv` calls the public arXiv Atom API and parses the XML feed.
   - `arxiv-web` calls arXiv's public HTML search page with ordinary HTTP and parses visible result metadata/full abstracts where the page provides them.
   - `pubmed` calls NCBI E-utilities ESearch and EFetch for PubMed records.
   - `semantic-scholar` calls the Semantic Scholar Graph API paper search endpoint.
   - `openreview` calls the OpenReview API 2 notes search endpoint.
6. **Normalize results**: provider-specific records are converted into shared `SearchResult` objects with fields such as title, URL, source, authors, year, venue, and abstract.
7. **Merge and deduplicate**: the service merges results from all selected providers, deduplicates by normalized title/link, and applies the global `--limit`.
8. **Format output**: the CLI prints readable text by default, or normalized JSON when `--format json` is passed.

Provider failures are isolated. If one provider fails but another returns results, the CLI still prints the successful results; if all selected providers fail, it returns a clear error.

## Supported Providers

| Provider | Status | Notes |
| --- | --- | --- |
| `acl` | Supported | Searches ACL Anthology using its public BibTeX export, preferring the abstracts export and falling back to the plain BibTeX export. Best for NLP and computational linguistics papers. |
| `arxiv` | Supported | Searches the public arXiv Atom API, sorted by last updated date. Best for broad CS, AI, ML, and NLP preprints. |
| `arxiv-web` | Supported | Browser-as-API style provider over arXiv's public HTML search page using normal HTTP. Useful fallback when the Atom API is rate-limited; preserves full public abstracts present in the page. |
| `pubmed` | Supported | Searches PubMed through NCBI E-utilities. Best for biomedical and clinical NLP queries. |
| `semantic-scholar` | Supported | Searches Semantic Scholar's official Graph API. Best for broad academic metadata. |
| `openreview` | Supported | Searches public OpenReview API 2 notes. Best for ML conference and workshop submissions visible through public search. |

## Provider Notes

- The CLI does not use paid APIs by default.
- Public providers may rate-limit requests or change response formats.
- Live search results can vary because they come from external websites.
- `--timeout` applies per provider request.
- Use `--verbose` to print selected providers and result counts to stderr.
- `arxiv` and `arxiv-web` enforce a 3-second minimum interval between repeated arXiv requests in the same process.
- `arxiv-web` is the safe browser-as-API pattern: ordinary HTTP over a public search page, no cdp/Chrome dependency, no copied cookies, and no forged browser headers. Set `QUERY_CLI_USER_AGENT` to your project-specific User-Agent if needed.
- `pubmed` enforces NCBI's default 3 requests/second limit without an API key and 10 requests/second with an API key.
- NCBI asks software developers to register a tool name and email with NCBI; passing `QUERY_CLI_NCBI_TOOL` and `QUERY_CLI_NCBI_EMAIL` is not a substitute for registration.
- `semantic-scholar` may return HTTP 429 without an API key. Set `QUERY_CLI_SEMANTIC_SCHOLAR_API_KEY` if you have one. Error messages include safe upstream diagnostics such as JSON `message`/`code`, `Retry-After`, `x-amzn-errortype`, or `x-amzn-waf-action` when present.
- `semantic-scholar` queries replace hyphens with spaces before calling the Graph API because the official docs say hyphenated query terms yield no matches.
- Browser-observed Semantic Scholar web XHRs are not used as a runtime fallback when they require browser state or WAF challenge handling. Query-kit does not depend on Chrome, cdp, copied cookies, or spoofed browser headers.
- `openreview` uses API 2 public search. Older API 1 venue-specific retrieval is not implemented in this generic search adapter.
- The HTTP client only sends a custom User-Agent when `QUERY_CLI_USER_AGENT` is set.

## Configuration

Flags take precedence over environment variables.

| Flag | Environment variable | Description |
| --- | --- | --- |
| `--timeout` | `QUERY_CLI_TIMEOUT` | Optional request timeout in seconds. Defaults to `30`. |
| `--since-year` | N/A | Optional publication-year lower bound. Providers apply it through source-specific filters or post-filtering when year metadata is available. |
| `--format` | N/A | Output format: `text` or `json`. Defaults to `text`. |
| `--verbose` | N/A | Print request diagnostics to stderr. |
| N/A | `QUERY_CLI_USER_AGENT` | Optional User-Agent value sent with provider HTTP requests. |
| N/A | `QUERY_CLI_NCBI_API_KEY` | Optional NCBI API key for PubMed E-utilities. Raises the default NCBI limit from 3 requests/second to 10 requests/second. |
| N/A | `QUERY_CLI_NCBI_TOOL` | Optional NCBI tool parameter. Register this value with NCBI for production use. |
| N/A | `QUERY_CLI_NCBI_EMAIL` | Optional NCBI email parameter. Register this value with NCBI for production use. |
| N/A | `QUERY_CLI_SEMANTIC_SCHOLAR_API_KEY` | Optional Semantic Scholar API key. |

## Live Smoke Checks

Normal tests use mocked HTTP responses. After installing the CLI, you can run live smoke checks manually:

```bash
query-cli search "explainable nlp" --provider arxiv --limit 2 --format json
query-cli search "Devanagari OCR" --provider arxiv-web --limit 2 --format json
query-cli search "explainable nlp" --provider pubmed --limit 2 --format json
query-cli search "explainable nlp" --provider semantic-scholar --limit 2 --format json
query-cli search "explainable nlp" --provider openreview --limit 2 --format json
query-cli search "explainable nlp" --provider all --limit 10 --format json
```

## Adding More Providers

Provider integrations follow a small ports-and-adapters shape:

1. Implement the `SearchProvider` protocol from `src/query_cli/application/ports.py`.
2. Implement `AsyncSearchProvider.search_async(...)` for providers that perform network I/O. Sync-only providers still work through the service compatibility bridge, but native async implementations avoid blocking event-loop-owned applications.
3. Return normalized `SearchResult` objects from `src/query_cli/domain/model.py`.
4. Register the provider in `src/query_cli/bootstrap.py`.
5. Add mocked HTTP adapter tests for both `search(...)` and `search_async(...)`, plus CLI/service tests.
6. Document provider limits and examples here.

Keep website-specific HTTP and parsing code inside `src/query_cli/adapters/` so the CLI and service layer stay reusable.

## Troubleshooting

### `uv tool reinstall` fails

`uv tool reinstall --force .` is not a valid `uv` command. Use this instead from the repository root:

```bash
uv tool install --force .
```

### `query-cli search` is not available after install

If `query-cli --help` only shows `{ask}`, the installed executable is stale. Pull the latest code and reinstall from the repository root:

```bash
git pull
uv tool install --force .
query-cli --help
```

The help output should include the `search` command.

### `query-cli --help` still shows stale commands after reinstall

If `uv tool install --force .` reports success but `query-cli --help` still shows
old commands, force uv to refresh its cached build:

```bash
uv tool install --force --reinstall --refresh .
query-cli --help
```

## Exit Codes

| Code | Meaning |
| --- | --- |
| `0` | Success. |
| `1` | User/configuration error, such as an invalid provider or limit. |
| `2` | Network or provider request error. |
