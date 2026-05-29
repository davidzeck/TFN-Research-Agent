"""
I/O Agent — fetches sector news via Gemini Search grounding (primary) or
DuckDuckGo (fallback when Gemini is rate-limited), then delivers the Excel
workbook via Gmail SMTP + App Password.
"""

import logging
import os
import re
import smtplib
import time
from datetime import datetime
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from dotenv import load_dotenv
from google import genai
from google.genai import types

from config import (
    GMAIL_APP_PASSWORD,
    GMAIL_SENDER,
    MODEL,
    RECIPIENTS,
    SECTOR_SOURCES,
)

load_dotenv()

logger = logging.getLogger(__name__)

_gemini = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

_SEARCH_CONFIG = types.GenerateContentConfig(
    tools=[types.Tool(google_search=types.GoogleSearch())],
)

_RATE_LIMIT_CODES = {429, 503}


def _is_rate_limited(exc: Exception) -> bool:
    msg = str(exc)
    return any(str(c) in msg for c in _RATE_LIMIT_CODES) or "RESOURCE_EXHAUSTED" in msg or "UNAVAILABLE" in msg


def _parse_retry_delay(exc: Exception) -> int:
    match = re.search(r"retry[^\d]*(\d+)[\.,]?\d*s", str(exc), re.IGNORECASE)
    return int(match.group(1)) if match else 0


# ── Gemini search ─────────────────────────────────────────────────────────────

def _gemini_search(sector: str, search_terms: list[str]) -> list[dict]:
    terms_str = " OR ".join(f'"{t}"' for t in search_terms[:3])
    query = (
        f"Find the 3 most recent news articles (last 7 days) about Kenya's {sector} "
        f"export sector. Focus on: {terms_str}. "
        f"For each article give: headline, a 2-3 sentence summary of what happened, "
        f"and why it matters to Kenyan exporters. Number each article 1. 2. 3."
    )
    response = _gemini.models.generate_content(
        model=MODEL, contents=query, config=_SEARCH_CONFIG
    )
    text = response.text or ""
    if not text.strip():
        return []

    sources = []
    try:
        chunks = response.candidates[0].grounding_metadata.grounding_chunks or []
        for chunk in chunks:
            if chunk.web and chunk.web.uri:
                sources.append({"url": chunk.web.uri, "name": chunk.web.title or chunk.web.uri})
    except AttributeError:
        pass

    logger.info("Gemini search: %d source(s) for %s (%d chars)", len(sources), sector, len(text))

    paragraphs = [p.strip() for p in re.split(r"(?m)^\d+\.\s+", text) if p.strip()]
    articles = []
    for i, para in enumerate(paragraphs):
        src = sources[i] if i < len(sources) else (sources[0] if sources else {})
        articles.append({
            "title": f"{sector} — News Item {i + 1}",
            "body_text": para[:1500],
            "source_name": src.get("name", "Gemini Search"),
            "url": src.get("url", ""),
            "date": datetime.now().strftime("%Y-%m-%d"),
            "expected_sector": sector,
            "search_provider": "gemini",
        })
    return articles or [{
        "title": f"{sector} — Sector News",
        "body_text": text[:1500],
        "source_name": sources[0].get("name", "Gemini Search") if sources else "Gemini Search",
        "url": sources[0].get("url", "") if sources else "",
        "date": datetime.now().strftime("%Y-%m-%d"),
        "expected_sector": sector,
        "search_provider": "gemini",
    }]


# ── DuckDuckGo fallback ───────────────────────────────────────────────────────

_DDG_EXCLUDE = "-site:wikipedia.org -site:worldatlas.com -site:britannica.com -site:cia.gov"

def _ddg_search(sector: str, search_terms: list[str]) -> list[dict]:
    from ddgs import DDGS
    # Use the two most specific search terms for a tighter query
    terms = " ".join(f'"{t}"' for t in search_terms[:2]) if search_terms else f'"{sector} Kenya"'
    query = f"{terms} export news 2025 {_DDG_EXCLUDE}"
    articles = []
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=4, timelimit="m"))  # last month
        # Filter out generic country pages
        _SKIP = {"wikipedia", "worldatlas", "britannica", "cia.gov", "countrycode"}
        results = [r for r in results if not any(s in r.get("href", "").lower() for s in _SKIP)]
        for r in results:
            articles.append({
                "title": r.get("title", f"{sector} news"),
                "body_text": r.get("body", "")[:1500],
                "source_name": r.get("source", r.get("href", "DuckDuckGo").split("/")[2]),
                "url": r.get("href", ""),
                "date": datetime.now().strftime("%Y-%m-%d"),
                "expected_sector": sector,
                "search_provider": "duckduckgo",
            })
        logger.info("DDG fallback: %d result(s) for %s", len(articles), sector)
    except Exception as exc:
        logger.warning("DuckDuckGo search failed for %s: %s", sector, exc)
    return articles


