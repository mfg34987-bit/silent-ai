from __future__ import annotations

import re
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from typing import Any
from urllib.parse import quote_plus, urlparse
import xml.etree.ElementTree as ET

import requests

try:
    from ddgs import DDGS
except ImportError:
    from duckduckgo_search import DDGS


UTC = timezone.utc


class _PageTextParser(HTMLParser):
    SKIP_TAGS = {
        "script", "style", "noscript", "svg", "canvas", "iframe",
        "nav", "footer", "header", "form", "button", "aside",
    }

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.skip_depth = 0
        self.title_depth = 0
        self.title_parts: list[str] = []
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if tag in self.SKIP_TAGS:
            self.skip_depth += 1
        elif tag == "title" and self.skip_depth == 0:
            self.title_depth += 1

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in self.SKIP_TAGS and self.skip_depth:
            self.skip_depth -= 1
        elif tag == "title" and self.title_depth:
            self.title_depth -= 1

    def handle_data(self, data: str) -> None:
        if self.skip_depth:
            return
        text = re.sub(r"\s+", " ", data).strip()
        if not text:
            return
        if self.title_depth:
            self.title_parts.append(text)
        if len(text) >= 25:
            self.parts.append(text)

    def text(self) -> str:
        return re.sub(r"\s+", " ", " ".join(self.parts)).strip()

    def title(self) -> str:
        return re.sub(r"\s+", " ", " ".join(self.title_parts)).strip()


