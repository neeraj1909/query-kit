# Query CLI

A small, independent Python CLI for searching public research sources from the shell.

It does not require a paid API, cloud account, hosted LLM, or project-specific backend. The CLI uses provider-specific adapters for supported research websites and normalizes results into a consistent text or JSON format.

## Requirements

- Python 3.10 or newer
- [`uv`](https://docs.astral.sh/uv/) for installation as a standalone tool

## Install

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

Search arXiv directly:

```bash
query-cli search "explainable NLP" --provider arxiv --limit 5
```

Search more than one provider by repeating `--provider`:

```bash
query-cli search "explainable NLP" --provider acl --provider arxiv --limit 10
```

Search all launch-ready providers:

```bash
query-cli search "explainable NLP" --provider all --limit 10
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

## Exit Codes

| Code | Meaning |
| --- | --- |
| `0` | Success. |
| `1` | User/configuration error, such as an invalid provider or limit. |
| `2` | Network or provider request error. |
