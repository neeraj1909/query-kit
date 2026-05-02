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

## Configuration

Flags take precedence over environment variables.

| Flag | Environment variable | Description |
| --- | --- | --- |
| `--base-url` | `QUERY_CLI_BASE_URL` | Base URL of the query service. Required by flag or env var. |
| `--api-key` | `QUERY_CLI_API_KEY` | Optional bearer token for authenticated services. |
| `--timeout` | `QUERY_CLI_TIMEOUT` | Optional request timeout in seconds. Defaults to `30`. |
| `--format` | N/A | Output format: `text` or `json`. Defaults to `text`. |
| `--verbose` | N/A | Print request diagnostics to stderr. |

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