class FreeSearchService:
    """
    Silent AI Search Engine V4.

    Free research pipeline:
      - DuckDuckGo/DDGS web + news search
      - GDELT global news search (no API key)
      - Google News RSS public feed (no API key)
      - Wikipedia/MediaWiki reference search (no API key)
      - public-page fetching for real evidence, not snippets only
      - source quality + recency + relevance + domain diversity ranking
      - lightweight corroboration scoring

    No paid search API is required. Public endpoints can still rate-limit
    or block automated traffic, so failures are isolated per source.
    """

    TRUSTED_DOMAINS = {
        "reuters.com": 5.0,
        "apnews.com": 5.0,
        "bbc.com": 4.5,
        "bbc.co.uk": 4.5,
        "npr.org": 4.0,
        "theguardian.com": 3.5,
        "nytimes.com": 3.5,
        "washingtonpost.com": 3.5,
        "ft.com": 3.5,
        "aljazeera.com": 3.5,
        "who.int": 5.0,
        "un.org": 5.0,
        "nasa.gov": 5.0,
        "nih.gov": 5.0,
        "cdc.gov": 5.0,
        "state.gov": 5.0,
        "whitehouse.gov": 5.0,
        "gov.uk": 5.0,
        "europa.eu": 5.0,
        "ecb.europa.eu": 5.0,
        "federalreserve.gov": 5.0,
        "openai.com": 5.0,
        "google.com": 4.5,
        "microsoft.com": 4.5,
        "github.com": 4.0,
        "arxiv.org": 4.5,
        "nature.com": 4.5,
        "wikipedia.org": 2.5,
    }

    def __init__(
        self,
        max_search_results: int = 8,
        max_queries: int = 6,
        max_final_sources: int = 10,
        max_page_chars: int = 7500,
        max_context_chars: int = 30000,
        request_timeout: int = 10,
    ) -> None:
        self.max_search_results = max_search_results
        self.max_queries = max_queries
        self.max_final_sources = max_final_sources
        self.max_page_chars = max_page_chars
        self.max_context_chars = max_context_chars
        self.request_timeout = request_timeout
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 Chrome/153 Safari/537.36 SilentAI/2.0"
            ),
            "Accept-Language": "en-US,en;q=0.9,ar;q=0.8",
        })

    @staticmethod
    def _clean(value: Any) -> str:
        return re.sub(r"\s+", " ", str(value or "")).strip()

    @staticmethod
    def _domain(url: str) -> str:
        try:
            host = urlparse(url).netloc.lower()
        except Exception:
            return ""
        return host[4:] if host.startswith("www.") else host

    @staticmethod
    def _now() -> datetime:
        return datetime.now(UTC)

    @staticmethod
    def _recent(query: str) -> bool:
        q = query.lower()
        words = (
            "latest", "recent", "today", "tonight", "current", "now", "breaking",
            "news", "update", "this week", "this month", "2026", "yesterday",
            "آخر", "أحدث", "اليوم", "دلوقتي", "حالي", "الآن", "أخبار", "اخبار",
            "حديث", "النهارده", "امبارح", "تحديث", "الجديد", "حصل ايه", "حصل إيه",
        )
        return any(x in q for x in words)

    @staticmethod
    def _terms(query: str) -> list[str]:
        words = re.findall(r"[\w\u0600-\u06FF][\w\u0600-\u06FF\-']*", query.lower())
        stop = {
            "what", "who", "when", "where", "why", "how", "the", "a", "an", "of",
            "to", "for", "in", "on", "with", "and", "or", "about", "today", "latest",
            "current", "recent", "this", "week", "month", "ما", "ماذا", "من", "متى",
            "أين", "اين", "لماذا", "ليه", "كيف", "هل", "هو", "هي", "في", "عن", "إلى",
            "الى", "مع", "و", "أو", "او", "دلوقتي", "الآن", "حاليا", "حاليًا", "اليوم",
            "آخر", "اخر", "أخبار", "اخبار", "النهارده", "ايه", "إيه",
        }
        return list(dict.fromkeys(x for x in words if len(x) >= 3 and x not in stop))[:12]

    @staticmethod
    def _normalize(item: dict[str, Any], query: str, kind: str = "web") -> dict[str, Any]:
        url = FreeSearchService._clean(item.get("href") or item.get("url"))
        return {
            "title": FreeSearchService._clean(item.get("title") or item.get("name") or "Untitled"),
            "url": url,
            "body": FreeSearchService._clean(item.get("body") or item.get("snippet") or item.get("description")),
            "domain": FreeSearchService._domain(url),
            "query": query,
            "kind": kind,
            "published": FreeSearchService._clean(item.get("published") or item.get("date") or ""),
            "page_text": "",
            "page_title": "",
            "fetch_status": "not_fetched",
        }

    def _search_ddgs(self, query: str, news: bool = False) -> list[dict[str, Any]]:
        try:
            with DDGS() as ddgs:
                raw = list(
                    ddgs.news(query, max_results=self.max_search_results)
                    if news
                    else ddgs.text(query, max_results=self.max_search_results)
                )
            return [self._normalize(x, query, "ddgs_news" if news else "ddgs_web") for x in raw if isinstance(x, dict)]
        except Exception:
            return []

    def _search_gdelt(self, query: str) -> list[dict[str, Any]]:
        """GDELT DOC 2.0: free global news index, no key required."""
        try:
            params = {
                "query": query,
                "mode": "artlist",
                "format": "json",
                "maxrecords": str(self.max_search_results),
                "sort": "datedesc",
                "timespan": "3months",
            }
            response = self.session.get(
                "https://api.gdeltproject.org/api/v2/doc/doc",
                params=params,
                timeout=self.request_timeout,
            )
            response.raise_for_status()
            articles = response.json().get("articles", [])
            output = []
            for article in articles:
                output.append(self._normalize({
                    "title": article.get("title"),
                    "url": article.get("url"),
                    "body": article.get("snippet") or article.get("seendate"),
                    "published": article.get("seendate"),
                }, query, "gdelt"))
            return output
        except Exception:
            return []

    def _search_google_news(self, query: str) -> list[dict[str, Any]]:
        """Public Google News RSS feed; no API key."""
        try:
            url = "https://news.google.com/rss/search?q=" + quote_plus(query) + "&hl=en-US&gl=US&ceid=US:en"
            response = self.session.get(url, timeout=self.request_timeout)
            response.raise_for_status()
            root = ET.fromstring(response.text)
            results = []
            for item in root.findall(".//item")[: self.max_search_results]:
                title = self._clean(item.findtext("title"))
                link = self._clean(item.findtext("link"))
                description = self._clean(item.findtext("description"))
                published = self._clean(item.findtext("pubDate"))
                results.append(self._normalize({
                    "title": title,
                    "url": link,
                    "body": re.sub(r"<[^>]+>", " ", description),
                    "published": published,
                }, query, "google_news"))
            return results
        except Exception:
            return []

    def _search_wikipedia(self, query: str) -> list[dict[str, Any]]:
        """MediaWiki OpenSearch reference lookup; no key."""
        try:
            url = "https://en.wikipedia.org/w/api.php"
            response = self.session.get(url, params={
                "action": "opensearch",
                "search": query,
                "limit": 4,
                "namespace": 0,
                "format": "json",
            }, timeout=self.request_timeout)
            response.raise_for_status()
            data = response.json()
            titles = data[1] if len(data) > 1 else []
            descriptions = data[2] if len(data) > 2 else []
            urls = data[3] if len(data) > 3 else []
            return [self._normalize({
                "title": titles[i] if i < len(titles) else "Wikipedia",
                "url": urls[i] if i < len(urls) else "",
                "body": descriptions[i] if i < len(descriptions) else "",
            }, query, "wikipedia") for i in range(min(len(titles), len(urls)))]
        except Exception:
            return []

    def _build_queries(self, query: str) -> list[tuple[str, str]]:
        terms = self._terms(query)
        core = " ".join(terms[:8]) or query
        recent = self._recent(query)
        queries = [
            (query, "primary web"),
            (f"{core} official source", "official verification"),
            (f"{core} facts evidence", "evidence verification"),
        ]
        if recent:
            queries += [
                (f"{core} latest news", "latest news"),
                (f"{core} Reuters AP BBC", "independent news"),
                (f"{core} official statement", "official statement"),
            ]
        else:
            queries += [(f"{core} research documentation", "deep reference")]
        out, seen = [], set()
        for q, reason in queries:
            key = q.lower().strip()
            if key not in seen:
                seen.add(key)
                out.append((q, reason))
        return out[: self.max_queries]

    def _fetch_page(self, item: dict[str, Any]) -> dict[str, Any]:
        url = item.get("url", "")
        if not url.startswith(("http://", "https://")):
            item["fetch_status"] = "invalid_url"
            return item
        try:
            response = self.session.get(url, timeout=self.request_timeout, allow_redirects=True)
            item["final_url"] = response.url
            item["domain"] = self._domain(response.url) or item.get("domain", "")
            content_type = response.headers.get("content-type", "").lower()
            if response.status_code >= 400:
                item["fetch_status"] = f"http_{response.status_code}"
                return item
            if "text/html" not in content_type and "application/xhtml" not in content_type:
                item["fetch_status"] = "non_html"
                return item
            parser = _PageTextParser()
            parser.feed(response.text[:1_500_000])
            text = parser.text()
            item["page_title"] = parser.title()
            item["page_text"] = text[: self.max_page_chars]
            item["fetch_status"] = "full_text" if len(text) >= 300 else "short_text"
            return item
        except Exception:
            item["fetch_status"] = "fetch_failed"
            return item

    def _fetch_pages(self, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        candidates = items[: min(len(items), self.max_final_sources * 2 + 8)]
        if not candidates:
            return items
        with ThreadPoolExecutor(max_workers=min(8, len(candidates))) as pool:
            futures = [pool.submit(self._fetch_page, dict(x)) for x in candidates]
            fetched = []
            for future in as_completed(futures):
                try:
                    fetched.append(future.result())
                except Exception:
                    pass
        by_url = {x.get("url", ""): x for x in fetched}
        return [by_url.get(x.get("url", ""), x) for x in items]

    @staticmethod
    def _parse_date(value: str) -> datetime | None:
        value = value.strip()
        if not value:
            return None
        try:
            dt = parsedate_to_datetime(value)
            return dt.astimezone(UTC) if dt.tzinfo else dt.replace(tzinfo=UTC)
        except Exception:
            pass
        for fmt in ("%Y%m%dT%H%M%SZ", "%Y%m%d%H%M%S", "%Y-%m-%dT%H:%M:%SZ"):
            try:
                return datetime.strptime(value[:len(fmt)], fmt).replace(tzinfo=UTC)
            except Exception:
                continue
        return None

    def _recency_score(self, item: dict[str, Any], query: str) -> float:
        if not self._recent(query):
            return 0.0
        dt = self._parse_date(str(item.get("published") or ""))
        if not dt:
            return 0.0
        age_hours = max(0.0, (self._now() - dt).total_seconds() / 3600.0)
        if age_hours <= 6:
            return 4.0
        if age_hours <= 24:
            return 3.0
        if age_hours <= 72:
            return 2.0
        if age_hours <= 24 * 14:
            return 1.0
        return 0.0

    def _source_quality(self, domain: str) -> float:
        domain = domain.lower().lstrip("www.")
        for trusted, score in self.TRUSTED_DOMAINS.items():
            if domain == trusted or domain.endswith("." + trusted):
                return score
        if domain.endswith(".gov") or ".gov." in domain:
            return 4.5
        if domain.endswith(".edu") or ".edu." in domain:
            return 3.8
        return 0.5

    def _score(self, item: dict[str, Any], query: str, position: int, domain_counts: Counter[str]) -> float:
        title = item.get("title", "").lower()
        body = item.get("body", "").lower()
        page = item.get("page_text", "").lower()
        domain = item.get("domain", "").lower()
        terms = self._terms(query)
        combined = f"{title} {body} {page[:9000]}"
        score = max(0.0, 6.0 - position * 0.15)
        score += min(sum(1 for term in terms if term in combined) * 0.7, 5.0)
        score += self._source_quality(domain)
        score += self._recency_score(item, query)
        if item.get("fetch_status") == "full_text":
            score += 3.0
        elif item.get("fetch_status") == "short_text":
            score += 1.0
        if item.get("kind") in {"gdelt", "google_news", "ddgs_news"}:
            score += 1.0
        if domain_counts[domain] == 1:
            score += 1.2
        return score

    def _rank(self, items: list[dict[str, Any]], query: str) -> list[dict[str, Any]]:
        domain_counts = Counter(x.get("domain", "") for x in items)
        ranked = []
        for i, item in enumerate(items):
            copy = dict(item)
            copy["_score"] = self._score(copy, query, i, domain_counts)
            ranked.append(copy)
        ranked.sort(key=lambda x: x["_score"], reverse=True)
        selected = []
        counts: Counter[str] = Counter()
        for item in ranked:
            domain = item.get("domain") or "unknown"
            if counts[domain] >= 2:
                continue
            counts[domain] += 1
            item.pop("_score", None)
            selected.append(item)
            if len(selected) >= self.max_final_sources:
                break
        return selected

    def _corroboration(self, sources: list[dict[str, Any]]) -> dict[str, Any]:
        domains = {x.get("domain", "") for x in sources if x.get("domain")}
        full = sum(1 for x in sources if x.get("fetch_status") == "full_text")
        official = sum(1 for x in sources if self._source_quality(x.get("domain", "")) >= 4.5)
        return {
            "independent_domains": len(domains),
            "full_page_sources": full,
            "high_quality_sources": official,
            "confidence_hint": "strong" if len(domains) >= 4 and full >= 3 else "moderate" if len(domains) >= 2 else "limited",
        }

    def _context(self, query: str, sources: list[dict[str, Any]], steps: list[str], corroboration: dict[str, Any]) -> str:
        now = self._now().isoformat()
        parts = [
            "SILENT AI RESEARCH PACK V4",
            f"Research UTC time: {now}",
            f"Question: {query}",
            "",
            "Evidence quality summary:",
            f"- Independent domains: {corroboration['independent_domains']}",
            f"- Full-page evidence sources: {corroboration['full_page_sources']}",
            f"- High-quality/official sources: {corroboration['high_quality_sources']}",
            f"- Confidence hint: {corroboration['confidence_hint']}",
            "",
            "Research steps:",
            *[f"- {step}" for step in steps],
            "",
            "Evidence:",
        ]
        used = sum(len(x) for x in parts)
        for i, source in enumerate(sources, 1):
            evidence = source.get("page_text") or source.get("body") or ""
            published = source.get("published") or "unknown"
            block = (
                f"\n[{i}] {source.get('page_title') or source.get('title') or 'Untitled'}\n"
                f"Domain: {source.get('domain', '')}\n"
                f"URL: {source.get('final_url') or source.get('url', '')}\n"
                f"Published/seen: {published}\n"
                f"Source type: {source.get('kind', 'unknown')}\n"
                f"Evidence status: {source.get('fetch_status', 'unknown')}\n"
                f"Snippet: {source.get('body', '')}\n"
                f"Page evidence: {evidence}\n"
            )
            if used + len(block) > self.max_context_chars:
                break
            parts.append(block)
            used += len(block)
        parts.extend([
            "",
            "STRICT RESEARCH RULES:",
            "- The system current date is supplied separately; never replace it with a guessed training cutoff date.",
            "- Prefer primary/official sources for official facts and independent reputable reporting for breaking news.",
            "- Cross-check important claims across independent domains.",
            "- A search snippet is evidence of what the index reported, not proof of the entire article.",
            "- Never invent a fact, date, quote, event, source, URL, or number that is absent from the evidence.",
            "- If sources conflict, state the conflict and use publication/update dates to explain it.",
            "- Do not turn an absence of search results into proof that an event did not happen.",
            "- For current events, distinguish publication date from event date.",
            "- Use source URLs in the final answer when making web-grounded claims.",
        ])
        return "\n".join(parts)

    def research(self, query: str) -> dict[str, Any]:
        query = self._clean(query)
        if not query:
            return {"sources": [], "context": "", "research_steps": [], "searched": False}

        started = time.time()
        steps: list[str] = []
        queries = self._build_queries(query)
        all_results: list[dict[str, Any]] = []

        # DDGS queries in parallel.
        with ThreadPoolExecutor(max_workers=min(6, len(queries))) as pool:
            futures = []
            for q, reason in queries:
                futures.append((pool.submit(self._search_ddgs, q, self._recent(query)), q, reason))
            for future, q, reason in futures:
                try:
                    results = future.result()
                except Exception:
                    results = []
                all_results.extend(results)
                steps.append(f"DDGS {reason}: {len(results)} results")

        # Independent news indexes.
        news_queries = [q for q, _ in queries if self._recent(query)][:3]
        with ThreadPoolExecutor(max_workers=4) as pool:
            jobs = []
            for q in news_queries:
                jobs.append((pool.submit(self._search_gdelt, q), "GDELT"))
                jobs.append((pool.submit(self._search_google_news, q), "Google News RSS"))
            for future, name in jobs:
                try:
                    results = future.result()
                except Exception:
                    results = []
                all_results.extend(results)
                steps.append(f"{name}: {len(results)} results")

        # Reference search is useful for factual/entity questions, but is never
        # allowed to dominate current-news evidence.
        wiki_results = self._search_wikipedia(query)
        all_results.extend(wiki_results)
        steps.append(f"Wikipedia reference: {len(wiki_results)} results")

        all_results = self._dedupe(all_results)
        steps.append(f"Unique results after dedupe: {len(all_results)}")

        # Fetch real pages so the model gets evidence, not just search snippets.
        all_results = self._fetch_pages(all_results)
        full = sum(1 for x in all_results if x.get("fetch_status") in {"full_text", "short_text"})
        steps.append(f"Fetched public pages: {full}/{len(all_results)}")

        final = self._rank(all_results, query)
        corroboration = self._corroboration(final)
        steps.append(f"Final evidence set: {len(final)} sources")
        steps.append(f"Research time: {round(time.time() - started, 2)}s")

        public_sources = [
            {
                "title": x.get("page_title") or x.get("title", "Untitled"),
                "url": x.get("final_url") or x.get("url", ""),
                "domain": x.get("domain", ""),
                "published": x.get("published", ""),
                "source_type": x.get("kind", ""),
            }
            for x in final
        ]

        return {
            "sources": public_sources,
            "context": self._context(query, final, steps, corroboration),
            "research_steps": steps,
            "searched": True,
            "result_count": len(final),
            "corroboration": corroboration,
            "generated_at": self._now().isoformat(),
        }

    def search(self, query: str) -> dict[str, Any]:
        return self.research(query)


free_search_service = FreeSearchService()
