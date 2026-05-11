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

type CommitMove = "down" | "up" | "right" | "left" | "none";

interface CellEditorProps {
  value: unknown;
  field: ContractProperty;
  onCommit: (value: unknown, move?: CommitMove) => void;
  onCancel: () => void;
  onError?: (message: string) => void;
}

// Parse the raw editor string into the value the SDK should receive.
// Returns `{ ok, value }` so the caller can keep the editor open on
// invalid input rather than silently dropping the keystrokes.
function parseByType(
  raw: string,
  logicalType: ContractProperty["logicalType"],
): { ok: true; value: unknown } | { ok: false; error: string } {
  const trimmed = raw.trim();
  if (trimmed === "") return { ok: true, value: null };
  switch (logicalType) {
    case "integer": {
      if (!/^-?\d+$/.test(trimmed)) return { ok: false, error: "must be an integer" };
      const n = Number.parseInt(trimmed, 10);
      if (!Number.isFinite(n)) return { ok: false, error: "integer out of range" };
      return { ok: true, value: n };
    }
    case "number": {
      const n = Number(trimmed);
      if (!Number.isFinite(n)) return { ok: false, error: "must be a number" };
      return { ok: true, value: n };
    }
    case "boolean": {
      if (trimmed === "true") return { ok: true, value: true };
      if (trimmed === "false") return { ok: true, value: false };
      return { ok: false, error: "boolean must be true or false" };
    }
    case "array":
    case "object": {
      try {
        const parsed = JSON.parse(trimmed);
        if (logicalType === "array" && !Array.isArray(parsed)) {
          return { ok: false, error: "must be a JSON array" };
        }
        if (
          logicalType === "object" &&
          (parsed === null || typeof parsed !== "object" || Array.isArray(parsed))
        ) {
          return { ok: false, error: "must be a JSON object" };
        }
        return { ok: true, value: parsed };
      } catch (err) {
        return { ok: false, error: "invalid JSON" };
      }
    }
    case "date":
      // Accept either yyyy-mm-dd from <input type=date> or any non-empty
      // string the user typed (free text fallback).
      if (/^\d{4}-\d{2}-\d{2}$/.test(trimmed)) {
        return { ok: true, value: trimmed };
      }
      return { ok: true, value: trimmed };
    case "timestamp": {
      // <input type=datetime-local> emits yyyy-mm-ddThh:mm[:ss], no `Z`.
      // Normalise to ISO-8601 UTC if it parses cleanly.
      if (/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2})?$/.test(trimmed)) {
        const d = new Date(trimmed + (trimmed.length === 16 ? ":00Z" : "Z"));
        if (!Number.isNaN(d.getTime())) {
          return { ok: true, value: d.toISOString().replace(/\.\d{3}Z$/, "Z") };
        }
      }
      return { ok: true, value: trimmed };
    }
    default:
      return { ok: true, value: trimmed };
  }
}

function stringifyForEdit(value: unknown, logicalType: ContractProperty["logicalType"]): string {
  if (value == null) return "";
  if (logicalType === "array" || logicalType === "object") {
    try {
      return JSON.stringify(value);
    } catch {
      return String(value);
    }
  }
  if (logicalType === "timestamp") {
    // datetime-local wants yyyy-mm-ddThh:mm (no zone).
    const s = String(value);
    const m = /^(\d{4}-\d{2}-\d{2})T(\d{2}:\d{2})(?::\d{2})?/.exec(s);
    return m ? `${m[1]}T${m[2]}` : s;
  }
  return String(value);
}

interface TagInputEditorProps {
  initial: unknown;
  onCommit: (value: string[], move?: CommitMove) => void;
  onCancel: () => void;
}

