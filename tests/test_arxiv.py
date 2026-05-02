import httpx

from query_cli.adapters.arxiv import ArxivProvider, parse_arxiv_feed
from query_cli.domain import SearchQuery


ARXIV_XML = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <id>http://arxiv.org/abs/2501.00001v1</id>
    <published>2025-01-02T00:00:00Z</published>
    <title>Explainable NLP with Local Attribution</title>
    <summary>This paper studies explainable NLP systems.</summary>
    <author><name>Jane Doe</name></author>
    <author><name>John Smith</name></author>
  </entry>
  <entry>
    <id>http://arxiv.org/abs/2501.00002v1</id>
    <published>2025-02-03T00:00:00Z</published>
    <title>Faithful Rationales for Language Models</title>
    <summary>Rationale extraction for language models.</summary>
    <author><name>Ada Lovelace</name></author>
  </entry>
</feed>
"""


def test_parse_arxiv_feed_normalizes_results():
    results = parse_arxiv_feed(ARXIV_XML, limit=10)

    assert len(results) == 2
    assert results[0].title == "Explainable NLP with Local Attribution"
    assert results[0].url == "http://arxiv.org/abs/2501.00001v1"
    assert results[0].source == "arXiv"
    assert results[0].authors == ("Jane Doe", "John Smith")
    assert results[0].year == 2025
    assert results[0].venue == "arXiv"
    assert results[0].abstract == "This paper studies explainable NLP systems."


def test_parse_arxiv_feed_applies_limit():
    results = parse_arxiv_feed(ARXIV_XML, limit=1)

    assert len(results) == 1


def test_arxiv_provider_requests_public_api():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        return httpx.Response(200, text=ARXIV_XML)

    provider = ArxivProvider(transport=httpx.MockTransport(handler))

    results = provider.search(SearchQuery(text="explainable NLP", limit=5))

    assert seen["url"] == (
        "https://export.arxiv.org/api/query?search_query=all%3Aexplainable+NLP&start=0&max_results=5"
    )
    assert len(results) == 2
