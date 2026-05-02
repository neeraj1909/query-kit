# Error History

## 2026-05-02 - ACL Anthology base URL returns 404

### Command

```bash
query-cli ask "list down xai driven nlp research papers in last 1 year" --base-url https://aclanthology.org/
```

### Observed Error

The CLI returned a server error with HTTP 404 and an HTML page from ACL Anthology.

### Root Cause

`query-cli` currently assumes a generic query-service contract:

```http
POST {base_url}/query
Content-Type: application/json
Accept: application/json
```

with body:

```json
{"query": "..."}
```

Passing `--base-url https://aclanthology.org/` makes the CLI call:

```text
POST https://aclanthology.org/query
```

ACL Anthology is a public website, not a service implementing this CLI's `POST /query` API contract, so `/query` does not exist and the site returns 404 HTML.

### Comment

This is expected behavior for the current provider-agnostic CLI. The CLI is not yet a general website search tool or scraper; it only talks to HTTP services that implement the documented `/query` JSON contract.

### Planned Fix

Keep `query-cli ask` for services that implement the generic `/query` JSON API, and add a separate provider-specific research search command:

```bash
query-cli search "xai driven nlp" --provider acl
```

That feature will call ACL Anthology's actual search flow, parse paper results, and format them through the same CLI output system. This remains separate from `query-cli ask` so adding website providers does not break the generic API-client contract.

### Implementation Note

The generic `ask` command should also avoid dumping large HTML error pages to stderr. When a server error response looks like HTML, print a concise incompatibility message and point ACL users toward `query-cli search --provider acl`.
