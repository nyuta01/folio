import { useEffect, useMemo, useState } from "react";
import type {
  AddPropertyInput,
  UpdatePropertyInput,
} from "./api";
import { Icons } from "./Icons";
import { ProvenancePop, RecordsGrid, SelectionBar } from "./RecordsGrid";
import { QueryBar, type DrawerTab } from "./QueryBar";
import { RightPanel, type TabId } from "./RightPanel";
import {
  addProperty,
  deleteProperty,
  deleteRecords,
  getContract,
  getProvenance,
  getStatus,
  listRecords,
  materializeAll,
  runQuery,
  updateProperty,
  upsertRecord,
} from "./api";
import { useEventStream } from "./useEventStream";
import type {
  ActivityEntry,
  Contract,
  ProvenanceEntry,
  QueryResult,
  TargetStatus,
} from "./types";

const cls = (...xs: Array<string | false | null | undefined>) =>
  xs.filter(Boolean).join(" ");

function evalFilterClient(
  records: Record<string, unknown>[],
  expr: string,
): { rows: Record<string, unknown>[]; error: string | null } {
  if (!expr || !expr.trim()) return { rows: records, error: null };
  // Accept both single and double quotes for string literals — SQL uses
  // single, but users frequently type double; either is unambiguous here.
  const Q = `(?:'([^']*)'|"([^"]*)")`;
  const reEq = new RegExp(`^(\\w+)\\s*(!=|<>|=)\\s*${Q}$`);
  const reLike = new RegExp(`^(\\w+)\\s+LIKE\\s+${Q}$`, "i");
  const reIn = /^(\w+)\s+IN\s*\(([^)]+)\)$/i;
  // Bare numeric / boolean comparisons (no quotes): country = 5
  const reEqBare = /^(\w+)\s*(!=|<>|=)\s*(-?\d+(?:\.\d+)?|true|false|null)$/i;
  try {
    const pieces = expr
      .split(/\s+AND\s+/i)
      .map((s) => s.trim())
      .filter(Boolean);
    const pred = (r: Record<string, unknown>) =>
      pieces.every((p) => {
        let m;
        if ((m = p.match(/^(\w+)\s+IS\s+NULL$/i))) return r[m[1]] == null;
        if ((m = p.match(/^(\w+)\s+IS\s+NOT\s+NULL$/i))) return r[m[1]] != null;
        if ((m = p.match(reLike))) {
          const pat = m[2] ?? m[3];
          const re = new RegExp(
            "^" +
              pat
                .replace(/[.+?^${}()|[\]\\]/g, "\\$&")
                .replace(/%/g, ".*")
                .replace(/_/g, ".") +
              "$",
            "i",
          );
          return r[m[1]] != null && re.test(String(r[m[1]]));
        }
        if ((m = p.match(reIn))) {
          const vals = m[2]
            .split(",")
            .map((s) => s.trim().replace(/^['"]|['"]$/g, ""));
          return vals.includes(String(r[m[1]]));
        }
        if ((m = p.match(reEq))) {
          const lit = m[3] ?? m[4];
          const v = r[m[1]];
          return m[2] === "=" ? String(v) === lit : String(v) !== lit;
        }
        if ((m = p.match(reEqBare))) {
          const v = r[m[1]];
          const rhs = m[3].toLowerCase();
          if (rhs === "null") return m[2] === "=" ? v == null : v != null;
          if (rhs === "true" || rhs === "false") {
            const b = rhs === "true";
            return m[2] === "=" ? v === b : v !== b;
          }
          const n = Number(rhs);
          return m[2] === "=" ? Number(v) === n : Number(v) !== n;
        }
        throw new Error("unparsed clause: " + p);
      });
    return { rows: records.filter(pred), error: null };
  } catch (e) {
    return { rows: records, error: e instanceof Error ? e.message : String(e) };
  }
}

export default function App() {
  const [contract, setContract] = useState<Contract | null>(null);
  const [records, setRecords] = useState<Record<string, unknown>[]>([]);
  const [provenance, setProvenance] = useState<
    Record<string, ProvenanceEntry | null>
  >({});
  const [status, setStatus] = useState<Record<string, TargetStatus>>({});
  const [activity, setActivity] = useState<ActivityEntry[]>([]);
  const [actor] = useState("agent:human");
  const [agentOnline] = useState(true);

  const [filter, setFilter] = useState("");
  const [activeFilter, setActiveFilter] = useState("");
  const [queryResult, setQueryResult] = useState<
    QueryResult | { error: string } | null
  >(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [drawerTab, setDrawerTab] = useState<DrawerTab>("query");
  const [history, setHistory] = useState<
    Array<{ q: string; rows: number | null; at: string }>
  >([]);

  const [editing, setEditing] = useState<{ recordId: string; field: string } | null>(null);
  const [focused, setFocused] = useState<{ recordId: string; field: string } | null>(null);
  const [toast, setToast] = useState<{ text: string; tone: "info" | "ok" | "err"; at: number } | null>(null);
  const [undoStack, setUndoStack] = useState<
    Array<{ rid: string; field: string; before: unknown; after: unknown }>
  >([]);
  const [redoStack, setRedoStack] = useState<
    Array<{ rid: string; field: string; before: unknown; after: unknown }>
  >([]);
  const [hovered, setHovered] = useState<{
    recordId: string;
    field: string;
    x: number;
    y: number;
  } | null>(null);
  const [pulsingCells, setPulsingCells] = useState<Set<string>>(new Set());
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [busy, setBusy] = useState(false);
  const [helpOpen, setHelpOpen] = useState(false);

  const [rpCollapsed, setRpCollapsed] = useState(false);
  const [rpTab, setRpTab] = useState<TabId>("schema");
  const [inspectorField, setInspectorField] = useState<string | null>(null);

  const evt = useEventStream();

  // initial load
  useEffect(() => {
    Promise.all([getContract(), listRecords({ limit: 500 }), getStatus()])
      .then(([c, recs, st]) => {
        setContract(c);
        setRecords(recs.records);
        setStatus(st);
      })
      .catch((e) => console.error(e));
  }, []);

  // refresh records & status after materialize finishes
  useEffect(() => {
    if (!evt.latest) return;
    if (evt.latest.kind === "materialize.start") {
      addActivity({
        id: "ms" + Date.now(),
        kind: "materialize.start",
        actor: String(evt.latest.actor || "system"),
        at: String(evt.latest.ts),
        meta: evt.latest as Record<string, unknown>,
      });
    } else if (
      evt.latest.kind === "materialize.end" ||
      evt.latest.kind === "materialize.error"
    ) {
      addActivity({
        id: "me" + Date.now(),
        kind: evt.latest.kind as "materialize.end" | "materialize.error",
        actor: String(evt.latest.actor || "system"),
        at: String(evt.latest.ts),
        meta: evt.latest as Record<string, unknown>,
      });
      // Reload records + status; flag changed cells with pulse animation.
      const beforeKeys = new Set(
        records.flatMap((r) =>
          Object.entries(r)
            .filter(([_, v]) => v != null)
            .map(([k]) => `${String(r.id)}::${k}`),
        ),
      );
      Promise.all([listRecords({ limit: 500 }), getStatus()])
        .then(([recs, st]) => {
          setRecords(recs.records);
          setStatus(st);
          const newPulses = new Set<string>();
          recs.records.forEach((r) => {
            Object.entries(r).forEach(([k, v]) => {
              const key = `${String(r.id)}::${k}`;
              if (v != null && !beforeKeys.has(key)) newPulses.add(key);
            });
          });
          if (newPulses.size > 0) {
            setPulsingCells((s) => {
              const n = new Set(s);
              newPulses.forEach((k) => n.add(k));
              return n;
            });
            setTimeout(() => {
              setPulsingCells((s) => {
                const n = new Set(s);
                newPulses.forEach((k) => n.delete(k));
                return n;
              });
            }, 1400);
          }
        })
        .catch((e) => console.error(e));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [evt.latest]);

  // memoized derived state
  const fields = contract?.schema[0]?.properties ?? [];
  const primaryKey = useMemo(
    () => fields.find((p) => p.primaryKey)?.name ?? "id",
    [fields],
  );
  const filteredEval = useMemo(
    () => evalFilterClient(records, activeFilter),
    [records, activeFilter],
  );
  const filtered = filteredEval.rows;
  const filterErr = filteredEval.error;

  const derivations = useMemo(() => {
    // Build a placeholder derivations map from contract; if unknown, just kind: "?"
    const out: Record<string, { kind: string; targets?: string[]; inputs?: string[] }> = {};
    fields
      .filter((p) => p["x-derived"])
      .forEach((p) => {
        const kind = inferKindFromStatus(status, p.name);
        out[p.name + ".yaml"] = {
          kind,
          targets: [p.name],
          inputs: p["x-inputs"],
        };
      });
    return out;
  }, [fields, status]);

  // ─── activity helpers ────────────────────────────────────────────────
  const addActivity = (a: ActivityEntry) =>
    setActivity((prev) => [...prev.slice(-499), a]);

  // ─── load provenance lazily on hover ─────────────────────────────────
  useEffect(() => {
    if (!hovered) return;
    const k = `${hovered.recordId}::${hovered.field}`;
    if (provenance[k] !== undefined) return; // cached (null counts)
    getProvenance(hovered.recordId, hovered.field)
      .then((p) => setProvenance((s) => ({ ...s, [k]: p })))
      .catch(() =>
        setProvenance((s) => ({ ...s, [k]: null })),
      );
  }, [hovered]);  // eslint-disable-line react-hooks/exhaustive-deps

  // ─── handlers ────────────────────────────────────────────────────────
  const onApplyWhere = (explicit?: string) => {
    const q = explicit ?? filter;
    setActiveFilter(q);
    if (q.trim()) {
      setHistory((h) => [
        ...h.slice(-49),
        { q, rows: null, at: new Date().toLocaleTimeString() },
      ]);
      addActivity({
        id: "q" + Date.now(),
        kind: "query",
        actor,
        sql: q,
        at: new Date().toISOString(),
      });
    }
  };

  const onClear = () => {
    setFilter("");
    setActiveFilter("");
    setQueryResult(null);
  };

  const onRunSql = async (
    sql: string,
  ): Promise<QueryResult | { error: string }> => {
    try {
      const out = await runQuery(sql);
      setHistory((h) => [
        ...h.slice(-49),
        { q: sql, rows: out.count, at: new Date().toLocaleTimeString() },
      ]);
      addActivity({
        id: "q" + Date.now(),
        kind: "query",
        actor,
        sql,
        at: new Date().toISOString(),
      });
      return out;
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      return { error: msg };
    }
  };

  const onMaterialize = async () => {
    if (busy) return;
    setBusy(true);
    try {
      const env = await materializeAll(actor);
      addActivity({
        id: "m" + Date.now(),
        kind: "note",
        actor,
        at: new Date().toISOString(),
        text: `materialize → ${env.materialized} ok · ${env.skipped} skipped · ${env.failures.length} failed`,
      });
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      addActivity({
        id: "m" + Date.now(),
        kind: "note",
        actor,
        at: new Date().toISOString(),
        text: `materialize failed: ${msg}`,
      });
    } finally {
      setBusy(false);
    }
  };

  const onSimulate = () => onMaterialize();

  const showToast = (text: string, tone: "info" | "ok" | "err" = "info") => {
    const at = Date.now();
    setToast({ text, tone, at });
    setTimeout(() => {
      setToast((cur) => (cur && cur.at === at ? null : cur));
    }, 1800);
  };

  const applyCellEdit = async (
    rid: string,
    field: string,
    next: unknown,
    options: { isUndoRedo?: boolean } = {},
  ) => {
    const prev = records.find((r) => String(r[primaryKey]) === rid)?.[field];
    if (prev === next) return false;
    try {
      await upsertRecord({ [primaryKey]: rid, [field]: next }, actor);
      setRecords((rs) =>
        rs.map((r) =>
          String(r[primaryKey]) === rid ? { ...r, [field]: next } : r,
        ),
      );
      setProvenance((s) => {
        const n = { ...s };
        delete n[`${rid}::${field}`];
        return n;
      });
      addActivity({
        id: "h" + Date.now(),
        kind: "human_edit",
        actor,
        record_id: rid,
        field,
        value: next,
        prior: prev,
        at: new Date().toISOString(),
      });
      if (!options.isUndoRedo) {
        setUndoStack((s) => [
          ...s.slice(-49),
          { rid, field, before: prev, after: next },
        ]);
        setRedoStack([]);
      }
      return true;
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      addActivity({
        id: "h" + Date.now(),
        kind: "note",
        actor,
        text: `edit failed: ${msg}`,
        at: new Date().toISOString(),
      });
      showToast(`Edit failed: ${msg}`, "err");
      return false;
    }
  };

  const commitEdit = async (
    rid: string,
    field: string,
    value: unknown,
    move: "down" | "up" | "right" | "left" | "none" = "none",
  ) => {
    setEditing(null);
    setFocused({ recordId: rid, field });
    // `value` is already parsed and typed by RecordsGrid's CellEditor
    // (booleans, numbers, arrays, etc.); empty inputs arrive as null.
    await applyCellEdit(rid, field, value);
    if (move !== "none") moveFocus(move, { recordId: rid, field });
  };

  const undo = async () => {
    if (undoStack.length === 0) {
      showToast("Nothing to undo");
      return;
    }
    const last = undoStack[undoStack.length - 1];
    setUndoStack((s) => s.slice(0, -1));
    const ok = await applyCellEdit(last.rid, last.field, last.before, {
      isUndoRedo: true,
    });
    if (ok) {
      setRedoStack((s) => [...s.slice(-49), last]);
      setFocused({ recordId: last.rid, field: last.field });
      showToast(`Undo · ${last.field}`, "ok");
    }
  };

  const redo = async () => {
    if (redoStack.length === 0) {
      showToast("Nothing to redo");
      return;
    }
    const last = redoStack[redoStack.length - 1];
    setRedoStack((s) => s.slice(0, -1));
    const ok = await applyCellEdit(last.rid, last.field, last.after, {
      isUndoRedo: true,
    });
    if (ok) {
      setUndoStack((s) => [...s.slice(-49), last]);
      setFocused({ recordId: last.rid, field: last.field });
      showToast(`Redo · ${last.field}`, "ok");
    }
  };

  // ─── Focus movement ──────────────────────────────────────────────────
  const moveFocus = (
    dir: "up" | "down" | "left" | "right",
    from?: { recordId: string; field: string } | null,
  ) => {
    const origin = from ?? focused ?? null;
    if (!origin) {
      // No focus yet: start at the first non-PK column of the first record.
      const first = filtered[0];
      if (!first) return;
      const firstField = fields.find((f) => !f.primaryKey)?.name ?? primaryKey;
      setFocused({ recordId: String(first[primaryKey]), field: firstField });
      return;
    }
    const rowIdx = filtered.findIndex(
      (r) => String(r[primaryKey]) === origin.recordId,
    );
    const colIdx = fields.findIndex((f) => f.name === origin.field);
    if (rowIdx < 0 || colIdx < 0) return;
    let nr = rowIdx;
    let nc = colIdx;
    if (dir === "up") nr = Math.max(0, rowIdx - 1);
    if (dir === "down") nr = Math.min(filtered.length - 1, rowIdx + 1);
    if (dir === "left") nc = Math.max(0, colIdx - 1);
    if (dir === "right") nc = Math.min(fields.length - 1, colIdx + 1);
    setFocused({
      recordId: String(filtered[nr][primaryKey]),
      field: fields[nc].name,
    });
  };

  const onDeleteSelected = async () => {
    if (selected.size === 0) return;
    const ids = [...selected];
    if (!confirm(`Delete ${ids.length} record(s)?`)) return;
    try {
      await deleteRecords(ids, actor);
      setRecords((rs) =>
        rs.filter((r) => !selected.has(String(r[primaryKey]))),
      );
      setProvenance((s) => {
        const n = { ...s };
        Object.keys(n).forEach((k) => {
          if (ids.some((id) => k.startsWith(id + "::"))) delete n[k];
        });
        return n;
      });
      addActivity({
        id: "d" + Date.now(),
        kind: "delete",
        actor,
        at: new Date().toISOString(),
        meta: { count: ids.length, ids: ids.join(", ") },
      });
      setSelected(new Set());
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      addActivity({
        id: "d" + Date.now(),
        kind: "note",
        actor,
        text: `delete failed: ${msg}`,
        at: new Date().toISOString(),
      });
    }
  };

  // ─── Row add ─────────────────────────────────────────────────────────
  const onAddRow = async () => {
    if (!contract) return;
    // Allocate a new id by extending the largest numeric suffix on the PK.
    let n = records.length + 1;
    let newId = `cust_${String(n).padStart(3, "0")}`;
    const taken = new Set(records.map((r) => String(r[primaryKey])));
    while (taken.has(newId)) {
      n += 1;
      newId = `cust_${String(n).padStart(3, "0")}`;
    }
    const stub: Record<string, unknown> = { [primaryKey]: newId };
    fields.forEach((f) => {
      if (f.name === primaryKey) return;
      if (f.required) stub[f.name] = "";
    });
    try {
      await upsertRecord(stub, actor);
      const recs = await listRecords({ limit: 500 });
      setRecords(recs.records);
      addActivity({
        id: "n" + Date.now(),
        kind: "note",
        actor,
        text: `added row ${newId}`,
        at: new Date().toISOString(),
      });
      setEditing({ recordId: newId, field: fields.find((f) => f.required && f.name !== primaryKey)?.name ?? primaryKey });
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      addActivity({
        id: "n" + Date.now(),
        kind: "note",
        actor,
        text: `add row failed: ${msg}`,
        at: new Date().toISOString(),
      });
    }
  };

  // ─── Contract editing ────────────────────────────────────────────────
  const onAddField = async (input: AddPropertyInput) => {
    try {
      const next = await addProperty(input, actor);
      setContract(next);
      addActivity({
        id: "f" + Date.now(),
        kind: "note",
        actor,
        text: `added field ${input.name}`,
        at: new Date().toISOString(),
      });
      setInspectorField(input.name);
      setRpTab("inspector");
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      addActivity({
        id: "f" + Date.now(),
        kind: "note",
        actor,
        text: `add field failed: ${msg}`,
        at: new Date().toISOString(),
      });
      throw e;
    }
  };

  const onUpdateField = async (
    name: string,
    changes: UpdatePropertyInput,
  ): Promise<string | null> => {
    try {
      const next = await updateProperty(name, changes, actor);
      setContract(next);
      // If we renamed, follow the field, and refresh records.
      const newName = changes.new_name && changes.new_name !== name ? changes.new_name : name;
      if (changes.new_name && changes.new_name !== name) {
        setInspectorField(changes.new_name);
        const recs = await listRecords({ limit: 500 });
        setRecords(recs.records);
      }
      addActivity({
        id: "f" + Date.now(),
        kind: "note",
        actor,
        text: `updated field ${name}${changes.new_name && changes.new_name !== name ? " → " + changes.new_name : ""}`,
        at: new Date().toISOString(),
      });
      return newName;
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      addActivity({
        id: "f" + Date.now(),
        kind: "note",
        actor,
        text: `update field failed: ${msg}`,
        at: new Date().toISOString(),
      });
      return null;
    }
  };

  const onDeleteField = async (name: string) => {
    try {
      const next = await deleteProperty(name, actor);
      setContract(next);
      const recs = await listRecords({ limit: 500 });
      setRecords(recs.records);
      addActivity({
        id: "f" + Date.now(),
        kind: "note",
        actor,
        text: `deleted field ${name}`,
        at: new Date().toISOString(),
      });
      setInspectorField(null);
      setRpTab("schema");
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      addActivity({
        id: "f" + Date.now(),
        kind: "note",
        actor,
        text: `delete field failed: ${msg}`,
        at: new Date().toISOString(),
      });
      throw e;
    }
  };

  // ─── Global keymap ──────────────────────────────────────────────────
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement | null;
      const tag = target?.tagName;
      const isInputFocused =
        tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT";
      const isCellEditor = target?.classList.contains("cell-input") === true;

      // Esc — close help, hover, drawer, editor (editor handles itself).
      if (e.key === "Escape") {
        if (helpOpen) {
          setHelpOpen(false);
          return;
        }
        if (hovered) setHovered(null);
        if (!isInputFocused) setEditing(null);
      }

      // Help: ? (Shift+/) — only when no input is focused
      if (
        !isInputFocused &&
        (e.key === "?" || (e.key === "/" && e.shiftKey && !e.metaKey && !e.ctrlKey))
      ) {
        e.preventDefault();
        setHelpOpen((v) => !v);
        return;
      }

      // ⌘/ — toggle right panel
      if ((e.metaKey || e.ctrlKey) && e.key === "/") {
        e.preventDefault();
        setRpCollapsed((v) => !v);
        return;
      }

      // ⌘F — focus the query bar
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "f") {
        e.preventDefault();
        setDrawerOpen(true);
        setDrawerTab("query");
        setTimeout(
          () => document.querySelector<HTMLInputElement>(".qbar-input input")?.focus(),
          0,
        );
        return;
      }

      // ⌘Enter — Materialize globally, except when typing (query textarea
      // owns this combo to run the query, cell editor owns it to commit).
      if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
        if (isCellEditor || isInputFocused) return;
        e.preventDefault();
        onMaterialize();
        return;
      }

      // ⌘S — Folio auto-saves; surface a toast so the user gets confirmation.
      if ((e.metaKey || e.ctrlKey) && !e.shiftKey && e.key.toLowerCase() === "s") {
        e.preventDefault();
        showToast("Already saved · auto", "ok");
        return;
      }

      // ⌘⇧Z / ⌘Y — redo (skip when input/textarea handles its own undo).
      if (
        !isInputFocused &&
        !isCellEditor &&
        ((e.metaKey || e.ctrlKey) &&
          ((e.shiftKey && e.key.toLowerCase() === "z") ||
            (!e.shiftKey && e.key.toLowerCase() === "y")))
      ) {
        e.preventDefault();
        redo();
        return;
      }

      // ⌘Z — undo (skip when input/textarea handles its own undo).
      if (
        !isInputFocused &&
        !isCellEditor &&
        (e.metaKey || e.ctrlKey) &&
        !e.shiftKey &&
        e.key.toLowerCase() === "z"
      ) {
        e.preventDefault();
        undo();
        return;
      }

      // ⌘⇧N — add row
      if (
        (e.metaKey || e.ctrlKey) &&
        e.shiftKey &&
        e.key.toLowerCase() === "n"
      ) {
        e.preventDefault();
        onAddRow();
        return;
      }

      // ⌘A — select all rows (only when no input focused)
      if (
        !isInputFocused &&
        (e.metaKey || e.ctrlKey) &&
        e.key.toLowerCase() === "a"
      ) {
        e.preventDefault();
        setSelected(new Set(filtered.map((r) => String(r[primaryKey]))));
        return;
      }

      // ⌘Backspace — delete selected rows
      if (
        (e.metaKey || e.ctrlKey) &&
        e.key === "Backspace" &&
        selected.size > 0 &&
        !isInputFocused
      ) {
        e.preventDefault();
        onDeleteSelected();
        return;
      }

      // From here on, rules apply only when no input is focused.
      if (isInputFocused) return;

      // Arrow keys / Tab — move focus
      if (e.key === "ArrowUp") {
        e.preventDefault();
        moveFocus("up");
        return;
      }
      if (e.key === "ArrowDown") {
        e.preventDefault();
        moveFocus("down");
        return;
      }
      if (e.key === "ArrowLeft") {
        e.preventDefault();
        moveFocus("left");
        return;
      }
      if (e.key === "ArrowRight") {
        e.preventDefault();
        moveFocus("right");
        return;
      }
      if (e.key === "Tab") {
        e.preventDefault();
        moveFocus(e.shiftKey ? "left" : "right");
        return;
      }

      // Enter / F2 — start editing the focused cell (if editable)
      if ((e.key === "Enter" || e.key === "F2") && focused) {
        const field = fields.find((f) => f.name === focused.field);
        if (!field) return;
        const editable = (field["x-editable-by"] || []).some(
          (p) =>
            p === actor ||
            p === "*" ||
            new RegExp(
              "^" +
                p
                  .replace(/[.+^${}()|[\]\\]/g, "\\$&")
                  .replace(/\*/g, ".*")
                  .replace(/\?/g, ".") +
                "$",
            ).test(actor),
        );
        if (editable && !field.primaryKey) {
          e.preventDefault();
          setEditing(focused);
        }
        return;
      }

      // Delete / Backspace — clear focused cell value
      if ((e.key === "Delete" || e.key === "Backspace") && focused) {
        const field = fields.find((f) => f.name === focused.field);
        if (!field || field.primaryKey || field["x-derived"]) return;
        const editable = (field["x-editable-by"] || []).some(
          (p) =>
            p === actor ||
            p === "*" ||
            new RegExp(
              "^" +
                p
                  .replace(/[.+^${}()|[\]\\]/g, "\\$&")
                  .replace(/\*/g, ".*")
                  .replace(/\?/g, ".") +
                "$",
            ).test(actor),
        );
        if (editable) {
          e.preventDefault();
          commitEdit(focused.recordId, focused.field, null, "none");
        }
        return;
      }

      // Space — toggle the focused row's checkbox
      if (e.key === " " && focused) {
        e.preventDefault();
        const id = focused.recordId;
        setSelected((s) => {
          const n = new Set(s);
          if (n.has(id)) n.delete(id);
          else n.add(id);
          return n;
        });
        return;
      }

      // ⌘⇧F handled separately so it doesn't conflict with ⌘F (find)
      if (
        (e.metaKey || e.ctrlKey) &&
        e.shiftKey &&
        e.key.toLowerCase() === "f"
      ) {
        e.preventDefault();
        setRpTab("schema");
        if (rpCollapsed) setRpCollapsed(false);
        // Auto-expand the add-field form by clicking it programmatically.
        // The Schema tab listens for this via an event; here we just open it.
        setTimeout(() => {
          document.querySelector<HTMLButtonElement>('.rp-section-title button.ghost-btn')?.click();
        }, 0);
        return;
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    helpOpen,
    hovered,
    focused,
    filtered,
    fields,
    primaryKey,
    selected,
    actor,
    rpCollapsed,
    undoStack,
    redoStack,
  ]);

  if (!contract) {
    return <LoadingSplash />;
  }

  return (
    <div className="app">
      <QueryBar
        filter={filter}
        setFilter={setFilter}
        activeFilter={activeFilter}
        activeFilterErr={activeFilter ? filterErr : null}
        filterErr={filterErr}
        filtered={filtered}
        totalRecords={records.length}
        busy={busy}
        onApplyWhere={onApplyWhere}
        onClear={onClear}
        onRunSql={onRunSql}
        onMaterialize={onMaterialize}
        fields={fields}
        history={history}
        drawerOpen={drawerOpen}
        setDrawerOpen={setDrawerOpen}
        drawerTab={drawerTab}
        setDrawerTab={setDrawerTab}
        queryResult={queryResult}
        setQueryResult={setQueryResult}
        sheetLabel={contract.id}
      />
      <div className={cls("body", rpCollapsed && "rp-collapsed")}>
        <main className="grid-pane">
          {selected.size > 0 && (
            <SelectionBar
              count={selected.size}
              onClear={() => setSelected(new Set())}
              onDelete={onDeleteSelected}
            />
          )}
          {activeFilter && (
            <ActiveFilterChip
              expr={activeFilter}
              shown={filtered.length}
              total={records.length}
              err={filterErr}
              onClear={onClear}
              onEdit={() => {
                setFilter(activeFilter);
                setDrawerOpen(true);
                setDrawerTab("query");
                setTimeout(
                  () =>
                    document
                      .querySelector<HTMLInputElement>(".qbar-input input")
                      ?.focus(),
                  0,
                );
              }}
            />
          )}
          <RecordsGrid
            records={filtered}
            cols={fields}
            primaryKey={primaryKey}
            actor={actor}
            provenance={provenance}
            pulsingCells={pulsingCells}
            editing={editing}
            setEditing={setEditing}
            focused={focused}
            setFocused={setFocused}
            selected={selected}
            setSelected={setSelected}
            onHover={setHovered}
            onCommit={commitEdit}
            onEditError={(msg) => showToast(msg, "err")}
            onPickField={(name) => {
              setInspectorField(name);
              setRpTab("inspector");
              if (rpCollapsed) setRpCollapsed(false);
            }}
          />
          <div className="grid-foot">
            <button className="ghost-btn small" onClick={onAddRow}>
              <Icons.Plus size={10} /> Add row
            </button>
          </div>
          <Statusbar
            total={records.length}
            shown={filtered.length}
            actor={actor}
            activeFilter={activeFilter}
            busy={busy}
            onOpenHelp={() => setHelpOpen(true)}
          />
        </main>
        <RightPanel
          contract={contract}
          records={records}
          derivations={derivations}
          activity={activity}
          agentOnline={agentOnline}
          inspectorField={inspectorField}
          setInspectorField={setInspectorField}
          collapsed={rpCollapsed}
          onToggle={() => setRpCollapsed((v) => !v)}
          activeTab={rpTab}
          setActiveTab={setRpTab}
          onSimulate={onSimulate}
          onAddField={onAddField}
          onUpdateField={onUpdateField}
          onDeleteField={onDeleteField}
        />
      </div>
      {hovered && (
        <ProvenancePop
          rid={hovered.recordId}
          field={hovered.field}
          x={hovered.x}
          y={hovered.y}
          provenance={provenance}
        />
      )}
      {helpOpen && <ShortcutHelp onClose={() => setHelpOpen(false)} />}
      {toast && <Toast text={toast.text} tone={toast.tone} />}
    </div>
  );
}

function Toast({
  text,
  tone,
}: {
  text: string;
  tone: "info" | "ok" | "err";
}) {
  return (
    <div className={cls("toast", `toast-${tone}`)} role="status">
      {tone === "ok" && <Icons.Check size={11} />}
      {tone === "err" && <Icons.X size={11} />}
      <span className="mono small">{text}</span>
    </div>
  );
}

const SHORTCUTS: Array<{
  group: string;
  items: Array<{ keys: string; desc: string }>;
}> = [
  {
    group: "Navigation",
    items: [
      { keys: "↑ ↓ ← →", desc: "Move focused cell" },
      { keys: "Tab / ⇧Tab", desc: "Move horizontally" },
      { keys: "Enter / F2", desc: "Edit focused cell" },
    ],
  },
  {
    group: "Editing",
    items: [
      { keys: "Enter", desc: "Commit + move down" },
      { keys: "⇧Enter", desc: "Commit + move up" },
      { keys: "Tab / ⇧Tab", desc: "Commit + move right / left" },
      { keys: "Esc", desc: "Cancel edit" },
      { keys: "Delete / Backspace", desc: "Clear focused cell" },
      { keys: "⌘Z", desc: "Undo last cell edit" },
      { keys: "⌘⇧Z / ⌘Y", desc: "Redo cell edit" },
      { keys: "⌘S", desc: "Confirm autosave (no-op)" },
    ],
  },
  {
    group: "Selection",
    items: [
      { keys: "Space", desc: "Toggle focused row" },
      { keys: "⌘A", desc: "Select all rows" },
      { keys: "⌘Backspace", desc: "Delete selected rows" },
    ],
  },
  {
    group: "Sheet",
    items: [
      { keys: "⌘Enter", desc: "Materialize (when not typing)" },
      { keys: "⌘F", desc: "Focus query / open Query tab" },
      { keys: "⌘K", desc: "Open query drawer" },
      { keys: "⌘/", desc: "Toggle right panel" },
      { keys: "⌘⇧N", desc: "Add row" },
      { keys: "⌘⇧F", desc: "Add field" },
    ],
  },
  {
    group: "Query tab",
    items: [
      { keys: "⌘Enter", desc: "Run the query" },
      { keys: "Tab", desc: "Accept autocomplete suggestion" },
      { keys: "↑ ↓", desc: "Cycle suggestions" },
    ],
  },
  {
    group: "Help",
    items: [
      { keys: "?", desc: "Toggle this help" },
      { keys: "Esc", desc: "Close help / popovers" },
    ],
  },
];

function ShortcutHelp({ onClose }: { onClose: () => void }) {
  return (
    <div
      className="help-overlay"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="help-card">
        <div className="help-head">
          <span className="mono" style={{ fontWeight: 600 }}>
            Keyboard shortcuts
          </span>
          <span className="spacer" />
          <button className="icon-btn" onClick={onClose} title="Close">
            <Icons.X size={11} />
          </button>
        </div>
        <div className="help-body">
          {SHORTCUTS.map((g) => (
            <div className="help-group" key={g.group}>
              <div className="help-group-title">{g.group}</div>
              <ul className="help-list">
                {g.items.map((it) => (
                  <li key={it.keys}>
                    <span className="help-keys mono">{it.keys}</span>
                    <span className="help-desc">{it.desc}</span>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

export function LoadingSplash({
  message = "Loading sheet…",
  sublabel,
}: {
  message?: string;
  sublabel?: string;
} = {}) {
  const [hint, setHint] = useState<string | null>(null);
  useEffect(() => {
    if (sublabel) return;
    if (typeof window === "undefined") return;
    const bridge = window.folioBridge;
    if (!bridge) return;
    bridge
      .currentSheet()
      .then((p) => {
        if (p) setHint(p.split("/").pop() ?? null);
      })
      .catch(() => {
        /* ignore */
      });
  }, [sublabel]);
  return (
    <div className="splash">
      <div className="splash-card">
        <div className="splash-mark mono">FOLIO</div>
        <div className="splash-spinner" aria-hidden="true" />
        <div className="splash-msg mono small">{message}</div>
        {(sublabel ?? hint) && (
          <div className="splash-sub mono small muted">{sublabel ?? hint}</div>
        )}
      </div>
    </div>
  );
}

function ActiveFilterChip({
  expr,
  shown,
  total,
  err,
  onClear,
  onEdit,
}: {
  expr: string;
  shown: number;
  total: number;
  err: string | null;
  onClear: () => void;
  onEdit: () => void;
}) {
  return (
    <div className={cls("active-filter-chip", err && "err")}>
      <Icons.Filter size={11} />
      <span className="afc-label mono small muted">WHERE</span>
      <button
        className="afc-expr mono small"
        onClick={onEdit}
        title="Click to edit in query bar"
      >
        {expr}
      </button>
      <span className="afc-count mono small muted">
        {err ? "filter parse error" : `${shown}/${total}`}
      </span>
      <button className="afc-clear" onClick={onClear} title="Clear filter">
        <Icons.X size={10} />
      </button>
    </div>
  );
}

function inferKindFromStatus(
  status: Record<string, TargetStatus>,
  name: string,
): string {
  const s = status[name];
  if (s?.derivation_kind) return s.derivation_kind;
  // fallback: pick whichever count is non-zero
  if ((s?.ai_count ?? 0) > 0) return "ai";
  if ((s?.import_count ?? 0) > 0) return "import";
  return "derived";
}

function Statusbar({
  total,
  shown,
  actor,
  activeFilter,
  busy,
  onOpenHelp,
}: {
  total: number;
  shown: number;
  actor: string;
  activeFilter: string;
  busy: boolean;
  onOpenHelp: () => void;
}) {
  return (
    <div className="statusbar mono">
      <span>
        <Icons.Cell size={10} /> {shown}/{total} records
      </span>
      <span className="sep">·</span>
      <span>
        actor <span className="mono">{actor}</span>
      </span>
      {activeFilter && (
        <>
          <span className="sep">·</span>
          <span>
            filter <span className="mono">{activeFilter}</span>
          </span>
        </>
      )}
      <span className="spacer" />
      <button
        className="status-hint"
        onClick={onOpenHelp}
        title="Keyboard shortcuts (?)"
      >
        <span className="kbd-tiny">?</span> shortcuts
      </button>
      <span className="sep">·</span>
      <span>
        <Icons.Lock size={10} /> .lock idle
      </span>
      <span className="sep">·</span>
      <span>
        <Icons.Shield size={10} /> writes via SDK
      </span>
      {busy && (
        <>
          <span className="sep">·</span>
          <span className="busy">
            <span className="dot" /> materializing
          </span>
        </>
      )}
    </div>
  );
}
