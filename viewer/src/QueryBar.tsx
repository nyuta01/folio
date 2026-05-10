import { useEffect, useRef, useState } from "react";
import { Icons } from "./Icons";
import type { ContractProperty, QueryResult } from "./types";

const cls = (...xs: Array<string | false | null | undefined>) =>
  xs.filter(Boolean).join(" ");

export function isWhereOnly(s: string): boolean {
  const t = (s || "").trim();
  if (!t) return true;
  return !/^\s*select/i.test(t);
}

interface HistoryEntry {
  q: string;
  rows: number | null;
  at: string;
}

interface QueryBarProps {
  filter: string;
  setFilter: (v: string) => void;
  activeFilter: string;
  filterErr: string | null;
  filtered: Record<string, unknown>[];
  totalRecords: number;
  busy: boolean;
  onApplyWhere: () => void;
  onClear: () => void;
  onRunSql: (sql: string) => Promise<QueryResult | { error: string }>;
  onMaterialize: () => void;
  fields: ContractProperty[];
  history: HistoryEntry[];
  drawerOpen: boolean;
  setDrawerOpen: (v: boolean) => void;
  queryResult: QueryResult | { error: string } | null;
  setQueryResult: (v: QueryResult | { error: string } | null) => void;
}

export function QueryBar({
  filter,
  setFilter,
  activeFilter,
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
  queryResult,
  setQueryResult,
}: QueryBarProps) {
  const [drawerTab, setDrawerTab] = useState<"result" | "history" | "schema">("result");
  const [drawerH, setDrawerH] = useState(280);
  const dragRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setDrawerOpen(true);
        setTimeout(
          () => document.querySelector<HTMLInputElement>(".qbar-input input")?.focus(),
          0,
        );
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [setDrawerOpen]);

  const startResize = (e: React.MouseEvent<HTMLDivElement>) => {
    const startY = e.clientY;
    const startH = drawerH;
    const move = (ev: MouseEvent) =>
      setDrawerH(Math.max(140, Math.min(620, startH - (ev.clientY - startY))));
    const up = () => {
      window.removeEventListener("mousemove", move);
      window.removeEventListener("mouseup", up);
    };
    window.addEventListener("mousemove", move);
    window.addEventListener("mouseup", up);
  };

  const handleRun = async () => {
    if (isWhereOnly(filter)) {
      onApplyWhere();
      setDrawerOpen(true);
    } else {
      const out = await onRunSql(filter);
      setQueryResult(out);
      setDrawerOpen(true);
    }
  };

  return (
    <div className="qbar-wrap">
      <div className="qbar">
        <div className={cls("qbar-input", filterErr && "err")}>
          <Icons.Db size={12} />
          <span className="mono prefix">QUERY</span>
          <input
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            placeholder="industry_tag IS NULL  ·  SELECT * FROM records …"
            onKeyDown={(e) => {
              if (e.key === "Enter") handleRun();
            }}
            className="mono"
          />
          {filter && (
            <button className="icon-btn" onClick={onClear} title="Clear">
              <Icons.X size={11} />
            </button>
          )}
          <span className={cls("qbar-mode mono small", isWhereOnly(filter) ? "mode-where" : "mode-sql")}>
            {isWhereOnly(filter) ? "WHERE" : "SQL"}
          </span>
          <button className="apply-btn" onClick={handleRun} disabled={busy}>
            Run <span className="kbd">↵</span>
          </button>
        </div>

        <div className="spacer" />

        <button
          className="toolbtn primary"
          onClick={onMaterialize}
          disabled={busy}
        >
          {busy ? (
            <>
              <Icons.Refresh size={12} style={{ animation: "spin 1s linear infinite" }} />
              {" "}Materializing…
            </>
          ) : (
            <>
              <Icons.Sparkle size={12} /> Materialize
            </>
          )}
        </button>
      </div>

      {drawerOpen && (
        <div className="qdrawer" style={{ height: drawerH }}>
          <div className="qdrawer-handle" onMouseDown={startResize} ref={dragRef} />
          <div className="qdrawer-tabs">
            {([
              {
                id: "result" as const,
                label: "Result",
                icon: "Cell",
                badge:
                  queryResult && "rows" in queryResult ? queryResult.rows.length : null,
              },
              {
                id: "history" as const,
                label: "History",
                icon: "Clock",
                badge: history.length || null,
              },
              {
                id: "schema" as const,
                label: "Schema",
                icon: "Db",
                badge: null,
              },
            ]).map((t) => {
              const Ico = (Icons as Record<string, (props: { size: number }) => JSX.Element>)[t.icon];
              return (
                <button
                  key={t.id}
                  className={cls("qdrawer-tab", drawerTab === t.id && "active")}
                  onClick={() => setDrawerTab(t.id)}
                >
                  <Ico size={11} /> {t.label}
                  {t.badge != null && (
                    <span className="qd-tab-badge mono">{t.badge}</span>
                  )}
                </button>
              );
            })}
            <span className="spacer" />
            <span className="muted small mono">DuckDB · table records · read-only</span>
            <button
              className="icon-btn"
              onClick={() => setDrawerOpen(false)}
              title="Close"
            >
              <Icons.X size={11} />
            </button>
          </div>
          <div className="qdrawer-body">
            {drawerTab === "result" && (
              <ResultPanel
                result={queryResult}
                activeFilter={activeFilter}
                filtered={filtered}
                totalRecords={totalRecords}
                onClear={onClear}
                isWhere={isWhereOnly(filter)}
              />
            )}
            {drawerTab === "history" && (
              <HistoryPanel
                history={history}
                onLoad={(q) => {
                  setFilter(q);
                  setTimeout(handleRun, 0);
                }}
              />
            )}
            {drawerTab === "schema" && (
              <SchemaPickerPanel
                fields={fields}
                onInsert={(name) => {
                  if (isWhereOnly(filter)) {
                    setFilter(filter ? `${filter} AND ${name} IS NOT NULL` : `${name} IS NOT NULL`);
                  } else {
                    setFilter(`${filter} ${name}`);
                  }
                }}
              />
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function ResultPanel({
  result,
  activeFilter,
  filtered,
  totalRecords,
  onClear,
  isWhere,
}: {
  result: QueryResult | { error: string } | null;
  activeFilter: string;
  filtered: Record<string, unknown>[];
  totalRecords: number;
  onClear: () => void;
  isWhere: boolean;
}) {
  if (!result && !activeFilter) {
    return (
      <div className="qd-empty">
        <div className="muted small">Run a query to see results here.</div>
        <div className="muted small mono" style={{ marginTop: 6 }}>Examples:</div>
        <ul className="qd-examples mono">
          <li><code>industry_tag IS NULL</code> — quick filter</li>
          <li><code>SELECT industry_tag, COUNT(*) AS n FROM records GROUP BY 1</code></li>
          <li><code>SELECT * FROM records WHERE company_name LIKE '%Inc%' LIMIT 10</code></li>
        </ul>
      </div>
    );
  }
  if (isWhere && activeFilter && !result) {
    return (
      <div className="qd-empty">
        <div className="qd-result-row">
          <span className="mono small">
            <Icons.Check size={10} /> Filter active
          </span>
          <span className="muted small">
            {filtered.length} of {totalRecords} rows match — visible in grid
          </span>
          <span className="spacer" />
          <button className="ghost-btn small" onClick={onClear}>
            Clear filter
          </button>
        </div>
        <div className="muted small mono qd-active-q">{activeFilter}</div>
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
  onInsert,
}: {
  fields: ContractProperty[];
  onInsert: (name: string) => void;
}) {
  return (
    <div className="qd-schema">
      <div className="muted small" style={{ padding: "4px 10px 8px" }}>
        Click a field to insert into query.
      </div>
      <ul className="qd-schema-list">
        {fields.map((f) => (
          <li key={f.name} className="qd-schema-item" onClick={() => onInsert(f.name)}>
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
      </ul>
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
