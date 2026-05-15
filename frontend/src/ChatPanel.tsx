/**
 * ChatPanel.tsx — Left panel: prompt input + chat-style agent trace.
 *
 * Visual language: ACTUS Mentor chat bubbles + pastel-colored agent zones.
 * Each completed agent becomes an "assistant message" with a hover-reveal
 * action bar (copy / thumbs up / thumbs down / share) and a collapsible
 * "Pipeline info" panel showing per-agent metadata.
 * The user prompt bubble has copy / edit / regenerate.
 */

import { useEffect, useRef, useState } from "react";
import {
  Send,
  Sparkles,
  AlertCircle,
  CheckCircle2,
  Loader2,
  Copy,
  Check,
  ThumbsUp,
  ThumbsDown,
  Share2,
  ChevronDown,
  ChevronUp,
  Pencil,
  RotateCcw,
} from "lucide-react";
import {
  startRun,
  subscribeTrace,
  type AuditEntry,
  type DoneEvent,
} from "./api";

interface Props {
  onRunStarted: (thread_id: string) => void;
  onNode: (entry: AuditEntry) => void;
  onDone: (done: DoneEvent) => void;
  activeThread: string | null;
  trace: AuditEntry[];
  done: DoneEvent | null;
  prompt: string;
  setPrompt: (v: string) => void;
  loanDoc: string;
  setLoanDoc: (v: string) => void;
}

const NODE_ZONES: Record<string, { zone: string; tone: string }> = {
  orchestrator:   { zone: "Control plane",  tone: "pastel-purple" },
  intake:         { zone: "Left wing",      tone: "pastel-pink" },
  market_context: { zone: "Left wing",      tone: "pastel-pink" },
  validator:      { zone: "Boundary",       tone: "pastel-yellow" },
  simulation:     { zone: "THE KNOT",       tone: "pastel-blue" },
  interpretation: { zone: "Right wing",     tone: "pastel-teal" },
  disclosure:     { zone: "Right wing",     tone: "pastel-teal" },
  memory:         { zone: "Memory loop",    tone: "pastel-orange" },
  give_up:        { zone: "Honest failure", tone: "pastel-red" },
};

const PIPELINE_ORDER = [
  "orchestrator",
  "intake",
  "market_context",
  "validator",
  "simulation",
  "interpretation",
  "disclosure",
  "memory",
];

