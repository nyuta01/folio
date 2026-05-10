import { useEffect, useState } from "react";
import { TargetStatus, getStatus, materializeAll } from "./api";
import { useEventStream } from "./useEventStream";

export function Dashboard({ actor }: { actor: string }) {
  const [status, setStatus] = useState<Record<string, TargetStatus>>({});
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const event = useEventStream();

  async function refresh() {
    try {
      setStatus(await getStatus());
    } catch (err) {
      setError(err instanceof Error ? err.message : "load failed");
    }
  }

  useEffect(() => {
    refresh();
  }, []);

  useEffect(() => {
    if (event && event.kind === "materialize.end") {
      refresh();
    }
  }, [event]);

  async function runAll() {
    setRunning(true);
    setError(null);
    try {
      await materializeAll(actor);
    } catch (err) {
      setError(err instanceof Error ? err.message : "materialize failed");
    } finally {
      setRunning(false);
      refresh();
    }
  }

  const banner = event && event.kind.startsWith("materialize.")
    ? `${event.kind} @ ${event.ts}`
    : null;

  return (
    <div data-testid="dashboard">
      <div style={{ marginBottom: 12 }}>
        <button
          data-testid="materialize-all"
          onClick={runAll}
          disabled={running}
        >
          {running ? "Materializing…" : "Materialize all"}
        </button>
        {banner && (
          <span style={{ marginLeft: 12, color: "#666" }}>{banner}</span>
        )}
      </div>
      {error && <p style={{ color: "red" }}>{error}</p>}
      <table style={{ borderCollapse: "collapse" }}>
        <thead>
          <tr>
            <th style={th}>Target</th>
            <th style={th}>Kind</th>
            <th style={th}>AI</th>
            <th style={th}>Import</th>
            <th style={th}>Human</th>
            <th style={th}>None</th>
            <th style={th}>Last run</th>
          </tr>
        </thead>
        <tbody>
          {Object.entries(status).map(([target, info]) => (
            <tr key={target}>
              <td style={td}>{target}</td>
              <td style={td}>{info.derivation_kind ?? ""}</td>
              <td style={td}>{info.ai_count ?? 0}</td>
              <td style={td}>{info.import_count ?? 0}</td>
              <td style={td}>{info.human_count ?? 0}</td>
              <td style={td}>{info.none_count ?? 0}</td>
              <td style={td}>{info.last_run ?? "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

const th: React.CSSProperties = {
  border: "1px solid #ccc",
  padding: "4px 8px",
  background: "#f5f5f5",
  textAlign: "left",
};

const td: React.CSSProperties = {
  border: "1px solid #eee",
  padding: "4px 8px",
};
