import asyncio

import httpx

from query_cli.adapters.arxiv_web import ArxivWebProvider, parse_arxiv_search_html
from query_cli.domain import SearchQuery


ARXIV_SEARCH_HTML = """
<ol class="breathe-horizontal" start="1">
  <li class="arxiv-result">
    <p class="list-title is-inline-block"><a href="https://arxiv.org/abs/2503.13060">arXiv:2503.13060</a></p>
    <p class="title is-5 mathjax">
      Historic Scripts to Modern Vision: A Novel Dataset and A VLM Framework for Transliteration of Modi Script to <span class="search-hit mathjax">Devanagari</span>
    </p>
    <p class="authors">
      <span>Authors:</span>
      <a href="/search/?searchtype=author&amp;query=Kausadikar%2C+H">Harshal Kausadikar</a>,
      <a href="/search/?searchtype=author&amp;query=Kale%2C+T">Tanvi Kale</a>
    </p>
    <p class="abstract mathjax">
      <span class="search-hit">Abstract</span>:
      <span class="abstract-short has-text-grey-dark mathjax" id="short" style="display: inline;">
        &hellip;short truncated abstract&hellip;
        <a class="is-size-7">&#9661; More</a>
      </span>
      <span class="abstract-full has-text-grey-dark mathjax" id="full" style="display: none;">
        Full public abstract about Modi script to <span class="search-hit mathjax">Devanagari</span> transliteration and optical character recognition (<span class="search-hit mathjax">OCR</span>) without truncation.
        <a class="is-size-7">&#9651; Less</a>
      </span>
    </p>
    <p class="is-size-7"><span>Submitted</span> 25 March, 2025; <span>v1</span> submitted 17 March, 2025;</p>
  </li>
</ol>
"""


def test_parse_arxiv_search_html_prefers_full_public_abstract():
    results = parse_arxiv_search_html(ARXIV_SEARCH_HTML, limit=5)

    assert len(results) == 1
    result = results[0]
    assert result.title == (
        "Historic Scripts to Modern Vision: A Novel Dataset and A VLM Framework "
        "for Transliteration of Modi Script to Devanagari"
    )
    assert result.url == "https://arxiv.org/abs/2503.13060"
    assert result.source == "arXiv Web"
    assert result.authors == ("Harshal Kausadikar", "Tanvi Kale")
    assert result.year == 2025
    assert result.venue == "arXiv"
    assert result.abstract == (
        "Full public abstract about Modi script to Devanagari transliteration "
        "and optical character recognition ( OCR ) without truncation."
    )


def test_arxiv_web_provider_requests_public_search_page_with_user_agent(monkeypatch):
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        seen["params"] = dict(request.url.params)
        seen["user_agent"] = request.headers.get("user-agent")
        return httpx.Response(200, text=ARXIV_SEARCH_HTML)

    monkeypatch.setenv("QUERY_CLI_USER_AGENT", "indic-research-agent/0.1")
    provider = ArxivWebProvider(
        base_url="https://arxiv.example.test/search/",
        transport=httpx.MockTransport(handler),
        min_interval=0,
    )

    results = provider.search(SearchQuery(text="Devanagari OCR", limit=3))

    assert seen["path"] == "/search/"
    assert seen["params"] == {
        "query": "Devanagari OCR",
        "searchtype": "all",
        "source": "header",
        "abstracts": "show",
        "size": "50",
    }
    assert seen["user_agent"] == "indic-research-agent/0.1"
    assert [result.title for result in results] == [
        "Historic Scripts to Modern Vision: A Novel Dataset and A VLM Framework "
        "for Transliteration of Modi Script to Devanagari"
    ]


def test_arxiv_web_provider_async_requests_public_search_page():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=ARXIV_SEARCH_HTML)

    provider = ArxivWebProvider(
        base_url="https://arxiv.example.test/search/",
        transport=httpx.MockTransport(handler),
        min_interval=0,
    )

    results = asyncio.run(provider.search_async(SearchQuery(text="Devanagari OCR", limit=3)))

    assert len(results) == 1
    assert results[0].abstract is not None
    assert "without truncation" in results[0].abstract
