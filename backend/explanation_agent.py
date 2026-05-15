"""
explanation_agent.py — N7 (optional, off the critical path).

Per design (DESIGN/DESIGN1/design-1-conceptual-design.md):
  "ACTUS-Mentor's 7-agent RAG pipeline answers ACTUS-standard questions grounded in the standard.
   A side assistant feature, not load-bearing."

This is NOT part of the main hedge pipeline. It's invoked separately when a user asks a follow-up
question about why a rate-reset clause behaves a certain way, etc.

Current status: NotImplementedError — the ACTUS-Mentor RAG endpoint shape is not yet verified
(see DESIGN/DESIGN1/design-1-detailed-design.md §6, note 3: backend liveness on :8000 not pinged).
"""

from __future__ import annotations

from typing import Any


def ask_explanation(question: str, context: dict[str, Any] | None = None) -> str:
    """N7 — reasoning (ACTUS-Mentor RAG pipeline).

    Args:
        question: free-text user follow-up about an ACTUS standard concept.
        context:  optional state from the most recent run (recommendation, simulation result).

    Returns:
        Plain-text grounded answer from the ACTUS-Mentor RAG pipeline.

    Raises:
        NotImplementedError: the ACTUS-Mentor backend RAG endpoint is not yet pinged.
            Verification required per DESIGN/DESIGN1/design-1-detailed-design.md §6 note 3
            (backend liveness on :8000) before this can be wired up.
    """
    raise NotImplementedError(
        "Explanation Agent (N7) requires verification of ACTUS-Mentor RAG endpoint. "
        "See DESIGN/DESIGN1/design-1-detailed-design.md §6 note 3. "
        "To wire up: confirm backend liveness on :8000, then implement HTTP call to "
        "the ACTUS-Mentor /ask or equivalent RAG endpoint."
    )
