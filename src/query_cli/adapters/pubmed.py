from __future__ import annotations

import os
import re
import xml.etree.ElementTree as ET

import httpx

from query_cli.adapters.http import (
    ProviderHttpClient,
    ensure_success,
    parse_json_response,
    parse_xml_text,
)
from query_cli.domain import SearchQuery, SearchResult
from query_cli.domain.errors import ProviderParseError

EUTILS_BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"


class PubMedProvider:
    provider_id = "pubmed"

    def __init__(
        self,
        *,
        base_url: str = EUTILS_BASE_URL,
        timeout: float = 30.0,
        transport: httpx.BaseTransport | None = None,
        api_key: str | None = None,
        tool: str | None = None,
        email: str | None = None,
        min_interval: float | None = None,
        retries: int = 1,
    ) -> None:
        self.api_key = (
            api_key if api_key is not None else os.environ.get("QUERY_CLI_NCBI_API_KEY")
        )
        self.tool = tool if tool is not None else os.environ.get("QUERY_CLI_NCBI_TOOL")
        self.email = (
            email if email is not None else os.environ.get("QUERY_CLI_NCBI_EMAIL")
        )
        if min_interval is None:
            min_interval = 0.1 if self.api_key else 1 / 3
        self.http = ProviderHttpClient(
            provider_id=self.provider_id,
            base_url=base_url,
            timeout=timeout,
            transport=transport,
            min_interval=min_interval,
            retries=retries,
        )

    def search(self, query: SearchQuery) -> list[SearchResult]:
        ids = self._search_ids(query)
        if not ids:
            return []
        response = self.http.get(
            "efetch.fcgi",
            params=self._with_common_params(
                {
                    "db": "pubmed",
                    "id": ",".join(ids),
                    "retmode": "xml",
                }
            ),
        )
        ensure_success(response)
        return parse_pubmed_articles(
            response.text, limit=query.limit, since_year=query.since_year
        )

    def _search_ids(self, query: SearchQuery) -> list[str]:
        params = {
            "db": "pubmed",
            "term": query.text,
            "retmode": "json",
            "retmax": str(query.limit),
        }
        if query.since_year is not None:
            params.update(
                {
                    "datetype": "pdat",
                    "mindate": f"{query.since_year}/01/01",
                    "maxdate": "3000/12/31",
                }
            )
        response = self.http.get(
            "esearch.fcgi", params=self._with_common_params(params)
        )
        ensure_success(response)
        data = parse_json_response(response)
        try:
            ids = data["esearchresult"]["idlist"]
        except (KeyError, TypeError) as exc:
            raise ProviderParseError("malformed PubMed ESearch response") from exc
        if not isinstance(ids, list):
            raise ProviderParseError("malformed PubMed ESearch id list")
        return [str(pmid) for pmid in ids if str(pmid).strip()]

    def _with_common_params(self, params: dict[str, str]) -> dict[str, str]:
        merged = dict(params)
        if self.api_key:
            merged["api_key"] = self.api_key
        if self.tool:
            merged["tool"] = self.tool
        if self.email:
            merged["email"] = self.email
        return merged


def parse_pubmed_articles(
    xml_text: str, *, limit: int, since_year: int | None = None
) -> list[SearchResult]:
    root = parse_xml_text(xml_text)
    results: list[SearchResult] = []
    for article in root.findall(".//PubmedArticle"):
        pmid = text_of(article, ".//PMID")
        title = text_of(article, ".//ArticleTitle")
        if not pmid or not title:
            continue
        year = parse_pubmed_year(article)
        if since_year is not None and year is not None and year < since_year:
            continue
        results.append(
            SearchResult(
                title=title,
                url=f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                source="PubMed",
                authors=parse_pubmed_authors(article),
                year=year,
                venue=text_of(article, ".//Journal/Title")
                or text_of(article, ".//ISOAbbreviation")
                or None,
                abstract=parse_pubmed_abstract(article),
            )
        )
        if len(results) >= limit:
            break
    return results


def parse_pubmed_authors(article: ET.Element) -> tuple[str, ...]:
    authors: list[str] = []
    for author in article.findall(".//AuthorList/Author"):
        collective = text_of(author, "CollectiveName")
        if collective:
            authors.append(collective)
            continue
        last_name = text_of(author, "LastName")
        fore_name = text_of(author, "ForeName")
        initials = text_of(author, "Initials")
        if fore_name and last_name:
            authors.append(f"{fore_name} {last_name}")
        elif initials and last_name:
            authors.append(f"{initials} {last_name}")
        elif last_name:
            authors.append(last_name)
    return tuple(authors)


def parse_pubmed_abstract(article: ET.Element) -> str | None:
    parts = [
        text_of(abstract_text, ".")
        for abstract_text in article.findall(".//Abstract/AbstractText")
    ]
    abstract = clean_text(" ".join(part for part in parts if part))
    return abstract or None


def parse_pubmed_year(article: ET.Element) -> int | None:
    for path in (
        ".//JournalIssue/PubDate/Year",
        ".//ArticleDate/Year",
        ".//DateCompleted/Year",
        ".//PubmedData/History/PubMedPubDate/Year",
    ):
        year = parse_year(text_of(article, path))
        if year is not None:
            return year
    medline_date = text_of(article, ".//JournalIssue/PubDate/MedlineDate")
    match = re.search(r"\b(1[89]\d{2}|20\d{2})\b", medline_date)
    if match:
        return int(match.group(1))
    return None


def text_of(element: ET.Element, path: str) -> str:
    child = element if path == "." else element.find(path)
    if child is None:
        return ""
    return clean_text("".join(child.itertext()))


def clean_text(value: str) -> str:
    return " ".join(value.split())


def parse_year(value: str) -> int | None:
    try:
        return int(value[:4])
    except ValueError:
        return None
