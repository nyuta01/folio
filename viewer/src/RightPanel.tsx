import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
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
import type { AgentAvailability, AgentEvent } from "./folio-bridge";

const RP_WIDTH_STORAGE_KEY = "folio:rp-width";
const RP_WIDTH_DEFAULT = 360;
const RP_WIDTH_MIN = 280;
const RP_WIDTH_MAX = 900;

function clampRpWidth(px: number): number {
  return Math.max(RP_WIDTH_MIN, Math.min(RP_WIDTH_MAX, Math.round(px)));
}

function applyRpWidth(px: number): void {
  document.documentElement.style.setProperty("--rp-width", `${px}px`);
}

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
  /** Called when a chat-agent turn ends. Lets the host refetch
   * records/contract from disk so writes the agent made via the
   * `folio` CLI (which bypass our in-process write API) show up in
   * the grid immediately. */
  onAgentDone?: () => void;
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
  onAgentDone,
}: RightPanelProps) {
  // Legacy `inspector` value funnels back into `schema` so the rail
  // never shows a third tab.
  const normalisedTab: TabId = activeTab === "inspector" ? "schema" : activeTab;
  const activeDef = TABS.find((t) => t.id === normalisedTab) ?? TABS[0];
  const onSchema = normalisedTab === "schema";
  const inFieldView = onSchema && inspectorField !== null;

  // Hydrate the persisted panel width on mount. We write the value into
  // a CSS variable that `.body` reads, so resizing doesn't re-render
  // any React tree during the drag.
  useEffect(() => {
    try {
      const raw = localStorage.getItem(RP_WIDTH_STORAGE_KEY);
      const px = raw ? Number.parseInt(raw, 10) : NaN;
      if (Number.isFinite(px)) applyRpWidth(clampRpWidth(px));
      else applyRpWidth(RP_WIDTH_DEFAULT);
    } catch {
      applyRpWidth(RP_WIDTH_DEFAULT);
    }
  }, []);

  const dragRef = useRef<{ startX: number; startWidth: number } | null>(null);
  const beginResize = (e: React.MouseEvent) => {
    if (collapsed) return;
    e.preventDefault();
    const startWidth =
      Number.parseFloat(
        getComputedStyle(document.documentElement).getPropertyValue(
          "--rp-width",
        ),
      ) || RP_WIDTH_DEFAULT;
    dragRef.current = { startX: e.clientX, startWidth };
    document.body.classList.add("rp-resizing");
    const onMove = (ev: MouseEvent) => {
      if (!dragRef.current) return;
      // Drag-left grows the panel — it sits on the right edge of the
      // viewport, so deltaX inverts.
      const delta = dragRef.current.startX - ev.clientX;
      const next = clampRpWidth(dragRef.current.startWidth + delta);
      applyRpWidth(next);
    };
    const onUp = () => {
      const finalPx =
        Number.parseFloat(
          getComputedStyle(document.documentElement).getPropertyValue(
            "--rp-width",
          ),
        ) || RP_WIDTH_DEFAULT;
      try {
        localStorage.setItem(RP_WIDTH_STORAGE_KEY, String(Math.round(finalPx)));
      } catch {
        /* storage full — ignore */
      }
      dragRef.current = null;
      document.body.classList.remove("rp-resizing");
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
    };
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
  };

  return (
    <aside className={cls("rp", collapsed && "collapsed")}>
      {!collapsed && (
        <div
          className="rp-resizer"
          onMouseDown={beginResize}
          onDoubleClick={() => {
            applyRpWidth(RP_WIDTH_DEFAULT);
            try {
              localStorage.setItem(
                RP_WIDTH_STORAGE_KEY,
                String(RP_WIDTH_DEFAULT),
              );
            } catch {
              /* ignore */
            }
          }}
          title="Drag to resize · double-click to reset"
        />
      )}
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
              {normalisedTab === "chat" && <ChatTab onAgentDone={onAgentDone} />}
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

type ChatBlock =
  | { kind: "text"; text: string }
  | { kind: "thinking"; text: string; done: boolean }
  | {
      kind: "tool_use";
      toolUseId: string;
      name: string;
      input: string;
      result?: string;
      isError?: boolean;
    };

type ChatTurn =
  | { role: "user"; text: string }
  | {
      role: "agent";
      /** Electron-side spawn id, used to route streaming events. */
      runId: string;
      blocks: ChatBlock[];
      stderr?: string;
      done: boolean;
      error?: string | null;
      exitCode?: number | null;
    };

interface ChatSession {
  /** UUID. Also passed to claude as --session-id so each conversation
   * gets its own on-disk store and we can resume specifically. */
  id: string;
  title: string;
  turns: ChatTurn[];
  createdAt: number;
  updatedAt: number;
}

const CHAT_STORAGE_PREFIX = "folio:chat:";

function makeChatUUID(): string {
  if (
    typeof crypto !== "undefined" &&
    typeof crypto.randomUUID === "function"
  ) {
    return crypto.randomUUID();
  }
  // Fallback shape-only UUID for older renderer envs.
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    return (c === "x" ? r : (r & 0x3) | 0x8).toString(16);
  });
}

