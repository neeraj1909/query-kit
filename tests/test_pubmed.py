import asyncio

import httpx

from query_cli.adapters.pubmed import PubMedProvider, parse_pubmed_articles
from query_cli.domain import SearchQuery


PUBMED_ESEARCH = {
    "esearchresult": {
        "idlist": ["42064032"],
    }
}

PUBMED_XML = """<?xml version="1.0" ?>
<PubmedArticleSet>
  <PubmedArticle>
    <MedlineCitation>
      <PMID>42064032</PMID>
      <Article>
        <Journal>
          <JournalIssue>
            <PubDate><Year>2026</Year></PubDate>
          </JournalIssue>
          <Title>Frontiers in artificial intelligence</Title>
        </Journal>
        <ArticleTitle>Applications of artificial intelligence in postoperative surveillance.</ArticleTitle>
        <Abstract>
          <AbstractText>This review includes natural language processing evidence.</AbstractText>
        </Abstract>
        <AuthorList>
          <Author><ForeName>Jane</ForeName><LastName>Doe</LastName></Author>
          <Author><Initials>J</Initials><LastName>Smith</LastName></Author>
        </AuthorList>
      </Article>
    </MedlineCitation>
  </PubmedArticle>
</PubmedArticleSet>
"""


def test_parse_pubmed_articles_normalizes_results():
    results = parse_pubmed_articles(PUBMED_XML, limit=5)

    assert len(results) == 1
    assert (
        results[0].title
        == "Applications of artificial intelligence in postoperative surveillance."
    )
    assert results[0].url == "https://pubmed.ncbi.nlm.nih.gov/42064032/"
    assert results[0].source == "PubMed"
    assert results[0].authors == ("Jane Doe", "J Smith")
    assert results[0].year == 2026
    assert results[0].venue == "Frontiers in artificial intelligence"
    assert (
        results[0].abstract
        == "This review includes natural language processing evidence."
    )


def test_pubmed_provider_requests_esearch_then_efetch_with_env_config():
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append((request.url.path, dict(request.url.params)))
        if request.url.path.endswith("/esearch.fcgi"):
            return httpx.Response(200, json=PUBMED_ESEARCH)
        return httpx.Response(200, text=PUBMED_XML)

    provider = PubMedProvider(
        base_url="https://eutils.example.test/entrez/eutils/",
        transport=httpx.MockTransport(handler),
        api_key="secret-key",
        tool="query-cli",
        email="dev@example.test",
        min_interval=0,
    )

    results = provider.search(
        SearchQuery(text="explainable nlp", since_year=2025, limit=2)
    )

    assert [path for path, _params in seen] == [
        "/entrez/eutils/esearch.fcgi",
        "/entrez/eutils/efetch.fcgi",
    ]
    assert seen[0][1] == {
        "db": "pubmed",
        "term": "explainable nlp",
        "retmode": "json",
        "retmax": "2",
        "datetype": "pdat",
        "mindate": "2025/01/01",
        "maxdate": "3000/12/31",
        "api_key": "secret-key",
        "tool": "query-cli",
        "email": "dev@example.test",
    }
    assert seen[1][1]["id"] == "42064032"
    assert len(results) == 1


def test_pubmed_provider_async_requests_esearch_then_efetch_with_env_config():
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append((request.url.path, dict(request.url.params)))
        if request.url.path.endswith("/esearch.fcgi"):
            return httpx.Response(200, json=PUBMED_ESEARCH)
        return httpx.Response(200, text=PUBMED_XML)

    provider = PubMedProvider(
        base_url="https://eutils.example.test/entrez/eutils/",
        transport=httpx.MockTransport(handler),
        api_key="secret-key",
        tool="query-cli",
        email="dev@example.test",
        min_interval=0,
    )

    results = asyncio.run(
        provider.search_async(
            SearchQuery(text="explainable nlp", since_year=2025, limit=2)
        )
    )

    assert [path for path, _params in seen] == [
        "/entrez/eutils/esearch.fcgi",
        "/entrez/eutils/efetch.fcgi",
    ]
    assert seen[0][1] == {
        "db": "pubmed",
        "term": "explainable nlp",
        "retmode": "json",
        "retmax": "2",
        "datetype": "pdat",
        "mindate": "2025/01/01",
        "maxdate": "3000/12/31",
        "api_key": "secret-key",
        "tool": "query-cli",
        "email": "dev@example.test",
    }
    assert seen[1][1]["id"] == "42064032"
    assert len(results) == 1
