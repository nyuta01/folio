import { useEffect, useMemo, useRef, useState } from "react";
import { Icons } from "./Icons";
import type { ContractProperty, QueryResult } from "./types";

const cls = (...xs: Array<string | false | null | undefined>) =>
  xs.filter(Boolean).join(" ");

export function isWhereOnly(s: string): boolean {
  const t = (s || "").trim();
  if (!t) return true;
  return !/^\s*select/i.test(t);
}

export type DrawerTab = "query" | "result" | "history" | "schema";

interface HistoryEntry {
  q: string;
  rows: number | null;
  at: string;
}

interface QueryBarProps {
  filter: string;
  setFilter: (v: string) => void;
  activeFilter: string;
  activeFilterErr: string | null;
  filterErr: string | null;
  filtered: Record<string, unknown>[];
  totalRecords: number;
  busy: boolean;
  onApplyWhere: (explicit?: string) => void;
  onClear: () => void;
  onRunSql: (sql: string) => Promise<QueryResult | { error: string }>;
  onMaterialize: () => void;
  fields: ContractProperty[];
  history: HistoryEntry[];
  drawerOpen: boolean;
  setDrawerOpen: (v: boolean) => void;
  drawerTab: DrawerTab;
  setDrawerTab: (t: DrawerTab) => void;
  queryResult: QueryResult | { error: string } | null;
  setQueryResult: (v: QueryResult | { error: string } | null) => void;
  sheetLabel: string;
}

