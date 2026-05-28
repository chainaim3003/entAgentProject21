# Design Summary

The authoritative design for **hedgeAdvisor2 (V2)** lives in:

```
DESIGN/DESIGN-V1/
├── README.md                              — Map of the design set
├── design-v1-problem-solution-impact.md   — Refined problem, solution, impact
├── design-v1-conceptual-design.md         — Bow-tie ASCII diagram + agent-type law
├── design-v1-detailed-design.md           — N0–N8 textual graph + edges + invariants + DRAPS-contract decision (§6)
├── design-v1-config-architecture.md       — The V2 config file split (§3.1 profile, §3.2 hedge-spec, §3.3 component schemas)
├── design-v1-risk-factor-catalog.md       — The risk factors V2 supports, by audience
├── design-v1-free-apis.md                 — Data sources (US/Japan/India)
├── design-v1-project-structure.md         — File layout
├── design-v1-migration-plan.md            — Layered migration (phases — superseded by iteration-plan below)
└── design-v1-iteration-plan.md            — 12 vertical-slice iterations; byte-equality is the gate
```

This `DESIGN.md` is intentionally short — it is the in-repo signpost. Read the files above for the substance.

The legacy V1 design (entAgentProject21) is preserved under `DESIGN/DESIGN1/` for reference. It is **not** the source of truth for hedgeAdvisor2; use `DESIGN-V1/` instead.

---

## Code ↔ design mapping (quick lookup)

| Design concept | Implementation file |
|---|---|
| `HedgeAdvisorState` (project-structure §8) | `backend/graph.py` |
| Reasoning agents N0, N1, N2, N5 | `backend/reasoning_agents.py` |
| Deterministic agents N3, N4, N6, N8, NX | `backend/deterministic_agents.py` |
| Explanation Agent N7 (off critical path) | `backend/explanation_agent.py` |
| DRAPS connector (knot) | `backend/draps_client.py` |
| ACTUS-Mentor connector (disclosure) | `backend/actus_mentor_client.py` |
| LangGraph wiring + conditional routing | `backend/graph.py` |
| API surface | `backend/api.py` |
| Memory store (predicted-vs-realised loop) | `backend/memory_store.py` |
| **V2 additions (iteration 1+):** | |
| Profile resolver (N3a) | `backend/profile_resolver.py` |
| Hedge-spec resolver (N3b) | `backend/hedge_spec_resolver.py` |
| Profile + spec validator (N3c) | `backend/profile_spec_validator.py` |
| Composer (N3d) — derived/supplied/derived_domestic | `backend/composer.py` |
| Risk-factor profiles | `config/risk-factor-profiles/**` |
| Hedge specs | `config/hedge-specs/**` |
| Risk-factor components (specs only in V2.0) | `config/risk-factor-components/**` |
| JSON Schemas | `schemas/**` |

---

## Invariants enforced by code structure (not by comments)

- **I1 — prompt boundary:** The Simulation node (N4) lives in `deterministic_agents.py`, which **does not import Gemini**. `grep -n "import" backend/deterministic_agents.py` is the audit.
- **I2 — clean-inputs gate:** `validated_inputs` is produced only by `validator_node` and consumed only by `simulation_node` (V1). In V2 it becomes `knot_payload`, produced only by `composer_node` and consumed only by `simulation_node`.
- **I3 — audit log:** Every node returns an entry that the LangGraph reducer appends to `state["audit_log"]`.
- **I4 — bounded retry:** `MAX_VALIDATOR_RETRIES` in `graph.py`; the retry edge cannot loop forever.
- **I5 — honest failure:** `give_up_node` in `deterministic_agents.py` returns a structured failure — no fabricated result, ever.
- **I6 — byte-equality gate:** `backend/tests/test_byte_equality_v1.py` must stay green from Iteration 1 onward. SOFR path matches V1 to 4 decimal places; A/B/C totals match exactly. This is the architectural lock.
- **I7 — provenance:** every numeric in the knot payload must be traceable to a source (config_file / api / caller_supplied / draps_v1_passthrough). Enforced in full from Iteration 5; stamped (not enforced) from Iteration 1.
