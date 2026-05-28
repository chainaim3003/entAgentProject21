# hedgeAdvisor2 — design-v1-conceptual-design

## The updated bow-tie

V1's bow-tie is preserved. V2 adds three deterministic nodes on the left wing (Profile-Resolver, HedgeSpec-Resolver, Composer), one wing-boundary (Profile-and-Spec-Validator), and one right-wing node (Provenance). Reasoning agents are unchanged in number and role. The knot is unchanged.

```
   PROMPT  ("hedge analysis for [business identity] [loan] [intent]")
      |
      v
 +-----------------------------------------------------------------------+
 |  N0  ORCHESTRATOR                            [reasoning - Gemini Pro] |
 |  Same as V1: decompose, sequence, checkpoint. No domain work.         |
 +-----------------------------------------------------------------------+
      |
      +--> LEFT WING ----------- stochastic inputs ----------------------+
      |                                                                   
      |  +-----------------------------------------------------------+
      |  | N1  INTAKE                       [reasoning - Gemini]      |
      |  | Same as V1 + extended to extract:                          |
      |  |   - business_identity { industry, country, mode }          |
      |  |   - hedge_intent       (existing fields)                   |
      |  | PRIVATE data enters here.                                  |
      |  +-----------------------------------------------------------+
      |  | N2  MARKET-CONTEXT               [reasoning - Gemini]      |
      |  | Same as V1 but generalised: resolves GTAP code only IF     |
      |  | mode == "export_import"; otherwise resolves industry/sector|
      |  | code (NAICS/ISIC) for domestic businesses.                 |
      |  | PUBLIC data enters here.                                   |
      |  +-----------------------------------------------------------+
      |  | N3  INPUT-VALIDATOR              [DETERMINISTIC]           |
      |  | UNCHANGED from V1 for the loan-level schema.               |
      |  +-----------------------------------------------------------+
      |  | N3a RISK-FACTOR-PROFILE-RESOLVER [DETERMINISTIC]    NEW    |
      |  | Loads risk_factor_profile from config/risk-factor-         |
      |  | profiles/ based on (industry, corridor, commodity, mode).  |
      |  | Honest failure if profile absent. No silent default.       |
      |  +-----------------------------------------------------------+
      |  | N3b HEDGE-SPEC-RESOLVER          [DETERMINISTIC]    NEW    |
      |  | Loads hedge_spec from config/hedge-specs/ (which scenarios |
      |  | to run, offsets, fixed-rate rule).                         |
      |  +-----------------------------------------------------------+
      |  | N3c PROFILE-AND-SPEC-VALIDATOR   [DETERMINISTIC]    NEW    |
      |  | Schema-checks the resolved profile and hedge_spec.         |
      |  | Adjacent boundary to N3, not a replacement.                |
      |  +-----------------------------------------------------------+
      |  | N3d RISK-FACTOR-COMPOSER         [DETERMINISTIC]    NEW    |
      |  | Three modes (chosen by profile, not code):                 |
      |  |   supplied        - SOFR + fixed rates passed through      |
      |  |   derived         - additive component formula (V1 path)   |
      |  |   derived_domestic- different components, same machinery   |
      |  | Produces sofr_path[], swap_now_fixed, swap_later_fixed.    |
      |  +-----------------------------------------------------------+
      |
      +--> KNOT --------------- deterministic core ----------------------+
      |  +-----------------------------------------------------------+
      |  | N4  SIMULATION    [DETERMINISTIC - DRAPS run_simulation]   |
      |  | UNCHANGED at the agent level.                              |
      |  | Input contract may extend - see detailed-design §6.        |
      |  +-----------------------------------------------------------+
      |
      +--> RIGHT WING --------- stochastic outputs ----------------------+
      |  +-----------------------------------------------------------+
      |  | N5  INTERPRETATION              [reasoning - Gemini]       |
      |  | UNCHANGED, but rationale prompt is profile-aware so the    |
      |  | "why" is phrased in the audience's vocabulary.             |
      |  +-----------------------------------------------------------+
      |  | N6  DISCLOSURE   [DETERMINISTIC - ACTUS-Mentor /xbrl]      |
      |  | UNCHANGED.                                                 |
      |  +-----------------------------------------------------------+
      |  | N6a PROVENANCE   [DETERMINISTIC]                    NEW    |
      |  | Walks audit_log, produces source-attribution report:       |
      |  | every input traced to (config-file + checksum) OR          |
      |  | (free-API call + timestamp + response hash) OR             |
      |  | (caller-supplied with flag).                               |
      |  +-----------------------------------------------------------+
      |  | N7  EXPLANATION  [reasoning - ACTUS-Mentor RAG]            |
      |  | UNCHANGED, optional side assistant.                        |
      |  +-----------------------------------------------------------+
      |
      +--> N8  MEMORY                       [DETERMINISTIC]              +
          UNCHANGED. Stores everything for predicted-vs-realised loop.
          (Drift attribution is now also profile-aware: when realised
           moves diverge from predicted, the drift can be attributed to
           a specific profile component, not a black box.)

   AGENT-TYPE LAW (preserved verbatim from V1):
     input ambiguous?   -> reasoning agent, lives on a wing.
     input structured?  -> deterministic agent.
     The knot never grows. New agents extend the wings.
```

