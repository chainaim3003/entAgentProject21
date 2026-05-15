/**
 * App.tsx — Top-level layout: sidebar + main area.
 *
 * Owns the full chat list (in localStorage, Mentor-style). Each chat stores its
 * prompt, loan doc, trace, and done result so the user can revisit it later.
 *
 * Backend "Past Recommendations" (memory_store SQLite) is rendered separately —
 * it only contains successful runs with predicted-vs-realised drift data.
 */

import { useCallback, useEffect, useMemo, useState } from "react";
import { Sidebar } from "./Sidebar";
import { ChatPanel } from "./ChatPanel";
import { ResultsPanel } from "./ResultsPanel";
import { getHistory, type AuditEntry, type DoneEvent, type HistoryEntry } from "./api";

const DEFAULT_PROMPT =
  "I have a $1M floating-rate loan financing textile imports from India, 24 months, spread 250bps. Should I hedge?";

const DEFAULT_LOAN_DOC =
  "Loan agreement: principal USD 1,000,000. Spread 250bps over SOFR. Term: 24 months. Origination: 2026-01-15. Currency: USD. Use of proceeds: imports of woven textile fabric from India (HS 50).";

const CHATS_KEY = "hedge-advisor-chats";
const ACTIVE_KEY = "hedge-advisor-active-chat";

export interface Chat {
  id: string;
  title: string;
  prompt: string;
  loanDoc: string;
  trace: AuditEntry[];
  done: DoneEvent | null;
  threadId: string | null;
  createdAt: string;
  updatedAt: string;
}