export function ChatPanel({
  onRunStarted,
  onNode,
  onDone,
  activeThread,
  trace,
  done,
  prompt,
  setPrompt,
  loanDoc,
  setLoanDoc,
}: Props) {
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [editingUser, setEditingUser] = useState(false);
  const [showLoanDoc, setShowLoanDoc] = useState(true);
  const unsubRef = useRef<(() => void) | null>(null);
  const scrollRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [trace, done]);

  useEffect(() => () => unsubRef.current?.(), []);

  useEffect(() => {
    if (done && unsubRef.current) {
      unsubRef.current();
      unsubRef.current = null;
      setSubmitting(false);
    }
  }, [done]);

  async function handleSubmit() {
    if (!prompt.trim() || !loanDoc.trim() || submitting) return;
    setError(null);
    setSubmitting(true);
    setEditingUser(false);
    unsubRef.current?.();
    unsubRef.current = null;

    try {
      const { thread_id } = await startRun({ prompt, loan_doc: loanDoc });
      onRunStarted(thread_id);
      unsubRef.current = subscribeTrace(thread_id, {
        onNode,
        onDone,
        onError: (e) => {
          setError(e.message);
          setSubmitting(false);
        },
      });
    } catch (e) {
      setError((e as Error).message);
      setSubmitting(false);
    }
  }

  const seenNodes = new Set(trace.map((t) => t.node));
  const isFailure = done?.status === "failed";
  const currentPending = !done
    ? PIPELINE_ORDER.find((n) => !seenNodes.has(n))
    : null;

  const runStarted = trace.length > 0 || submitting || done;

  return (
    <section className="chat-panel">
      <div className="chat-panel-header">
        <h2 className="panel-title">
          <Sparkles size={16} className="panel-title-icon" />
          Ask the bow-tie
        </h2>
        {activeThread && (
          <span className="thread-badge" title="LangGraph thread (for resume)">
            {activeThread.slice(0, 16)}…
          </span>
        )}
      </div>

      {/* Prompt cards (loan doc is collapsible after first run) */}
      <div className="prompt-cards">
        <label className="prompt-card">
          <div className="prompt-card-row">
            <span className="prompt-card-label">Private loan document</span>
            {runStarted && (
              <button
                className="prompt-card-collapse"
                onClick={() => setShowLoanDoc((s) => !s)}
                type="button"
              >
                {showLoanDoc ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
                {showLoanDoc ? "Hide" : "Show"}
              </button>
            )}
          </div>
          {showLoanDoc && (
            <textarea
              rows={4}
              value={loanDoc}
              onChange={(e) => setLoanDoc(e.target.value)}
              disabled={submitting}
              placeholder="Paste loan terms here…"
            />
          )}
        </label>
      </div>

      {/* Mentor-style pill input bar for the natural-language ask */}
      <div className={`ask-bar ${submitting ? "ask-bar-disabled" : ""}`}>
        <textarea
          className="ask-textarea"
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey && !submitting) {
              e.preventDefault();
              handleSubmit();
            }
          }}
          placeholder="Describe your loan situation and ask: should I hedge?"
          rows={1}
          disabled={submitting}
        />
        <button
          className={`ask-send-btn ${prompt.trim() && loanDoc.trim() && !submitting ? "active" : ""}`}
          onClick={handleSubmit}
          disabled={submitting || !prompt.trim() || !loanDoc.trim()}
          title="Run analysis (Enter)"
        >
          {submitting ? <Loader2 size={16} className="spinning" /> : <Send size={15} />}
        </button>
      </div>
      <p className="ask-hint">
        Press <kbd>Enter</kbd> to run · <kbd>Shift+Enter</kbd> for new line
      </p>

      {error && (
        <div className="error-banner">
          <AlertCircle size={14} />
          <span>{error}</span>
        </div>
      )}

      {/* Trace — chat-style messages */}
      <div className="trace-wrap" ref={scrollRef}>
        <h3 className="trace-heading">Agent trace</h3>

        {trace.length === 0 && !done && !submitting && (
          <p className="trace-empty">
            Submit a question to watch the bow-tie work — eight agents stream their progress here in real time.
          </p>
        )}

        {/* User prompt bubble with copy / edit / regenerate */}
        {runStarted && (
          <UserMessage
            prompt={prompt}
            onCopy={() => navigator.clipboard.writeText(prompt)}
            onEdit={() => setEditingUser(true)}
            onRegenerate={handleSubmit}
            editing={editingUser}
            onEditChange={setPrompt}
            onEditSubmit={() => {
              setEditingUser(false);
              handleSubmit();
            }}
            onEditCancel={() => setEditingUser(false)}
            disabled={submitting}
          />
        )}

        {/* Assistant messages — one per completed agent */}
        {trace.map((entry, i) => (
          <AssistantMessage key={i} entry={entry} />
        ))}

        {/* Pending indicator */}
        {currentPending && submitting && (
          <div className="msg msg-assistant">
            <div className={`msg-avatar msg-avatar-pending`}>
              <Loader2 size={14} className="spinning" />
            </div>
            <div className="msg-bubble msg-bubble-pending">
              <div className="msg-header">
                <span className={`msg-zone-chip chip-pending`}>
                  {NODE_ZONES[currentPending]?.zone ?? "Working"}
                </span>
                <span className="msg-node-name">{currentPending}</span>
              </div>
              <div className="msg-summary">
                <span className="typing-dots">
                  <span></span><span></span><span></span>
                </span>
              </div>
            </div>
          </div>
        )}

        {/* Honest failure */}
        {isFailure && done?.status === "failed" && (
          <div className="msg msg-assistant">
            <div className="msg-avatar msg-avatar-pastel-red">
              <AlertCircle size={14} />
            </div>
            <div className="msg-bubble msg-bubble-failure">
              <div className="msg-header">
                <span className="msg-zone-chip chip-pastel-red">Honest failure</span>
                <span className="msg-node-name">{done.failure.last_node}</span>
              </div>
              <div className="msg-summary">
                <strong>{done.failure.reason}</strong>
                {done.failure.errors.length > 0 && (
                  <ul className="failure-list">
                    {done.failure.errors.map((e, j) => (
                      <li key={j}>{e}</li>
                    ))}
                  </ul>
                )}
                <div className="failure-hint">
                  No fabricated result returned (design invariant I5).
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </section>
  );
}

/* ───────────────────────────────────────────────────────────
   User prompt bubble — with copy / edit / regenerate
   ─────────────────────────────────────────────────────────── */
