/**
 * api.ts — All backend endpoints + SSE stream parsing.
 *
 * Single source of truth for what the UI talks to.
 * Endpoint: POST /run, GET /trace (SSE), POST /resume, GET /history, POST /explain.
 */

const BACKEND_URL =
  (import.meta as any).env?.VITE_BACKEND_URL ?? "http://localhost:8000";

// ─── Types ────────────────────────────────────────────────────────────

export interface RunRequest {
  prompt: string;
  loan_doc: string;
  thread_id?: string | null;
}

export interface RunResponse {
  thread_id: string;
  status: string;
}

export interface AuditEntry {
  node: string;
  summary: string;
  output: Record<string, unknown>;
  ts: string;
}

export interface DoneSuccess {
  status: "success";
  thread_id: string;
  recommendation: Recommendation | null;
  memory_record_id: string;
  simulation_result: SimulationResult | null;
  disclosure_doc: Record<string, unknown> | null;
}

export interface DoneFailure {
  status: "failed";
  thread_id: string;
  failure: { reason: string; errors: string[]; retry_count: number; last_node: string };
}

export type DoneEvent = DoneSuccess | DoneFailure;

export interface Recommendation {
  winner: "A" | "B" | "C";
  predicted_saving_usd: number;
  cost_of_delay_usd: number | null;
  rationale: string;
}

export interface CashflowEvent {
  time: string;             // ISO date or relative period
  type: string;             // PR, IP, MD, FP, IED, etc. (ACTUS event types)
  payoff: number;           // signed amount
  currency: string;
  contract_id?: string;
  // Allow any extra fields DRAPS may return (notional, accrued, etc.) without breaking
  [key: string]: unknown;
}

export interface SimulationResult {
  A_total: number;
  B_total: number;
  C_total: number;
  // Cashflow events from DRAPS. May be flat (one stream) or grouped by scenario.
  events?: CashflowEvent[];
  events_by_scenario?: {
    A?: CashflowEvent[];
    B?: CashflowEvent[];
    C?: CashflowEvent[];
  };
}

export interface HistoryEntry {
  record_id: string;
  thread_id: string;
  created_at: string;
  recommendation: Recommendation;
  drift: { predicted_saving: number; realised_saving: number; delta_usd: number } | null;
}

// ─── POST /run ────────────────────────────────────────────────────────

export async function startRun(body: RunRequest): Promise<RunResponse> {
  const resp = await fetch(`${BACKEND_URL}/run`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!resp.ok) {
    const text = await resp.text();
    throw new Error(`POST /run failed (${resp.status}): ${text}`);
  }
  return resp.json();
}

// ─── GET /trace (SSE) ─────────────────────────────────────────────────

export interface TraceCallbacks {
  onNode: (entry: AuditEntry) => void;
  onDone: (done: DoneEvent) => void;
  onError: (err: Error) => void;
}

/**
 * Subscribe to the SSE stream for a thread. Returns an unsubscribe function.
 *
 * Uses native EventSource. Both 'node' and 'done' events are typed via the SSE 'event:' field.
 */
export function subscribeTrace(thread_id: string, cb: TraceCallbacks): () => void {
  const url = `${BACKEND_URL}/trace?thread_id=${encodeURIComponent(thread_id)}`;
  const es = new EventSource(url);

  es.addEventListener("node", (evt) => {
    try {
      const data = JSON.parse((evt as MessageEvent).data) as AuditEntry;
      cb.onNode(data);
    } catch (e) {
      cb.onError(new Error(`Bad 'node' event payload: ${(e as Error).message}`));
    }
  });

  es.addEventListener("done", (evt) => {
    try {
      const data = JSON.parse((evt as MessageEvent).data) as DoneEvent;
      cb.onDone(data);
      es.close();
    } catch (e) {
      cb.onError(new Error(`Bad 'done' event payload: ${(e as Error).message}`));
    }
  });

  es.onerror = () => {
    // EventSource auto-reconnects on transient errors; we only escalate on close.
    if (es.readyState === EventSource.CLOSED) {
      cb.onError(new Error("SSE stream closed unexpectedly"));
    }
  };

  return () => es.close();
}

// ─── POST /resume ─────────────────────────────────────────────────────

export async function resumeRun(thread_id: string): Promise<{ thread_id: string; resuming_from_node: string }> {
  const resp = await fetch(`${BACKEND_URL}/resume`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ thread_id }),
  });
  if (!resp.ok) {
    const text = await resp.text();
    throw new Error(`POST /resume failed (${resp.status}): ${text}`);
  }
  return resp.json();
}

// ─── GET /history ─────────────────────────────────────────────────────

export async function getHistory(limit = 50, offset = 0): Promise<HistoryEntry[]> {
  const resp = await fetch(
    `${BACKEND_URL}/history?limit=${limit}&offset=${offset}`
  );
  if (!resp.ok) {
    throw new Error(`GET /history failed (${resp.status})`);
  }
  return resp.json();
}

// ─── POST /explain (off critical path) ────────────────────────────────

export async function askExplanation(
  question: string,
  record_id?: string
): Promise<string> {
  const resp = await fetch(`${BACKEND_URL}/explain`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question, record_id }),
  });
  if (resp.status === 501) {
    const detail = (await resp.json()).detail ?? "Explanation agent not yet wired.";
    throw new Error(detail);
  }
  if (!resp.ok) {
    throw new Error(`POST /explain failed (${resp.status})`);
  }
  return (await resp.json()).answer;
}
