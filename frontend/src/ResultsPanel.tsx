/**
 * ResultsPanel.tsx — Right panel: scenario cards + recommendation + cashflows + XBRL.
 *
 * Visual language: ACTUS Mentor result cards with pastel chips and soft shadows.
 * Adds Mentor-style cashflow table and tabbed XBRL disclosure view.
 */

import { useMemo, useState } from "react";
import {
  TrendingUp,
  TrendingDown,
  Award,
  FileText,
  ChevronDown,
  ChevronUp,
  AlertTriangle,
  Table as TableIcon,
  FileCode2,
  Map as MapIcon,
  ListTree,
  Download,
} from "lucide-react";
import type {
  AuditEntry,
  CashflowEvent,
  DoneEvent,
  HistoryEntry,
  Recommendation,
  SimulationResult,
} from "./api";

interface Props {
  trace: AuditEntry[];
  done: DoneEvent | null;
  history: HistoryEntry[];
  historyError: string | null;
}

function formatUsd(n: number | null | undefined): string {
  if (n === null || n === undefined || Number.isNaN(n)) return "—";
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  }).format(n);
}

function formatSigned(n: number): string {
  const sign = n >= 0 ? "+" : "";
  return sign + new Intl.NumberFormat("en-US", { maximumFractionDigits: 2 }).format(n);
}

