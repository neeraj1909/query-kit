from query_cli.bootstrap import get_search_providers


def test_get_search_providers_expands_all():
    providers = get_search_providers(["all"], timeout=1)

    assert [provider.provider_id for provider in providers] == ["acl", "arxiv"]


def test_get_search_providers_deduplicates_repeated_providers():
    providers = get_search_providers(["acl", "acl", "arxiv"], timeout=1)

    assert [provider.provider_id for provider in providers] == ["acl", "arxiv"]
