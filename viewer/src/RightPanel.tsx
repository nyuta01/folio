import { useEffect, useState } from "react";
import { Icons } from "./Icons";
import { FieldBadge, TypeChip } from "./RecordsGrid";
import { getProvenanceHistory } from "./api";
import type {
  ActivityEntry,
  Contract,
  ProvenanceEntry,
} from "./types";

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

export type TabId = "schema" | "activity" | "inspector";

const TABS: Array<{ id: TabId; label: string; icon: keyof typeof Icons }> = [
  { id: "schema", label: "Schema", icon: "Cell" },
  { id: "activity", label: "Activity", icon: "Sparkle" },
  { id: "inspector", label: "Inspector", icon: "Eye" },
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
}: RightPanelProps) {
  const activeDef = TABS.find((t) => t.id === activeTab) ?? TABS[0];

  return (
    <aside className={cls("rp", collapsed && "collapsed")}>
      {!collapsed && (
        <div className="rp-content">
          <div className="rp-content-head">
            <span className="rp-content-title mono">{activeDef.label}</span>
            {activeDef.id === "activity" && agentOnline && (
              <span className="live-dot live" />
            )}
            <span className="rp-tabs-spacer" />
            <button className="icon-btn" onClick={onToggle} title="Collapse">
              <Icons.X size={11} />
            </button>
          </div>
          <div className="rp-body">
            {activeTab === "schema" && (
              <SchemaTab
                contract={contract}
                records={records}
                derivations={derivations}
                onPickField={(name) => {
                  setInspectorField(name);
                  setActiveTab("inspector");
                }}
              />
            )}
            {activeTab === "activity" && (
              <ActivityTab
                activity={activity}
                agentOnline={agentOnline}
                onSimulate={onSimulate}
              />
            )}
            {activeTab === "inspector" && (
              <InspectorTab
                fieldName={inspectorField}
                contract={contract}
                records={records}
                derivations={derivations}
              />
            )}
          </div>
        </div>
      )}
      <div className="rp-rail-bar">
        {TABS.map((t) => {
          const Ico = Icons[t.icon];
          const isActive = !collapsed && activeTab === t.id;
          return (
            <button
              key={t.id}
              className={cls("rp-rail-btn", isActive && "active")}
              onClick={() => {
                if (isActive) onToggle();
                else {
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
  onPickField,
}: {
  contract: Contract;
  records: Record<string, unknown>[];
  derivations: Record<string, { kind: string; targets?: string[] }>;
  onPickField: (name: string) => void;
}) {
  const props = contract.schema[0].properties;
  const total = records.length;
  const nullCount = (name: string) =>
    records.filter((r) => r[name] == null).length;

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
      </div>
      <ul className="fieldlist">
        {props.map((p) => {
          const nulls = nullCount(p.name);
          return (
            <li
              key={p.name}
              className={cls("field-item", p["x-derived"] && "is-derived")}
              onClick={() => onPickField(p.name)}
            >
              <div className="field-name">
                <span className="mono">{p.name}</span>
                <FieldBadge prop={p} />
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
}: {
  fieldName: string | null;
  contract: Contract;
  records: Record<string, unknown>[];
  derivations: Record<string, { kind: string; targets?: string[]; model?: string; inputs?: string[]; prompt?: string }>;
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

  return (
    <div className="rp-pad">
      <div className="ins-head-display">
        <div className="ins-title">{field.name}</div>
        <div className="ins-sub">{field.description || "—"}</div>
      </div>
      <div className="ins-row">
        <FieldBadge prop={field} />
        <TypeChip t={field.logicalType} />
        {field.required && <span className="pill mono" data-tone="warn">required</span>}
        {field["x-derived"] && (
          <span className="pill mono" data-tone="ai">derived</span>
        )}
      </div>

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
