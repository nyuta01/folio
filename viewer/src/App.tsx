import { useEffect, useMemo, useState } from "react";
import { Icons } from "./Icons";
import { ProvenancePop, RecordsGrid, SelectionBar } from "./RecordsGrid";
import { QueryBar } from "./QueryBar";
import { RightPanel, type TabId } from "./RightPanel";
import {
  deleteRecords,
  getContract,
  getProvenance,
  getStatus,
  listRecords,
  materializeAll,
  runQuery,
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
        if ((m = p.match(/^(\w+)\s+LIKE\s+'(.+)'$/i))) {
          const re = new RegExp(
            "^" +
              m[2]
                .replace(/[.+?^${}()|[\]\\]/g, "\\$&")
                .replace(/%/g, ".*")
                .replace(/_/g, ".") +
              "$",
            "i",
          );
          return r[m[1]] != null && re.test(String(r[m[1]]));
        }
        if ((m = p.match(/^(\w+)\s+IN\s*\(([^)]+)\)$/i))) {
          const vals = m[2]
            .split(",")
            .map((s) => s.trim().replace(/^'|'$/g, ""));
          return vals.includes(String(r[m[1]]));
        }
        if ((m = p.match(/^(\w+)\s*(!=|<>|=)\s*'([^']*)'$/))) {
          const v = r[m[1]];
          return m[2] === "=" ? v === m[3] : v !== m[3];
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
  const [history, setHistory] = useState<
    Array<{ q: string; rows: number | null; at: string }>
  >([]);

  const [editing, setEditing] = useState<{ recordId: string; field: string } | null>(null);
  const [hovered, setHovered] = useState<{
    recordId: string;
    field: string;
    x: number;
    y: number;
  } | null>(null);
  const [pulsingCells, setPulsingCells] = useState<Set<string>>(new Set());
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [busy, setBusy] = useState(false);

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
  const onApplyWhere = () => {
    setActiveFilter(filter);
    if (filter.trim()) {
      setHistory((h) => [
        ...h.slice(-49),
        { q: filter, rows: null, at: new Date().toLocaleTimeString() },
      ]);
      addActivity({
        id: "q" + Date.now(),
        kind: "query",
        actor,
        sql: filter,
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

  const commitEdit = async (rid: string, field: string, value: string) => {
    setEditing(null);
    const prev = records.find((r) => String(r[primaryKey]) === rid)?.[field];
    const next = value === "" ? null : value;
    if (prev === next) return;
    try {
      await upsertRecord({ [primaryKey]: rid, [field]: next }, actor);
      setRecords((rs) =>
        rs.map((r) =>
          String(r[primaryKey]) === rid ? { ...r, [field]: next } : r,
        ),
      );
      // invalidate provenance cache for this cell
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
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      addActivity({
        id: "h" + Date.now(),
        kind: "note",
        actor,
        text: `edit failed: ${msg}`,
        at: new Date().toISOString(),
      });
    }
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

  // keyboard
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setEditing(null);
      }
      if ((e.metaKey || e.ctrlKey) && e.key === "/") {
        e.preventDefault();
        setRpCollapsed((v) => !v);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  if (!contract) {
    return (
      <div className="app">
        <div className="empty">Loading sheet…</div>
      </div>
    );
  }

  return (
    <div className="app">
      <QueryBar
        filter={filter}
        setFilter={setFilter}
        activeFilter={activeFilter}
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
        queryResult={queryResult}
        setQueryResult={setQueryResult}
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
          <RecordsGrid
            records={filtered}
            cols={fields}
            primaryKey={primaryKey}
            actor={actor}
            provenance={provenance}
            pulsingCells={pulsingCells}
            editing={editing}
            setEditing={setEditing}
            selected={selected}
            setSelected={setSelected}
            onHover={setHovered}
            onCommit={commitEdit}
            onPickField={(name) => {
              setInspectorField(name);
              setRpTab("inspector");
              if (rpCollapsed) setRpCollapsed(false);
            }}
          />
          <Statusbar
            total={records.length}
            shown={filtered.length}
            actor={actor}
            activeFilter={activeFilter}
            busy={busy}
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
}: {
  total: number;
  shown: number;
  actor: string;
  activeFilter: string;
  busy: boolean;
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
