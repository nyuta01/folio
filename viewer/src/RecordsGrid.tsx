import { useEffect, useRef, useState } from "react";
import { Icons } from "./Icons";
import type { ContractProperty, ProvenanceEntry } from "./types";

const cls = (...xs: Array<string | false | null | undefined>) =>
  xs.filter(Boolean).join(" ");

const fmtTime = (iso: string): string => {
  const d = new Date(iso);
  const now = new Date();
  const diff = (now.getTime() - d.getTime()) / 1000;
  if (diff < 60) return Math.max(1, Math.floor(diff)) + "s ago";
  if (diff < 3600) return Math.floor(diff / 60) + "m ago";
  if (diff < 86400) return Math.floor(diff / 3600) + "h ago";
  return d.toISOString().slice(0, 10);
};

const fmtCost = (n: number) => "$" + n.toFixed(4);

interface FieldBadgeProps {
  prop: ContractProperty;
}
function FieldBadge({ prop }: FieldBadgeProps) {
  if (prop.primaryKey) return <span className="pill mono" data-tone="key">PK</span>;
  if (prop["x-derived"]) return <span className="pill mono" data-tone="ai">AI</span>;
  return null;
}

export function TypeChip({ t }: { t: string }) {
  return <span className="type-chip mono">{t}</span>;
}

export { FieldBadge };

interface CellEditorProps {
  value: unknown;
  onCommit: (value: string) => void;
  onCancel: () => void;
}
function CellEditor({ value, onCommit, onCancel }: CellEditorProps) {
  const [v, setV] = useState(value == null ? "" : String(value));
  const ref = useRef<HTMLInputElement>(null);
  useEffect(() => {
    ref.current?.focus();
    ref.current?.select();
  }, []);
  return (
    <input
      ref={ref}
      className="cell-input mono"
      value={v}
      onChange={(e) => setV(e.target.value)}
      onBlur={() => onCommit(v)}
      onKeyDown={(e) => {
        if (e.key === "Enter") {
          e.preventDefault();
          onCommit(v);
        }
        if (e.key === "Escape") {
          e.preventDefault();
          onCancel();
        }
      }}
    />
  );
}

interface CellValueProps {
  value: unknown;
  field: ContractProperty;
}
function CellValue({ value, field }: CellValueProps) {
  if (value == null) return <span className="null mono">∅ null</span>;
  const v = String(value);
  if (field.logicalType === "timestamp") {
    return <span className="mono small">{v.replace("T", " ").replace("Z", " Z")}</span>;
  }
  if (field.primaryKey) return <span className="mono">{v}</span>;
  if (field.name.includes("url") || /^https?:\/\//.test(v)) {
    return <span className="mono ellipsis url">{v}</span>;
  }
  if (field.logicalType === "string" && field["x-derived"]) {
    return <span className="tag">{v}</span>;
  }
  if (field.logicalType === "string" && /^[A-Z]{2,3}$/.test(v)) {
    return <span className="mono iso">{v}</span>;
  }
  return <span className="ellipsis">{v}</span>;
}

interface CellProps {
  recordId: string;
  field: ContractProperty;
  value: unknown;
  prov: ProvenanceEntry | undefined;
  stale: boolean;
  pulsing: boolean;
  editing: boolean;
  editable: boolean;
  setEditing: (v: { recordId: string; field: string } | null) => void;
  onHover: (info: { recordId: string; field: string; x: number; y: number } | null) => void;
  onCommit: (recordId: string, field: string, value: string) => void;
}

function Cell({
  recordId,
  field,
  value,
  prov,
  stale,
  pulsing,
  editing,
  editable,
  setEditing,
  onHover,
  onCommit,
}: CellProps) {
  const isPK = field.primaryKey === true;
  const isDerived = field["x-derived"] === true;
  const overridden = isDerived && prov?.source === "human_override";
  const provKind = prov?.source;

  const handleEnter = (e: React.MouseEvent<HTMLTableCellElement>) => {
    if (prov) {
      const r = (e.currentTarget as HTMLTableCellElement).getBoundingClientRect();
      onHover({ recordId, field: field.name, x: r.left, y: r.bottom });
    }
  };
  const handleLeave = () => onHover(null);
  const handleClick = () => {
    if (editable && !isPK) setEditing({ recordId, field: field.name });
  };

  if (editing) {
    return (
      <td className="td td-edit">
        <CellEditor
          value={value}
          onCommit={(v) => onCommit(recordId, field.name, v)}
          onCancel={() => setEditing(null)}
        />
      </td>
    );
  }

  return (
    <td
      className={cls(
        "td",
        isDerived && "td-derived",
        overridden && "td-overridden",
        stale && "td-stale",
        pulsing && "td-pulse",
        value == null && "td-null",
        isPK && "td-pk",
      )}
      onMouseEnter={handleEnter}
      onMouseLeave={handleLeave}
      onClick={handleClick}
      title={editable ? "click to edit" : undefined}
    >
      <div className="td-inner">
        {isDerived && !stale && value != null && provKind && (
          <span
            className={cls(
              "cell-prov-dot",
              provKind === "human_override" ? "human" : provKind,
            )}
          />
        )}
        {stale && <span className="cell-prov-dot stale" title="stale" />}
        <CellValue value={value} field={field} />
      </div>
    </td>
  );
}

interface RecordsGridProps {
  records: Record<string, unknown>[];
  cols: ContractProperty[];
  primaryKey: string;
  actor: string;
  provenance: Record<string, ProvenanceEntry | null>;
  pulsingCells: Set<string>;
  editing: { recordId: string; field: string } | null;
  setEditing: (v: { recordId: string; field: string } | null) => void;
  selected: Set<string>;
  setSelected: (s: Set<string>) => void;
  onHover: (info: { recordId: string; field: string; x: number; y: number } | null) => void;
  onCommit: (recordId: string, field: string, value: string) => void;
  onPickField: (name: string) => void;
}

