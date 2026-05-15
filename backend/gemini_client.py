"""
gemini_client.py — Single source of truth for all Gemini reasoning calls.

Centralizes:
  • API client construction (uses GEMINI_API_KEY from config)
  • Model selection (GEMINI_MODEL)
  • Structured-output (JSON) prompting
  • Retry/timeout policy

No fallbacks: if Gemini returns malformed JSON or fails, the error propagates.
The Input-Validator downstream will catch malformed extraction and trigger the bounded retry edge.
"""

from __future__ import annotations

import json
from typing import Any

import google.generativeai as genai

from config import settings


# Initialize once at import (fails fast if API key invalid format)
genai.configure(api_key=settings.gemini_api_key)


class GeminiError(Exception):
    """Raised when a Gemini call fails. Never silently swallowed."""


def _build_model(system_instruction: str | None = None):
    """Construct a Gemini model handle with optional system instruction."""
    return genai.GenerativeModel(
        model_name=settings.gemini_model,
        system_instruction=system_instruction,
    )


def generate_text(
    prompt: str,
    *,
    system_instruction: str | None = None,
    temperature: float = 0.2,
) -> str:
    """Plain-text generation. Used by Interpretation agent for the 'why' narrative."""
    model = _build_model(system_instruction)
    try:
        response = model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(
                temperature=temperature,
            ),
        )
    except Exception as e:
        raise GeminiError(f"Gemini generate_text failed: {e}") from e

    if not response.candidates or not response.candidates[0].content.parts:
        raise GeminiError("Gemini returned an empty response (no candidates)")

    return response.text


def extract_structured(
    prompt: str,
    *,
    response_schema: dict[str, Any],
    system_instruction: str | None = None,
    temperature: float = 0.0,
) -> dict[str, Any]:
    """Structured-output generation.

    Uses Gemini's response_mime_type='application/json' + response_schema to force
    a JSON object matching the schema. If Gemini returns invalid JSON, raises GeminiError
    — no silent recovery. The downstream Validator catches malformed extraction.

    Args:
        prompt: the user message
        response_schema: a JSON schema (Pydantic-style dict) describing the expected output
        system_instruction: optional system-level instruction
        temperature: 0.0 by default for extraction (deterministic per call)

    Returns:
        Parsed JSON object (dict) matching the schema.
    """
    model = _build_model(system_instruction)
    try:
        response = model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(
                temperature=temperature,
                response_mime_type="application/json",
                response_schema=response_schema,
            ),
        )
    except Exception as e:
        raise GeminiError(f"Gemini extract_structured failed: {e}") from e

    if not response.candidates or not response.candidates[0].content.parts:
        raise GeminiError("Gemini returned an empty response (no candidates)")

    raw = response.text
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        raise GeminiError(
            f"Gemini returned non-JSON despite response_mime_type='application/json'. "
            f"Raw: {raw[:500]}"
        ) from e