# ── Public fetch API ──────────────────────────────────────────────────────────

def _is_daily_quota_exhausted(exc: Exception) -> bool:
    msg = str(exc)
    return "PerDay" in msg or ("limit" in msg and "day" in msg.lower())


def _fetch_sector_news(sector: str, search_terms: list[str]) -> list[dict]:
    """Try Gemini search first; fall back to DuckDuckGo on any rate-limit or error."""
    try:
        return _gemini_search(sector, search_terms)
    except Exception as exc:
        if _is_rate_limited(exc):
            if _is_daily_quota_exhausted(exc):
                logger.warning("Gemini daily quota exhausted for %s — using DuckDuckGo", sector)
            else:
                delay = _parse_retry_delay(exc)
                logger.warning("Gemini search rate-limited for %s — using DuckDuckGo%s",
                               sector, f" (retry delay was {delay}s)" if delay else "")
        else:
            logger.warning("Gemini search error for %s: %s", sector, str(exc)[:120])
        return _ddg_search(sector, search_terms)


def fetch_all_articles() -> list[dict]:
    """Fetch news for all 10 sectors. Gemini primary, DuckDuckGo fallback."""
    all_articles = []
    for sector, cfg in SECTOR_SOURCES.items():
        articles = _fetch_sector_news(sector, cfg.get("search_terms", [sector]))
        all_articles.extend(articles)
        logger.info("Sector '%s': %d article(s)", sector, len(articles))
    logger.info("I/O Agent: %d total articles", len(all_articles))
    return all_articles


# ── Email delivery ────────────────────────────────────────────────────────────

def deliver_workbook(workbook_path: str) -> bool:
    """Send the Excel workbook to all configured recipients via Gmail SMTP."""
    if not os.path.exists(workbook_path):
        logger.error("Workbook not found at %s", workbook_path)
        return False
    if os.path.getsize(workbook_path) == 0:
        logger.error("Workbook at %s is empty", workbook_path)
        return False
    if not RECIPIENTS:
        logger.error("No recipients configured in .env")
        return False
    if not GMAIL_SENDER or not GMAIL_APP_PASSWORD:
        logger.error("Gmail credentials missing — check GMAIL_SENDER and GMAIL_APP_PASSWORD in .env")
        return False

    today = datetime.now().strftime("%Y-%m-%d")
    msg = MIMEMultipart()
    msg["From"] = GMAIL_SENDER
    msg["To"] = ", ".join(RECIPIENTS)
    msg["Subject"] = f"TFN Sector Intelligence Report — {today}"
    msg.attach(MIMEText(
        "Please find attached the TFN Sector Intelligence workbook.\n\n"
        "Kenya's 10 export sectors — colour-coded by impact: "
        "Red = High, Orange = Medium, Green = Low.\n\n"
        "— TFN Intelligence System",
        "plain",
    ))

    with open(workbook_path, "rb") as f:
        part = MIMEBase("application", "octet-stream")
        part.set_payload(f.read())
    encoders.encode_base64(part)
    part.add_header("Content-Disposition", f'attachment; filename="{os.path.basename(workbook_path)}"')
    msg.attach(part)

    for attempt in (1, 2):
        try:
            with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
                server.login(GMAIL_SENDER, GMAIL_APP_PASSWORD)
                server.sendmail(GMAIL_SENDER, RECIPIENTS, msg.as_string())
            logger.info("Email sent to %s at %s", ", ".join(RECIPIENTS), datetime.now().strftime("%H:%M:%S"))
            return True
        except Exception as exc:
            logger.warning("Email attempt %d failed: %s", attempt, exc)
            if attempt == 1:
                time.sleep(60)

    logger.error("Email delivery failed after 2 attempts")
    return False