---

## The three-mode flow

```
                                       ┌─────────────────────┐
                                       │  N3d COMPOSER       │
                                       │  reads profile.mode │
                                       └─────────────────────┘
                                                  │
                  ┌───────────────────────────────┼───────────────────────────────┐
                  │                               │                               │
                  ▼                               ▼                               ▼
        ┌─────────────────┐           ┌──────────────────────┐         ┌──────────────────────┐
        │  mode=supplied  │           │  mode=derived        │         │ mode=derived_domestic│
        │                 │           │                      │         │                      │
        │ caller provided │           │ profile declares     │         │ profile declares     │
        │  sofr_path      │           │  components:         │         │  components:         │
        │  swap_now_fixed │           │   - base_sofr        │         │   - base_sofr        │
        │  swap_later_fxd │           │   - tariff           │         │   - demand_vol       │
        │                 │           │   - sovereign        │         │   - inventory_carry  │
        │ Composer        │           │   - wc               │         │   - payment_cycle    │
        │ pass-through +  │           │  AND inputs for each │         │   - wc               │
        │ provenance-stamp│           │  AND calibration     │         │                      │
        │                 │           │                      │         │ same machinery       │
        │                 │           │ Composer runs the    │         │ different components │
        │                 │           │ additive formula     │         │                      │
        └─────────────────┘           └──────────────────────┘         └──────────────────────┘
                  │                               │                               │
                  └───────────────────────────────┼───────────────────────────────┘
                                                  ▼
                                       ┌──────────────────────┐
                                       │  N3c VALIDATOR       │
                                       │  schema-checks output│
                                       └──────────────────────┘
                                                  │
                                                  ▼
                                       ┌──────────────────────┐
                                       │  N4 SIMULATION (knot)│
                                       └──────────────────────┘
```

The composer does not know about commodities, corridors, ecommerce, or services. It knows about **components and inputs**. The profile is the polymorphism layer.

---

## What the audience sees vs what is preserved underneath

| Audience | Sees as input shape | Resolves to (mode, profile) | Knot receives |
|---|---|---|---|
| V1 customer (India-US-tex exporter) | unchanged from V1 | `(derived, india-us-textiles.json)` | identical 4-component SOFR path |
| Sophisticated treasurer who has rates | `sofr_path[]`, `swap_now_fixed`, `swap_later_fixed` | `(supplied, none)` | exactly those numbers |
| New corridor (e.g. Vietnam-US apparel) | unchanged from V1 (intake extracts corridor) | `(derived, vietnam-us-apparel.json)` | new 4-component SOFR path |
| US ecommerce small business | intake extracts "domestic ecommerce" | `(derived_domestic, us-ecommerce.json)` | N-component SOFR path with no tariff term |
| US services business | intake extracts "domestic services" | `(derived_domestic, us-services.json)` | smaller N-component SOFR path |
| Japan-based business | intake extracts country=JP | `(derived_domestic, jp-services.json)` etc | components keyed off TONA/JGB instead of SOFR |

The knot computes the same way for every row in that table. The only thing that varies is the profile and the resolved path.

---

## Extension pattern

The V1 extension pattern stands:

- **Further left** = more input-resolution agents (a live USTR-tariff-feed agent, a live FRED-rate agent, a live UN-Comtrade-flow agent). All reasoning or deterministic depending on whether the API output needs interpretation. All feed the **same** Risk-Factor-Profile-Resolver — they augment a profile rather than bypass it.

- **Further right** = more output agents (portfolio rollup across many loans, board memo writer, regulatory filer). Mix of reasoning and deterministic per the agent-type law.

- **Components are the new extension axis** introduced in V2. A new risk-factor component (`fx_translation_risk` for multi-currency revenues, `cyber_disruption_risk` for businesses with significant digital exposure) is added by:
  1. defining its input schema in `config/risk-factor-components/<name>.json` with the formula and primary-source citation,
  2. listing it in any profile that should use it,
  3. — that's it. No code change in the Composer.

The Composer's contract is: read a list of component specs, evaluate each with the input bundle, sum the result. The intelligence is in the component spec, not in the Composer code.

---

## Track fit (unchanged from V1)

Track 2 (Gemini reasoning on N0, N1, N2, N5) and Track 4 (public/private data fusion). The new agents are all deterministic, which **strengthens** the efficiency case from V1 — V2 still uses Gemini on the same 4 nodes as V1 even though the architecture covers many more audiences. That is the agent-type law paying off again.

---

**End of design-v1-conceptual-design.md**
