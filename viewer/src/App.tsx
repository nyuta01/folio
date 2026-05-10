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

const TYPE_CHIP_STYLE: React.CSSProperties = {
  display: "inline-block",
  padding: "0 6px",
  marginLeft: 6,
  borderRadius: 4,
  fontSize: 10,
  fontWeight: 600,
  textTransform: "uppercase",
  background: "#eef",
  color: "#225",
};

const DERIVED_BADGE_STYLE: React.CSSProperties = {
  display: "inline-block",
  padding: "0 4px",
  marginLeft: 4,
  borderRadius: 4,
  fontSize: 9,
  background: "#fea",
  color: "#660",
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
}: {
  recordId: string;
  field: string;
  value: unknown;
}) {
  const [entry, setEntry] = useState<ProvenanceEntry | null>(null);
  useEffect(() => {
    getProvenance(recordId, field).then(setEntry).catch(() => setEntry(null));
  }, [recordId, field]);
  const display = value === null || value === undefined ? "" : String(value);
  const tooltip = entry
    ? `${entry.source} by ${entry.actor} @ ${entry.timestamp}`
    : "no provenance";
  return (
    <span title={tooltip}>
      {display}
      {entry && entry.source !== "human" && (
        <span
          data-testid={`badge-${field}`}
          style={{
            ...DERIVED_BADGE_STYLE,
            background: entry.source === "ai" ? "#fea" : "#cef",
          }}
        >
          {entry.source}
        </span>
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
  const [draft, setDraft] = useState(value === null || value === undefined ? "" : String(value));
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function save() {
    setSaving(true);
    setError(null);
    try {
      await upsertRecord({ id: recordId, [field]: draft });
      onSaved();
    } catch (err) {
      setError(err instanceof Error ? err.message : "save failed");
    } finally {
      setSaving(false);
    }
  }

  return (
    <span>
      <input
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        onBlur={save}
        disabled={saving}
        data-testid={`edit-${field}`}
        style={{ width: "100%" }}
      />
      {error && <span style={{ color: "red", marginLeft: 4 }}>{error}</span>}
    </span>
  );
}

type Tab = "records" | "dashboard" | "history";

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
    return properties.map((prop) => ({
      id: prop.name,
      accessorKey: prop.name,
      header: () => (
        <span title={prop.description || ""}>
          {prop.name}
          <span style={TYPE_CHIP_STYLE}>{prop.logicalType}</span>
          {prop["x-derived"] && (
            <span style={{ ...DERIVED_BADGE_STYLE, background: "#cfd" }}>
              derived
            </span>
          )}
        </span>
      ),
      cell: ({ row }) => {
        const recordId = String(row.original[primaryKey] ?? "");
        const value = row.original[prop.name];
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
          <span
            onClick={() => {
              setHistoryTarget({ recordId, field: prop.name });
              setTab("history");
            }}
            style={{ cursor: "pointer" }}
          >
            <ProvenanceCell
              recordId={recordId}
              field={prop.name}
              value={value}
            />
          </span>
        );
      },
    }));
  }, [properties, primaryKey, actor]);

  const table = useReactTable({
    data: rows,
    columns,
    getCoreRowModel: getCoreRowModel(),
  });

  if (!contract) return <div>Loading…</div>;

  return (
    <div style={{ fontFamily: "system-ui", padding: 16 }}>
      <h1>{contract.name}</h1>
      <p style={{ color: "#666" }}>
        {contract.id} · v{contract.version} · actor {actor}
      </p>
      <nav data-testid="nav" style={{ marginBottom: 12 }}>
        {(["records", "dashboard", "history"] as Tab[]).map((t) => (
          <button
            key={t}
            data-testid={`tab-${t}`}
            onClick={() => setTab(t)}
            disabled={tab === t}
            style={{
              marginRight: 6,
              padding: "4px 10px",
              fontWeight: tab === t ? 700 : 400,
            }}
          >
            {t}
          </button>
        ))}
      </nav>
      {tab === "records" && (
        <table data-testid="records-table" style={{ borderCollapse: "collapse" }}>
          <thead>
            {table.getHeaderGroups().map((group) => (
              <tr key={group.id}>
                {group.headers.map((header) => (
                  <th
                    key={header.id}
                    style={{
                      border: "1px solid #ccc",
                      padding: "4px 8px",
                      background: "#f5f5f5",
                      textAlign: "left",
                    }}
                  >
                    {flexRender(header.column.columnDef.header, header.getContext())}
                  </th>
                ))}
              </tr>
            ))}
          </thead>
          <tbody>
            {table.getRowModel().rows.map((row) => (
              <tr key={row.id}>
                {row.getVisibleCells().map((cell) => (
                  <td
                    key={cell.id}
                    style={{ border: "1px solid #eee", padding: "4px 8px" }}
                  >
                    {flexRender(cell.column.columnDef.cell, cell.getContext())}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {tab === "dashboard" && <Dashboard actor={actor} />}
      {tab === "history" && historyTarget && (
        <History recordId={historyTarget.recordId} field={historyTarget.field} />
      )}
      {tab === "history" && !historyTarget && (
        <p>Click a non-editable cell on the records tab to view its history.</p>
      )}
    </div>
  );
}