export function QueryBar({
  filter,
  setFilter,
  activeFilter,
  activeFilterErr,
  filterErr,
  filtered,
  totalRecords,
  busy,
  onApplyWhere,
  onClear,
  onRunSql,
  onMaterialize,
  fields,
  history,
  drawerOpen,
  setDrawerOpen,
  drawerTab,
  setDrawerTab,
  queryResult,
  setQueryResult,
  sheetLabel,
}: QueryBarProps) {
  const [drawerH, setDrawerH] = useState(280);
  const dragRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setDrawerOpen(true);
        setDrawerTab("query");
        setTimeout(
          () => document.querySelector<HTMLInputElement>(".qbar-input input")?.focus(),
          0,
        );
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [setDrawerOpen, setDrawerTab]);

  const startResize = (e: React.MouseEvent<HTMLDivElement>) => {
    const startY = e.clientY;
    const startH = drawerH;
    const move = (ev: MouseEvent) =>
      setDrawerH(Math.max(140, Math.min(620, startH + (ev.clientY - startY))));
    const up = () => {
      window.removeEventListener("mousemove", move);
      window.removeEventListener("mouseup", up);
    };
    window.addEventListener("mousemove", move);
    window.addEventListener("mouseup", up);
  };

  const handleRun = async () => {
    if (!drawerOpen) setDrawerOpen(true);
    if (isWhereOnly(filter)) {
      onApplyWhere();
    } else {
      const out = await onRunSql(filter);
      setQueryResult(out);
    }
    setDrawerTab("result");
  };

  const runWith = async (q: string) => {
    setFilter(q);
    if (!drawerOpen) setDrawerOpen(true);
    if (isWhereOnly(q)) {
      onApplyWhere(q);
    } else {
      const out = await onRunSql(q);
      setQueryResult(out);
    }
    setDrawerTab("result");
  };

  const tabs: Array<{
    id: DrawerTab;
    label: string;
    icon: keyof typeof Icons;
    badge: number | null;
  }> = [
    { id: "query", label: "Query", icon: "Search", badge: null },
    {
      id: "result",
      label: "Result",
      icon: "Cell",
      badge:
        queryResult && "rows" in queryResult ? queryResult.rows.length : null,
    },
    {
      id: "history",
      label: "History",
      icon: "Clock",
      badge: history.length || null,
    },
    { id: "schema", label: "Schema", icon: "Db", badge: null },
  ];

  return (
    <div className="qbar-wrap">
      <div
        className={cls("qdrawer", !drawerOpen && "collapsed")}
        style={drawerOpen ? { height: drawerH } : undefined}
      >
        {drawerOpen && (
          <div
            className="qdrawer-handle"
            onMouseDown={startResize}
            ref={dragRef}
          />
        )}
        <div className="qdrawer-tabs">
          <SheetSwitcher label={sheetLabel} />
          {tabs.map((t) => {
            const Ico = Icons[t.icon];
            return (
              <button
                key={t.id}
                className={cls(
                  "qdrawer-tab",
                  drawerOpen && drawerTab === t.id && "active",
                )}
                onClick={() => {
                  if (!drawerOpen) setDrawerOpen(true);
                  setDrawerTab(t.id);
                }}
              >
                <Ico size={11} /> {t.label}
                {t.badge != null && (
                  <span className="qd-tab-badge mono">{t.badge}</span>
                )}
              </button>
            );
          })}
          <span className="spacer" />
          {activeFilter && (
            <span className="qdrawer-meta mono small muted">
              <Icons.Filter size={10} /> WHERE active
            </span>
          )}
          <button
            className="toolbtn primary small"
            onClick={onMaterialize}
            disabled={busy}
            title="Materialize derived fields (⌘↵)"
          >
            {busy ? (
              <>
                <Icons.Refresh
                  size={11}
                  style={{ animation: "spin 1s linear infinite" }}
                />
                {" "}Materializing…
              </>
            ) : (
              <>
                <Icons.Sparkle size={11} /> Materialize
              </>
            )}
          </button>
          <button
            className="icon-btn"
            onClick={() => setDrawerOpen(!drawerOpen)}
            title={drawerOpen ? "Collapse panel" : "Expand panel"}
          >
            <Icons.Chevron
              size={11}
              style={{
                transform: drawerOpen ? "rotate(0deg)" : "rotate(180deg)",
                transition: "transform 140ms ease",
              }}
            />
          </button>
        </div>
        {drawerOpen && (
          <div className="qdrawer-body">
            {drawerTab === "query" && (
              <QueryPanel
                filter={filter}
                setFilter={setFilter}
                filterErr={filterErr}
                fields={fields}
                onClear={onClear}
                onRun={handleRun}
                busy={busy}
              />
            )}
            {drawerTab === "result" && (
              <ResultPanel
                result={queryResult}
                activeFilter={activeFilter}
                activeFilterErr={activeFilterErr}
                filtered={filtered}
                totalRecords={totalRecords}
                onClear={onClear}
                isWhere={isWhereOnly(filter)}
                onPickExample={runWith}
              />
            )}
            {drawerTab === "history" && (
              <HistoryPanel history={history} onLoad={(q) => runWith(q)} />
            )}
            {drawerTab === "schema" && (
              <SchemaPickerPanel
                fields={fields}
                onApply={(clause) => runWith(clause)}
              />
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function QueryPanel({
  filter,
  setFilter,
  filterErr,
  fields,
  onClear,
  onRun,
  busy,
}: {
  filter: string;
  setFilter: (v: string) => void;
  filterErr: string | null;
  fields: ContractProperty[];
  onClear: () => void;
  onRun: () => void;
  busy: boolean;
}) {
  const inputRef = useRef<HTMLTextAreaElement | null>(null);
  const [acOpen, setAcOpen] = useState(false);
  const [acIdx, setAcIdx] = useState(0);
  const [caretPos, setCaretPos] = useState(0);

  useEffect(() => {
    const el = inputRef.current;
    if (!el) return;
    el.focus();
    el.setSelectionRange(el.value.length, el.value.length);
  }, []);

  const mode = isWhereOnly(filter) ? "WHERE" : "SQL";

  const tokenAtCaret = useMemo(() => {
    const before = filter.slice(0, caretPos);
    const m = /([A-Za-z_][A-Za-z0-9_]*)$/.exec(before);
    if (!m) return null;
    const tok = m[1];
    const KW = new Set([
      "SELECT", "FROM", "WHERE", "AND", "OR", "NOT", "NULL", "IS",
      "LIKE", "IN", "GROUP", "BY", "ORDER", "LIMIT", "AS", "COUNT",
      "DESC", "ASC", "ON", "JOIN",
    ]);
    if (KW.has(tok.toUpperCase())) return null;
    return { token: tok, start: m.index, end: caretPos };
  }, [filter, caretPos]);

  const suggestions = useMemo(() => {
    if (!tokenAtCaret) return [];
    const t = tokenAtCaret.token.toLowerCase();
    return fields
      .filter(
        (f) => f.name.toLowerCase().includes(t) && f.name !== tokenAtCaret.token,
      )
      .slice(0, 6);
  }, [tokenAtCaret, fields]);

  useEffect(() => {
    setAcIdx(0);
  }, [tokenAtCaret?.token]);

  const acceptSuggestion = (name: string) => {
    if (!tokenAtCaret) return;
    const next =
      filter.slice(0, tokenAtCaret.start) + name + filter.slice(tokenAtCaret.end);
    setFilter(next);
    setAcOpen(false);
    setTimeout(() => {
      const el = inputRef.current;
      if (!el) return;
      const pos = tokenAtCaret.start + name.length;
      el.setSelectionRange(pos, pos);
      setCaretPos(pos);
      el.focus();
    }, 0);
  };

  const insertAtCaret = (snippet: string) => {
    const el = inputRef.current;
    const start = el?.selectionStart ?? filter.length;
    const end = el?.selectionEnd ?? filter.length;
    const before = filter.slice(0, start);
    const after = filter.slice(end);
    const sep = before && !before.endsWith(" ") ? " " : "";
    const next = before + sep + snippet + after;
    setFilter(next);
    setTimeout(() => {
      const e2 = inputRef.current;
      if (!e2) return;
      const pos = (before + sep + snippet).length;
      e2.setSelectionRange(pos, pos);
      e2.focus();
      setCaretPos(pos);
    }, 0);
  };

  const onInputKey = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (acOpen && suggestions.length > 0) {
      if (e.key === "ArrowDown") {
        e.preventDefault();
        setAcIdx((i) => (i + 1) % suggestions.length);
        return;
      }
      if (e.key === "ArrowUp") {
        e.preventDefault();
        setAcIdx((i) => (i - 1 + suggestions.length) % suggestions.length);
        return;
      }
      if (e.key === "Tab") {
        e.preventDefault();
        acceptSuggestion(suggestions[acIdx].name);
        return;
      }
      if (e.key === "Escape") {
        e.preventDefault();
        setAcOpen(false);
        return;
      }
    }
    // ⌘↵ / Ctrl↵ runs the query; plain Enter inserts a newline (textarea).
    if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
      e.preventDefault();
      setAcOpen(false);
      onRun();
    }
  };

  const onInputChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setFilter(e.target.value);
    setCaretPos(e.target.selectionStart ?? e.target.value.length);
    setAcOpen(true);
  };

  const onInputSelect = (e: React.SyntheticEvent<HTMLTextAreaElement>) => {
    const t = e.currentTarget;
    setCaretPos(t.selectionStart ?? t.value.length);
  };

  return (
    <div className="qpanel">
      <form
        className="qpanel-form"
        onSubmit={(e) => {
          e.preventDefault();
          onRun();
        }}
      >
        <div className="qpanel-row qpanel-row-head">
          <label className="qpanel-label mono">
            <Icons.Db size={11} /> QUERY
          </label>
          <ModeBadge mode={mode} />
          <span className="spacer" />
          <span className="muted small">
            {mode === "WHERE"
              ? "client filter — runs on the visible grid"
              : "DuckDB read-only — runs on table records"}
          </span>
        </div>

        <div className={cls("qpanel-textarea-wrap", filterErr && "err")}>
          <textarea
            ref={inputRef}
            value={filter}
            onChange={onInputChange}
            onSelect={onInputSelect}
            onFocus={() => setAcOpen(true)}
            onBlur={() => setTimeout(() => setAcOpen(false), 120)}
            placeholder={
              "industry_tag IS NULL\n" +
              "company_name LIKE '%Inc%' AND country = 'US'\n" +
              "SELECT industry_tag, COUNT(*) FROM records GROUP BY 1"
            }
            onKeyDown={onInputKey}
            className="qpanel-textarea mono"
            rows={4}
            spellCheck={false}
          />
          {acOpen && suggestions.length > 0 && tokenAtCaret && (
            <ul className="qbar-ac mono">
              {suggestions.map((f, i) => (
                <li
                  key={f.name}
                  className={cls("qbar-ac-item", i === acIdx && "active")}
                  onMouseDown={(e) => {
                    e.preventDefault();
                    acceptSuggestion(f.name);
                  }}
                  onMouseEnter={() => setAcIdx(i)}
                >
                  <span className="mono">{f.name}</span>
                  <span className="type-chip mono">{f.logicalType}</span>
                  {f["x-derived"] && (
                    <span className="pill mono" data-tone="ai">AI</span>
                  )}
                  {f.primaryKey && (
                    <span className="pill mono" data-tone="key">PK</span>
                  )}
                </li>
              ))}
              <li className="qbar-ac-hint mono small muted">
                Tab to accept · Esc to close
              </li>
            </ul>
          )}
        </div>

        <div className="qpanel-row qpanel-row-actions">
          <button
            type="button"
            className="ghost-btn small"
            onClick={onClear}
            disabled={!filter}
          >
            <Icons.X size={10} /> Clear
          </button>
          <span className="muted small mono">
            <span className="kbd">⌘</span>
            <span className="kbd">↵</span> to run · <span className="kbd">Tab</span> to autocomplete
          </span>
          <span className="spacer" />
          <button type="submit" className="apply-btn" disabled={busy}>
            Run <span className="kbd">⌘↵</span>
          </button>
        </div>
      </form>

      <SyntaxRef fields={fields} onInsert={insertAtCaret} />
    </div>
  );
}

const SYNTAX_GROUPS: Array<{
  title: string;
  items: Array<{ snippet: string; desc: string }>;
}> = [
  {
    title: "Filter (WHERE) — predicates",
    items: [
      { snippet: "field IS NULL", desc: "field is empty / null" },
      { snippet: "field IS NOT NULL", desc: "field has a value" },
      { snippet: "field = 'value'", desc: "exact match (string)" },
      { snippet: "field != 'value'", desc: "not equal" },
      { snippet: "field LIKE '%abc%'", desc: "contains substring" },
      { snippet: "field IN ('a', 'b')", desc: "one of a list" },
      { snippet: "field = 42", desc: "numeric / boolean / null literal" },
    ],
  },
  {
    title: "Filter (WHERE) — combine",
    items: [
      {
        snippet: "country = 'US' AND industry_tag IS NULL",
        desc: "all conditions must match (AND)",
      },
    ],
  },
  {
    title: "SQL (DuckDB) — full SELECT",
    items: [
      {
        snippet: "SELECT * FROM records LIMIT 10",
        desc: "first 10 rows",
      },
      {
        snippet: "SELECT industry_tag, COUNT(*) FROM records GROUP BY 1",
        desc: "aggregate",
      },
      {
        snippet:
          "SELECT * FROM records WHERE company_name LIKE '%Inc%' ORDER BY company_name",
        desc: "filter + sort",
      },
    ],
  },
];

function SyntaxRef({
  fields,
  onInsert,
}: {
  fields: ContractProperty[];
  onInsert: (s: string) => void;
}) {
  const [open, setOpen] = useState(true);
  return (
    <div className={cls("qpanel-syntax", open && "open")}>
      <button
        type="button"
        className="qpanel-syntax-toggle"
        onClick={() => setOpen((v) => !v)}
      >
        <Icons.Chevron
          size={11}
          style={{
            transform: open ? "rotate(0deg)" : "rotate(-90deg)",
            transition: "transform 120ms ease",
          }}
        />
        <span className="mono small">Syntax reference</span>
        <span className="muted small" style={{ marginLeft: 6 }}>
          click any example to insert at cursor
        </span>
      </button>
      {open && (
        <div className="qpanel-syntax-body">
          <section className="qpanel-syntax-section">
            <h5 className="qpanel-syntax-title mono small">
              Fields ({fields.length})
            </h5>
            <div className="qpanel-syntax-fields">
              {fields.map((f) => (
                <button
                  key={f.name}
                  type="button"
                  className="qpanel-field-chip mono"
                  onClick={() => onInsert(f.name)}
                  title={`${f.logicalType}${f.primaryKey ? " · PK" : ""}${f["x-derived"] ? " · AI" : ""}`}
                >
                  {f.name}
                </button>
              ))}
            </div>
          </section>
          {SYNTAX_GROUPS.map((g) => (
            <section className="qpanel-syntax-section" key={g.title}>
              <h5 className="qpanel-syntax-title mono small">{g.title}</h5>
              <ul className="qpanel-syntax-list">
                {g.items.map((it) => (
                  <li key={it.snippet}>
                    <button
                      type="button"
                      className="qpanel-syntax-snippet"
                      onClick={() => onInsert(it.snippet)}
                      title="Click to insert at cursor"
                    >
                      <code className="mono">{it.snippet}</code>
                    </button>
                    <span className="muted small qpanel-syntax-desc">
                      {it.desc}
                    </span>
                  </li>
                ))}
              </ul>
            </section>
          ))}
        </div>
      )}
    </div>
  );
}

function SheetSwitcher({ label }: { label: string }) {
  const [menuOpen, setMenuOpen] = useState(false);
  const [switching, setSwitching] = useState<string | null>(null);
  const [recents, setRecents] = useState<
    Array<{ path: string; name: string }>
  >([]);
  const wrapRef = useRef<HTMLDivElement | null>(null);
  const bridge = typeof window !== "undefined" ? window.folioBridge : undefined;

  useEffect(() => {
    if (!bridge || !menuOpen) return;
    bridge.recentSheets().then(setRecents).catch(() => setRecents([]));
  }, [bridge, menuOpen]);

  useEffect(() => {
    if (!menuOpen) return;
    const onDoc = (e: MouseEvent) => {
      const node = wrapRef.current;
      if (node && !node.contains(e.target as Node)) {
        setMenuOpen(false);
      }
    };
    // Use mousedown so the close fires before any click handler inside the menu;
    // contains() correctly keeps the menu open while interacting with it.
    window.addEventListener("mousedown", onDoc);
    return () => window.removeEventListener("mousedown", onDoc);
  }, [menuOpen]);

  if (!bridge) {
    return (
      <button
        type="button"
        className="sheet-switcher disabled"
        title="Sheet switching is available in Folio Desktop. The browser viewer is bound to the sheet the server was started with."
        disabled
      >
        <Icons.Folder size={11} />
        <span className="mono small ellipsis">{label}</span>
      </button>
    );
  }

  const onOpenPicker = async () => {
    setMenuOpen(false);
    // Show overlay immediately. If the dialog is cancelled, hide it again.
    // If the user picks a sheet, the new URL navigates this renderer away
    // and the overlay state goes away with it.
    setSwitching("Switching sheet…");
    try {
      const res = await bridge.openSheet();
      if (!res?.ok) setSwitching(null);
    } catch (err) {
      setSwitching(null);
      console.error("openSheet failed", err);
    }
  };

  const onPickRecent = async (path: string) => {
    setMenuOpen(false);
    const name = path.split("/").pop() ?? path;
    setSwitching(`Switching to ${name}…`);
    try {
      const res = await bridge.switchSheet(path);
      if (!res?.ok) setSwitching(null);
    } catch (err) {
      setSwitching(null);
      console.error("switchSheet failed", err);
    }
  };

  return (
    <>
    <div className="sheet-switcher-wrap" ref={wrapRef}>
      <button
        type="button"
        className="sheet-switcher"
        onClick={onOpenPicker}
        title="Open another sheet (⌘O)"
      >
        <Icons.Folder size={11} />
        <span className="mono small ellipsis">{label}</span>
      </button>
      <button
        type="button"
        className="sheet-switcher-caret"
        onClick={(e) => {
          e.stopPropagation();
          setMenuOpen((v) => !v);
        }}
        title="Recent sheets"
        aria-label="Recent sheets"
      >
        <Icons.Chevron size={10} />
      </button>
      {menuOpen && (
        <div className="sheet-switcher-menu" role="menu">
          <button
            type="button"
            className="ssm-item"
            onClick={onOpenPicker}
            role="menuitem"
          >
            <Icons.Folder size={11} />
            <span>Open Sheet…</span>
            <span className="kbd-tiny mono small">⌘O</span>
          </button>
          {recents.length > 0 ? (
            <>
              <div className="ssm-sep" />
              <div className="ssm-head mono small muted">Recent</div>
              {recents.map((r) => (
                <button
                  key={r.path}
                  type="button"
                  className="ssm-item ssm-recent"
                  onClick={() => onPickRecent(r.path)}
                  role="menuitem"
                  title={r.path}
                >
                  <span className="mono">{r.name}</span>
                  <span className="muted small ellipsis ssm-recent-path">
                    {r.path}
                  </span>
                </button>
              ))}
            </>
          ) : (
            <>
              <div className="ssm-sep" />
              <div className="ssm-head mono small muted">No recent sheets</div>
            </>
          )}
        </div>
      )}
    </div>
    {switching && (
      <div className="switch-overlay" role="status" aria-live="polite">
        <div className="switch-card">
          <div className="splash-spinner" aria-hidden="true" />
          <div className="mono small">{switching}</div>
        </div>
      </div>
    )}
    </>
  );
}

function ModeBadge({ mode }: { mode: "WHERE" | "SQL" }) {
  const tip =
    mode === "WHERE"
      ? "WHERE — filters the visible rows in the grid (client-side, fast)."
      : "SQL — runs full SELECT on DuckDB and shows the result here.";
  return (
    <span
      className={cls(
        "qbar-mode mono small",
        mode === "WHERE" ? "mode-where" : "mode-sql",
      )}
      data-tip={tip}
    >
      {mode}
    </span>
  );
}

function ResultPanel({
  result,
  activeFilter,
  activeFilterErr,
  filtered,
  totalRecords,
  onClear,
  isWhere,
  onPickExample,
}: {
  result: QueryResult | { error: string } | null;
  activeFilter: string;
  activeFilterErr: string | null;
  filtered: Record<string, unknown>[];
  totalRecords: number;
  onClear: () => void;
  isWhere: boolean;
  onPickExample: (q: string) => void;
}) {
  const examples = [
    { q: "industry_tag IS NULL", label: "industry_tag IS NULL", note: "quick filter" },
    {
      q: "SELECT industry_tag, COUNT(*) AS n FROM records GROUP BY 1",
      label: "SELECT industry_tag, COUNT(*) AS n FROM records GROUP BY 1",
      note: null,
    },
    {
      q: "SELECT * FROM records WHERE company_name LIKE '%Inc%' LIMIT 10",
      label: "SELECT * FROM records WHERE company_name LIKE '%Inc%' LIMIT 10",
      note: null,
    },
  ];
  if (!result && !activeFilter) {
    return (
      <div className="qd-empty">
        <div className="muted small">Run a query to see results here.</div>
        <div className="muted small mono" style={{ marginTop: 6 }}>Examples (click to run):</div>
        <ul className="qd-examples mono">
          {examples.map((ex) => (
            <li key={ex.q}>
              <button
                type="button"
                className="qd-example-btn"
                onClick={() => onPickExample(ex.q)}
                title="Click to insert and run"
              >
                <code>{ex.label}</code>
                {ex.note && <span className="muted small"> — {ex.note}</span>}
              </button>
            </li>
          ))}
        </ul>
      </div>
    );
  }
  if (isWhere && activeFilter && !result) {
    return (
      <div className="qd-empty">
        <div className="qd-result-row">
          {activeFilterErr ? (
            <span className="mono small" style={{ color: "var(--err)" }}>
              <Icons.X size={10} /> Filter parse error
            </span>
          ) : (
            <span className="mono small">
              <Icons.Check size={10} /> Filter active
            </span>
          )}
          <span className="muted small">
            {activeFilterErr
              ? "showing all rows — fix expression to filter"
              : `${filtered.length} of ${totalRecords} rows match — visible in grid`}
          </span>
          <span className="spacer" />
          <button className="ghost-btn small" onClick={onClear}>
            Clear filter
          </button>
        </div>
        <div className="muted small mono qd-active-q">{activeFilter}</div>
        {activeFilterErr && (
          <div
            className="mono small qd-active-q"
            style={{
              color: "var(--err)",
              background:
                "color-mix(in oklab, var(--err) 8%, var(--panel))",
              marginTop: 4,
            }}
          >
            {activeFilterErr}
          </div>
        )}
        <div className="muted small" style={{ marginTop: 8, fontSize: 11 }}>
          Supported: <code>field IS NULL</code>, <code>field = 'val'</code>,{" "}
          <code>field LIKE '%v%'</code>, <code>field IN (a, b)</code>, joined
          with <code>AND</code>. Or open <b>Schema</b> for guided filters.
        </div>
      </div>
    );
  }
  if (!result) return <div className="qd-empty muted small">No results.</div>;
  if ("error" in result) {
    return (
      <div className="qd-error">
        <Icons.X size={12} /> <span className="mono">{result.error}</span>
      </div>
    );
  }
  const rows = result.rows;
  const cols = rows.length ? Object.keys(rows[0]) : [];
  return (
    <div className="qd-result">
      <div className="qd-result-row">
        <span className="mono small">
          <Icons.Check size={10} /> {rows.length} row{rows.length === 1 ? "" : "s"} ·{" "}
          {cols.length} col{cols.length === 1 ? "" : "s"}
        </span>
        <span className="spacer" />
        <button className="ghost-btn small" onClick={() => copyAsCsv(rows, cols)}>
          <Icons.Copy size={10} /> Copy CSV
        </button>
        <button
          className="ghost-btn small"
          onClick={() => downloadCsv(rows, cols, "query.csv")}
        >
          <Icons.Download size={10} /> Download
        </button>
      </div>
      <div className="qd-result-table-wrap">
        <table className="qtable mono">
          <thead>
            <tr>
              {cols.map((c) => (
                <th key={c}>{c}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.slice(0, 200).map((r, i) => (
              <tr key={i}>
                {cols.map((c) => (
                  <td key={c}>
                    {r[c] == null ? <span className="null mono">∅</span> : String(r[c])}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {rows.length > 200 && (
        <div className="muted small mono" style={{ padding: "4px 10px" }}>
          showing first 200 of {rows.length}
        </div>
      )}
    </div>
  );
}

function HistoryPanel({
  history,
  onLoad,
}: {
  history: HistoryEntry[];
  onLoad: (q: string) => void;
}) {
  if (history.length === 0)
    return (
      <div className="qd-empty muted small">
        No queries yet. Press ↵ to run one.
      </div>
    );
  return (
    <ul className="qd-list">
      {history
        .slice()
        .reverse()
        .map((h, i) => (
          <li key={i} className="qd-item" onClick={() => onLoad(h.q)}>
            <div className="qd-item-q mono small">{h.q}</div>
            <div className="qd-item-meta muted small mono">
              {h.rows != null ? `${h.rows} rows` : ""} · {h.at}
            </div>
          </li>
        ))}
    </ul>
  );
}

function SchemaPickerPanel({
  fields,
  onApply,
}: {
  fields: ContractProperty[];
  onApply: (clause: string) => void;
}) {
  const [open, setOpen] = useState<string | null>(null);
  return (
    <div className="qd-schema">
      <div className="muted small" style={{ padding: "4px 10px 8px" }}>
        Click a field to filter the grid by it.
      </div>
      <ul className="qd-schema-list">
        {fields.map((f) => (
          <li key={f.name} className="qd-schema-item-wrap">
            <button
              type="button"
              className={cls("qd-schema-item", open === f.name && "open")}
              onClick={() => setOpen((cur) => (cur === f.name ? null : f.name))}
            >
              <span className="mono">{f.name}</span>
              <span className="type-chip mono">{f.logicalType}</span>
              {f["x-derived"] && (
                <span className="pill mono" data-tone="ai">AI</span>
              )}
              {f.primaryKey && (
                <span className="pill mono" data-tone="key">PK</span>
              )}
              <span className="spacer" />
              <Icons.ChevronR
                size={10}
                style={{
                  transform: open === f.name ? "rotate(90deg)" : "none",
                  transition: "transform 120ms ease",
                }}
              />
            </button>
            {open === f.name && (
              <FilterOps
                field={f}
                onApply={(clause) => {
                  onApply(clause);
                  setOpen(null);
                }}
              />
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}

function FilterOps({
  field,
  onApply,
}: {
  field: ContractProperty;
  onApply: (clause: string) => void;
}) {
  const [eqVal, setEqVal] = useState("");
  const [likeVal, setLikeVal] = useState("");
  const isText = field.logicalType === "string";
  return (
    <div className="qd-filter-ops">
      <button
        className="ghost-btn small"
        onClick={() => onApply(`${field.name} IS NULL`)}
      >
        IS NULL
      </button>
      <button
        className="ghost-btn small"
        onClick={() => onApply(`${field.name} IS NOT NULL`)}
      >
        IS NOT NULL
      </button>
      <div className="qd-filter-op-input">
        <span className="mono small muted">=</span>
        <input
          className="mono"
          value={eqVal}
          onChange={(e) => setEqVal(e.target.value)}
          placeholder="value"
          onKeyDown={(e) => {
            if (e.key === "Enter" && eqVal) {
              onApply(`${field.name} = '${eqVal.replace(/'/g, "''")}'`);
            }
          }}
        />
        <button
          className="ghost-btn small"
          disabled={!eqVal}
          onClick={() =>
            onApply(`${field.name} = '${eqVal.replace(/'/g, "''")}'`)
          }
        >
          Apply
        </button>
      </div>
      {isText && (
        <div className="qd-filter-op-input">
          <span className="mono small muted">LIKE</span>
          <input
            className="mono"
            value={likeVal}
            onChange={(e) => setLikeVal(e.target.value)}
            placeholder="%pattern%"
            onKeyDown={(e) => {
              if (e.key === "Enter" && likeVal) {
                onApply(`${field.name} LIKE '${likeVal.replace(/'/g, "''")}'`);
              }
            }}
          />
          <button
            className="ghost-btn small"
            disabled={!likeVal}
            onClick={() =>
              onApply(`${field.name} LIKE '${likeVal.replace(/'/g, "''")}'`)
            }
          >
            Apply
          </button>
        </div>
      )}
    </div>
  );
}

function csvCell(v: unknown): string {
  if (v == null) return "";
  const s = String(v);
  return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}

function copyAsCsv(rows: Record<string, unknown>[], cols: string[]) {
  const lines = [cols.join(",")];
  rows.forEach((r) =>
    lines.push(cols.map((c) => csvCell(r[c])).join(",")),
  );
  navigator.clipboard?.writeText(lines.join("\n"));
}

function downloadCsv(
  rows: Record<string, unknown>[],
  cols: string[],
  name: string,
) {
  const lines = [cols.join(",")];
  rows.forEach((r) =>
    lines.push(cols.map((c) => csvCell(r[c])).join(",")),
  );
  const blob = new Blob([lines.join("\n")], { type: "text/csv" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
