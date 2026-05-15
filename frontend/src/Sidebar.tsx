/**
 * Sidebar.tsx — Left navigation, Mentor-style.
 *
 * - "+ New Chat" button
 * - RECENT CHATS section (localStorage chats list + search + delete-on-hover)
 * - PAST RECOMMENDATIONS section (backend SQLite, only successful runs with drift)
 * - User badge popup at bottom (Settings + Get help)
 *
 * Modals (Settings + Help) live inline at the bottom of this file.
 */

import { useEffect, useMemo, useRef, useState } from "react";
import {
  Plus,
  MessageSquare,
  ChevronLeft,
  ChevronRight,
  Moon,
  Sun,
  TrendingUp,
  Settings2,
  HelpCircle,
  X,
  ExternalLink,
  Search,
  Trash2,
} from "lucide-react";
import type { HistoryEntry } from "./api";
import type { Chat } from "./App";
import { useTheme } from "./theme";

interface Props {
  open: boolean;
  onToggle: () => void;

  // Local chats (Mentor-style)
  chats: Chat[];
  activeChatId: string;
  onNewChat: () => void;
  onSelectChat: (id: string) => void;
  onDeleteChat: (id: string) => void;

  // Backend history (Past Recommendations)
  history: HistoryEntry[];
  activeRecordId: string | null;
  activeThread: string | null;
  onSelectRecord: (id: string) => void;
}