// Inline tag/chip editor for `logicalType: array`. Each existing item
// shows as a chip with an × remove button; the trailing text input
// accepts new items (Enter or comma to add, Backspace on empty to peel
// the last chip off, Escape to cancel the whole edit).
function TagInputEditor({ initial, onCommit, onCancel }: TagInputEditorProps) {
  const initialTags = (() => {
    if (Array.isArray(initial)) return initial.map((x) => String(x));
    if (typeof initial === "string") {
      try {
        const parsed = JSON.parse(initial);
        if (Array.isArray(parsed)) return parsed.map((x) => String(x));
      } catch {}
    }
    return [];
  })();
  const [tags, setTags] = useState<string[]>(initialTags);
  const [draft, setDraft] = useState<string>("");
  const inputRef = useRef<HTMLInputElement>(null);
  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  const flushDraft = (raw: string) => {
    // Split on commas so users can paste comma-separated lists.
    const parts = raw
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean);
    if (!parts.length) return tags;
    const next = [...tags, ...parts];
    setTags(next);
    setDraft("");
    return next;
  };

  const removeAt = (i: number) => {
    setTags((cur) => cur.filter((_, j) => j !== i));
    inputRef.current?.focus();
  };

  const commit = (move: CommitMove) => {
    const next = draft.trim() ? flushDraft(draft) : tags;
    onCommit(next, move);
  };

  return (
    <div
      className="tag-input"
      // Commit when focus leaves the whole container, not just the inner input
      // (which would fire when the user clicks a chip's × button).
      onBlur={(e) => {
        if (!e.currentTarget.contains(e.relatedTarget as Node | null)) {
          commit("none");
        }
      }}
    >
      {tags.map((tag, i) => (
        <span key={`${tag}-${i}`} className="tag tag-chip">
          {tag}
          <button
            type="button"
            className="tag-chip-x"
            tabIndex={-1}
            onMouseDown={(e) => e.preventDefault()}
            onClick={() => removeAt(i)}
            title="remove"
          >
            ×
          </button>
        </span>
      ))}
      <input
        ref={inputRef}
        className="tag-input-field mono"
        value={draft}
        placeholder={tags.length ? "" : "add item, press Enter"}
        onChange={(e) => {
          const v = e.target.value;
          // Comma typed → commit the segment as a tag.
          if (v.endsWith(",")) {
            flushDraft(v);
            return;
          }
          setDraft(v);
        }}
        onKeyDown={(e) => {
          if (e.key === "Enter") {
            e.preventDefault();
            if (draft.trim()) {
              flushDraft(draft);
              return;
            }
            // Enter on empty input → commit the whole array.
            commit(e.shiftKey ? "up" : "down");
            return;
          }
          if (e.key === "Tab") {
            e.preventDefault();
            commit(e.shiftKey ? "left" : "right");
            return;
          }
          if (e.key === "Escape") {
            e.preventDefault();
            onCancel();
            return;
          }
          if (e.key === "Backspace" && draft === "" && tags.length > 0) {
            e.preventDefault();
            removeAt(tags.length - 1);
            return;
          }
        }}
      />
    </div>
  );
}

function CellEditor({ value, field, onCommit, onCancel, onError }: CellEditorProps) {
  const logicalType = field.logicalType;
  const [v, setV] = useState<string>(() => stringifyForEdit(value, logicalType));
  const inputRef = useRef<HTMLInputElement | null>(null);
  const selectRef = useRef<HTMLSelectElement | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);
  useEffect(() => {
    inputRef.current?.focus();
    inputRef.current?.select();
    selectRef.current?.focus();
    textareaRef.current?.focus();
    textareaRef.current?.select();
  }, []);

  const commit = (raw: string, move: CommitMove) => {
    const parsed = parseByType(raw, logicalType);
    if (!parsed.ok) {
      onError?.(`${field.name}: ${parsed.error}`);
      return;
    }
    onCommit(parsed.value, move);
  };

  const handleKey = (
    e: React.KeyboardEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>,
  ) => {
    if (e.key === "Escape") {
      e.preventDefault();
      onCancel();
      return;
    }
    if (e.key === "Enter") {
      // In textarea (array/object), allow newline with shift+enter for
      // hand-edited multi-line JSON; commit on bare Enter.
      const isTextarea = logicalType === "array" || logicalType === "object";
      if (isTextarea && e.shiftKey) return;
      e.preventDefault();
      commit(v, e.shiftKey ? "up" : "down");
      return;
    }
    if (e.key === "Tab") {
      e.preventDefault();
      commit(v, e.shiftKey ? "left" : "right");
      return;
    }
  };

  // Contract declares an explicit enum → render the closed list as a
  // dropdown regardless of the underlying logicalType (strings are the
  // common case; integers can be enumerated too).
  if (field.enum && field.enum.length > 0) {
    return (
      <select
        ref={selectRef}
        className="cell-input mono"
        value={v}
        onChange={(e) => {
          setV(e.target.value);
          commit(e.target.value, "none");
        }}
        onBlur={() => commit(v, "none")}
        onKeyDown={handleKey}
      >
        {!field.required && <option value=""></option>}
        {field.enum.map((opt) => (
          <option key={opt} value={opt}>
            {opt}
          </option>
        ))}
      </select>
    );
  }

  if (logicalType === "boolean") {
    return (
      <select
        ref={selectRef}
        className="cell-input mono"
        value={v}
        onChange={(e) => {
          setV(e.target.value);
          // selects don't always emit a follow-on blur; commit eagerly.
          commit(e.target.value, "none");
        }}
        onBlur={() => commit(v, "none")}
        onKeyDown={handleKey}
      >
        <option value=""></option>
        <option value="true">true</option>
        <option value="false">false</option>
      </select>
    );
  }

  if (logicalType === "array") {
    return (
      <TagInputEditor
        initial={value}
        onCommit={(arr, move) => onCommit(arr, move)}
        onCancel={onCancel}
      />
    );
  }

  if (logicalType === "object") {
    return (
      <textarea
        ref={textareaRef}
        className="cell-input mono cell-input-multi"
        rows={2}
        value={v}
        placeholder='{"k":"v"}'
        onChange={(e) => setV(e.target.value)}
        onBlur={() => commit(v, "none")}
        onKeyDown={handleKey}
      />
    );
  }

  const inputType =
    logicalType === "integer" || logicalType === "number"
      ? "number"
      : logicalType === "date"
      ? "date"
      : logicalType === "timestamp"
      ? "datetime-local"
      : "text";
  const step = logicalType === "integer" ? "1" : logicalType === "number" ? "any" : undefined;

  return (
    <input
      ref={inputRef}
      className="cell-input mono"
      type={inputType}
      step={step}
      value={v}
      onChange={(e) => setV(e.target.value)}
      onBlur={() => commit(v, "none")}
      onKeyDown={handleKey}
    />
  );
}

