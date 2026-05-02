from query_cli.bootstrap import get_search_providers


def test_get_search_providers_expands_all():
    providers = get_search_providers(["all"], timeout=1)

    assert [provider.provider_id for provider in providers] == [
        "acl",
        "arxiv",
        "pubmed",
        "semantic-scholar",
        "openreview",
    ]


def test_get_search_providers_deduplicates_repeated_providers():
    providers = get_search_providers(["acl", "acl", "arxiv", "pubmed"], timeout=1)

    assert [provider.provider_id for provider in providers] == [
        "acl",
        "arxiv",
        "pubmed",
    ]


def test_get_search_providers_passes_provider_environment():
    providers = get_search_providers(
        ["pubmed", "semantic-scholar"],
        timeout=1,
        environ={
            "QUERY_CLI_NCBI_API_KEY": "ncbi-key",
            "QUERY_CLI_NCBI_TOOL": "query-cli",
            "QUERY_CLI_NCBI_EMAIL": "dev@example.test",
            "QUERY_CLI_SEMANTIC_SCHOLAR_API_KEY": "s2-key",
        },
    )

    assert providers[0].api_key == "ncbi-key"
    assert providers[0].tool == "query-cli"
    assert providers[0].email == "dev@example.test"
    assert providers[1].api_key == "s2-key"
