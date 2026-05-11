import { useEffect, useRef, useState } from "react";
import { Icons } from "./Icons";
import { FieldBadge, TypeChip } from "./RecordsGrid";
import {
  getProvenanceHistory,
  type AddPropertyInput,
  type UpdatePropertyInput,
} from "./api";
import type {
  ActivityEntry,
  Contract,
  ProvenanceEntry,
} from "./types";
import type { AgentAvailability } from "./folio-bridge";

const cls = (...xs: Array<string | false | null | undefined>) =>
  xs.filter(Boolean).join(" ");

const fmtClock = (iso: string) => new Date(iso).toISOString().slice(11, 19);
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

// `inspector` is kept in the union for callers that still emit it
// (e.g. legacy persisted UI state) — it's coerced back to `schema`
// inside the panel, since the inspector now lives as a nested detail
// view inside the Schema tab.
export type TabId = "schema" | "activity" | "chat" | "inspector";

const TABS: Array<{ id: TabId; label: string; icon: keyof typeof Icons }> = [
  { id: "schema", label: "Schema", icon: "Cell" },
  { id: "activity", label: "Activity", icon: "Sparkle" },
  { id: "chat", label: "Chat", icon: "Bot" },
];

interface RightPanelProps {
  contract: Contract;
  records: Record<string, unknown>[];
  derivations: Record<string, { kind: string; targets?: string[] }>;
  activity: ActivityEntry[];
  agentOnline: boolean;
  inspectorField: string | null;
  setInspectorField: (v: string | null) => void;
  collapsed: boolean;
  onToggle: () => void;
  activeTab: TabId;
  setActiveTab: (t: TabId) => void;
  onSimulate: () => void;
  onAddField: (input: AddPropertyInput) => Promise<void>;
  onUpdateField: (
    name: string,
    changes: UpdatePropertyInput,
  ) => Promise<string | null>;
  onDeleteField: (name: string) => Promise<void>;
}

export function RightPanel({
  contract,
  records,
  derivations,
  activity,
  agentOnline,
  inspectorField,
  setInspectorField,
  collapsed,
  onToggle,
  activeTab,
  setActiveTab,
  onSimulate,
  onAddField,
  onUpdateField,
  onDeleteField,
}: RightPanelProps) {
  // Legacy `inspector` value funnels back into `schema` so the rail
  // never shows a third tab.
  const normalisedTab: TabId = activeTab === "inspector" ? "schema" : activeTab;
  const activeDef = TABS.find((t) => t.id === normalisedTab) ?? TABS[0];
  const onSchema = normalisedTab === "schema";
  const inFieldView = onSchema && inspectorField !== null;

  return (
    <aside className={cls("rp", collapsed && "collapsed")}>
      {!collapsed && (
        <div className="rp-content">
          <div className="rp-content-head">
            {inFieldView && (
              <button
                className="icon-btn"
                onClick={() => setInspectorField(null)}
                title="Back to schema"
              >
                <Icons.ChevronL size={12} />
              </button>
            )}
            <span className="rp-content-title mono">
              {inFieldView ? (
                <>
                  <span className="muted">Schema · </span>
                  {inspectorField}
                </>
              ) : (
                activeDef.label
              )}
            </span>
            {activeDef.id === "activity" && agentOnline && (
              <span className="live-dot live" />
            )}
            <span className="rp-tabs-spacer" />
            <button className="icon-btn" onClick={onToggle} title="Collapse">
              <Icons.X size={11} />
            </button>
          </div>
          <div className="rp-body">
            {/* `key` forces a remount on transition so the entering
                view replays its CSS slide-in. A subtle 6px translate
                + fade tells the eye "moved laterally" without making
                the animation a feature. */}
            <div
              className={cls(
                "rp-view",
                inFieldView ? "rp-view-enter-right" : "rp-view-enter-left",
              )}
              key={
                normalisedTab === "activity"
                  ? "activity"
                  : inFieldView
                  ? `detail:${inspectorField}`
                  : "list"
              }
            >
              {onSchema && !inFieldView && (
                <SchemaTab
                  contract={contract}
                  records={records}
                  derivations={derivations}
                  selectedField={inspectorField}
                  onPickField={(name) => {
                    setInspectorField(name);
                    if (activeTab !== "schema") setActiveTab("schema");
                  }}
                  onAddField={onAddField}
                />
              )}
              {onSchema && inFieldView && (
                <InspectorTab
                  fieldName={inspectorField}
                  contract={contract}
                  records={records}
                  derivations={derivations}
                  onUpdateField={onUpdateField}
                  onDeleteField={onDeleteField}
                />
              )}
              {normalisedTab === "activity" && (
                <ActivityTab
                  activity={activity}
                  agentOnline={agentOnline}
                  onSimulate={onSimulate}
                />
              )}
              {normalisedTab === "chat" && <ChatTab />}
            </div>
          </div>
        </div>
      )}
      <div className="rp-rail-bar">
        {TABS.map((t) => {
          const Ico = Icons[t.icon];
          const isActive = !collapsed && normalisedTab === t.id;
          return (
            <button
              key={t.id}
              className={cls("rp-rail-btn", isActive && "active")}
              onClick={() => {
                if (isActive) {
                  // Clicking the active rail when in the field-detail
                  // view pops back to the list, otherwise collapses
                  // the panel.
                  if (t.id === "schema" && inFieldView) {
                    setInspectorField(null);
                  } else {
                    onToggle();
                  }
                } else {
                  setActiveTab(t.id);
                  if (collapsed) onToggle();
                }
              }}
              title={t.label}
            >
              <Ico size={15} />
              {t.id === "activity" && agentOnline && (
                <span className="live-dot live rail-live" />
              )}
            </button>
          );
        })}
      </div>
    </aside>
  );
}