function makeNewChatSession(title = "New chat"): ChatSession {
  const now = Date.now();
  return {
    id: makeChatUUID(),
    title,
    turns: [],
    createdAt: now,
    updatedAt: now,
  };
}

/** Render one ChatSession to a stand-alone Markdown document. The
 * output is plain GFM so it pastes cleanly into docs, PR descriptions,
 * notebooks, etc. Thinking blocks live inside `<details>` so they're
 * collapsed by default in renderers that support it (GitHub does). */
function sessionToMarkdown(session: ChatSession, agentLabel: string): string {
  const fmt = (ms: number) => new Date(ms).toISOString();
  const lines: string[] = [];
  lines.push(`# ${session.title}`);
  lines.push("");
  lines.push(
    `_Agent: **${agentLabel}** · Created: ${fmt(session.createdAt)} · Updated: ${fmt(session.updatedAt)} · Session id: \`${session.id}\`_`,
  );
  lines.push("");
  for (const turn of session.turns) {
    if (turn.role === "user") {
      lines.push("## 🧑 You");
      lines.push("");
      lines.push(turn.text);
      lines.push("");
      continue;
    }
    lines.push(`## 🤖 ${agentLabel}`);
    lines.push("");
    for (const b of turn.blocks) {
      if (b.kind === "text") {
        lines.push(b.text);
        lines.push("");
      } else if (b.kind === "thinking") {
        lines.push("<details><summary>💭 Thinking</summary>");
        lines.push("");
        // Indent thinking as a blockquote so it stays readable even if
        // the host renderer ignores <details>.
        lines.push(
          b.text
            .split("\n")
            .map((l) => "> " + l)
            .join("\n"),
        );
        lines.push("");
        lines.push("</details>");
        lines.push("");
      } else {
        // tool_use
        lines.push(`<details><summary>⚙ <code>${b.name}</code></summary>`);
        lines.push("");
        const input = (() => {
          try {
            return "```json\n" + JSON.stringify(JSON.parse(b.input), null, 2) + "\n```";
          } catch {
            return "```\n" + b.input + "\n```";
          }
        })();
        lines.push("**input**");
        lines.push("");
        lines.push(input);
        if (b.result !== undefined) {
          lines.push("");
          lines.push(`**result${b.isError ? " (error)" : ""}**`);
          lines.push("");
          lines.push("```");
          lines.push(b.result);
          lines.push("```");
        }
        lines.push("");
        lines.push("</details>");
        lines.push("");
      }
    }
    if (turn.error) {
      lines.push(`> ⚠ error: ${turn.error}`);
      lines.push("");
    } else if (turn.exitCode != null && turn.exitCode !== 0) {
      lines.push(`> ⚠ exited ${turn.exitCode}`);
      lines.push("");
    }
  }
  return lines.join("\n").replace(/\n{3,}/g, "\n\n").trim() + "\n";
}

