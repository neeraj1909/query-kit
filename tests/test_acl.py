import asyncio
import gzip

import httpx

from query_cli.adapters.acl import (
    AclAnthologyProvider,
    parse_acl_results,
    search_acl_bibtex,
)
from query_cli.domain import SearchQuery


ACL_BIB = b"""
@inproceedings{paper-2025-one,
    title = "Explaining NLP Model Decisions with Faithful Rationales",
    author = "Doe, Jane  and Smith, John",
    booktitle = "Proceedings of ACL 2025",
    abstract = "This paper studies explainable NLP systems.",
    year = "2025",
    url = "https://aclanthology.org/2025.acl-long.123/"
}
@inproceedings{paper-2024-two,
    title = "Unrelated Parsing Work",
    author = "Other, Person",
    year = "2024",
    url = "https://aclanthology.org/2024.acl-long.456/"
}
"""

ACL_HTML = """
<html>
  <body>
    <p><a href="/2025.acl-long.123/">Explaining NLP Model Decisions with Faithful Rationales</a></p>
    <p><a href="/2025.findings-acl.456/">Counterfactual Explanations for Text Classification</a></p>
    <p><a href="/2025.acl-long.123/">Explaining NLP Model Decisions with Faithful Rationales</a></p>
    <p><a href="/faq/">FAQ</a></p>
  </body>
</html>
"""


def test_parse_acl_results_extracts_paper_links():
    results = parse_acl_results(
        ACL_HTML, base_url="https://aclanthology.org/", limit=10
    )

    assert [result.title for result in results] == [
        "Explaining NLP Model Decisions with Faithful Rationales",
        "Counterfactual Explanations for Text Classification",
    ]
    assert results[0].url == "https://aclanthology.org/2025.acl-long.123/"
    assert results[0].source == "ACL Anthology"


def test_parse_acl_results_applies_limit():
    results = parse_acl_results(ACL_HTML, base_url="https://aclanthology.org/", limit=1)

    assert len(results) == 1


def test_search_acl_bibtex_matches_query_terms():
    results = search_acl_bibtex(
        gzip.compress(ACL_BIB),
        query=SearchQuery(text="explaining nlp", limit=5),
        limit=5,
    )

    assert len(results) == 1
    assert results[0].title == "Explaining NLP Model Decisions with Faithful Rationales"
    assert results[0].url == "https://aclanthology.org/2025.acl-long.123/"
    assert results[0].authors == ("Doe, Jane", "Smith, John")
    assert results[0].year == 2025
    assert results[0].abstract == "This paper studies explainable NLP systems."


def test_acl_provider_requests_bibtex_export():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        return httpx.Response(200, content=gzip.compress(ACL_BIB))

    provider = AclAnthologyProvider(
        base_url="https://aclanthology.org/",
        transport=httpx.MockTransport(handler),
    )

    results = provider.search(SearchQuery(text="explaining nlp", limit=5))

    assert seen["url"] == "https://aclanthology.org/anthology+abstracts.bib.gz"
    assert len(results) == 1


def test_acl_provider_async_requests_bibtex_export():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        return httpx.Response(200, content=gzip.compress(ACL_BIB))

    provider = AclAnthologyProvider(
        base_url="https://aclanthology.org/",
        transport=httpx.MockTransport(handler),
    )

    results = asyncio.run(
        provider.search_async(SearchQuery(text="explaining nlp", limit=5))
    )

    assert seen["url"] == "https://aclanthology.org/anthology+abstracts.bib.gz"
    assert len(results) == 1


def test_acl_provider_falls_back_to_plain_bibtex_export():
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        if str(request.url).endswith("anthology+abstracts.bib.gz"):
            return httpx.Response(404)
        return httpx.Response(200, content=gzip.compress(ACL_BIB))

    provider = AclAnthologyProvider(
        base_url="https://aclanthology.org/",
        transport=httpx.MockTransport(handler),
    )

    results = provider.search(SearchQuery(text="explaining nlp", limit=5))

    assert seen == [
        "https://aclanthology.org/anthology+abstracts.bib.gz",
        "https://aclanthology.org/anthology.bib.gz",
    ]
    assert len(results) == 1


def test_acl_provider_falls_back_to_plain_bibtex_export_on_transient_status():
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        if str(request.url).endswith("anthology+abstracts.bib.gz"):
            return httpx.Response(503)
        return httpx.Response(200, content=gzip.compress(ACL_BIB))

    provider = AclAnthologyProvider(
        base_url="https://aclanthology.org/",
        transport=httpx.MockTransport(handler),
        retries=0,
    )

    results = provider.search(SearchQuery(text="explaining nlp", limit=5))

    assert seen == [
        "https://aclanthology.org/anthology+abstracts.bib.gz",
        "https://aclanthology.org/anthology.bib.gz",
    ]
    assert len(results) == 1


def test_acl_provider_async_falls_back_to_plain_bibtex_export_on_transient_status():
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        if str(request.url).endswith("anthology+abstracts.bib.gz"):
            return httpx.Response(503)
        return httpx.Response(200, content=gzip.compress(ACL_BIB))

    provider = AclAnthologyProvider(
        base_url="https://aclanthology.org/",
        transport=httpx.MockTransport(handler),
        retries=0,
    )

    results = asyncio.run(
        provider.search_async(SearchQuery(text="explaining nlp", limit=5))
    )

    assert seen == [
        "https://aclanthology.org/anthology+abstracts.bib.gz",
        "https://aclanthology.org/anthology.bib.gz",
    ]
    assert len(results) == 1
