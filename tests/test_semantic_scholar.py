import asyncio

import httpx

from query_cli.adapters.semantic_scholar import (
    SemanticScholarProvider,
    parse_semantic_scholar_results,
)
from query_cli.domain import SearchQuery
from query_cli.domain.errors import ProviderParseError


SEMANTIC_SCHOLAR_JSON = {
    "data": [
        {
            "paperId": "abc123",
            "title": "Faithful Explanations for NLP Models",
            "url": "https://www.semanticscholar.org/paper/abc123",
            "authors": [{"name": "Jane Doe"}, {"name": "John Smith"}],
            "year": 2025,
            "venue": "ACL",
            "abstract": "A paper about explainable NLP.",
        },
        {
            "paperId": "old",
            "title": "Older NLP Work",
            "authors": [],
            "year": 2020,
        },
    ]
}


def test_parse_semantic_scholar_results_normalizes_records():
    results = parse_semantic_scholar_results(
        SEMANTIC_SCHOLAR_JSON, limit=5, since_year=2024
    )

    assert len(results) == 1
    assert results[0].title == "Faithful Explanations for NLP Models"
    assert results[0].url == "https://www.semanticscholar.org/paper/abc123"
    assert results[0].source == "Semantic Scholar"
    assert results[0].authors == ("Jane Doe", "John Smith")
    assert results[0].year == 2025
    assert results[0].venue == "ACL"
    assert results[0].abstract == "A paper about explainable NLP."


def test_parse_semantic_scholar_results_rejects_malformed_schema():
    try:
        parse_semantic_scholar_results({"total": 0}, limit=5)
    except ProviderParseError as exc:
        assert "malformed Semantic Scholar search response" in str(exc)
    else:
        raise AssertionError("expected malformed Semantic Scholar response to fail")


def test_semantic_scholar_provider_maps_invalid_json_response():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="{", headers={"content-type": "application/json"})

    provider = SemanticScholarProvider(
        base_url="https://api.example.test/graph/v1/",
        transport=httpx.MockTransport(handler),
        min_interval=0,
    )

    try:
        provider.search(SearchQuery(text="Hindi OCR", limit=3))
    except ProviderParseError as exc:
        assert "invalid JSON" in str(exc)
    else:
        raise AssertionError("expected invalid Semantic Scholar JSON to fail")


def test_semantic_scholar_provider_requests_graph_search_with_filters():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        seen["params"] = dict(request.url.params)
        seen["api_key"] = request.headers.get("x-api-key")
        return httpx.Response(200, json=SEMANTIC_SCHOLAR_JSON)

    provider = SemanticScholarProvider(
        base_url="https://api.example.test/graph/v1/",
        transport=httpx.MockTransport(handler),
        api_key="secret-key",
        min_interval=0,
    )

    results = provider.search(
        SearchQuery(text="explainable nlp", since_year=2024, limit=3)
    )

    assert seen["path"] == "/graph/v1/paper/search"
    assert seen["params"] == {
        "query": "explainable nlp",
        "limit": "3",
        "fields": "title,authors,year,venue,abstract,url",
        "year": "2024-",
        "publicationDateOrYear": "2024:",
    }
    assert seen["api_key"] == "secret-key"
    assert len(results) == 1


def test_semantic_scholar_provider_sanitizes_hyphenated_query_terms():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["params"] = dict(request.url.params)
        return httpx.Response(200, json={"data": []})

    provider = SemanticScholarProvider(
        base_url="https://api.example.test/graph/v1/",
        transport=httpx.MockTransport(handler),
        min_interval=0,
    )

    results = provider.search(SearchQuery(text="Hindi-OCR", limit=3))

    assert seen["params"]["query"] == "Hindi OCR"
    assert results == []


def test_semantic_scholar_provider_async_requests_graph_search_with_filters():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        seen["params"] = dict(request.url.params)
        seen["api_key"] = request.headers.get("x-api-key")
        return httpx.Response(200, json=SEMANTIC_SCHOLAR_JSON)

    provider = SemanticScholarProvider(
        base_url="https://api.example.test/graph/v1/",
        transport=httpx.MockTransport(handler),
        api_key="secret-key",
        min_interval=0,
    )

    results = asyncio.run(
        provider.search_async(
            SearchQuery(text="explainable nlp", since_year=2024, limit=3)
        )
    )

    assert seen["path"] == "/graph/v1/paper/search"
    assert seen["params"] == {
        "query": "explainable nlp",
        "limit": "3",
        "fields": "title,authors,year,venue,abstract,url",
        "year": "2024-",
        "publicationDateOrYear": "2024:",
    }
    assert seen["api_key"] == "secret-key"
    assert len(results) == 1