function SchemaTab({
  contract,
  records,
  derivations,
  selectedField,
  onPickField,
  onAddField,
}: {
  contract: Contract;
  records: Record<string, unknown>[];
  derivations: Record<string, { kind: string; targets?: string[] }>;
  selectedField: string | null;
  onPickField: (name: string) => void;
  onAddField: (input: AddPropertyInput) => Promise<void>;
}) {
  const props = contract.schema[0].properties;
  const total = records.length;
  const nullCount = (name: string) =>
    records.filter((r) => r[name] == null).length;

  const [adding, setAdding] = useState(false);
  const [newName, setNewName] = useState("");
  const [newType, setNewType] = useState<string>("string");
  const [error, setError] = useState<string | null>(null);

  const submit = async () => {
    const name = newName.trim();
    if (!name) return;
    setError(null);
    try {
      await onAddField({
        name,
        logicalType: newType,
        editable_by: ["agent:human"],
      });
      setNewName("");
      setNewType("string");
      setAdding(false);
    } catch (e) {
      setError(e instanceof Error ? e.message : "add failed");
    }
  };

  return (
    <div className="rp-pad">
      <div className="rp-section-title">Contract</div>
      <div className="rp-meta">
        <div>
          <span className="muted">id</span>
          <span className="mono">{contract.id}</span>
        </div>
        <div>
          <span className="muted">version</span>
          <span className="mono">{contract.version}</span>
        </div>
        <div>
          <span className="muted">model</span>
          <span className="mono">{contract.schema[0].name}</span>
        </div>
      </div>

      <div className="rp-section-title">
        Fields <span className="muted mono small">{props.length}</span>
        <span className="rp-tabs-spacer" />
        <button
          className="ghost-btn small"
          onClick={() => setAdding((v) => !v)}
        >
          <Icons.Plus size={10} /> Add field
        </button>
      </div>

      {adding && (
        <div className="add-field-form">
          <input
            className="mono"
            placeholder="field_name"
            value={newName}
            onChange={(e) => setNewName(e.target.value.replace(/[^a-z0-9_]/gi, "_").toLowerCase())}
            autoFocus
            onKeyDown={(e) => {
              if (e.key === "Enter") submit();
              if (e.key === "Escape") setAdding(false);
            }}
          />
          <select
            className="mono"
            value={newType}
            onChange={(e) => setNewType(e.target.value)}
          >
            {[
              "string",
              "integer",
              "number",
              "boolean",
              "date",
              "timestamp",
              "array",
              "object",
            ].map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </select>
          <button className="apply-btn" onClick={submit} disabled={!newName.trim()}>
            Add
          </button>
          <button className="icon-btn" onClick={() => setAdding(false)} title="Cancel">
            <Icons.X size={11} />
          </button>
          {error && <div className="add-field-err mono small err">{error}</div>}
        </div>
      )}
      <ul className="fieldlist">
        {props.map((p) => {
          const nulls = nullCount(p.name);
          return (
            <li
              key={p.name}
              className={cls(
                "field-item",
                p["x-derived"] && "is-derived",
                selectedField === p.name && "is-selected",
              )}
              onClick={() => onPickField(p.name)}
            >
              <div className="field-name">
                <span className="mono">{p.name}</span>
                <FieldBadge prop={p} />
                <span className="rp-tabs-spacer" />
                <Icons.ChevronR size={10} />
              </div>
              <div className="field-meta">
                <TypeChip t={p.logicalType} />
                {p.required && <span className="req mono">req</span>}
                {p["x-derived"] && p["x-inputs"] && (
                  <span className="inputs mono">
                    <Icons.Link size={10} /> {p["x-inputs"].length}
                  </span>
                )}
              </div>
              {nulls > 0 && (
                <div className="nullbar">
                  <div
                    className="nullbar-fill"
                    style={{ width: `${(nulls / total) * 100}%` }}
                  />
                  <span className="mono small">{nulls} ∅</span>
                </div>
              )}
            </li>
          );
        })}
      </ul>

      {Object.keys(derivations).length > 0 && (
        <>
          <div className="rp-section-title">
            Derivations{" "}
            <span className="muted mono small">{Object.keys(derivations).length}</span>
          </div>
          <ul className="derivlist">
            {Object.entries(derivations).map(([name, d]) => (
              <li key={name} className="deriv-item">
                <div className="deriv-head">
                  <span className="mono">{name}</span>
                  <span className="pill mono" data-tone="ai">{d.kind}</span>
                </div>
                {d.targets && (
                  <div className="deriv-line mono small">
                    <span className="muted">→</span> {d.targets.join(", ")}
                  </div>
                )}
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  );
}

function ActivityTab({
  activity,
  agentOnline,
  onSimulate,
}: {
  activity: ActivityEntry[];
  agentOnline: boolean;
  onSimulate: () => void;
}) {
  const [filter, setFilter] = useState<"all" | "agent" | "human">("all");
  const filtered = activity.filter(
    (a) =>
      filter === "all" ||
      (filter === "agent" && a.actor?.startsWith("agent:")) ||
      (filter === "human" && a.actor?.startsWith("human:")),
  );
  const reversed = [...filtered].reverse();

  return (
    <div className="rp-tabbody">
      <div className="rp-toolrow">
        <div className="rp-segctrl">
          {(["all", "agent", "human"] as const).map((t) => (
            <button
              key={t}
              className={cls("rp-segbtn", filter === t && "on")}
              onClick={() => setFilter(t)}
            >
              {t}
            </button>
          ))}
        </div>
        <span className="rp-tabs-spacer" />
        <button className="toolbtn small" onClick={onSimulate} disabled={!agentOnline}>
          <Icons.Play size={10} /> simulate
        </button>
      </div>
      <div className="activity-list">
        {reversed.length === 0 && (
          <div className="rp-empty muted small">
            No activity yet. Run a query, edit a cell, or click materialize.
          </div>
        )}
        {reversed.map((ev) => (
          <ActivityRow key={ev.id} ev={ev} />
        ))}
      </div>
      <div className="activity-foot">
        <div className="meta-row">
          <span className="muted small">total events</span>
          <span className="mono small">{activity.length}</span>
        </div>
        <div className="meta-row">
          <span className="muted small">last</span>
          <span className="mono small">
            {activity.length ? fmtTime(activity[activity.length - 1].at) : "—"}
          </span>
        </div>
      </div>
    </div>
  );
}

function ActivityRow({ ev }: { ev: ActivityEntry }) {
  const isAgent = ev.actor?.startsWith("agent:");
  const Ico =
    ev.kind === "human_edit"
      ? Icons.User
      : ev.kind === "materialize.start"
        ? Icons.Play
        : ev.kind === "materialize.end"
          ? Icons.Check
          : ev.kind === "materialize.error"
            ? Icons.X
            : ev.kind === "query"
              ? Icons.Db
              : ev.kind === "delete"
                ? Icons.X
                : Icons.Sparkle;
  return (
    <div className={cls("act-row", isAgent ? "agent" : "human")}>
      <div className="act-gutter">
        <div className="act-icon">
          <Ico size={11} />
        </div>
        <div className="act-rail" />
      </div>
      <div className="act-body">
        <div className="act-line">
          <span className="mono small actor-tag">{ev.actor || "system"}</span>
          <span className="muted small">·</span>
          <span className="mono small muted">{fmtClock(ev.at)}</span>
        </div>
        <div className="act-msg">{renderActMsg(ev)}</div>
      </div>
    </div>
  );
}

function renderActMsg(ev: ActivityEntry) {
  switch (ev.kind) {
    case "human_edit":
      return (
        <div>
          edited <span className="mono">{ev.field}</span> on{" "}
          <span className="mono">{ev.record_id}</span> →{" "}
          <span className="tag">{String(ev.value)}</span>
        </div>
      );
    case "materialize.start":
      return (
        <div>
          started materialize
          {ev.meta && typeof ev.meta.actor === "string" && (
            <> · by <span className="mono">{ev.meta.actor}</span></>
          )}
        </div>
      );
    case "materialize.end": {
      const m = ev.meta || {};
      return (
        <div>
          finished materialize ·{" "}
          <span className="ok mono">
            {Number(m.materialized || 0)} ok
          </span>
          {Number(m.failures || 0) > 0 && (
            <span className="err mono"> · {Number(m.failures)} failed</span>
          )}
          {m.total_cost != null && Number(m.total_cost) > 0 && (
            <span className="muted small mono">
              {" "}· {fmtCost(Number(m.total_cost))}
            </span>
          )}
        </div>
      );
    }
    case "materialize.error":
      return (
        <div className="err">
          materialize error: {String(ev.meta?.message || "unknown")}
        </div>
      );
    case "query":
      return (
        <div className="mono small query-snip">
          {(ev.sql || "").length > 110
            ? (ev.sql || "").slice(0, 110) + "…"
            : ev.sql}
        </div>
      );
    case "delete":
      return (
        <div className="muted">
          deleted {String(ev.meta?.count || 0)} record(s):{" "}
          <span className="mono">{String(ev.meta?.ids || "")}</span>
        </div>
      );
    case "note":
      return <div className="muted">{ev.text}</div>;
    default:
      return <div className="muted small">{ev.kind}</div>;
  }
}

function InspectorTab({
  fieldName,
  contract,
  records,
  derivations,
  onUpdateField,
  onDeleteField,
}: {
  fieldName: string | null;
  contract: Contract;
  records: Record<string, unknown>[];
  derivations: Record<string, { kind: string; targets?: string[]; model?: string; inputs?: string[]; prompt?: string }>;
  onUpdateField: (
    name: string,
    changes: UpdatePropertyInput,
  ) => Promise<string | null>;
  onDeleteField: (name: string) => Promise<void>;
}) {
  if (!fieldName) {
    return (
      <div className="rp-pad">
        <div className="rp-empty muted small">
          Click a column header or a field in Schema to inspect.
        </div>
      </div>
    );
  }
  const field = contract.schema[0].properties.find((p) => p.name === fieldName);
  if (!field) {
    return (
      <div className="rp-pad">
        <div className="rp-empty muted small">field not found.</div>
      </div>
    );
  }
  const deriv = derivations[fieldName];
  const nulls = records.filter((r) => r[fieldName] == null).length;
  const buckets: Record<string, number> = {};
  records.forEach((r) => {
    const k = r[fieldName] == null ? "∅ null" : String(r[fieldName]);
    buckets[k] = (buckets[k] || 0) + 1;
  });
  const dist = Object.entries(buckets)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 12);

  const editable = !field.primaryKey && !field["x-derived"];
  return (
    <div className="rp-pad">
      <InspectorEditableHeader
        field={field}
        editable={editable}
        onUpdateField={onUpdateField}
        onDeleteField={onDeleteField}
      />
      <div className="ins-row">
        <FieldBadge prop={field} />
        <TypeChip t={field.logicalType} />
        {field.required && <span className="pill mono" data-tone="warn">required</span>}
        {field["x-derived"] && (
          <span className="pill mono" data-tone="ai">derived</span>
        )}
      </div>
      {editable && (
        <InspectorEditableProps
          field={field}
          onUpdateField={onUpdateField}
        />
      )}

      {field["x-derived"] && deriv && (
        <>
          <div className="rp-section-title">Derivation</div>
          <div className="ins-codeblock mono small">
            <div>
              <span className="kw">kind:</span> {deriv.kind}
            </div>
            {deriv.model && (
              <div>
                <span className="kw">model:</span> {deriv.model}
              </div>
            )}
            {deriv.inputs && (
              <div>
                <span className="kw">inputs:</span> [{deriv.inputs.join(", ")}]
              </div>
            )}
            {deriv.targets && (
              <div>
                <span className="kw">targets:</span> [{deriv.targets.join(", ")}]
              </div>
            )}
            {deriv.prompt && (
              <div className="prompt-block">
                <div className="kw">prompt: |</div>
                <pre>{deriv.prompt}</pre>
              </div>
            )}
          </div>
        </>
      )}

      {field["x-editable-by"] && field["x-editable-by"].length > 0 && (
        <>
          <div className="rp-section-title">x-editable-by</div>
          <div className="ins-row">
            {field["x-editable-by"].map((p) => (
              <span key={p} className="pill mono" data-tone="neutral">
                {p}
              </span>
            ))}
          </div>
        </>
      )}

      <div className="rp-section-title">Distribution</div>
      <ul className="dist-list">
        {dist.map(([k, n]) => (
          <li key={k}>
            <span className={cls("dist-k mono ellipsis", k === "∅ null" && "null")}>
              {k}
            </span>
            <div className="dist-bar">
              <div
                className="dist-bar-fill"
                style={{ width: `${(n / records.length) * 100}%` }}
              />
            </div>
            <span className="mono small">{n}</span>
          </li>
        ))}
      </ul>

      <div className="rp-section-title">Stats</div>
      <div className="ins-stats">
        <div>
          <span className="muted small">records</span>
          <span className="mono">{records.length}</span>
        </div>
        <div>
          <span className="muted small">filled</span>
          <span className="mono">{records.length - nulls}</span>
        </div>
        <div>
          <span className="muted small">null</span>
          <span className="mono">{nulls}</span>
        </div>
      </div>

      {!field["x-derived"] && fieldName && (
        <FieldHistorySection fieldName={fieldName} records={records} />
      )}
    </div>
  );
}

function InspectorEditableHeader({
  field,
  editable,
  onUpdateField,
  onDeleteField,
}: {
  field: import("./types").ContractProperty;
  editable: boolean;
  onUpdateField: (
    name: string,
    changes: UpdatePropertyInput,
  ) => Promise<string | null>;
  onDeleteField: (name: string) => Promise<void>;
}) {
  const [name, setName] = useState(field.name);
  const [desc, setDesc] = useState(field.description || "");
  useEffect(() => {
    setName(field.name);
    setDesc(field.description || "");
  }, [field.name, field.description]);

  const commitName = async () => {
    const next = name.trim();
    if (!next || next === field.name) {
      setName(field.name);
      return;
    }
    const result = await onUpdateField(field.name, { new_name: next });
    if (!result) setName(field.name);
  };
  const commitDesc = async () => {
    if (desc === (field.description || "")) return;
    await onUpdateField(field.name, { description: desc || null });
  };

  if (!editable) {
    return (
      <div className="ins-head-display">
        <div className="ins-title">{field.name}</div>
        <div className="ins-sub">{field.description || "—"}</div>
      </div>
    );
  }
  return (
    <div className="ins-head-display">
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <input
          className="ins-title-input mono"
          value={name}
          onChange={(e) =>
            setName(e.target.value.replace(/[^a-z0-9_]/gi, "_").toLowerCase())
          }
          onBlur={commitName}
          onKeyDown={(e) => {
            if (e.key === "Enter") (e.target as HTMLInputElement).blur();
            if (e.key === "Escape") {
              setName(field.name);
              (e.target as HTMLInputElement).blur();
            }
          }}
        />
        <button
          className="icon-btn"
          onClick={() => {
            if (confirm(`Delete field "${field.name}"?`)) onDeleteField(field.name);
          }}
          title="Delete field"
          style={{ color: "var(--err)" }}
        >
          <Icons.Trash size={13} />
        </button>
      </div>
      <input
        className="ins-sub-input"
        value={desc}
        placeholder="add description…"
        onChange={(e) => setDesc(e.target.value)}
        onBlur={commitDesc}
        onKeyDown={(e) => {
          if (e.key === "Enter") (e.target as HTMLInputElement).blur();
          if (e.key === "Escape") {
            setDesc(field.description || "");
            (e.target as HTMLInputElement).blur();
          }
        }}
      />
    </div>
  );
}

function InspectorEditableProps({
  field,
  onUpdateField,
}: {
  field: import("./types").ContractProperty;
  onUpdateField: (
    name: string,
    changes: UpdatePropertyInput,
  ) => Promise<string | null>;
}) {
  return (
    <div className="ins-row" style={{ gap: 8 }}>
      <label className="muted small">type</label>
      <select
        className="mono small"
        value={field.logicalType}
        onChange={(e) =>
          onUpdateField(field.name, { logicalType: e.target.value })
        }
      >
        {[
          "string",
          "integer",
          "number",
          "boolean",
          "date",
          "timestamp",
          "array",
          "object",
        ].map((t) => (
          <option key={t} value={t}>
            {t}
          </option>
        ))}
      </select>
      <label className="muted small" style={{ marginLeft: 8 }}>
        <input
          type="checkbox"
          checked={!!field.required}
          onChange={(e) =>
            onUpdateField(field.name, { required: e.target.checked })
          }
        />{" "}
        required
      </label>
    </div>
  );
}

function FieldHistorySection({
  fieldName,
  records,
}: {
  fieldName: string;
  records: Record<string, unknown>[];
}) {
  // Show a tiny summary of provenance entries for the first record (sample).
  const [history, setHistory] = useState<ProvenanceEntry[] | null>(null);
  const sampleId = records[0] ? String(records[0].id ?? "") : null;
  useEffect(() => {
    if (!sampleId) return;
    getProvenanceHistory(sampleId, fieldName)
      .then(setHistory)
      .catch(() => setHistory([]));
  }, [sampleId, fieldName]);
  if (!history || history.length === 0) return null;
  return (
    <>
      <div className="rp-section-title">
        Sample history{" "}
        <span className="muted mono small">{sampleId}</span>
      </div>
      <div className="ins-codeblock mono small">
        {history.slice(-3).map((h, i) => (
          <div key={i} style={{ padding: "2px 0" }}>
            <span className="kw">{h.source}</span> · {h.actor} · {fmtTime(h.at)}
          </div>
        ))}
      </div>
    </>
  );
}

// ───────────────────────────────────────────────────────────────────────────
// Chat tab — drives a coding agent (Claude Code today; Codex / Aider later)
// over the Electron preload bridge. The bridge is only present inside the
// Folio Desktop shell; when running as a plain browser tab the tab shows
// a "Desktop only" message.
// ───────────────────────────────────────────────────────────────────────────

type ChatTurn =
  | { role: "user"; text: string }
  | { role: "agent"; text: string; sessionId: string; stderr?: string; done: boolean; error?: string | null; exitCode?: number | null };

function ChatTab() {
  const bridge = (typeof window !== "undefined" && window.folioBridge?.agents) || null;
  const [agents, setAgents] = useState<AgentAvailability[]>([]);
  const [selectedAgent, setSelectedAgent] = useState<string>("claude-code");
  const [turns, setTurns] = useState<ChatTurn[]>([]);
  const [draft, setDraft] = useState("");
  const [running, setRunning] = useState<string | null>(null); // active sessionId
  const [hasTurnedOnce, setHasTurnedOnce] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to the bottom on new chunks.
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ block: "end" });
  }, [turns]);

  // Probe available agents on mount.
  useEffect(() => {
    if (!bridge) return;
    bridge.list().then((list) => {
      setAgents(list);
      const firstAvail = list.find((a) => a.available)?.id;
      if (firstAvail) setSelectedAgent(firstAvail);
    });
  }, [bridge]);

  // Subscribe to streaming events for the lifetime of the tab. The
  // handlers append to whichever agent turn matches `sessionId`.
  useEffect(() => {
    if (!bridge) return;
    const offChunk = bridge.onChunk(({ sessionId, stream, data }) => {
      setTurns((cur) => {
        const i = cur.findIndex((t) => t.role === "agent" && t.sessionId === sessionId);
        if (i < 0) return cur;
        const next = cur.slice();
        const t = next[i] as Extract<ChatTurn, { role: "agent" }>;
        if (stream === "stdout") {
          next[i] = { ...t, text: t.text + data };
        } else {
          next[i] = { ...t, stderr: (t.stderr ?? "") + data };
        }
        return next;
      });
    });
    const offEnd = bridge.onEnd(({ sessionId, exitCode, error }) => {
      setTurns((cur) =>
        cur.map((t) =>
          t.role === "agent" && t.sessionId === sessionId
            ? { ...t, done: true, exitCode, error }
            : t,
        ),
      );
      setRunning((cur) => (cur === sessionId ? null : cur));
    });
    return () => {
      offChunk();
      offEnd();
    };
  }, [bridge]);

  if (!bridge) {
    return (
      <div className="rp-pad">
        <div className="rp-section-title">Chat</div>
        <p className="muted small">
          The chat panel runs coding agents on the sheet's directory. It needs
          access to the host shell and is therefore <strong>Folio Desktop
          only</strong> — the standalone <code>folio serve</code> viewer can't
          spawn binaries.
        </p>
        <p className="muted small">
          Launch the desktop app and reopen this sheet to use it.
        </p>
      </div>
    );
  }

  const send = async () => {
    const prompt = draft.trim();
    if (!prompt || running) return;
    const spec = agents.find((a) => a.id === selectedAgent);
    if (!spec?.available) return;

    setDraft("");
    setTurns((cur) => [...cur, { role: "user", text: prompt }]);

    const result = await bridge.run({
      agentId: selectedAgent,
      prompt,
      isFollowup: hasTurnedOnce,
    });
    if (!result.ok) {
      setTurns((cur) => [
        ...cur,
        {
          role: "agent",
          sessionId: "err-" + Date.now(),
          text: "",
          done: true,
          error: result.error,
          exitCode: null,
        },
      ]);
      return;
    }
    setRunning(result.sessionId);
    setHasTurnedOnce(true);
    setTurns((cur) => [
      ...cur,
      { role: "agent", sessionId: result.sessionId, text: "", done: false },
    ]);
  };

  const stop = () => {
    if (running) bridge.stop({ sessionId: running });
  };

  const selectedSpec = agents.find((a) => a.id === selectedAgent);
  const canSend = !!selectedSpec?.available && !running && draft.trim().length > 0;

  return (
    <div className="chat-tab">
      <div className="chat-header rp-pad">
        <div className="chat-pickrow">
          <label className="muted small" htmlFor="chat-agent">agent</label>
          <select
            id="chat-agent"
            className="mono small"
            value={selectedAgent}
            onChange={(e) => setSelectedAgent(e.target.value)}
            disabled={!!running}
          >
            {agents.map((a) => (
              <option key={a.id} value={a.id} disabled={!a.available}>
                {a.label}
                {a.available ? "" : " (not installed)"}
              </option>
            ))}
          </select>
          {selectedSpec?.version && (
            <span className="muted small mono">{selectedSpec.version}</span>
          )}
        </div>
        {selectedSpec && !selectedSpec.available && (
          <div className="chat-install-hint muted small">
            {selectedSpec.installHint ?? "binary not on $PATH"}
          </div>
        )}
        {hasTurnedOnce && (
          <button
            className="ghost-btn small"
            onClick={() => {
              setTurns([]);
              setHasTurnedOnce(false);
            }}
            disabled={!!running}
            title="Start a new conversation"
          >
            <Icons.Plus size={10} /> New chat
          </button>
        )}
      </div>

      <div className="chat-stream">
        {turns.length === 0 && (
          <div className="chat-empty muted small">
            Send a message to {selectedSpec?.label ?? "the agent"}. It runs in
            this sheet's directory and can read / edit files there.
          </div>
        )}
        {turns.map((t, i) => (
          <ChatBubble key={i} turn={t} />
        ))}
        <div ref={bottomRef} />
      </div>

      <div className="chat-composer">
        <textarea
          className="mono"
          placeholder={
            selectedSpec?.available
              ? "ask the agent…  (⌘/Ctrl + Enter to send)"
              : "agent not installed"
          }
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
              e.preventDefault();
              send();
            }
          }}
          disabled={!selectedSpec?.available || !!running}
          rows={3}
        />
        <div className="chat-composer-actions">
          {running ? (
            <button className="ghost-btn small" onClick={stop}>
              <Icons.X size={10} /> Stop
            </button>
          ) : (
            <button
              className="apply-btn"
              onClick={send}
              disabled={!canSend}
              title="Send (⌘/Ctrl + Enter)"
            >
              Send
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

function ChatBubble({ turn }: { turn: ChatTurn }) {
  if (turn.role === "user") {
    return (
      <div className="chat-bubble chat-user">
        <div className="chat-bubble-text">{turn.text}</div>
      </div>
    );
  }
  return (
    <div className="chat-bubble chat-agent">
      {turn.text && <div className="chat-bubble-text">{turn.text}</div>}
      {!turn.done && !turn.text && (
        <div className="chat-typing muted small">…</div>
      )}
      {turn.stderr && (
        <details className="chat-stderr">
          <summary className="muted small">stderr</summary>
          <pre className="mono small">{turn.stderr}</pre>
        </details>
      )}
      {turn.done && turn.error && (
        <div className="chat-error err small">⚠ {turn.error}</div>
      )}
      {turn.done && turn.exitCode != null && turn.exitCode !== 0 && !turn.error && (
        <div className="muted small">exited {turn.exitCode}</div>
      )}
    </div>
  );
}
