"""LLM-powered insights from grouped logs and spikes."""
import json
import logging
from typing import Any, Optional

import requests

from app.config import settings
from app.group import get_groups
from app.schema import InsightsResponse
from app.spikes import get_spikes

logger = logging.getLogger(__name__)

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
GEMINI_REST_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


def _openrouter_generate(prompt: str) -> str:
    """Call OpenRouter (OpenAI-compatible) for summarization. One API for 300+ models."""
    resp = requests.post(
        OPENROUTER_URL,
        headers={
            "Authorization": f"Bearer {settings.openrouter_api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "http://127.0.0.1:5000",
        },
        json={
            "model": settings.openrouter_model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 500,
        },
        timeout=30,
    )
    if not resp.ok:
        try:
            err_body = resp.json()
            logger.warning("OpenRouter %s: %s", resp.status_code, err_body)
        except Exception:
            pass
    resp.raise_for_status()
    data = resp.json()
    choices = data.get("choices") or []
    if not choices:
        raise ValueError(data.get("error") or "No choices in OpenRouter response")
    content = (choices[0].get("message") or {}).get("content") or ""
    return content.strip()


def _gemini_rest_generate(prompt: str) -> str:
    """Call Gemini API via REST (no SDK). Use when SDK import fails (e.g. cryptography DLL on Windows)."""
    url = GEMINI_REST_URL.format(model=settings.gemini_model)
    resp = requests.post(
        url,
        params={"key": settings.gemini_api_key},
        json={"contents": [{"parts": [{"text": prompt}]}]},
        headers={"Content-Type": "application/json"},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    # Response: {"candidates": [{"content": {"parts": [{"text": "..."}]}, ...}]}
    candidates = data.get("candidates") or []
    if not candidates:
        raise ValueError(data.get("promptFeedback") or "No candidates in response")
    parts = (candidates[0].get("content") or {}).get("parts") or []
    if not parts:
        raise ValueError("No parts in candidate")
    return (parts[0].get("text") or "").strip()


def build_context(
    service: Optional[str] = None,
    level: Optional[str] = None,
    since: Optional[str] = None,
    top_groups_limit: int = 10,
) -> tuple[list[dict], list[dict]]:
    """Fetch top groups and current spikes for LLM context."""
    groups_resp = get_groups(service=service, level=level, limit=top_groups_limit, since=since)
    spikes_resp = get_spikes(service=service, level=level)
    top_groups = [
        {
            "group_id": g.group_id,
            "count": g.count,
            "level": g.level,
            "service": g.service,
            "sample_message": g.sample_message,
            "first_seen": g.first_seen.isoformat(),
            "last_seen": g.last_seen.isoformat(),
        }
        for g in groups_resp.groups
    ]
    spikes = [
        {
            "group_id": s.group_id,
            "service": s.service,
            "level": s.level,
            "count": s.count,
            "baseline_avg": s.baseline_avg,
            "ratio": s.ratio,
        }
        for s in spikes_resp.spikes
    ]
    return top_groups, spikes


def _build_insights_prompt(top_groups: list, spikes: list) -> str:
    return f"""You are a log investigation assistant. Based on the following log groups and spikes, write a short human-friendly summary (2-4 sentences) for an on-call engineer. Focus on what is most important: recurring errors, spikes, and suggested attention order.

Top error groups (by count):
{json.dumps(top_groups, indent=2)}

Current spikes (volume above baseline):
{json.dumps(spikes, indent=2)}

Respond with only the summary text, no markdown."""


def get_insights(
    service: Optional[str] = None,
    level: Optional[str] = None,
    since: Optional[str] = None,
) -> InsightsResponse:
    """Generate human-friendly summary using LLM if configured (OpenRouter, Gemini, or OpenAI), else static summary."""
    top_groups, spikes = build_context(service=service, level=level, since=since)
    prompt = _build_insights_prompt(top_groups, spikes)

    # Prefer OpenRouter (one API, 300+ models) if key is set
    if settings.openrouter_api_key:
        try:
            summary = _openrouter_generate(prompt)
        except Exception as e:
            logger.warning("OpenRouter API failed: %s", e, exc_info=True)
            summary = (
                f"OpenRouter error: {e}. Top groups: {len(top_groups)}; Spikes: {len(spikes)}."
            )
    # Fallback: Gemini (free tier)
    elif settings.gemini_api_key:
        try:
            import google.generativeai as genai
        except ImportError as e:
            logger.warning("Gemini SDK import failed (%s), using REST fallback", e)
            try:
                summary = _gemini_rest_generate(prompt)
            except Exception as rest_e:
                logger.warning("Gemini REST fallback failed: %s", rest_e, exc_info=True)
                summary = (
                    f"Gemini API error: {rest_e}. Top groups: {len(top_groups)}; Spikes: {len(spikes)}."
                )
        else:
            try:
                genai.configure(api_key=settings.gemini_api_key)
                model = genai.GenerativeModel(settings.gemini_model)
                resp = model.generate_content(prompt)
                summary = (resp.text or "").strip()
            except Exception as e:
                logger.warning("Gemini API call failed: %s", e, exc_info=True)
                summary = f"Gemini API error: {e}. Top groups: {len(top_groups)}; Spikes: {len(spikes)}."
    elif settings.openai_api_key:
        try:
            from openai import OpenAI
            client = OpenAI(api_key=settings.openai_api_key)
            resp = client.chat.completions.create(
                model=settings.openai_model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=500,
            )
            summary = (resp.choices[0].message.content or "").strip()
        except Exception as e:
            err_str = str(e).lower()
            if "429" in err_str or "quota" in err_str or "insufficient_quota" in err_str:
                summary = (
                    "OpenAI quota exceeded (429). Use GEMINI_API_KEY (free at aistudio.google.com) or remove keys for text-only summary. "
                    f"Top groups: {len(top_groups)}; Spikes: {len(spikes)}."
                )
            else:
                summary = (
                    f"LLM insights unavailable: {e}. Set OPENROUTER_API_KEY (openrouter.ai/settings/keys) for summarization. "
                    f"Top groups: {len(top_groups)}; Spikes: {len(spikes)}."
                )
    else:
        parts = []
        if top_groups:
            parts.append(f"Top {len(top_groups)} error groups by volume.")
            for g in top_groups[:3]:
                parts.append(f"  - [{g['service']}] {g['level']}: {g['count']}x — {g['sample_message'][:80]}...")
        if spikes:
            parts.append(f"{len(spikes)} spike(s) detected above baseline.")
        summary = " ".join(parts) if parts else "No log groups or spikes in the selected range."

    return InsightsResponse(summary=summary, top_groups=top_groups, spikes=spikes)
