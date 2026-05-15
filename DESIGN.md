# Design Summary

The authoritative design lives in:

```
DESIGN/DESIGN1/
├── design-1-problem-solution-impact.md   — Refined problem, solution, impact (the latest framing)
├── design-1-conceptual-design.md         — Bow-tie ASCII diagram + agent-type law
├── design-1-detailed-design.md           — N0–N8 textual graph + edges + invariants + verification gaps
├── design-1-project-structure.md         — File layout (this repo implements §3 of that doc)
└── design-1-files-on-disk.md             — Inventory of source design files
```

This `DESIGN.md` is intentionally short — it is the in-repo signpost. Read the files above for the substance.

---

## Code ↔ design mapping (quick lookup)

| Design concept | Implementation file |
|---|---|
| `HedgeAdvisorState` (§8 of project-structure) | `backend/graph.py` |
| Reasoning agents N0, N1, N2, N5 | `backend/reasoning_agents.py` |
| Deterministic agents N3, N4, N6, N8, NX | `backend/deterministic_agents.py` |
| Explanation Agent N7 (off critical path) | `backend/explanation_agent.py` |
| DRAPS connector (knot) | `backend/draps_client.py` |
| ACTUS-Mentor connector (disclosure) | `backend/actus_mentor_client.py` |
| LangGraph wiring + conditional routing | `backend/graph.py` |
| API surface (§7) | `backend/api.py` |
| Memory store (predicted-vs-realised loop) | `backend/memory_store.py` |

---

## Invariants enforced by code structure (not by comments)

- **I1 — prompt boundary:** The Simulation node (N4) lives in `deterministic_agents.py`, which **does not import Gemini**. `grep -n "import" backend/deterministic_agents.py` is the audit.
- **I2 — clean-inputs gate:** `validated_inputs` is produced only by `validator_node` and consumed only by `simulation_node`. Grepping the codebase for `validated_inputs` shows exactly one producer and one consumer.
- **I3 — audit log:** Every node returns an entry that the LangGraph reducer appends to `state["audit_log"]`.
- **I4 — bounded retry:** `MAX_VALIDATOR_RETRIES` in `graph.py`; the retry edge cannot loop forever.
- **I5 — honest failure:** `give_up_node` in `deterministic_agents.py` returns a structured failure — no fabricated result, ever.