export function Sidebar({
  open,
  onToggle,
  chats,
  activeChatId,
  onNewChat,
  onSelectChat,
  onDeleteChat,
  history,
  activeRecordId,
  activeThread,
  onSelectRecord,
}: Props) {
  const { theme, toggleTheme } = useTheme();
  const [hoveredChatId, setHoveredChatId] = useState<string | null>(null);
  const [hoveredRecordId, setHoveredRecordId] = useState<string | null>(null);
  const [showUserMenu, setShowUserMenu] = useState(false);
  const [modal, setModal] = useState<"settings" | "help" | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [deleteConfirmId, setDeleteConfirmId] = useState<string | null>(null);
  const userMenuRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!showUserMenu) return;
    const handler = (e: MouseEvent) => {
      if (userMenuRef.current && !userMenuRef.current.contains(e.target as Node)) {
        setShowUserMenu(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [showUserMenu]);

  useEffect(() => {
    if (!modal && !deleteConfirmId) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setModal(null);
        setDeleteConfirmId(null);
      }
    };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [modal, deleteConfirmId]);

  // Search filter (title, prompt body, loan doc body)
  const filteredChats = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    if (!q) return chats;
    return chats.filter((c) => {
      return (
        c.title.toLowerCase().includes(q) ||
        c.prompt.toLowerCase().includes(q) ||
        c.loanDoc.toLowerCase().includes(q)
      );
    });
  }, [chats, searchQuery]);

  const openSettings = () => {
    setShowUserMenu(false);
    setModal("settings");
  };
  const openHelp = () => {
    setShowUserMenu(false);
    setModal("help");
  };

  return (
    <>
      {!open && (
        <button className="sidebar-open-btn" onClick={onToggle} title="Open sidebar">
          <ChevronRight size={18} />
        </button>
      )}

      <aside className={`sidebar ${open ? "open" : "closed"}`}>
        {/* Header */}
        <div className="sidebar-header">
          <div className="sidebar-logo">
            <svg
              width="32"
              height="32"
              viewBox="0 0 80 80"
              fill="none"
              xmlns="http://www.w3.org/2000/svg"
              style={{ flexShrink: 0 }}
            >
              <defs>
                <linearGradient id="hedgeOrbit" x1="0" y1="0" x2="80" y2="80" gradientUnits="userSpaceOnUse">
                  <stop offset="0%" stopColor="#4F52D0" />
                  <stop offset="100%" stopColor="#818CF8" />
                </linearGradient>
                <linearGradient id="hedgeRing" x1="0" y1="0" x2="80" y2="80" gradientUnits="userSpaceOnUse">
                  <stop offset="0%" stopColor="#6366F1" stopOpacity="1" />
                  <stop offset="60%" stopColor="#818CF8" stopOpacity="0.6" />
                  <stop offset="100%" stopColor="#C7D2FE" stopOpacity="0.2" />
                </linearGradient>
              </defs>
              <circle cx="40" cy="40" r="37" stroke="url(#hedgeRing)" strokeWidth="2" fill="none" />
              <circle
                cx="40"
                cy="40"
                r="30"
                stroke="#6366F1"
                strokeWidth="0.75"
                fill="none"
                strokeOpacity="0.25"
                strokeDasharray="3 5"
              />
              <circle cx="40" cy="3" r="3.5" fill="#6366F1" />
              <circle cx="71" cy="56" r="2.5" fill="#818CF8" fillOpacity="0.7" />
              <circle cx="9" cy="56" r="2.5" fill="#818CF8" fillOpacity="0.7" />
              <text
                x="40"
                y="47"
                textAnchor="middle"
                fontFamily="'Poppins', 'Inter', sans-serif"
                fontSize="22"
                fontWeight="800"
                letterSpacing="0.5"
                fill="url(#hedgeOrbit)"
              >
                HA
              </text>
            </svg>
            <span className="logo-text">Hedge Advisor</span>
          </div>
          <div style={{ display: "flex", gap: 4 }}>
            <button
              className="icon-btn"
              onClick={toggleTheme}
              title={theme === "light" ? "Switch to dark mode" : "Switch to light mode"}
            >
              {theme === "light" ? <Moon size={16} /> : <Sun size={16} />}
            </button>
            <button className="icon-btn" onClick={onToggle} title="Collapse sidebar">
              <ChevronLeft size={18} />
            </button>
          </div>
        </div>

        {/* New Chat */}
        <button className="new-chat-btn" onClick={onNewChat}>
          <Plus size={16} />
          <span>New Chat</span>
        </button>

        <div className="sidebar-divider" />

        {/* Recent Chats (localStorage) */}
        <div className="sidebar-section">
          <p className="section-title">Recent Chats</p>

          <div className="search-bar">
            <Search size={13} className="search-icon" />
            <input
              className="search-input"
              placeholder="Search chats…"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
            {searchQuery && (
              <button
                className="search-clear"
                onClick={() => setSearchQuery("")}
                title="Clear"
              >
                ×
              </button>
            )}
          </div>
          {searchQuery && (
            <p className="search-result-count">
              {filteredChats.length} result{filteredChats.length !== 1 ? "s" : ""}
            </p>
          )}

          {filteredChats.length === 0 ? (
            <p className="no-chats">
              {searchQuery ? "No chats match your search." : "No chats yet."}
            </p>
          ) : (
            <ul className="chat-list">
              {filteredChats.map((chat) => (
                <li
                  key={chat.id}
                  className={`chat-item ${chat.id === activeChatId ? "active" : ""}`}
                  onMouseEnter={() => setHoveredChatId(chat.id)}
                  onMouseLeave={() => setHoveredChatId(null)}
                  onClick={() => onSelectChat(chat.id)}
                  title={new Date(chat.updatedAt).toLocaleString()}
                >
                  <MessageSquare size={13} className="chat-icon" />
                  <span className="chat-title">{chat.title}</span>
                  {hoveredChatId === chat.id && chats.length > 1 && (
                    <button
                      className="chat-delete-btn"
                      onClick={(e) => {
                        e.stopPropagation();
                        setDeleteConfirmId(chat.id);
                      }}
                      title="Delete chat"
                    >
                      <Trash2 size={12} />
                    </button>
                  )}
                </li>
              ))}
            </ul>
          )}
        </div>

        {/* Past Recommendations (backend SQLite) — only successful runs with drift */}
        {history.length > 0 && (
          <>
            <div className="sidebar-divider" />
            <div className="sidebar-section sidebar-section-secondary">
              <p className="section-title">Past Recommendations</p>
              <ul className="chat-list">
                {history.slice(0, 10).map((h) => (
                  <li
                    key={h.record_id}
                    className={`chat-item ${h.record_id === activeRecordId ? "active" : ""}`}
                    onMouseEnter={() => setHoveredRecordId(h.record_id)}
                    onMouseLeave={() => setHoveredRecordId(null)}
                    onClick={() => onSelectRecord(h.record_id)}
                    title={new Date(h.created_at).toLocaleString()}
                  >
                    <TrendingUp size={13} className="chat-icon" />
                    <span className="chat-title">
                      Hedge {h.recommendation.winner} · $
                      {Math.round(h.recommendation.predicted_saving_usd).toLocaleString()}
                    </span>
                    {hoveredRecordId === h.record_id && h.drift && (
                      <span
                        className="drift-pill"
                        title={`Drift: $${h.drift.delta_usd.toLocaleString()}`}
                      >
                        <TrendingUp size={11} />
                      </span>
                    )}
                  </li>
                ))}
              </ul>
            </div>
          </>
        )}

        {/* Footer — User badge */}
        <div className="sidebar-footer">
          <div className="user-menu-wrapper" ref={userMenuRef}>
            <button
              className="user-badge user-badge-btn"
              onClick={() => setShowUserMenu((p) => !p)}
            >
              <div className="user-avatar">U</div>
              <div className="user-info">
                <span className="user-name">User</span>
                <span className="user-plan">Hedge Advisor</span>
              </div>
            </button>

            {showUserMenu && (
              <div className="user-menu">
                <div className="user-menu-email">Local session · v0.1</div>
                <div className="user-menu-divider" />
                <button className="user-menu-item" onClick={openSettings}>
                  <Settings2 size={15} className="user-menu-item-icon" />
                  <span className="user-menu-item-label">Settings</span>
                </button>
                <button className="user-menu-item" onClick={openHelp}>
                  <HelpCircle size={15} className="user-menu-item-icon" />
                  <span className="user-menu-item-label">Get help</span>
                </button>
              </div>
            )}
          </div>
        </div>
      </aside>

      {/* Delete confirmation dialog */}
      {deleteConfirmId && (
        <div className="modal-overlay" onClick={() => setDeleteConfirmId(null)}>
          <div className="confirm-dialog" onClick={(e) => e.stopPropagation()}>
            <div className="confirm-icon">
              <Trash2 size={22} />
            </div>
            <h3 className="confirm-title">Delete this chat?</h3>
            <p className="confirm-body">
              "{chats.find((c) => c.id === deleteConfirmId)?.title ?? "Untitled"}"
              <br />
              This cannot be undone.
            </p>
            <div className="confirm-actions">
              <button
                className="confirm-cancel"
                onClick={() => setDeleteConfirmId(null)}
              >
                Cancel
              </button>
              <button
                className="confirm-delete"
                onClick={() => {
                  onDeleteChat(deleteConfirmId);
                  setDeleteConfirmId(null);
                }}
              >
                <Trash2 size={13} /> Delete
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Modals */}
      {modal === "settings" && (
        <SettingsModal
          theme={theme}
          toggleTheme={toggleTheme}
          activeThread={activeThread}
          onClose={() => setModal(null)}
        />
      )}
      {modal === "help" && <HelpModal onClose={() => setModal(null)} />}
    </>
  );
}

