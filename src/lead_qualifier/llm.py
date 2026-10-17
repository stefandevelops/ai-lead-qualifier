from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass

import httpx

from lead_qualifier.icp import ICP
from lead_qualifier.models import Enrichment, InboundLead, ScoreResult


@dataclass
class LLMConfig:
    provider: str
    api_key: str
    model: str
    base_url: str


def detect_llm() -> LLMConfig | None:
    openai_key = os.getenv("OPENAI_API_KEY", "").strip()
    gemini_key = os.getenv("GEMINI_API_KEY", "").strip() or os.getenv("GOOGLE_API_KEY", "").strip()

    if openai_key:
        return LLMConfig(
            provider="openai",
            api_key=openai_key,
            model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            base_url=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/"),
        )
    if gemini_key:
        return LLMConfig(
            provider="gemini",
            api_key=gemini_key,
            model=os.getenv("GEMINI_MODEL", "gemini-2.0-flash"),
            base_url="https://generativelanguage.googleapis.com/v1beta",
        )
    return None


def _prompt(lead: InboundLead, enrichment: Enrichment, scoring: ScoreResult, icp: ICP) -> str:
    seller = icp.seller
    return f"""Write a short first-touch sales email. Draft only — it will not be sent.

Seller: {seller.sender_name}, {seller.sender_title} at {seller.name}.
Product: {seller.product}.
Lead: {lead.full_name}, {lead.title} at {lead.company} ({enrichment.industry_norm or lead.industry}, {lead.employees or "unknown"} employees, {enrichment.region or lead.country}).
Inbound source: {lead.source}
Their note: {lead.notes}
Score: {scoring.score} ({scoring.tier})
Why: {scoring.explanation}

Rules:
- 90-130 words, no exclamation marks, no invented facts.
- Reference one concrete detail from their note or title.
- Soft ask for 15 minutes. If the lead is cold, keep it low-pressure and say why you still wrote.
- Sign off as {seller.sender_name}.
- Return JSON only: {{"subject": "...", "body": "..."}}
"""


def _parse_json(text: str) -> dict:
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", cleaned)
    return json.loads(cleaned)


def generate_with_llm(
    lead: InboundLead,
    enrichment: Enrichment,
    scoring: ScoreResult,
    icp: ICP,
    config: LLMConfig | None = None,
    timeout: float = 20.0,
) -> tuple[str, str]:
    cfg = config or detect_llm()
    if cfg is None:
        raise RuntimeError("No LLM API key is set.")

    prompt = _prompt(lead, enrichment, scoring, icp)

    if cfg.provider == "openai":
        payload = {
            "model": cfg.model,
            "temperature": 0.4,
            "messages": [
                {"role": "system", "content": "You write concise B2B sales drafts. Reply with JSON only."},
                {"role": "user", "content": prompt},
            ],
        }
        response = httpx.post(
            f"{cfg.base_url}/chat/completions",
            headers={"Authorization": f"Bearer {cfg.api_key}"},
            json=payload,
            timeout=timeout,
        )
        response.raise_for_status()
        text = response.json()["choices"][0]["message"]["content"]
    else:
        response = httpx.post(
            f"{cfg.base_url}/models/{cfg.model}:generateContent",
            params={"key": cfg.api_key},
            json={"contents": [{"parts": [{"text": prompt}]}]},
            timeout=timeout,
        )
        response.raise_for_status()
        text = response.json()["candidates"][0]["content"]["parts"][0]["text"]

    parsed = _parse_json(text)
    subject = str(parsed.get("subject") or "").strip()
    body = str(parsed.get("body") or "").strip()
    if not subject or not body:
        raise ValueError("LLM response was missing subject or body.")
    return subject, body
