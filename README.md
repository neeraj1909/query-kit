# Query CLI

A small, independent Python CLI for submitting queries to any HTTP service that implements a simple `/query` endpoint.

It is provider-agnostic: it does not require a paid API, cloud account, hosted LLM, or project-specific backend. You can use it with any self-hosted, open-source, local, or internal service that accepts the documented request shape.

## Requirements

- Python 3.10 or newer
- [`uv`](https://docs.astral.sh/uv/) for installation as a standalone tool
- An HTTP service that accepts the `/query` contract documented below

## Install

`uv tool install --force .` installs the project from the current directory only. If you do not already have the repository locally, clone it first, then run the install command from inside the checkout.

```bash
git clone git@github.com:neeraj1909/query-kit.git
cd query-kit
uv tool install --force .
```

After installation, confirm the executable is available:

```bash
query-cli --help
```

To reinstall after local changes, run the install command again from the repository root:

```bash
uv tool install --force .
```

## Use

`query-cli` has two modes:

- `ask` sends a query to a compatible JSON API that implements `POST /query`.
- `search` searches supported research websites through provider-specific adapters.

### Generic API queries

Submit a query by passing the service base URL explicitly:

```bash
query-cli ask "hello" --base-url http://localhost:8000
```

Or set the base URL once in your shell:

```bash
export QUERY_CLI_BASE_URL=http://localhost:8000
query-cli ask "hello"
```

Return structured JSON for scripts:

```bash
query-cli ask "hello" --base-url http://localhost:8000 --format json
```

Set a request timeout in seconds:

```bash
query-cli ask "hello" --base-url http://localhost:8000 --timeout 10
```

If your service requires bearer-token authentication, pass an API key:

```bash
query-cli ask "hello" --base-url http://localhost:8000 --api-key "$QUERY_CLI_API_KEY"
```

Or use the environment variable directly:

```bash
export QUERY_CLI_API_KEY=your-token
query-cli ask "hello" --base-url http://localhost:8000
```

Do not pass a normal website URL to `ask` unless that website implements the `/query` JSON API. For example, ACL Anthology should use research search mode instead of `ask --base-url https://aclanthology.org/`.

### Research website search

Search ACL Anthology directly:

```bash
query-cli search "xai driven nlp" --provider acl --limit 5
```

Search arXiv directly:

```bash
query-cli search "explainable NLP" --provider arxiv --limit 5
```

Return normalized JSON results:

```bash
query-cli search "explainable NLP" --provider acl --limit 5 --format json
```

Search more than one provider by repeating `--provider`:

```bash
query-cli search "explainable NLP" --provider acl --provider arxiv --limit 10
```

Search all launch-ready providers:

```bash
query-cli search "explainable NLP" --provider all --limit 10
```

Results are normalized into the same shape across providers, deduplicated by title/link, and limited after merging.

## Supported Providers

| Provider | Status | Notes |
| --- | --- | --- |
| `acl` | Supported | Searches ACL Anthology using its public BibTeX export. Best for NLP and computational linguistics papers. |
| `arxiv` | Supported | Searches the public arXiv Atom API. Best for broad CS, AI, ML, and NLP preprints. |
| `semantic-scholar` | Planned | Good candidate for broad academic metadata, but should remain optional and free/public. |
| `openreview` | Planned | Good candidate for ML conference submissions and reviews. |
| `pubmed` | Planned | Good candidate for biomedical and clinical NLP queries. |

## Provider Notes

- The CLI does not use paid APIs by default.
- Public providers may rate-limit requests or change response formats.
- Live search results can vary because they come from external websites.
- `--timeout` applies per provider request.
- Use `--verbose` to print selected providers and result counts to stderr.

## Configuration

Flags take precedence over environment variables.

| Flag | Environment variable | Description |
| --- | --- | --- |
| `--base-url` | `QUERY_CLI_BASE_URL` | Base URL of the query service. Required by flag or env var. |
| `--api-key` | `QUERY_CLI_API_KEY` | Optional bearer token for authenticated services. |
| `--timeout` | `QUERY_CLI_TIMEOUT` | Optional request timeout in seconds. Defaults to `30`. |
| `--format` | N/A | Output format: `text` or `json`. Defaults to `text`. |
| `--verbose` | N/A | Print request diagnostics to stderr. |

## Adding More Providers

Provider integrations follow a small ports-and-adapters shape:

1. Implement the `SearchProvider` protocol from `src/query_cli/application/ports.py`.
2. Return normalized `SearchResult` objects from `src/query_cli/domain/model.py`.
3. Register the provider in `src/query_cli/bootstrap.py`.
4. Add mocked HTTP adapter tests and CLI/service tests.
5. Document provider limits and examples here.

Keep website-specific HTTP and parsing code inside `src/query_cli/adapters/` so the CLI and service layer stay reusable.

## HTTP Contract

The CLI sends a JSON request:

```http
POST {base_url}/query
Accept: application/json
Content-Type: application/json
```

```json
{"query": "..."}
```

If an API key is configured, the CLI also sends:

```http
Authorization: Bearer <token>
```

The response must be a JSON object containing one of these fields:

```json
{"result": "..."}
{"answer": "..."}
{"results": ["..."]}
```

## Exit Codes

| Code | Meaning |
| --- | --- |
| `0` | Success. |
| `1` | User/configuration error, such as missing `--base-url`. |
| `2` | Network or HTTP transport error. |
| `3` | Server returned an error response. |
| `4` | Response was not valid JSON or did not match the expected shape. |