function loadChats(): Chat[] {
  try {
    const raw = localStorage.getItem(CHATS_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed;
  } catch {
    return [];
  }
}

function saveChats(chats: Chat[]) {
  try {
    localStorage.setItem(CHATS_KEY, JSON.stringify(chats));
  } catch (e) {
    // Quota exceeded or storage disabled — log and continue
    console.warn("Failed to save chats", e);
  }
}

function makeChat(): Chat {
  const id =
    typeof crypto !== "undefined" && (crypto as any).randomUUID
      ? (crypto as any).randomUUID()
      : Math.random().toString(36).slice(2) + Date.now().toString(36);
  const now = new Date().toISOString();
  return {
    id,
    title: "New Chat",
    prompt: DEFAULT_PROMPT,
    loanDoc: DEFAULT_LOAN_DOC,
    trace: [],
    done: null,
    threadId: null,
    createdAt: now,
    updatedAt: now,
  };
}

function titleFromPrompt(prompt: string): string {
  const trimmed = prompt.trim();
  if (!trimmed) return "New Chat";
  return trimmed.length > 50 ? trimmed.slice(0, 47) + "…" : trimmed;
}

function getInitialState(): { chats: Chat[]; activeId: string } {
  const loaded = loadChats();
  if (loaded.length === 0) {
    const first = makeChat();
    return { chats: [first], activeId: first.id };
  }
  const storedActive = localStorage.getItem(ACTIVE_KEY);
  const activeId =
    storedActive && loaded.some((c) => c.id === storedActive)
      ? storedActive
      : loaded[0].id;
  return { chats: loaded, activeId };
}

export function App() {
  const [sidebarOpen, setSidebarOpen] = useState(true);

  // Chat list — single source of truth, persisted to localStorage
  const initial = useMemo(() => getInitialState(), []);
  const [chats, setChats] = useState<Chat[]>(initial.chats);
  const [activeChatId, setActiveChatId] = useState<string>(initial.activeId);

  // Backend-history (Past Recommendations) — separate from local chats
  const [history, setHistory] = useState<HistoryEntry[]>([]);
  const [historyError, setHistoryError] = useState<string | null>(null);
  const [activeRecordId, setActiveRecordId] = useState<string | null>(null);

  // Persist chats on any change
  useEffect(() => {
    saveChats(chats);
  }, [chats]);

  useEffect(() => {
    try {
      localStorage.setItem(ACTIVE_KEY, activeChatId);
    } catch {
      // ignore
    }
  }, [activeChatId]);

  // Derive active-chat state
  const activeChat = chats.find((c) => c.id === activeChatId) ?? chats[0];
  const prompt = activeChat?.prompt ?? DEFAULT_PROMPT;
  const loanDoc = activeChat?.loanDoc ?? DEFAULT_LOAN_DOC;
  const trace = activeChat?.trace ?? [];
  const done = activeChat?.done ?? null;
  const activeThread = activeChat?.threadId ?? null;

  // Helper: update the active chat
  const updateActiveChat = useCallback(
    (updates: Partial<Chat>) => {
      setChats((prev) =>
        prev.map((c) =>
          c.id === activeChatId
            ? { ...c, ...updates, updatedAt: new Date().toISOString() }
            : c
        )
      );
    },
    [activeChatId]
  );

  // Refresh backend history (successful runs only)
  const refreshHistory = useCallback(async () => {
    try {
      const rows = await getHistory(20, 0);
      setHistory(rows);
      setHistoryError(null);
    } catch (e) {
      setHistoryError((e as Error).message);
    }
  }, []);

  useEffect(() => {
    void refreshHistory();
  }, [refreshHistory]);

  useEffect(() => {
    if (done?.status === "success") {
      void refreshHistory();
      if (done.memory_record_id) setActiveRecordId(done.memory_record_id);
    }
  }, [done, refreshHistory]);

  // Prompt / loan-doc setters — flow through the active chat
  const setPrompt = useCallback(
    (v: string) => {
      updateActiveChat({ prompt: v, title: titleFromPrompt(v) });
    },
    [updateActiveChat]
  );

  const setLoanDoc = useCallback(
    (v: string) => {
      updateActiveChat({ loanDoc: v });
    },
    [updateActiveChat]
  );

  // SSE callbacks — also save into the active chat
  const handleRunStarted = useCallback(
    (thread_id: string) => {
      updateActiveChat({ threadId: thread_id, trace: [], done: null });
      setActiveRecordId(null);
    },
    [updateActiveChat]
  );

  const handleNode = useCallback(
    (entry: AuditEntry) => {
      setChats((prev) =>
        prev.map((c) =>
          c.id === activeChatId
            ? {
                ...c,
                trace: [...c.trace, entry],
                updatedAt: new Date().toISOString(),
              }
            : c
        )
      );
    },
    [activeChatId]
  );

  const handleDone = useCallback(
    (d: DoneEvent) => {
      updateActiveChat({ done: d });
    },
    [updateActiveChat]
  );

  // New / select / delete chat
  const handleNewChat = useCallback(() => {
    const fresh = makeChat();
    setChats((prev) => [fresh, ...prev]);
    setActiveChatId(fresh.id);
    setActiveRecordId(null);
  }, []);

  const handleSelectChat = useCallback((id: string) => {
    setActiveChatId(id);
    setActiveRecordId(null);
  }, []);

  const handleDeleteChat = useCallback(
    (id: string) => {
      setChats((prev) => {
        const next = prev.filter((c) => c.id !== id);
        if (next.length === 0) {
          // Always keep at least one chat available
          const fresh = makeChat();
          setActiveChatId(fresh.id);
          return [fresh];
        }
        if (id === activeChatId) {
          setActiveChatId(next[0].id);
        }
        return next;
      });
    },
    [activeChatId]
  );

  // Click a past recommendation in the history table
  const handleSelectRecord = useCallback(
    (id: string) => {
      setActiveRecordId(id);
      const entry = history.find((h) => h.record_id === id);
      if (entry) {
        // Show the recommendation in a synthetic "done" view on the active chat
        updateActiveChat({
          done: {
            status: "success",
            thread_id: entry.thread_id,
            recommendation: entry.recommendation,
            memory_record_id: entry.record_id,
            simulation_result: null,
            disclosure_doc: null,
          },
          threadId: entry.thread_id,
        });
      }
    },
    [history, updateActiveChat]
  );

  return (
    <div className="app">
      <Sidebar
        open={sidebarOpen}
        onToggle={() => setSidebarOpen((o) => !o)}
        chats={chats}
        activeChatId={activeChatId}
        onNewChat={handleNewChat}
        onSelectChat={handleSelectChat}
        onDeleteChat={handleDeleteChat}
        history={history}
        activeRecordId={activeRecordId}
        activeThread={activeThread}
        onSelectRecord={handleSelectRecord}
      />

      <main className={`main ${sidebarOpen ? "sidebar-open" : "sidebar-closed"}`}>
        <div className="main-grid">
          <ChatPanel
            onRunStarted={handleRunStarted}
            onNode={handleNode}
            onDone={handleDone}
            activeThread={activeThread}
            trace={trace}
            done={done}
            prompt={prompt}
            setPrompt={setPrompt}
            loanDoc={loanDoc}
            setLoanDoc={setLoanDoc}
          />
          <ResultsPanel
            trace={trace}
            done={done}
            history={history}
            historyError={historyError}
          />
        </div>
      </main>
    </div>
  );
}