/* ───────────────────────────────────────────────────────────
   Settings modal
   ─────────────────────────────────────────────────────────── */

function SettingsModal({
  theme,
  toggleTheme,
  activeThread,
  onClose,
}: {
  theme: "light" | "dark";
  toggleTheme: () => void;
  activeThread: string | null;
  onClose: () => void;
}) {
  const backendUrl =
    (import.meta as any).env?.VITE_BACKEND_URL ?? "http://localhost:8000";

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <header className="modal-header">
          <h3 className="modal-title">
            <Settings2 size={18} />
            Settings
          </h3>
          <button className="modal-close" onClick={onClose} title="Close (Esc)">
            <X size={16} />
          </button>
        </header>

        <div className="modal-body">
          <div className="settings-block">
            <h4 className="settings-block-title">Appearance</h4>
            <div className="settings-row">
              <div className="settings-row-info">
                <span className="settings-row-label">Theme</span>
                <span className="settings-row-hint">
                  Currently <strong>{theme}</strong> mode
                </span>
              </div>
              <button className="settings-row-btn" onClick={toggleTheme}>
                {theme === "light" ? (
                  <>
                    <Moon size={13} />
                    <span>Switch to dark</span>
                  </>
                ) : (
                  <>
                    <Sun size={13} />
                    <span>Switch to light</span>
                  </>
                )}
              </button>
            </div>
          </div>

          <div className="settings-block">
            <h4 className="settings-block-title">Connection</h4>
            <div className="settings-row">
              <div className="settings-row-info">
                <span className="settings-row-label">Backend URL</span>
                <span className="settings-row-hint">
                  Set via <code>VITE_BACKEND_URL</code> env var
                </span>
              </div>
              <code className="settings-mono">{backendUrl}</code>
            </div>
            <div className="settings-row">
              <div className="settings-row-info">
                <span className="settings-row-label">Active thread</span>
                <span className="settings-row-hint">
                  LangGraph thread for the current run
                </span>
              </div>
              <code className="settings-mono">{activeThread ?? "— none —"}</code>
            </div>
            <a
              className="settings-link"
              href={`${backendUrl}/health`}
              target="_blank"
              rel="noopener noreferrer"
            >
              <ExternalLink size={13} />
              Check backend health
            </a>
          </div>

          <div className="settings-block">
            <h4 className="settings-block-title">About</h4>
            <div className="settings-about">
              <p>
                <strong>ACTUS Hedge Advisor</strong> v0.1 · Bow-tie multi-agent
                system for autonomous supply-chain hedging.
              </p>
              <p>
                Reasoning agents (Gemini) on the wings, deterministic agents at
                the knot. The prompt never reaches the simulation core.
              </p>
              <p className="settings-about-meta">
                Design docs: <code>DESIGN/DESIGN1/design-1-*.md</code>
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

/* ───────────────────────────────────────────────────────────
   Help modal
   ─────────────────────────────────────────────────────────── */

function HelpModal({ onClose }: { onClose: () => void }) {
  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <header className="modal-header">
          <h3 className="modal-title">
            <HelpCircle size={18} />
            Get help
          </h3>
          <button className="modal-close" onClick={onClose} title="Close (Esc)">
            <X size={16} />
          </button>
        </header>

        <div className="modal-body">
          <div className="settings-block">
            <h4 className="settings-block-title">How to use</h4>
            <ol className="help-list">
              <li>
                Paste your loan document text in the{" "}
                <strong>Private loan document</strong> box.
              </li>
              <li>
                Type a natural-language question in the input bar below.
              </li>
              <li>Press <strong>Enter</strong> or click the send button.</li>
              <li>
                Watch the 8 agents stream their progress, color-coded by bow-tie
                zone.
              </li>
              <li>
                The right panel shows the A/B/C scenarios, the recommended
                scenario, cashflows, and a regulatory (XBRL) disclosure.
              </li>
            </ol>
          </div>

          <div className="settings-block">
            <h4 className="settings-block-title">The bow-tie</h4>
            <p className="help-paragraph">
              The system has 8 agents arranged in a bow-tie. Reasoning agents
              (Gemini) live on the wings — they handle ambiguous, fuzzy
              input/output. Deterministic agents live at the knot — they handle
              exact math and disclosure. The architecture guarantees the user's
              prompt <strong>never</strong> reaches the simulation core
              (invariant I1).
            </p>
            <div className="help-zones">
              <span className="msg-zone-chip chip-pastel-purple">Control plane</span>
              <span className="msg-zone-chip chip-pastel-pink">Left wing</span>
              <span className="msg-zone-chip chip-pastel-yellow">Boundary</span>
              <span className="msg-zone-chip chip-pastel-blue">The knot</span>
              <span className="msg-zone-chip chip-pastel-teal">Right wing</span>
              <span className="msg-zone-chip chip-pastel-orange">Memory loop</span>
            </div>
          </div>

          <div className="settings-block">
            <h4 className="settings-block-title">Troubleshooting</h4>
            <dl className="help-faq">
              <dt>"Failed to fetch"</dt>
              <dd>
                The backend isn't running on <code>localhost:8000</code>. Start
                it with <code>python -m main</code> in the <code>backend/</code>{" "}
                directory.
              </dd>

              <dt>Run halts at the Simulation agent</dt>
              <dd>
                The DRAPS MCP server isn't configured yet. See{" "}
                <code>DESIGN/DESIGN1/design-1-detailed-design.md §6 note 1</code>.
                The system fails honestly — it never fabricates a result.
              </dd>

              <dt>"401" or empty Gemini responses</dt>
              <dd>
                The <code>GEMINI_API_KEY</code> in <code>backend/.env</code> is
                missing or invalid. Get one at{" "}
                <a
                  href="https://aistudio.google.com/apikey"
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  aistudio.google.com/apikey
                </a>
                .
              </dd>
            </dl>
          </div>

          <div className="settings-block">
            <h4 className="settings-block-title">Design documents</h4>
            <p className="help-paragraph">Full design lives in the repo at:</p>
            <pre className="help-codeblock">{`DESIGN/DESIGN1/
├── design-1-problem-solution-impact.md
├── design-1-conceptual-design.md
├── design-1-detailed-design.md
├── design-1-project-structure.md
└── design-1-files-on-disk.md`}</pre>
          </div>
        </div>
      </div>
    </div>
  );
}
