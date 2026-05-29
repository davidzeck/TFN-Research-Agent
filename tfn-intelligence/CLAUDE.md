# CLAUDE.md

## Project: TFN Sector Intelligence Automation

## What this is
A Python agentic workflow that collects Kenyan export sector intelligence,
summarizes it using the Anthropic Claude API, writes it into an Excel workbook,
and emails it every Friday to recipients.

## Architecture
- orchestrator.py — controls agent sequence, scheduling
- agents/io_agent.py — fetches articles (trafilatura + feedparser) + sends Gmail via SMTP
- agents/summarizer_agent.py — calls Claude API using tool_use for structured JSON output
- agents/excel_agent.py — writes/deduplicates rows into openpyxl workbook

## Tech stack
- Python 3.11
- google-generativeai SDK (gemini-1.5-flash model) with function calling for structured output
- trafilatura for clean article body extraction
- requests for HTML fetching, feedparser for RSS
- openpyxl for Excel
- smtplib + Gmail App Password for email delivery
- python-dotenv for env vars

## Key rules
- All API keys come from .env via dotenv — never hardcode
- Every agent must log its actions to both console and logs/run_YYYY-MM-DD.log
- Excel workbook path: data/TFN_Export_Intelligence.xlsx
- Deduplication: md5 hash of article URL (not headline — headlines vary between runs)
- Impact levels: High / Medium / Low only
- Gemini API model: gemini-2.0-flash (key in GEMINI_API_KEY env var)
- Fetch strategy: Gemini Google Search grounding (no web scraping) — io_agent calls Gemini with google_search tool per sector

## Sectors (10 total)
Tea, Coffee, Flowers, Avocado, Apparel & Textiles,
Macadamia Nuts, French Beans & Snow Peas, Mangoes,
Leather & Leather Products, Transport & Logistics

## Commands
- python orchestrator.py --run-now    # single run
- python orchestrator.py --schedule   # start scheduler (for VPS)
- python orchestrator.py --test-email # test email delivery only
