import asyncio

import httpx

from query_cli.adapters.openreview import OpenReviewProvider, parse_openreview_notes
from query_cli.domain import SearchQuery


OPENREVIEW_JSON = {
    "notes": [
        {
            "id": "AABeMBYoAr",
            "forum": "AABeMBYoAr",
            "pdate": 1696857857811,
            "content": {
                "title": {
                    "value": "News Signals: An NLP Library for Text and Time Series"
                },
                "authors": {"value": ["Chris Hokamp", "Parsa Ghaffari"]},
                "venue": {"value": "NLP-OSS 2023"},
                "abstract": {"value": "An NLP dataset library paper."},
            },
        },
        {
            "id": "old",
            "pdate": 1600000000000,
            "content": {
                "title": {"value": "Older OpenReview Paper"},
                "authors": {"value": []},
            },
        },
    ]
}


def test_parse_openreview_notes_normalizes_records():
    results = parse_openreview_notes(OPENREVIEW_JSON, limit=5, since_year=2022)

    assert len(results) == 1
    assert results[0].title == "News Signals: An NLP Library for Text and Time Series"
    assert results[0].url == "https://openreview.net/forum?id=AABeMBYoAr"
    assert results[0].source == "OpenReview"
    assert results[0].authors == ("Chris Hokamp", "Parsa Ghaffari")
    assert results[0].year == 2023
    assert results[0].venue == "NLP-OSS 2023"
    assert results[0].abstract == "An NLP dataset library paper."


def test_openreview_provider_requests_notes_search():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        seen["params"] = dict(request.url.params)
        return httpx.Response(200, json=OPENREVIEW_JSON)

    provider = OpenReviewProvider(
        base_url="https://api2.example.test/",
        transport=httpx.MockTransport(handler),
        min_interval=0,
    )

    results = provider.search(
        SearchQuery(text="explainable nlp", since_year=2022, limit=2)
    )

    assert seen["path"] == "/notes/search"
    assert seen["params"] == {"term": "explainable nlp", "limit": "2"}
    assert len(results) == 1


def test_openreview_provider_async_requests_notes_search():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        seen["params"] = dict(request.url.params)
        return httpx.Response(200, json=OPENREVIEW_JSON)

    provider = OpenReviewProvider(
        base_url="https://api2.example.test/",
        transport=httpx.MockTransport(handler),
        min_interval=0,
    )

    results = asyncio.run(
        provider.search_async(
            SearchQuery(text="explainable nlp", since_year=2022, limit=2)
        )
    )

    assert seen["path"] == "/notes/search"
    assert seen["params"] == {"term": "explainable nlp", "limit": "2"}
    assert len(results) == 1