interface CellValueProps {
  value: unknown;
  field: ContractProperty;
}

const NUMBER_FMT = new Intl.NumberFormat(undefined, { maximumFractionDigits: 6 });

function CellValue({ value, field }: CellValueProps) {
  if (value == null) return <span className="null mono">∅ null</span>;

  // Booleans: visual tone instead of bare "true"/"false" text.
  if (field.logicalType === "boolean") {
    if (value === true) return <span className="pill" data-tone="ok">✓ true</span>;
    if (value === false) return <span className="pill" data-tone="warn">✗ false</span>;
    return <span className="ellipsis">{String(value)}</span>;
  }

  // Numbers: right-align + locale grouping. Integers render without
  // decimals; numbers keep significant precision up to 6 digits.
  if (field.logicalType === "integer" || field.logicalType === "number") {
    const n = typeof value === "number" ? value : Number(value);
    if (Number.isFinite(n)) {
      return <span className="mono num">{NUMBER_FMT.format(n)}</span>;
    }
    return <span className="ellipsis">{String(value)}</span>;
  }

  // Arrays: render each item as a compact inline chip; cap at 3 visible
  // and roll the rest into a "+N" badge so wide rows don't shove other
  // columns offscreen. Empty arrays read as a single muted `[]` glyph.
  if (field.logicalType === "array") {
    const items = Array.isArray(value)
      ? value
      : (() => {
          try {
            const parsed = JSON.parse(String(value));
            return Array.isArray(parsed) ? parsed : null;
          } catch {
            return null;
          }
        })();
    if (items === null) return <span className="ellipsis">{String(value)}</span>;
    if (items.length === 0)
      return <span className="null mono small">[ ]</span>;
    const visible = items.slice(0, 3);
    const remainder = items.length - visible.length;
    return (
      <span className="chip-row">
        {visible.map((item, i) => (
          <span key={i} className="tag tag-cell">{String(item)}</span>
        ))}
        {remainder > 0 && (
          <span className="tag tag-cell muted">+{remainder}</span>
        )}
      </span>
    );
  }

  // Objects: compact one-line JSON so the cell stays readable;
  // truncate with ellipsis when wider than the column.
  if (field.logicalType === "object") {
    let compact: string;
    try {
      compact =
        typeof value === "string"
          ? value
          : JSON.stringify(value);
    } catch {
      compact = String(value);
    }
    return <span className="mono ellipsis">{compact}</span>;
  }

  // Enum: render the constrained value as a pill so it scans
  // visually like the closed choice it is.
  if (field.enum && field.enum.length > 0 && typeof value === "string") {
    return <span className="tag">{value}</span>;
  }

  const v = String(value);
  if (field.logicalType === "timestamp") {
    return <span className="mono small">{v.replace("T", " ").replace("Z", " Z")}</span>;
  }
  if (field.primaryKey) return <span className="mono">{v}</span>;
  // URL-looking values: clickable, opens in a new tab. Matches the
  // colour treatment the cell used to have, just upgraded to a real
  // anchor.
  if (field.name.includes("url") || /^https?:\/\//.test(v)) {
    const href = /^https?:\/\//.test(v) ? v : undefined;
    if (href) {
      return (
        <a
          className="mono ellipsis url cell-link"
          href={href}
          target="_blank"
          rel="noreferrer"
          onClick={(e) => e.stopPropagation()}
        >
          {v}
        </a>
      );
    }
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
  focused: boolean;
  editable: boolean;
  setEditing: (v: { recordId: string; field: string } | null) => void;
  setFocused: (v: { recordId: string; field: string } | null) => void;
  onHover: (info: { recordId: string; field: string; x: number; y: number } | null) => void;
  onCommit: (
    recordId: string,
    field: string,
    value: unknown,
    move?: CommitMove,
  ) => void;
  onEditError?: (message: string) => void;
}

function Cell({
  recordId,
  field,
  value,
  prov,
  stale,
  pulsing,
  editing,
  focused,
  editable,
  setEditing,
  setFocused,
  onHover,
  onCommit,
  onEditError,
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
    setFocused({ recordId, field: field.name });
    if (editable && !isPK) setEditing({ recordId, field: field.name });
  };

  if (editing) {
    return (
      <td className="td td-edit">
        <CellEditor
          value={value}
          field={field}
          onCommit={(v, move) => onCommit(recordId, field.name, v, move)}
          onCancel={() => setEditing(null)}
          onError={onEditError}
        />
      </td>
    );
  }

  const isNumeric =
    field.logicalType === "integer" || field.logicalType === "number";
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
        isNumeric && "td-num",
        focused && "td-focused",
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
  focused: { recordId: string; field: string } | null;
  setFocused: (v: { recordId: string; field: string } | null) => void;
  selected: Set<string>;
  setSelected: (s: Set<string>) => void;
  onHover: (info: { recordId: string; field: string; x: number; y: number } | null) => void;
  onCommit: (
    recordId: string,
    field: string,
    value: unknown,
    move?: CommitMove,
  ) => void;
  onPickField: (name: string) => void;
  onEditError?: (message: string) => void;
}

// Per-field "preferred for content" widths — used as a floor so common
// columns (like company_name) stay roomy even when their header is short.
const COL_WIDTHS: Record<string, number> = {
  company_name: 240,
  company_url: 230,
  industry_tag: 150,
  industry_name: 180,
  employee_size: 130,
  hq_country: 100,
  created_at: 170,
};

const COL_MIN_WIDTH = 60;

// Compute the natural width to show the full header (name + chips) without
// truncation, then take the max with any "content-preferred" override.
function defaultColWidth(prop: ContractProperty): number {
  // JetBrains Mono 11px ≈ 7.5px / char; field-badge ~32, type-chip ~58, gutter ~32.
  const nameW = prop.name.length * 7.5;
  const badgeW = (prop.primaryKey ? 32 : 0) + (prop["x-derived"] ? 32 : 0);
  const typeW = 58;
  const gutter = 32;
  const headerFit = Math.ceil(nameW + badgeW + typeW + gutter);
  const explicit = COL_WIDTHS[prop.name];
  return Math.max(headerFit, explicit ?? 0);
}

export function RecordsGrid({
  records,
  cols,
  primaryKey,
  actor,
  provenance,
  pulsingCells,
  editing,
  setEditing,
  focused,
  setFocused,
  selected,
  setSelected,
  onHover,
  onCommit,
  onPickField,
  onEditError,
}: RecordsGridProps) {
  const [colOverrides, setColOverrides] = useState<Record<string, number>>({});
  const widthOf = (c: ContractProperty) =>
    colOverrides[c.name] ?? defaultColWidth(c);

  const startColResize = (
    name: string,
    startWidth: number,
    e: React.MouseEvent<HTMLDivElement>,
  ) => {
    e.preventDefault();
    e.stopPropagation();
    const startX = e.clientX;
    const onMove = (ev: MouseEvent) => {
      const next = Math.max(COL_MIN_WIDTH, startWidth + (ev.clientX - startX));
      setColOverrides((s) => ({ ...s, [name]: next }));
    };
    const onUp = () => {
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
      document.body.classList.remove("col-resizing");
    };
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
    document.body.classList.add("col-resizing");
  };

  const resetColWidth = (name: string) =>
    setColOverrides((s) => {
      if (!(name in s)) return s;
      const n = { ...s };
      delete n[name];
      return n;
    });

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
            <col key={c.name} style={{ width: widthOf(c) }} />
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
                <div
                  className="th-resize"
                  onMouseDown={(e) => startColResize(c.name, widthOf(c), e)}
                  onDoubleClick={(e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    resetColWidth(c.name);
                  }}
                  onClick={(e) => e.stopPropagation()}
                  title="Drag to resize · double-click to auto-fit"
                />
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
                      focused={
                        !editing &&
                        focused?.recordId === id &&
                        focused?.field === c.name
                      }
                      editable={isEditable(c)}
                      setEditing={setEditing}
                      setFocused={setFocused}
                      onHover={onHover}
                      onCommit={onCommit}
                      onEditError={onEditError}
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
