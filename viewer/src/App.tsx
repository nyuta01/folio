import { useEffect, useMemo, useState } from "react";
import {
  flexRender,
  getCoreRowModel,
  useReactTable,
  type ColumnDef,
} from "@tanstack/react-table";
import {
  Contract,
  ContractProperty,
  ProvenanceEntry,
  getContract,
  getProvenance,
  listRecords,
  upsertRecord,
} from "./api";
import { Dashboard } from "./Dashboard";
import { History } from "./History";

type Row = Record<string, unknown>;
type Tab = "records" | "dashboard" | "history";

const KIND_LABEL: Record<string, string> = {
  ai: "ai",
  import: "import",
  python: "python",
  sql: "sql",
  http: "http",
  cross_sheet: "cross",
  human: "human",
};

function isEditable(prop: ContractProperty, actor: string): boolean {
  const patterns = prop["x-editable-by"];
  if (!patterns?.length) return false;
  return patterns.some((p) => p === actor || p === "*");
}

function ProvenanceCell({
  recordId,
  field,
  value,
  onClick,
}: {
  recordId: string;
  field: string;
  value: unknown;
  onClick: () => void;
}) {
  const [entry, setEntry] = useState<ProvenanceEntry | null>(null);
  useEffect(() => {
    getProvenance(recordId, field)
      .then(setEntry)
      .catch(() => setEntry(null));
  }, [recordId, field]);

  const display =
    value === null || value === undefined || value === ""
      ? null
      : String(value);
  const tip = entry
    ? `${entry.source} · ${entry.actor} · ${entry.timestamp}`
    : "no provenance";

  return (
    <span
      className="cell-provenance tooltip"
      data-tip={tip}
      onClick={onClick}
    >
      {display === null ? (
        <span className="cell-empty">—</span>
      ) : (
        <span>{display}</span>
      )}
      {entry && entry.source !== "human" && (
        <>
          <span className={`kind-dot kind-${entry.source}`} />
          <span className={`kind-label kind-text-${entry.source}`}>
            {KIND_LABEL[entry.source] ?? entry.source}
          </span>
        </>
      )}
    </span>
  );
}

function EditableCell({
  recordId,
  field,
  value,
  onSaved,
}: {
  recordId: string;
  field: string;
  value: unknown;
  onSaved: () => void;
}) {
  const [draft, setDraft] = useState(
    value === null || value === undefined ? "" : String(value),
  );
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [dirty, setDirty] = useState(false);

  useEffect(() => {
    setDraft(value === null || value === undefined ? "" : String(value));
    setDirty(false);
  }, [value]);

  async function commit() {
    if (!dirty) return;
    setSaving(true);
    setError(null);
    try {
      await upsertRecord({ id: recordId, [field]: draft });
      setDirty(false);
      onSaved();
    } catch (err) {
      setError(err instanceof Error ? err.message : "save failed");
    } finally {
      setSaving(false);
    }
  }

  return (
    <span className="cell-editable">
      <input
        value={draft}
        onChange={(e) => {
          setDraft(e.target.value);
          setDirty(true);
        }}
        onBlur={commit}
        onKeyDown={(e) => {
          if (e.key === "Enter") (e.target as HTMLInputElement).blur();
          if (e.key === "Escape") {
            setDraft(value === null || value === undefined ? "" : String(value));
            setDirty(false);
            (e.target as HTMLInputElement).blur();
          }
        }}
        disabled={saving}
        data-testid={`edit-${field}`}
      />
      <span className="pencil" aria-hidden="true">
        ✎
      </span>
      {error && <span className="cell-error">{error}</span>}
    </span>
  );
}

