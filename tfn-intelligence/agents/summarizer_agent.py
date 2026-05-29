"""
Summarizer Agent — structures raw article text into intelligence rows.
Primary: Gemini 2.5 Flash with function calling.
Fallback: Groq llama-3.3-70b when Gemini is rate-limited.
"""

import json
import logging
import os
import re
import time

from dotenv import load_dotenv
from google import genai
from google.genai import types
from groq import Groq

from config import GROQ_MODEL, MODEL, SECTORS

load_dotenv()

logger = logging.getLogger(__name__)

_gemini = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
_groq = Groq(api_key=os.getenv("GROQ_API_KEY"))

# ── Shared schema ─────────────────────────────────────────────────────────────

_SYSTEM_PROMPT = (
    "You are an export intelligence analyst focused on Kenyan exporters. "
    "Read article text and extract structured intelligence. "
    "Be factual and concise.\n\n"
    "Impact rules:\n"
    "  High   = regulation change, ban, levy, market closure, urgent disruption\n"
    "  Medium = price trend, forecast, planning signal, competitive shift\n"
    "  Low    = background context, slow-moving information\n\n"
    f"Valid sectors: {', '.join(SECTORS)}"
)

_FIELD_DESCRIPTIONS = {
    "headline": "Short factual headline, max 12 words",
    "summary": "Exactly 2 sentences explaining what happened",
    "sector": f"One of: {', '.join(SECTORS)}",
    "exporter_implication": "One sentence on what this means for Kenyan exporters",
    "impact": "One of: High, Medium, Low",
}

# ── Gemini function-call config ───────────────────────────────────────────────

_GEMINI_TOOL = types.Tool(function_declarations=[
    types.FunctionDeclaration(
        name="extract_intelligence",
        description="Extract structured export intelligence from an article.",
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "headline": types.Schema(type=types.Type.STRING, description=_FIELD_DESCRIPTIONS["headline"]),
                "summary": types.Schema(type=types.Type.STRING, description=_FIELD_DESCRIPTIONS["summary"]),
                "sector": types.Schema(type=types.Type.STRING, enum=SECTORS, description=_FIELD_DESCRIPTIONS["sector"]),
                "exporter_implication": types.Schema(type=types.Type.STRING, description=_FIELD_DESCRIPTIONS["exporter_implication"]),
                "impact": types.Schema(type=types.Type.STRING, enum=["High", "Medium", "Low"], description=_FIELD_DESCRIPTIONS["impact"]),
            },
            required=["headline", "summary", "sector", "exporter_implication", "impact"],
        ),
    )
])

_GEMINI_CONFIG = types.GenerateContentConfig(
    system_instruction=_SYSTEM_PROMPT,
    tools=[_GEMINI_TOOL],
    tool_config=types.ToolConfig(
        function_calling_config=types.FunctionCallingConfig(mode="ANY")
    ),
)

# ── Groq tool schema (OpenAI-compatible) ─────────────────────────────────────

_GROQ_TOOL = {
    "type": "function",
    "function": {
        "name": "extract_intelligence",
        "description": "Extract structured export intelligence from an article.",
        "parameters": {
            "type": "object",
            "properties": {
                "headline": {"type": "string", "description": _FIELD_DESCRIPTIONS["headline"]},
                "summary": {"type": "string", "description": _FIELD_DESCRIPTIONS["summary"]},
                "sector": {"type": "string", "enum": SECTORS, "description": _FIELD_DESCRIPTIONS["sector"]},
                "exporter_implication": {"type": "string", "description": _FIELD_DESCRIPTIONS["exporter_implication"]},
                "impact": {"type": "string", "enum": ["High", "Medium", "Low"], "description": _FIELD_DESCRIPTIONS["impact"]},
            },
            "required": ["headline", "summary", "sector", "exporter_implication", "impact"],
        },
    },
}

# ── Helpers ───────────────────────────────────────────────────────────────────

def _is_rate_limited(exc: Exception) -> bool:
    msg = str(exc)
    return "429" in msg or "RESOURCE_EXHAUSTED" in msg or "503" in msg or "UNAVAILABLE" in msg