const COL_WIDTHS: Record<string, number> = {
  id: 110,
  company_name: 240,
  company_url: 230,
  industry_tag: 150,
  employee_size: 130,
  hq_country: 100,
  created_at: 170,
};

export function RecordsGrid({
  records,
  cols,
  primaryKey,
  actor,
  provenance,
  pulsingCells,
  editing,
  setEditing,
  selected,
  setSelected,
  onHover,
  onCommit,
  onPickField,
}: RecordsGridProps) {
  const toggleSel = (id: string) => {
    const n = new Set(selected);
    if (n.has(id)) n.delete(id);
    else n.add(id);
    setSelected(n);
  };
  const toggleAll = () =>
    setSelected(
      selected.size === records.length
        ? new Set()
        : new Set(records.map((r) => String(r[primaryKey]))),
    );

  const isEditable = (prop: ContractProperty) => {
    const patterns = prop["x-editable-by"];
    if (!patterns?.length) return false;
    return patterns.some((p) => p === actor || p === "*" || matchPattern(p, actor));
  };

  return (
    <div className="grid-wrap">
      <table className="grid" style={{ tableLayout: "fixed" }}>
        <colgroup>
          <col style={{ width: 36 }} />
          {cols.map((c) => (
            <col key={c.name} style={{ width: COL_WIDTHS[c.name] || 140 }} />
          ))}
        </colgroup>
        <thead>
          <tr>
            <th className="th-check">
              <input
                type="checkbox"
                checked={selected.size === records.length && records.length > 0}
                onChange={toggleAll}
              />
            </th>
            {cols.map((c) => (
              <th
                key={c.name}
                onClick={() => onPickField(c.name)}
                className={cls(c["x-derived"] && "th-derived")}
              >
                <div className="th-inner">
                  <span className="mono">{c.name}</span>
                  <FieldBadge prop={c} />
                  <TypeChip t={c.logicalType} />
                </div>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {records.map((r) => {
            const id = String(r[primaryKey]);
            return (
              <tr key={id} className={cls(selected.has(id) && "selected")}>
                <td className="td-check">
                  <input
                    type="checkbox"
                    checked={selected.has(id)}
                    onChange={() => toggleSel(id)}
                  />
                </td>
                {cols.map((c) => {
                  const k = `${id}::${c.name}`;
                  const prov = provenance[k] ?? undefined;
                  const stale =
                    c["x-derived"] === true &&
                    r[c.name] == null &&
                    (prov == null || prov.source !== "human_override");
                  return (
                    <Cell
                      key={c.name}
                      recordId={id}
                      field={c}
                      value={r[c.name]}
                      prov={prov ?? undefined}
                      stale={stale}
                      pulsing={pulsingCells.has(k)}
                      editing={
                        editing?.recordId === id && editing?.field === c.name
                      }
                      editable={isEditable(c)}
                      setEditing={setEditing}
                      onHover={onHover}
                      onCommit={onCommit}
                    />
                  );
                })}
              </tr>
            );
          })}
          {records.length === 0 && (
            <tr>
              <td colSpan={cols.length + 1} className="empty">
                No records match the current filter.
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}

function matchPattern(pattern: string, actor: string): boolean {
  // fnmatch-style: * matches any, ? matches one char.
  const re = new RegExp(
    "^" +
      pattern
        .replace(/[.+^${}()|[\]\\]/g, "\\$&")
        .replace(/\*/g, ".*")
        .replace(/\?/g, ".") +
      "$",
  );
  return re.test(actor);
}

interface ProvenancePopProps {
  rid: string;
  field: string;
  x: number;
  y: number;
  provenance: Record<string, ProvenanceEntry | null>;
}

export function ProvenancePop({ rid, field, x, y, provenance }: ProvenancePopProps) {
  const last = provenance[`${rid}::${field}`];
  if (!last) return null;
  const tone =
    last.source === "human_override"
      ? "human"
      : last.source === "ai"
      ? "ai"
      : "neutral";
  return (
    <div
      className="prov-pop"
      style={{ left: Math.min(x, window.innerWidth - 360), top: y + 6 }}
    >
      <div className="prov-head">
        <span className="pill mono" data-tone={tone}>
          {last.source}
        </span>
        <span className="mono small muted">{fmtTime(last.at)}</span>
      </div>
      <div className="prov-row">
        <span className="muted small">actor</span>
        <span className="mono small">{last.actor}</span>
      </div>
      {last.model && (
        <div className="prov-row">
          <span className="muted small">model</span>
          <span className="mono small">{last.model}</span>
        </div>
      )}
      {last.cost_usd != null && (
        <div className="prov-row">
          <span className="muted small">cost</span>
          <span className="mono small">{fmtCost(Number(last.cost_usd))}</span>
        </div>
      )}
      {last.input_hash && (
        <div className="prov-row">
          <span className="muted small">input_hash</span>
          <span className="mono small ellipsis" style={{ maxWidth: 180 }}>
            {last.input_hash.replace("sha256:", "").slice(0, 12)}…
          </span>
        </div>
      )}
    </div>
  );
}

export function SelectionBar({
  count,
  onClear,
  onDelete,
}: {
  count: number;
  onClear: () => void;
  onDelete: () => void;
}) {
  return (
    <div className="selection-bar">
      <span className="mono small">{count} selected</span>
      <span className="spacer" />
      <button className="ghost-btn small" onClick={onClear}>
        Clear
      </button>
      <button
        className="ghost-btn small"
        onClick={onDelete}
        style={{ color: "var(--err)" }}
      >
        <Icons.X size={10} /> Delete
      </button>
    </div>
  );
}
