import asyncio
import json

import httpx
import pytest

from query_cli.adapters.semantic_scholar_web import (
    SemanticScholarWebProvider,
    build_semantic_scholar_web_payload,
    parse_semantic_scholar_web_search_json,
)
from query_cli.domain import SearchQuery
from query_cli.domain.errors import SearchNetworkError


SEMANTIC_SCHOLAR_WEB_JSON = {
    "results": [
        {
            "id": "bc6c79384492b69095b8592be44556d9fa00dffa",
            "slug": "Multi-Feature-Graph-Convolution-Network-for-Hindi-Dubey-Mittal",
            "title": {
                "text": "Multi-Feature Graph Convolution Network for Hindi OCR Verification"
            },
            "authors": [
                [
                    {"name": "Shikha Dubey"},
                    {"text": "Shikha Dubey"},
                ],
                [
                    {"name": "K. Mittal"},
                    {"text": "K. Mittal"},
                ],
            ],
            "year": {"text": "2025"},
            "venue": {"text": "Bhasha"},
            "paperAbstract": {
                "text": (
                    "This paper presents a novel Graph Convolutional Network "
                    "framework for verifying OCR predictions on real Hindi "
                    "document images with complex conjuncts."
                )
            },
        },
        {
            "id": "1ea231be195204359a2bc70a89a4d80063001b44",
            "slug": "Adaptive-Hindi-OCR-using-generalized-Hausdorff-Ma-Doermann",
            "title": {"text": "Adaptive Hindi OCR using generalized Hausdorff image comparison"},
            "structuredAuthors": [
                {"firstName": "Huanfeng", "lastName": "Ma", "middleNames": []},
                {"firstName": "D.", "lastName": "Doermann", "middleNames": []},
            ],
            "year": {"text": "2003"},
            "venue": {"text": "TALIP"},
            "paperAbstract": {"text": ""},
            "tldr": {
                "text": (
                    "An adaptive Hindi OCR system reached strong recognition "
                    "accuracy on noisy and ideal images."
                )
            },
        },
    ]
}


def test_build_semantic_scholar_web_payload_uses_public_search_shape():
    payload = build_semantic_scholar_web_payload(SearchQuery(text="Hindi OCR", limit=3))

    assert payload["queryString"] == "Hindi OCR"
    assert payload["page"] == 1
    assert payload["pageSize"] == 3
    assert payload["sort"] == "relevance"
    assert payload["includeTldrs"] is True
    assert payload["performTitleMatch"] is True
    assert "cookies" not in payload


def test_parse_semantic_scholar_web_search_json_preserves_full_public_abstract():
    results = parse_semantic_scholar_web_search_json(
        SEMANTIC_SCHOLAR_WEB_JSON, limit=5, since_year=2020
    )

    assert len(results) == 1
    result = results[0]
    assert result.title == "Multi-Feature Graph Convolution Network for Hindi OCR Verification"
    assert result.url == (
        "https://www.semanticscholar.org/paper/"
        "Multi-Feature-Graph-Convolution-Network-for-Hindi-Dubey-Mittal/"
        "bc6c79384492b69095b8592be44556d9fa00dffa"
    )
    assert result.source == "Semantic Scholar Web"
    assert result.authors == ("Shikha Dubey", "K. Mittal")
    assert result.year == 2025
    assert result.venue == "Bhasha"
    assert result.abstract == (
        "This paper presents a novel Graph Convolutional Network framework "
        "for verifying OCR predictions on real Hindi document images with "
        "complex conjuncts."
    )


def test_parse_semantic_scholar_web_search_json_uses_tldr_when_abstract_missing():
    results = parse_semantic_scholar_web_search_json(
        SEMANTIC_SCHOLAR_WEB_JSON, limit=5, since_year=None
    )

    old_result = results[1]
    assert old_result.authors == ("Huanfeng Ma", "D. Doermann")
    assert old_result.abstract == (
        "An adaptive Hindi OCR system reached strong recognition accuracy "
        "on noisy and ideal images."
    )


def test_semantic_scholar_web_provider_posts_public_search_payload_with_user_agent(
    monkeypatch,
):
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        seen["payload"] = request.read().decode()
        seen["user_agent"] = request.headers.get("user-agent")
        return httpx.Response(200, json=SEMANTIC_SCHOLAR_WEB_JSON)

    monkeypatch.setenv("QUERY_CLI_USER_AGENT", "indic-research-agent/0.1")
    provider = SemanticScholarWebProvider(
        base_url="https://semanticscholar.example.test/",
        transport=httpx.MockTransport(handler),
        min_interval=0,
    )

    results = provider.search(SearchQuery(text="Hindi OCR", limit=3, since_year=2020))

    assert seen["path"] == "/api/1/search"
    assert json.loads(seen["payload"])["queryString"] == "Hindi OCR"
    assert seen["user_agent"] == "indic-research-agent/0.1"
    assert [result.title for result in results] == [
        "Multi-Feature Graph Convolution Network for Hindi OCR Verification"
    ]


def test_semantic_scholar_web_provider_reports_waf_challenge():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(202, headers={"x-amzn-waf-action": "challenge"})

    provider = SemanticScholarWebProvider(
        base_url="https://semanticscholar.example.test/",
        transport=httpx.MockTransport(handler),
        min_interval=0,
    )

    with pytest.raises(SearchNetworkError, match="x-amzn-waf-action=challenge"):
        provider.search(SearchQuery(text="Hindi OCR", limit=3))


def test_semantic_scholar_web_provider_async_requests_public_search_endpoint():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=SEMANTIC_SCHOLAR_WEB_JSON)

    provider = SemanticScholarWebProvider(
        base_url="https://semanticscholar.example.test/",
        transport=httpx.MockTransport(handler),
        min_interval=0,
    )

    results = asyncio.run(
        provider.search_async(SearchQuery(text="Hindi OCR", limit=3, since_year=2020))
    )

    assert len(results) == 1
    assert results[0].source == "Semantic Scholar Web"
