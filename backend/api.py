"""
api.py — FastAPI routes + Pydantic request/response schemas.

The full backend contract per DESIGN/DESIGN1/design-1-project-structure.md §7:
  POST /run      — start a hedge analysis
  GET  /trace    — SSE stream of agent progress for a thread_id
  POST /resume   — resume a crashed run
  GET  /history  — past recommendations + drift

Routes and schemas are kept in a single file because they always change together.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from typing import Any, AsyncGenerator

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

import memory_store
from explanation_agent import ask_explanation


# ───────────────────────────────────────────────────────────────────────
# Schemas
# ───────────────────────────────────────────────────────────────────────

class SuppliedSofrPathPoint(BaseModel):
    """One point on a caller-supplied SOFR path.

    `time` is an ISO 8601 timestamp string (e.g. '2026-02-28T00:00:00'), matching
    the V1 SOFR_PATH shape returned by DRAPS for the derived path.
    `value` is the rate as a decimal (e.g. 0.0602 for 6.02%).
    """
    time: str = Field(..., min_length=1)
    value: float


class Supplied(BaseModel):
    """Caller-supplied SOFR path + fixed swap rates (Iteration 3, Problem A).

    When this block is present on POST /run, the V2 graph routes via
    `mode='supplied'`: the profile resolver synthesizes a supplied-mode profile,
    the composer copies this block verbatim into `knot_payload['supplied']`,
    and the simulation node honors these numbers instead of derivation.

    The shape mirrors the composer's `SUPPLIED_REQUIRED_KEYS` contract — the
    validation here is the first line of defense; the composer re-validates
    so the contract is enforced at both the API edge and the graph boundary.
    """
    sofr_path: list[SuppliedSofrPathPoint] = Field(
        ...,
        min_length=1,
        description="Non-empty list of {time, value} points. Caller is responsible "
                    "for ordering and frequency; the composer does not re-sort or interpolate.",
    )
    swap_now_fixed: float = Field(..., description="Fixed rate for the 'swap now' (B) scenario, as a decimal.")
    swap_later_fixed: float = Field(..., description="Fixed rate for the 'swap later' (C) scenario, as a decimal.")


class RunRequest(BaseModel):
    prompt: str = Field(..., min_length=1, description="Natural-language hedging question")
    loan_doc: str = Field(..., min_length=1, description="Private loan document content (text)")
    thread_id: str | None = Field(
        default=None,
        description="Optional thread_id for resume. If absent, server generates one.",
    )
    supplied: Supplied | None = Field(
        default=None,
        description="Optional. If present, the request is a supplied-mode run: "
                    "the caller is asserting a pre-computed SOFR path and fixed "
                    "swap rates that should flow through verbatim. The profile "
                    "resolver synthesizes a supplied-mode profile when this is set.",
    )


class RunResponse(BaseModel):
    thread_id: str
    status: str  # "started"


class ResumeRequest(BaseModel):
    thread_id: str = Field(..., min_length=1)


class ResumeResponse(BaseModel):
    thread_id: str
    resuming_from_node: str


class HistoryEntry(BaseModel):
    record_id: str
    thread_id: str
    created_at: str
    recommendation: dict[str, Any]
    drift: dict[str, Any] | None = None


class ExplainRequest(BaseModel):
    question: str = Field(..., min_length=1)
    record_id: str | None = None


# ───────────────────────────────────────────────────────────────────────
# Router
# ───────────────────────────────────────────────────────────────────────

router = APIRouter()


def _get_app(request: Request):
    """Pull the compiled LangGraph app off app state (set in main.py lifespan)."""
    app = getattr(request.app.state, "graph_app", None)
    if app is None:
        raise HTTPException(status_code=500, detail="Graph not initialized")
    return app


def _get_runs(request: Request) -> dict[str, asyncio.Task]:
    """Pull the in-memory run registry off app state."""
    runs = getattr(request.app.state, "runs", None)
    if runs is None:
        raise HTTPException(status_code=500, detail="Run registry not initialized")
    return runs


# ───────────────────────────────────────────────────────────────────────
# POST /run
# ───────────────────────────────────────────────────────────────────────

def _build_initial_state(body: RunRequest, thread_id: str) -> dict[str, Any]:
    """Translate a /run request body into the graph's initial state.

    Extracted from the route handler so it can be unit-tested without spinning up
    the FastAPI app, the SQLite checkpointer, or the LangGraph compile step.

    Iteration-3 contract: when `body.supplied` is present, lift it into
    `state['supplied']` as a plain dict (Pydantic → dict via model_dump).
    Otherwise the state shape is identical to the V1 baseline.
    """
    initial_state: dict[str, Any] = {
        "prompt": body.prompt,
        "private_loan_doc": body.loan_doc,
        "thread_id": thread_id,
        "retry_count": 0,
        "validation_errors": [],
        "audit_log": [],
    }
    if body.supplied is not None:
        # Pydantic → plain dict matches the composer's expected shape exactly.
        initial_state["supplied"] = body.supplied.model_dump()
    return initial_state


@router.post("/run", response_model=RunResponse)
async def run(request: Request, body: RunRequest) -> RunResponse:
    """Start a new hedge analysis. Returns immediately; client polls via /trace."""
    graph_app = _get_app(request)
    runs = _get_runs(request)

    thread_id = body.thread_id or f"thread-{uuid.uuid4().hex[:12]}"
    config = {"configurable": {"thread_id": thread_id}}

    initial_state = _build_initial_state(body, thread_id)

    # Fire-and-forget the workflow. /trace will read the stream of checkpoints.
    task = asyncio.create_task(_invoke_graph(graph_app, initial_state, config))
    runs[thread_id] = task

    return RunResponse(thread_id=thread_id, status="started")


async def _invoke_graph(graph_app, initial_state: dict, config: dict) -> None:
    """Run the graph to completion in the background.

    On any unexpected exception, log full traceback to terminal. The /trace
    SSE handler reads the task state directly (via the runs registry) and
    surfaces the exception to the UI as a 'done' event with failure details.
    """
    import logging
    import traceback
    logger = logging.getLogger("hedge_advisor")
    try:
        await graph_app.ainvoke(initial_state, config=config)
    except Exception:
        tb = traceback.format_exc()
        thread_id = config.get("configurable", {}).get("thread_id")
        logger.error("Graph crashed for thread %s:\n%s", thread_id, tb)
        # Re-raise so the task's exception is preserved (task.exception() will
        # return it). The /trace handler reads this and forwards to the UI.
        raise


# ───────────────────────────────────────────────────────────────────────
# GET /trace  (SSE)
# ───────────────────────────────────────────────────────────────────────

@router.get("/trace")
async def trace(request: Request, thread_id: str = Query(..., min_length=1)):
    """Stream agent progress for a given thread_id via Server-Sent Events.

    Each event is the latest audit_log entry that has not yet been streamed.
    Closes when the run terminates (memory_record_id set OR failure set OR
    background task crashed with an exception).
    """
    graph_app = _get_app(request)
    runs = _get_runs(request)
    config = {"configurable": {"thread_id": thread_id}}

    async def stream() -> AsyncGenerator[dict, None]:
        seen = 0
        while True:
            if await request.is_disconnected():
                break

            # Check if the background task crashed (uncaught exception)
            task = runs.get(thread_id)
            if task is not None and task.done():
                exc = task.exception()
                if exc is not None:
                    # Re-fetch state one more time to catch any audit entries
                    # that were written just before the crash
                    snapshot = await graph_app.aget_state(config)
                    state = (snapshot.values if snapshot else {}) or {}
                    audit = state.get("audit_log") or []
                    while seen < len(audit):
                        entry = audit[seen]
                        seen += 1
                        yield {"event": "node", "data": json.dumps(entry, default=str)}
                    # Find last node name from audit if available
                    last_node = audit[-1].get("node", "unknown") if audit else "unknown"
                    yield {
                        "event": "done",
                        "data": json.dumps(
                            {
                                "status": "failed",
                                "thread_id": thread_id,
                                "failure": {
                                    "reason": "backend_exception",
                                    "errors": [f"{type(exc).__name__}: {str(exc)[:800]}"],
                                    "retry_count": 0,
                                    "last_node": last_node,
                                },
                            },
                            default=str,
                        ),
                    }
                    break

            snapshot = await graph_app.aget_state(config)
            if snapshot is None:
                # No checkpoints yet; wait briefly.
                await asyncio.sleep(0.2)
                continue

            state = snapshot.values or {}
            audit = state.get("audit_log") or []

            # Stream any new audit entries
            while seen < len(audit):
                entry = audit[seen]
                seen += 1
                yield {"event": "node", "data": json.dumps(entry, default=str)}

            # Terminal conditions: success or honest failure
            if state.get("memory_record_id"):
                yield {
                    "event": "done",
                    "data": json.dumps(
                        {
                            "status": "success",
                            "thread_id": thread_id,
                            "recommendation": state.get("recommendation"),
                            "memory_record_id": state.get("memory_record_id"),
                            "simulation_result": state.get("simulation_result"),
                            "disclosure_doc": state.get("disclosure_doc"),
                        },
                        default=str,
                    ),
                }
                break

            if state.get("failure"):
                yield {
                    "event": "done",
                    "data": json.dumps(
                        {"status": "failed", "thread_id": thread_id, "failure": state["failure"]},
                        default=str,
                    ),
                }
                break

            await asyncio.sleep(0.3)

    return EventSourceResponse(stream())


# ───────────────────────────────────────────────────────────────────────
# POST /resume
# ───────────────────────────────────────────────────────────────────────

@router.post("/resume", response_model=ResumeResponse)
async def resume(request: Request, body: ResumeRequest) -> ResumeResponse:
    """Resume a previously-crashed run by thread_id.

    LangGraph reloads state from the checkpointer and continues at the failed node.
    """
    graph_app = _get_app(request)
    runs = _get_runs(request)
    config = {"configurable": {"thread_id": body.thread_id}}

    snapshot = await graph_app.aget_state(config)
    if snapshot is None or not snapshot.values:
        raise HTTPException(
            status_code=404,
            detail=f"No checkpoint found for thread_id={body.thread_id}",
        )

    # `next` on a snapshot is the tuple of nodes that would run next.
    resuming_from = ",".join(snapshot.next) if snapshot.next else "END"

    # Resume by ainvoke(None, config) — LangGraph picks up at the next pending node.
    task = asyncio.create_task(_invoke_graph(graph_app, None, config))  # type: ignore[arg-type]
    runs[body.thread_id] = task

    return ResumeResponse(thread_id=body.thread_id, resuming_from_node=resuming_from)


# ───────────────────────────────────────────────────────────────────────
# GET /history
# ───────────────────────────────────────────────────────────────────────

@router.get("/history", response_model=list[HistoryEntry])
async def history(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[HistoryEntry]:
    """List past recommendations, newest first. Includes drift if comparison has run."""
    rows = memory_store.list_history(limit=limit, offset=offset)
    return [HistoryEntry(**r) for r in rows]


# ───────────────────────────────────────────────────────────────────────
# POST /explain  (optional, off-critical-path RAG)
# ───────────────────────────────────────────────────────────────────────

@router.post("/explain")
async def explain(body: ExplainRequest) -> dict[str, Any]:
    """N7 Explanation Agent — ACTUS-Mentor RAG side assistant.

    Returns NotImplementedError-equivalent (HTTP 501) until the RAG endpoint is verified.
    """
    try:
        answer = ask_explanation(body.question, context={"record_id": body.record_id})
        return {"answer": answer}
    except NotImplementedError as e:
        raise HTTPException(status_code=501, detail=str(e))