def _is_daily_quota_exhausted(exc: Exception) -> bool:
    """True when the per-day quota is gone — no point retrying Gemini today."""
    msg = str(exc)
    return "PerDay" in msg or "per_day" in msg.lower() or ("limit" in msg and "20" in msg and "PerDay" not in msg and "day" in msg.lower())


def _parse_retry_delay(exc: Exception) -> int:
    match = re.search(r"retry[^\d]*(\d+)[\.,]?\d*s", str(exc), re.IGNORECASE)
    return int(match.group(1)) if match else 0


def _build_prompt(article: dict) -> str:
    return (
        f"Title: {article.get('title', '')}\n"
        f"Source: {article.get('source_name', '')} (via {article.get('search_provider', 'search')})\n"
        f"Date: {article.get('date', '')}\n"
        f"Expected sector: {article.get('expected_sector', '')}\n\n"
        f"{article.get('body_text', '')}"
    )


def _build_row(data: dict, article: dict) -> dict:
    return {
        "headline": data.get("headline", ""),
        "summary": data.get("summary", ""),
        "sector": data.get("sector", article.get("expected_sector", "")),
        "exporter_implication": data.get("exporter_implication", ""),
        "impact": data.get("impact", "Low"),
        "source": article.get("source_name", ""),
        "url": article.get("url", ""),
        "date": article.get("date", ""),
    }


# ── Gemini summarizer ─────────────────────────────────────────────────────────

def _summarize_gemini(article: dict) -> dict | None:
    prompt = f"Extract intelligence from this article:\n\n{_build_prompt(article)}"
    response = _gemini.models.generate_content(model=MODEL, contents=prompt, config=_GEMINI_CONFIG)
    func_call = next(
        (p.function_call for p in response.candidates[0].content.parts if p.function_call),
        None,
    )
    if not func_call:
        return None
    row = _build_row(dict(func_call.args), article)
    logger.info("Gemini → [%s] %s (impact=%s)", row["sector"], row["headline"][:60], row["impact"])
    return row


# ── Groq fallback summarizer ──────────────────────────────────────────────────

def _summarize_groq(article: dict) -> dict | None:
    prompt = f"Extract intelligence from this article:\n\n{_build_prompt(article)}"
    response = _groq.chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        tools=[_GROQ_TOOL],
        tool_choice={"type": "function", "function": {"name": "extract_intelligence"}},
        max_tokens=512,
    )
    tool_calls = response.choices[0].message.tool_calls
    if not tool_calls:
        return None
    data = json.loads(tool_calls[0].function.arguments)
    row = _build_row(data, article)
    logger.info("Groq   → [%s] %s (impact=%s)", row["sector"], row["headline"][:60], row["impact"])
    return row


# ── Public API ────────────────────────────────────────────────────────────────

def process(article: dict) -> dict | None:
    """
    Summarize one article. Tries Gemini up to 2 times; if rate-limited,
    switches to Groq. Returns None only if both providers fail.
    """
    title = article.get("title", "unknown")

    # --- Gemini: one attempt, max 20s wait, then hand off ---
    try:
        return _summarize_gemini(article)
    except Exception as exc:
        if _is_rate_limited(exc):
            if _is_daily_quota_exhausted(exc):
                logger.warning("[GEMINI] Daily quota exhausted for '%s' — switching to Groq", title)
            else:
                delay = min(_parse_retry_delay(exc), 20)
                logger.warning("[GEMINI] Rate-limited for '%s' — waiting %ds then trying Groq", title, delay)
                if delay:
                    time.sleep(delay)
        else:
            logger.warning("[GEMINI] Error for '%s': %s", title, str(exc)[:120])

    # --- Groq fallback: 3 attempts, no sleep ---
    for attempt in range(1, 4):
        try:
            return _summarize_groq(article)
        except Exception as exc:
            logger.warning("[GROQ] Error (attempt %d/3) for '%s': %s", attempt, title, str(exc)[:80])

    logger.error("[QUOTA LIMIT] Both Gemini and Groq hit limits for '%s' — skipping", title)
    return None