export default function App() {
  const [contract, setContract] = useState<Contract | null>(null);
  const [rows, setRows] = useState<Row[]>([]);
  const [actor] = useState("agent:human");
  const [reloadKey, setReloadKey] = useState(0);
  const [tab, setTab] = useState<Tab>("records");
  const [historyTarget, setHistoryTarget] = useState<{
    recordId: string;
    field: string;
  } | null>(null);

  useEffect(() => {
    getContract().then(setContract).catch(console.error);
  }, []);

  useEffect(() => {
    listRecords({ limit: 200 })
      .then((envelope) => setRows(envelope.records as Row[]))
      .catch(console.error);
  }, [reloadKey]);

  const properties = contract?.schema?.[0]?.properties ?? [];
  const primaryKey =
    properties.find((p) => p.primaryKey)?.name ?? properties[0]?.name ?? "id";

  const columns = useMemo<ColumnDef<Row>[]>(() => {
    return properties.map((prop) => {
      const isPk = prop.primaryKey === true;
      return {
        id: prop.name,
        accessorKey: prop.name,
        header: () => (
          <span title={prop.description || ""}>
            <span className="col-name">{prop.name}</span>
            <span className={`type-chip${prop["x-derived"] ? " derived" : ""}`}>
              {prop["x-derived"] ? "derived" : prop.logicalType}
            </span>
            {prop.required && <span className="col-flag-required">·req</span>}
          </span>
        ),
        cell: ({ row }) => {
          const recordId = String(row.original[primaryKey] ?? "");
          const value = row.original[prop.name];
          if (isPk) {
            return <span className="mono">{String(value ?? "")}</span>;
          }
          if (isEditable(prop, actor)) {
            return (
              <EditableCell
                recordId={recordId}
                field={prop.name}
                value={value}
                onSaved={() => setReloadKey((k) => k + 1)}
              />
            );
          }
          return (
            <ProvenanceCell
              recordId={recordId}
              field={prop.name}
              value={value}
              onClick={() => {
                setHistoryTarget({ recordId, field: prop.name });
                setTab("history");
              }}
            />
          );
        },
        meta: { isPk },
      };
    });
  }, [properties, primaryKey, actor]);

  const table = useReactTable({
    data: rows,
    columns,
    getCoreRowModel: getCoreRowModel(),
  });

  if (!contract) {
    return (
      <div className="app-shell">
        <div className="loading">Loading sheet…</div>
      </div>
    );
  }

  return (
    <div className="app-shell">
      <header className="app-header">
        <div className="app-title">
          <h1>{contract.name}</h1>
          <div className="meta">
            <span>{contract.id}</span>
            <span className="sep">·</span>
            <span>v{contract.version}</span>
            <span className="sep">·</span>
            <span>{rows.length} records</span>
          </div>
        </div>
        <div style={{ display: "flex", gap: 14, alignItems: "center" }}>
          <div className="actor-pill">
            <span className="dot" />
            {actor}
          </div>
          <div className="segmented" role="tablist">
            {(["records", "dashboard", "history"] as Tab[]).map((t) => (
              <button
                key={t}
                role="tab"
                aria-selected={tab === t}
                onClick={() => setTab(t)}
                data-testid={`tab-${t}`}
              >
                {t}
              </button>
            ))}
          </div>
        </div>
      </header>

      <main className="app-main">
        {tab === "records" && (
          <div className="records-frame">
            <div className="records-toolbar">
              <span>
                <span className="count">{rows.length}</span> records
              </span>
              <span className="mono" style={{ color: "var(--ink-subtle)" }}>
                primaryKey · <code>{primaryKey}</code>
              </span>
            </div>
            <div className="table-scroll">
              <table
                className="folio-table"
                data-testid="records-table"
              >
                <thead>
                  {table.getHeaderGroups().map((group) => (
                    <tr key={group.id}>
                      {group.headers.map((header) => {
                        const isPk = (header.column.columnDef.meta as { isPk?: boolean } | undefined)?.isPk;
                        return (
                          <th key={header.id} className={isPk ? "pk" : ""}>
                            {flexRender(
                              header.column.columnDef.header,
                              header.getContext(),
                            )}
                          </th>
                        );
                      })}
                    </tr>
                  ))}
                </thead>
                <tbody>
                  {table.getRowModel().rows.map((row) => (
                    <tr key={row.id}>
                      {row.getVisibleCells().map((cell) => {
                        const isPk = (cell.column.columnDef.meta as { isPk?: boolean } | undefined)?.isPk;
                        return (
                          <td key={cell.id} className={isPk ? "pk" : ""}>
                            {flexRender(
                              cell.column.columnDef.cell,
                              cell.getContext(),
                            )}
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {tab === "dashboard" && <Dashboard actor={actor} />}

        {tab === "history" && historyTarget && (
          <History
            recordId={historyTarget.recordId}
            field={historyTarget.field}
          />
        )}

        {tab === "history" && !historyTarget && (
          <div className="card empty">
            <div className="empty-mark">↺</div>
            <div>
              Click a non-editable cell on <strong>records</strong> to inspect
              its append-only history.
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