export function ResultsPanel({ trace, done, history, historyError }: Props) {
  const success = done?.status === "success" ? done : null;
  const failure = done?.status === "failed" ? done : null;
  const rec: Recommendation | null = success?.recommendation ?? null;
  const sim: SimulationResult | null = success?.simulation_result ?? null;

  return (
    <section className="results-panel">
      <div className="results-panel-header">
        <h2 className="panel-title">
          <Award size={16} className="panel-title-icon" />
          Hedge recommendation
        </h2>
      </div>

      {/* Empty state */}
      {!done && trace.length === 0 && (
        <div className="results-empty">
          <div className="results-empty-orb">
            <svg width="56" height="56" viewBox="0 0 80 80" fill="none">
              <defs>
                <linearGradient id="emptyOrb" x1="0" y1="0" x2="80" y2="80">
                  <stop offset="0%" stopColor="#6366F1" stopOpacity="0.4" />
                  <stop offset="100%" stopColor="#A78BFA" stopOpacity="0.2" />
                </linearGradient>
              </defs>
              <circle cx="40" cy="40" r="34" fill="url(#emptyOrb)" />
              <circle cx="40" cy="40" r="34" stroke="#6366F1" strokeWidth="1.5" fill="none" strokeOpacity="0.25" />
            </svg>
          </div>
          <p className="results-empty-text">
            Submit a question to see the bow-tie produce a recommendation, cashflow simulation, and IFRS/US-GAAP disclosure document.
          </p>
        </div>
      )}

      {/* Running */}
      {!done && trace.length > 0 && (
        <div className="results-running">
          <div className="running-pill">
            <span className="running-dot" />
            Running… {trace.length} of 8 agents complete
          </div>
        </div>
      )}

      {/* Failure */}
      {failure && (
        <div className="failure-card">
          <div className="failure-card-icon">
            <AlertTriangle size={22} />
          </div>
          <div className="failure-card-body">
            <h3>Analysis halted honestly</h3>
            <p className="failure-card-reason">
              <strong>{failure.failure.reason}</strong> · last node: <code>{failure.failure.last_node}</code>
            </p>
            {failure.failure.errors.length > 0 && (
              <ul className="failure-card-errors">
                {failure.failure.errors.map((e, i) => (
                  <li key={i}>{e}</li>
                ))}
              </ul>
            )}
            <p className="failure-card-hint">
              The system never fabricates a result when inputs are bad. Fix the issue and resubmit.
            </p>
          </div>
        </div>
      )}

      {/* Recommendation hero */}
      {rec && (
        <div className="rec-hero">
          <div className="rec-hero-top">
            <span className="rec-winner-badge">Scenario {rec.winner}</span>
            <span className="rec-saving">
              <TrendingUp size={14} />
              Predicted saving {formatUsd(rec.predicted_saving_usd)}
            </span>
          </div>
          <p className="rec-rationale">{rec.rationale}</p>
          {rec.cost_of_delay_usd !== null && rec.cost_of_delay_usd !== undefined && (
            <div className="rec-delay">
              <TrendingDown size={13} />
              <span>Cost of delay (B vs C): {formatUsd(rec.cost_of_delay_usd)}</span>
            </div>
          )}
        </div>
      )}

      {/* Scenario cards */}
      {sim && (
        <div className="scenarios-section">
          <h3 className="section-h3">A / B / C scenarios</h3>
          <p className="section-sub">Deterministic, from the DRAPS knot</p>
          <div className="scenario-cards">
            <ScenarioCard letter="A" label="No hedge"        total={sim.A_total} tone="pastel-pink"   winner={rec?.winner === "A"} />
            <ScenarioCard letter="B" label="Hedge now"       total={sim.B_total} tone="pastel-purple" winner={rec?.winner === "B"} />
            <ScenarioCard letter="C" label="Hedge in 3 mo"   total={sim.C_total} tone="pastel-teal"   winner={rec?.winner === "C"} />
          </div>
        </div>
      )}

      {/* Cashflow events — NEW */}
      {sim && hasCashflows(sim) && (
        <CashflowSection sim={sim} winner={rec?.winner ?? null} />
      )}

      {/* XBRL disclosure — NEW polished view */}
      {success?.disclosure_doc && <DisclosureView doc={success.disclosure_doc} />}

      {/* History */}
      <div className="history-section">
        <h3 className="section-h3">Past recommendations</h3>
        {historyError && (
          <div className="error-banner">
            <AlertTriangle size={13} />
            <span>{historyError}</span>
          </div>
        )}
        {!historyError && history.length === 0 && (
          <p className="section-sub">No prior recommendations yet.</p>
        )}
        {history.length > 0 && (
          <table className="history-table">
            <thead>
              <tr>
                <th>When</th>
                <th>Winner</th>
                <th>Predicted</th>
                <th>Realised</th>
                <th>Drift</th>
              </tr>
            </thead>
            <tbody>
              {history.map((h) => (
                <tr key={h.record_id}>
                  <td>{new Date(h.created_at).toLocaleDateString()}</td>
                  <td>
                    <span className={`winner-chip chip-pastel-purple`}>
                      {h.recommendation.winner}
                    </span>
                  </td>
                  <td>{formatUsd(h.recommendation.predicted_saving_usd)}</td>
                  <td>{h.drift ? formatUsd(h.drift.realised_saving) : "—"}</td>
                  <td>
                    {h.drift ? (
                      <span className={h.drift.delta_usd >= 0 ? "drift-up" : "drift-down"}>
                        {h.drift.delta_usd >= 0 ? "+" : ""}
                        {formatUsd(h.drift.delta_usd)}
                      </span>
                    ) : (
                      "—"
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </section>
  );
}

function ScenarioCard({
  letter,
  label,
  total,
  tone,
  winner,
}: {
  letter: string;
  label: string;
  total: number;
  tone: string;
  winner: boolean;
}) {
  return (
    <div className={`scenario-card chip-${tone} ${winner ? "scenario-winner" : ""}`}>
      <div className="scenario-letter">{letter}</div>
      <div className="scenario-label">{label}</div>
      <div className="scenario-total">{formatUsd(total)}</div>
      {winner && (
        <div className="scenario-winner-badge">
          <Award size={11} />
          Winner
        </div>
      )}
    </div>
  );
}

/* ───────────────────────────────────────────────────────────
   Cashflow table — Mentor's ActusRunner-style table
   ─────────────────────────────────────────────────────────── */

function hasCashflows(sim: SimulationResult): boolean {
  if (sim.events && sim.events.length > 0) return true;
  const grouped = sim.events_by_scenario;
  if (!grouped) return false;
  return (grouped.A?.length || grouped.B?.length || grouped.C?.length || 0) > 0;
}

function CashflowSection({
  sim,
  winner,
}: {
  sim: SimulationResult;
  winner: "A" | "B" | "C" | null;
}) {
  // Build per-scenario lists. Prefer events_by_scenario; fall back to flat events on winner.
  const lists = useMemo<Record<"A" | "B" | "C", CashflowEvent[]>>(() => {
    if (sim.events_by_scenario) {
      return {
        A: sim.events_by_scenario.A ?? [],
        B: sim.events_by_scenario.B ?? [],
        C: sim.events_by_scenario.C ?? [],
      };
    }
    // Flat events: attach them to the winner (or A if no winner identified)
    const target = winner ?? "A";
    const empty = { A: [] as CashflowEvent[], B: [] as CashflowEvent[], C: [] as CashflowEvent[] };
    return { ...empty, [target]: sim.events ?? [] };
  }, [sim, winner]);

  // Default-open scenario = winner (or whichever has events)
  const firstNonEmpty: "A" | "B" | "C" =
    (lists.A.length && "A") || (lists.B.length && "B") || (lists.C.length && "C") || "A";
  const [openScenario, setOpenScenario] = useState<"A" | "B" | "C">(winner ?? firstNonEmpty);

  const scenarios: Array<{ key: "A" | "B" | "C"; label: string }> = [
    { key: "A", label: "No hedge" },
    { key: "B", label: "Hedge now" },
    { key: "C", label: "Hedge in 3 mo" },
  ];

  const active = lists[openScenario];

  return (
    <div className="cashflow-section">
      <div className="cashflow-header">
        <div>
          <h3 className="section-h3">
            <TableIcon size={14} style={{ display: "inline-block", marginRight: 6, verticalAlign: "-2px", color: "var(--accent)" }} />
            Cashflow events
          </h3>
          <p className="section-sub">From the DRAPS simulation. Click a scenario tab to view its events.</p>
        </div>
        <button className="link-btn" onClick={() => downloadCashflowsJson(lists)}>
          <Download size={12} />
          JSON
        </button>
      </div>

      <div className="cashflow-tabs">
        {scenarios.map(({ key, label }) => {
          const count = lists[key].length;
          const isWinner = winner === key;
          return (
            <button
              key={key}
              className={`cashflow-tab ${openScenario === key ? "active" : ""}`}
              onClick={() => setOpenScenario(key)}
              disabled={count === 0}
              title={count === 0 ? "No events for this scenario" : undefined}
            >
              <span className={`cashflow-tab-letter chip-pastel-${key === "A" ? "pink" : key === "B" ? "purple" : "teal"}`}>
                {key}
              </span>
              <span className="cashflow-tab-label">{label}</span>
              <span className="cashflow-tab-count">{count}</span>
              {isWinner && <Award size={10} className="cashflow-tab-trophy" />}
            </button>
          );
        })}
      </div>

      {active.length === 0 ? (
        <div className="cashflow-empty">No events for scenario {openScenario}.</div>
      ) : (
        <div className="cashflow-table-wrap">
          <table className="cashflow-table">
            <thead>
              <tr>
                <th className="td-num">#</th>
                <th>Time</th>
                <th>Event</th>
                <th className="td-right">Payoff</th>
                <th>CCY</th>
              </tr>
            </thead>
            <tbody>
              {active.map((ev, i) => (
                <tr key={i}>
                  <td className="td-num">{i + 1}</td>
                  <td className="td-time">{ev.time ?? "—"}</td>
                  <td>
                    <span className="cashflow-event-type">{ev.type ?? "—"}</span>
                  </td>
                  <td className={`td-right td-payoff ${ev.payoff >= 0 ? "positive" : "negative"}`}>
                    {formatSigned(ev.payoff ?? 0)}
                  </td>
                  <td>{ev.currency ?? "USD"}</td>
                </tr>
              ))}
            </tbody>
            <tfoot>
              <tr>
                <td colSpan={3} className="td-right" style={{ fontWeight: 700 }}>
                  Total
                </td>
                <td className="td-right" style={{ fontWeight: 700 }}>
                  {formatSigned(active.reduce((s, e) => s + (e.payoff ?? 0), 0))}
                </td>
                <td>{active[0]?.currency ?? "USD"}</td>
              </tr>
            </tfoot>
          </table>
        </div>
      )}
    </div>
  );
}

function downloadCashflowsJson(lists: Record<"A" | "B" | "C", CashflowEvent[]>) {
  const blob = new Blob([JSON.stringify(lists, null, 2)], { type: "application/json" });
  triggerDownload(blob, "cashflows.json");
}

/* ───────────────────────────────────────────────────────────
   XBRL disclosure — Mentor-style tabbed view
   ─────────────────────────────────────────────────────────── */

interface DisclosureDoc {
  taxonomy?: string;
  standard?: string;     // alt name some servers use
  ifrs?: Record<string, unknown>;
  usgaap?: Record<string, unknown>;
  xml?: string;
  mapping?: Array<{ field: string; ifrs?: string; usgaap?: string; value?: string | number }>;
  summary?: Record<string, string | number>;
  [key: string]: unknown;
}

function DisclosureView({ doc }: { doc: Record<string, unknown> }) {
  const d = doc as DisclosureDoc;
  const [tab, setTab] = useState<"summary" | "mapping" | "xml" | "raw">("summary");

  const taxonomy = d.taxonomy ?? d.standard ?? "IFRS + US-GAAP";
  const hasMapping = Array.isArray(d.mapping) && d.mapping.length > 0;
  const hasXml = typeof d.xml === "string" && d.xml.length > 0;
  const hasSummary = d.summary && typeof d.summary === "object";

  return (
    <div className="xbrl-section">
      <div className="xbrl-header">
        <div className="xbrl-header-left">
          <h3 className="section-h3">
            <FileText size={14} style={{ display: "inline-block", marginRight: 6, verticalAlign: "-2px", color: "var(--accent)" }} />
            Regulatory disclosure
          </h3>
          <div className="xbrl-badges">
            <span className="xbrl-badge xbrl-badge-standard">{String(taxonomy)}</span>
            <span className="xbrl-badge xbrl-badge-ready">Ready to file</span>
          </div>
        </div>
        <div className="xbrl-header-actions">
          {hasXml && (
            <button className="link-btn" onClick={() => downloadText(d.xml!, "disclosure.xml", "application/xml")}>
              <Download size={12} /> XML
            </button>
          )}
          <button className="link-btn" onClick={() => downloadText(JSON.stringify(doc, null, 2), "disclosure.json", "application/json")}>
            <Download size={12} /> JSON
          </button>
        </div>
      </div>

      <div className="xbrl-tabs">
        <button className={`xbrl-tab ${tab === "summary" ? "active" : ""}`} onClick={() => setTab("summary")} disabled={!hasSummary && !d.ifrs && !d.usgaap}>
          <ListTree size={12} /> Summary
        </button>
        <button className={`xbrl-tab ${tab === "mapping" ? "active" : ""}`} onClick={() => setTab("mapping")} disabled={!hasMapping}>
          <MapIcon size={12} /> Mapping
        </button>
        <button className={`xbrl-tab ${tab === "xml" ? "active" : ""}`} onClick={() => setTab("xml")} disabled={!hasXml}>
          <FileCode2 size={12} /> XML
        </button>
        <button className={`xbrl-tab ${tab === "raw" ? "active" : ""}`} onClick={() => setTab("raw")}>
          <FileText size={12} /> Raw JSON
        </button>
      </div>

      <div className="xbrl-tab-body">
        {tab === "summary" && <DisclosureSummary doc={d} />}
        {tab === "mapping" && hasMapping && (
          <DisclosureMapping rows={d.mapping!} />
        )}
        {tab === "xml" && hasXml && (
          <pre className="xbrl-xml">{d.xml}</pre>
        )}
        {tab === "raw" && (
          <pre className="xbrl-xml">{JSON.stringify(doc, null, 2)}</pre>
        )}
      </div>
    </div>
  );
}

function DisclosureSummary({ doc }: { doc: DisclosureDoc }) {
  // Try summary block first; otherwise show ifrs / usgaap key-value pairs side by side
  if (doc.summary && typeof doc.summary === "object") {
    return (
      <div className="xbrl-summary-grid">
        {Object.entries(doc.summary).map(([k, v]) => (
          <div className="xbrl-summary-item" key={k}>
            <div className="xbrl-summary-label">{k}</div>
            <div className="xbrl-summary-value">{String(v)}</div>
          </div>
        ))}
      </div>
    );
  }

  const ifrs = (doc.ifrs ?? {}) as Record<string, unknown>;
  const usgaap = (doc.usgaap ?? {}) as Record<string, unknown>;
  const ifrsKeys = Object.keys(ifrs);
  const usgaapKeys = Object.keys(usgaap);

  if (ifrsKeys.length === 0 && usgaapKeys.length === 0) {
    return (
      <p className="xbrl-empty">
        The disclosure document was generated, but doesn&rsquo;t expose a known summary shape.
        See the <strong>Raw JSON</strong> tab to inspect it.
      </p>
    );
  }

  return (
    <div className="xbrl-summary-cols">
      {ifrsKeys.length > 0 && (
        <div className="xbrl-summary-col">
          <h4 className="xbrl-summary-col-title">IFRS</h4>
          {ifrsKeys.map((k) => (
            <div className="xbrl-summary-item" key={k}>
              <div className="xbrl-summary-label">{k}</div>
              <div className="xbrl-summary-value">{String(ifrs[k])}</div>
            </div>
          ))}
        </div>
      )}
      {usgaapKeys.length > 0 && (
        <div className="xbrl-summary-col">
          <h4 className="xbrl-summary-col-title">US-GAAP</h4>
          {usgaapKeys.map((k) => (
            <div className="xbrl-summary-item" key={k}>
              <div className="xbrl-summary-label">{k}</div>
              <div className="xbrl-summary-value">{String(usgaap[k])}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function DisclosureMapping({ rows }: { rows: NonNullable<DisclosureDoc["mapping"]> }) {
  return (
    <div className="cashflow-table-wrap">
      <table className="cashflow-table">
        <thead>
          <tr>
            <th>Field</th>
            <th>IFRS tag</th>
            <th>US-GAAP tag</th>
            <th>Value</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i}>
              <td>{r.field}</td>
              <td><code className="inline-code">{r.ifrs ?? "—"}</code></td>
              <td><code className="inline-code">{r.usgaap ?? "—"}</code></td>
              <td>{r.value !== undefined ? String(r.value) : "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/* ───────────────────────────────────────────────────────────
   Helpers
   ─────────────────────────────────────────────────────────── */

function triggerDownload(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  setTimeout(() => URL.revokeObjectURL(url), 0);
}

function downloadText(text: string, filename: string, mime: string) {
  triggerDownload(new Blob([text], { type: mime }), filename);
}