function triggerDownload(filename: string, content: string, mime: string): void {
  const blob = new Blob([content], { type: mime });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  // Give the browser a tick to start the download before revoking.
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function slugify(s: string, fallback = "chat"): string {
  const cleaned = s
    .toLowerCase()
    .replace(/[^a-z0-9가-힣ぁ-んァ-ヴ一-龯]+/gi, "-")
    .replace(/^-+|-+$/g, "");
  return cleaned || fallback;
}

function ChatTab({ onAgentDone }: { onAgentDone?: () => void }) {
  const folioBridge =
    (typeof window !== "undefined" && window.folioBridge) || null;
  // Stash the callback in a ref so the streaming-event subscription
  // (which lives in a useEffect keyed only on `bridge`) always sees
  // the latest value without re-subscribing on every render.
  const onAgentDoneRef = useRef(onAgentDone);
  useEffect(() => {
    onAgentDoneRef.current = onAgentDone;
  }, [onAgentDone]);
  const bridge = folioBridge?.agents || null;
  const [sheetPath, setSheetPath] = useState<string | null>(null);
  const [hydrated, setHydrated] = useState(false);
  const [agentList, setAgentList] = useState<AgentAvailability[]>([]);
  const [selectedAgent, setSelectedAgent] = useState<string>("claude-code");
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  // Electron-side runId of the in-flight spawn, or null. One concurrent
  // run at a time keeps the model simple — sessions can be many, but
  // only the active one is "talking."
  const [runningRunId, setRunningRunId] = useState<string | null>(null);
  const [sessionMenuOpen, setSessionMenuOpen] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  const activeSession = sessions.find((s) => s.id === activeId) ?? null;

  // Resolve sheet path and hydrate sessions from localStorage.
  useEffect(() => {
    if (!folioBridge) {
      setHydrated(true);
      return;
    }
    folioBridge.currentSheet().then((path) => {
      setSheetPath(path);
      if (path) {
        try {
          const raw = localStorage.getItem(CHAT_STORAGE_PREFIX + path);
          if (raw) {
            const parsed = JSON.parse(raw) as ChatSession[];
            if (Array.isArray(parsed) && parsed.length > 0) {
              // Pre-block-rendering turns stored their reply as `text`
              // rather than `blocks[]`. Convert on the way in so the
              // bubble can render legacy history without crashing.
              const migrated = parsed.map((s) => ({
                ...s,
                turns: s.turns.map((t) => {
                  if (t.role !== "agent") return t;
                  const tx = t as Record<string, unknown> & { role: "agent" };
                  if (Array.isArray(tx.blocks)) return t;
                  const legacyText =
                    typeof tx.text === "string" ? tx.text : "";
                  const blocks: ChatBlock[] = legacyText
                    ? [{ kind: "text", text: legacyText }]
                    : [];
                  const { text: _legacy, ...rest } = tx;
                  void _legacy;
                  return { ...rest, blocks } as unknown as ChatTurn;
                }),
              }));
              setSessions(migrated);
              const newest = [...migrated].sort(
                (a, b) => b.updatedAt - a.updatedAt,
              )[0];
              setActiveId(newest.id);
            }
          }
        } catch {
          /* corrupt blob — ignore */
        }
      }
      setHydrated(true);
    });
  }, [folioBridge]);

  // Persist after every change (after the initial hydrate so we don't
  // wipe storage on first render).
  useEffect(() => {
    if (!hydrated || !sheetPath) return;
    const key = CHAT_STORAGE_PREFIX + sheetPath;
    if (sessions.length === 0) localStorage.removeItem(key);
    else localStorage.setItem(key, JSON.stringify(sessions));
  }, [sessions, sheetPath, hydrated]);

  useEffect(() => {
    if (!bridge) return;
    bridge.list().then((list) => {
      setAgentList(list);
      const firstAvail = list.find((a) => a.available)?.id;
      if (firstAvail) setSelectedAgent(firstAvail);
    });
  }, [bridge]);

  // Per-message → blocks[] index mapping. Claude's stream-json resets
  // content_block indices to 0 every time the assistant starts a new
  // message (after tool roundtrips), but our renderer keeps a single
  // flat `blocks[]` list per turn. Keyed by runId so concurrent runs
  // don't share state. Lives in a ref so updates don't re-render.
  const blockIndexRef = useRef<Map<string, Map<number, number>>>(new Map());

  // Route structured events into whichever session holds the matching
  // runId, regardless of which one is currently visible.
  useEffect(() => {
    if (!bridge) return;

    const updateAgentTurn = (
      runId: string,
      mut: (t: Extract<ChatTurn, { role: "agent" }>) => ChatTurn,
    ) => {
      setSessions((cur) =>
        cur.map((s) => {
          const i = s.turns.findIndex(
            (t) => t.role === "agent" && t.runId === runId,
          );
          if (i < 0) return s;
          const nextTurns = s.turns.slice();
          nextTurns[i] = mut(
            nextTurns[i] as Extract<ChatTurn, { role: "agent" }>,
          );
          return { ...s, turns: nextTurns, updatedAt: Date.now() };
        }),
      );
    };

    const getIndexMap = (runId: string): Map<number, number> => {
      let m = blockIndexRef.current.get(runId);
      if (!m) {
        m = new Map();
        blockIndexRef.current.set(runId, m);
      }
      return m;
    };

    const offEvent = bridge.onEvent(({ sessionId: runId, event }) => {
      const ev = event as AgentEvent;
      if (ev.kind === "message_start") {
        // Per-message indices reset; flush our mapping so the next
        // block_start gets a fresh slot in blocks[].
        getIndexMap(runId).clear();
        return;
      }
      if (ev.kind === "block_start") {
        updateAgentTurn(runId, (t) => {
          const blocks = t.blocks.slice();
          let block: ChatBlock;
          if (ev.blockType === "thinking") {
            block = { kind: "thinking", text: "", done: false };
          } else if (ev.blockType === "tool_use") {
            block = {
              kind: "tool_use",
              toolUseId: ev.toolUseId ?? "",
              name: ev.toolName ?? "tool",
              input: "",
            };
          } else {
            block = { kind: "text", text: "" };
          }
          blocks.push(block);
          getIndexMap(runId).set(ev.index, blocks.length - 1);
          return { ...t, blocks };
        });
        return;
      }
      if (ev.kind === "block_delta") {
        const pos = getIndexMap(runId).get(ev.index);
        if (pos == null) return;
        updateAgentTurn(runId, (t) => {
          const blocks = t.blocks.slice();
          const b = blocks[pos];
          if (b.kind === "text" || b.kind === "thinking") {
            blocks[pos] = { ...b, text: b.text + ev.text };
          } else if (b.kind === "tool_use") {
            blocks[pos] = { ...b, input: b.input + ev.text };
          }
          return { ...t, blocks };
        });
        return;
      }
      if (ev.kind === "block_stop") {
        const pos = getIndexMap(runId).get(ev.index);
        if (pos == null) return;
        updateAgentTurn(runId, (t) => {
          const blocks = t.blocks.slice();
          const b = blocks[pos];
          if (b.kind === "thinking") blocks[pos] = { ...b, done: true };
          return { ...t, blocks };
        });
        return;
      }
      if (ev.kind === "tool_result") {
        updateAgentTurn(runId, (t) => {
          const i = t.blocks.findIndex(
            (b) => b.kind === "tool_use" && b.toolUseId === ev.toolUseId,
          );
          if (i < 0) return t;
          const blocks = t.blocks.slice();
          const b = blocks[i];
          if (b.kind === "tool_use") {
            blocks[i] = { ...b, result: ev.content, isError: ev.isError };
          }
          return { ...t, blocks };
        });
        return;
      }
      // `status` events are informational; ignore for now.
    });

    const offChunk = bridge.onChunk(({ sessionId: runId, stream, data }) => {
      // Only stderr reaches us when an adapter uses parseLine — stdout
      // is JSON we've already parsed into block_* events upstream.
      if (stream !== "stderr") return;
      updateAgentTurn(runId, (t) => ({
        ...t,
        stderr: (t.stderr ?? "") + data,
      }));
    });

    const offEnd = bridge.onEnd(({ sessionId: runId, exitCode, error }) => {
      updateAgentTurn(runId, (t) => ({ ...t, done: true, exitCode, error }));
      blockIndexRef.current.delete(runId);
      setRunningRunId((cur) => (cur === runId ? null : cur));
      // Agents write via the `folio` CLI, which bypasses our in-process
      // write API. Ping the host so it refetches records/contract from
      // disk; otherwise the grid silently drifts out of sync with the
      // sheet that the agent just modified.
      onAgentDoneRef.current?.();
    });
    return () => {
      offEvent();
      offChunk();
      offEnd();
    };
  }, [bridge]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ block: "end" });
  }, [activeSession?.turns]);

  if (!bridge) {
    return (
      <div className="rp-pad">
        <div className="rp-section-title">Chat</div>
        <p className="muted small">
          The chat panel runs coding agents on the sheet's directory. It needs
          access to the host shell and is therefore{" "}
          <strong>Folio Desktop only</strong> — the standalone{" "}
          <code>folio serve</code> viewer can't spawn binaries.
        </p>
        <p className="muted small">
          Launch the desktop app and reopen this sheet to use it.
        </p>
      </div>
    );
  }

  const newSession = () => {
    const s = makeNewChatSession();
    setSessions((cur) => [...cur, s]);
    setActiveId(s.id);
    setSessionMenuOpen(false);
  };

  const deleteSession = (id: string) => {
    setSessions((cur) => cur.filter((s) => s.id !== id));
    if (activeId === id) setActiveId(null);
    if (sessions.length <= 1) setSessionMenuOpen(false);
  };

  const switchSession = (id: string) => {
    setActiveId(id);
    setSessionMenuOpen(false);
  };

  const exportSession = (s: ChatSession): void => {
    const label =
      agentList.find((a) => a.id === selectedAgent)?.label ?? "Agent";
    const md = sessionToMarkdown(s, label);
    const stamp = new Date(s.updatedAt).toISOString().slice(0, 10);
    triggerDownload(
      `folio-chat-${stamp}-${slugify(s.title)}.md`,
      md,
      "text/markdown",
    );
  };

  const send = async () => {
    const prompt = draft.trim();
    if (!prompt || runningRunId) return;
    const spec = agentList.find((a) => a.id === selectedAgent);
    if (!spec?.available) return;

    let target = activeSession;
    if (!target) {
      target = makeNewChatSession(prompt.slice(0, 60));
      setSessions((cur) => [...cur, target!]);
      setActiveId(target.id);
    }
    const chatId = target.id;
    const isFollowup = target.turns.length > 0;

    setDraft("");
    setSessions((cur) =>
      cur.map((s) => {
        if (s.id !== chatId) return s;
        const turns: ChatTurn[] = [...s.turns, { role: "user", text: prompt }];
        const title = s.turns.length === 0 ? prompt.slice(0, 60) : s.title;
        return { ...s, turns, title, updatedAt: Date.now() };
      }),
    );

    const result = await bridge.run({
      agentId: selectedAgent,
      prompt,
      sessionId: chatId,
      isFollowup,
    });
    if (!result.ok) {
      setSessions((cur) =>
        cur.map((s) =>
          s.id === chatId
            ? {
                ...s,
                turns: [
                  ...s.turns,
                  {
                    role: "agent",
                    runId: "err-" + Date.now(),
                    blocks: [],
                    done: true,
                    error: result.error,
                    exitCode: null,
                  },
                ],
                updatedAt: Date.now(),
              }
            : s,
        ),
      );
      return;
    }
    setRunningRunId(result.sessionId);
    setSessions((cur) =>
      cur.map((s) =>
        s.id === chatId
          ? {
              ...s,
              turns: [
                ...s.turns,
                {
                  role: "agent",
                  runId: result.sessionId,
                  blocks: [],
                  done: false,
                },
              ],
              updatedAt: Date.now(),
            }
          : s,
      ),
    );
  };

  const stop = () => {
    if (runningRunId) bridge.stop({ sessionId: runningRunId });
  };

  const selectedSpec = agentList.find((a) => a.id === selectedAgent);
  const canSend =
    !!selectedSpec?.available && !runningRunId && draft.trim().length > 0;
  const turns = activeSession?.turns ?? [];
  const sortedSessions = [...sessions].sort(
    (a, b) => b.updatedAt - a.updatedAt,
  );
  const triggerTitle =
    activeSession?.title ??
    (sessions.length === 0 ? "New chat" : "Select a session");

  return (
    <div className="chat-tab">
      <div className="chat-header">
        <div className="chat-pickrow">
          <select
            id="chat-agent"
            className="chat-agent-select mono small"
            value={selectedAgent}
            onChange={(e) => setSelectedAgent(e.target.value)}
            disabled={!!runningRunId}
          >
            {agentList.map((a) => (
              <option key={a.id} value={a.id} disabled={!a.available}>
                {a.label}
                {a.available ? "" : " (not installed)"}
              </option>
            ))}
          </select>
          {selectedSpec?.version && (
            <span className="muted small mono chat-version">
              {selectedSpec.version}
            </span>
          )}
          <span className="rp-tabs-spacer" />
        </div>
        {selectedSpec && !selectedSpec.available && (
          <div className="chat-install-hint muted small">
            {selectedSpec.installHint ?? "binary not on $PATH"}
          </div>
        )}

        <div className="chat-sessions-row">
          <button
            className={cls(
              "chat-session-trigger",
              sessionMenuOpen && "open",
            )}
            onClick={() => setSessionMenuOpen((v) => !v)}
            title="Switch chat session"
          >
            <span className="chat-session-caret" aria-hidden>
              <Icons.ChevronR size={10} />
            </span>
            <span className="ellipsis chat-session-trigger-label">
              {triggerTitle}
            </span>
            {sessions.length > 0 && (
              <span className="muted small mono chat-session-count">
                {sessions.length}
              </span>
            )}
          </button>
          <button
            className="ghost-btn small chat-session-new"
            onClick={() => activeSession && exportSession(activeSession)}
            disabled={!activeSession || activeSession.turns.length === 0}
            title="Export this conversation as Markdown"
          >
            <Icons.Download size={10} />
          </button>
          <button
            className="ghost-btn small chat-session-new"
            onClick={newSession}
            disabled={!!runningRunId}
            title="Start a new conversation"
          >
            <Icons.Plus size={10} />
          </button>
        </div>
        {sessionMenuOpen && (
          <ul className="chat-sessions-menu">
            {sortedSessions.length === 0 && (
              <li className="muted small chat-session-empty">
                No sessions yet — send a message to start one.
              </li>
            )}
            {sortedSessions.map((s) => (
              <li
                key={s.id}
                className={cls(
                  "chat-session-row",
                  s.id === activeId && "active",
                )}
              >
                <button
                  className="chat-session-pick"
                  onClick={() => switchSession(s.id)}
                >
                  <span className="chat-session-title ellipsis">
                    {s.title}
                  </span>
                  <span className="muted small chat-session-time">
                    {fmtTime(new Date(s.updatedAt).toISOString())}
                  </span>
                </button>
                <button
                  className="icon-btn chat-session-del"
                  onClick={(e) => {
                    e.stopPropagation();
                    exportSession(s);
                  }}
                  title="Export as Markdown"
                  disabled={s.turns.length === 0}
                >
                  <Icons.Download size={10} />
                </button>
                <button
                  className="icon-btn chat-session-del"
                  onClick={(e) => {
                    e.stopPropagation();
                    deleteSession(s.id);
                  }}
                  title="Delete session"
                >
                  <Icons.X size={10} />
                </button>
              </li>
            ))}
          </ul>
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
          disabled={!selectedSpec?.available || !!runningRunId}
          rows={3}
        />
        <div className="chat-composer-actions">
          {runningRunId ? (
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
      <div className="chat-row chat-row-user">
        <div className="chat-bubble chat-user">
          <div className="chat-bubble-text">{turn.text}</div>
        </div>
      </div>
    );
  }
  const failed =
    !!turn.error || (turn.exitCode != null && turn.exitCode !== 0);
  const showStderr = failed && !!turn.stderr;
  const hasContent = turn.blocks.length > 0;
  return (
    <div className="chat-row chat-row-agent">
      <div className="chat-bubble chat-agent">
        {turn.blocks.map((b, i) => (
          <ChatBlockView key={i} block={b} />
        ))}
        {!turn.done && !hasContent && (
          <div className="chat-typing muted small">…</div>
        )}
        {turn.done && turn.error && (
          <div className="chat-error err small">⚠ {turn.error}</div>
        )}
        {turn.done && failed && !turn.error && (
          <div className="muted small">exited {turn.exitCode}</div>
        )}
        {showStderr && (
          <details className="chat-stderr">
            <summary className="muted small">stderr</summary>
            <pre className="mono small">{turn.stderr}</pre>
          </details>
        )}
      </div>
    </div>
  );
}

function ChatBlockView({ block }: { block: ChatBlock }) {
  if (block.kind === "thinking") {
    // Default-open while streaming so the user can watch reasoning;
    // collapse once done so the final answer stays visually dominant.
    return (
      <details className="chat-thinking" open={!block.done}>
        <summary>{block.done ? "Thought" : "Thinking…"}</summary>
        <div className="chat-thinking-body">{block.text || "…"}</div>
      </details>
    );
  }
  if (block.kind === "tool_use") {
    const argsPreview = summarizeToolArgs(block.input);
    return (
      <details className={cls("chat-tool", block.isError && "is-error")}>
        <summary>
          <span className="chat-tool-icon" aria-hidden>
            ⚙
          </span>
          <span className="chat-tool-name">{block.name}</span>
          {argsPreview && (
            <span className="chat-tool-args">{argsPreview}</span>
          )}
        </summary>
        <div className="chat-tool-body">
          {block.input && (
            <>
              <div className="muted small">input</div>
              <pre>{prettyJsonOrRaw(block.input)}</pre>
            </>
          )}
          {block.result !== undefined && (
            <>
              <div className="muted small" style={{ marginTop: 6 }}>
                result{block.isError ? " (error)" : ""}
              </div>
              <pre>{block.result}</pre>
            </>
          )}
        </div>
      </details>
    );
  }
  // text block — render as markdown
  return (
    <div className="chat-md">
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{block.text}</ReactMarkdown>
    </div>
  );
}

/** Pull a short args preview out of a tool's (partial) JSON input. We
 * never block on parsing — if the JSON isn't complete yet, return a
 * truncated raw slice instead so the chip still shows something. */
function summarizeToolArgs(raw: string): string {
  if (!raw) return "";
  try {
    const obj = JSON.parse(raw) as Record<string, unknown>;
    // Common shapes: { path }, { command }, { url }, { file_path }, …
    for (const k of ["path", "file_path", "command", "url", "pattern", "query"]) {
      const v = obj[k];
      if (typeof v === "string" && v) return v;
    }
    const first = Object.values(obj).find((x) => typeof x === "string");
    if (typeof first === "string") return first;
  } catch {
    /* not yet complete JSON — fall through */
  }
  const flat = raw.replace(/\s+/g, " ").trim();
  return flat.length > 80 ? flat.slice(0, 80) + "…" : flat;
}

function prettyJsonOrRaw(s: string): string {
  try {
    return JSON.stringify(JSON.parse(s), null, 2);
  } catch {
    return s;
  }
}
