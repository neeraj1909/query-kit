# Query CLI

A small, independent Python CLI for submitting queries to any HTTP service that implements a simple `/query` endpoint.

It is provider-agnostic: it does not require a paid API, cloud account, hosted LLM, or project-specific backend. You can use it with any self-hosted, open-source, local, or internal service that accepts the documented request shape.

## Install

```bash
uv tool install --force .
```

## Usage

```bash
query-cli --help
query-cli ask "hello" --base-url http://localhost:8000
QUERY_CLI_BASE_URL=http://localhost:8000 query-cli ask "hello"
query-cli ask "hello" --base-url http://localhost:8000 --format json
```

## HTTP contract

The CLI sends a JSON request:

```http
POST {base_url}/query
Accept: application/json
Content-Type: application/json
```

```json
{"query": "..."}
```

The response must be a JSON object containing one of these fields:

```json
{"result": "..."}
{"answer": "..."}
{"results": ["..."]}
```

Set `QUERY_CLI_API_KEY` or pass `--api-key` only if your service needs bearer-token authentication.