function UserMessage({
  prompt,
  onCopy,
  onEdit,
  onRegenerate,
  editing,
  onEditChange,
  onEditSubmit,
  onEditCancel,
  disabled,
}: {
  prompt: string;
  onCopy: () => void;
  onEdit: () => void;
  onRegenerate: () => void;
  editing: boolean;
  onEditChange: (v: string) => void;
  onEditSubmit: () => void;
  onEditCancel: () => void;
  disabled: boolean;
}) {
  const [copied, setCopied] = useState(false);
  const doCopy = () => {
    onCopy();
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  return (
    <div className="msg msg-user">
      <div className="msg-avatar msg-avatar-user">U</div>
      <div className="msg-bubble-wrapper">
        {editing ? (
          <div className="edit-box">
            <textarea
              className="edit-textarea"
              value={prompt}
              autoFocus
              rows={3}
              onChange={(e) => onEditChange(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  onEditSubmit();
                }
                if (e.key === "Escape") onEditCancel();
              }}
            />
            <div className="edit-actions">
              <button className="edit-cancel-btn" onClick={onEditCancel}>Cancel</button>
              <button className="edit-send-btn" onClick={onEditSubmit} disabled={disabled}>
                Send & run
              </button>
            </div>
          </div>
        ) : (
          <div className="msg-bubble msg-bubble-user">
            <div className="msg-prompt">{prompt}</div>
          </div>
        )}

        {!editing && (
          <div className="msg-action-bar bar-user">
            <button className="msg-icon-btn" onClick={doCopy} title="Copy">
              {copied ? <Check size={14} className="active-green" /> : <Copy size={14} />}
            </button>
            <button className="msg-icon-btn" onClick={onEdit} title="Edit">
              <Pencil size={14} />
            </button>
            <button
              className="msg-icon-btn"
              onClick={onRegenerate}
              disabled={disabled}
              title="Re-run analysis"
            >
              <RotateCcw size={14} />
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

/* ───────────────────────────────────────────────────────────
   Assistant message — per-agent bubble with action bar + pipeline info
   ─────────────────────────────────────────────────────────── */
function AssistantMessage({ entry }: { entry: AuditEntry }) {
  const meta = NODE_ZONES[entry.node] ?? { zone: "Unknown", tone: "pastel-purple" };
  const [copied, setCopied] = useState(false);
  const [liked, setLiked] = useState<null | "up" | "down">(null);
  const [showInfo, setShowInfo] = useState(false);

  const doCopy = () => {
    navigator.clipboard.writeText(entry.summary);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  const doShare = () => {
    const text = `[${entry.node}] ${entry.summary}`;
    if ((navigator as any).share) {
      (navigator as any).share({ text }).catch(() => navigator.clipboard.writeText(text));
    } else {
      navigator.clipboard.writeText(text);
    }
  };

  return (
    <div className="msg msg-assistant">
      <div className={`msg-avatar msg-avatar-${meta.tone}`}>
        <CheckCircle2 size={14} />
      </div>
      <div className="msg-bubble-wrapper">
        <div className="msg-bubble msg-bubble-assistant">
          <div className="msg-header">
            <span className={`msg-zone-chip chip-${meta.tone}`}>{meta.zone}</span>
            <span className="msg-node-name">{entry.node}</span>
          </div>
          <div className="msg-summary">{entry.summary}</div>
        </div>

        <div className="msg-action-bar bar-assistant">
          <button className="msg-icon-btn" onClick={doCopy} title="Copy">
            {copied ? <Check size={14} className="active-green" /> : <Copy size={14} />}
          </button>
          <div className="msg-bar-divider" />
          <button
            className={`msg-icon-btn ${liked === "up" ? "active-blue" : ""}`}
            onClick={() => setLiked((p) => (p === "up" ? null : "up"))}
            title="Good response"
          >
            <ThumbsUp size={14} />
          </button>
          <button
            className={`msg-icon-btn ${liked === "down" ? "active-red" : ""}`}
            onClick={() => setLiked((p) => (p === "down" ? null : "down"))}
            title="Bad response"
          >
            <ThumbsDown size={14} />
          </button>
          <div className="msg-bar-divider" />
          <button className="msg-icon-btn" onClick={doShare} title="Share">
            <Share2 size={14} />
          </button>
        </div>

        <button className="meta-toggle" onClick={() => setShowInfo((p) => !p)}>
          {showInfo ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
          <span>Pipeline info</span>
        </button>
        {showInfo && (
          <div className="meta-details">
            <div className="meta-item">
              <span>Node: <strong>{entry.node}</strong></span>
            </div>
            <div className="meta-item">
              <span>Zone: <strong>{meta.zone}</strong></span>
            </div>
            <div className="meta-item">
              <span>Timestamp: <strong>{new Date(entry.ts).toLocaleTimeString()}</strong></span>
            </div>
            {Object.keys(entry.output ?? {}).length > 0 && (
              <details className="meta-output">
                <summary>Output state delta</summary>
                <pre>{JSON.stringify(entry.output, null, 2)}</pre>
              </details>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
