import { useEffect, useState } from "react";
import { ProvenanceEntry, getProvenanceHistory } from "./api";

export function History({
  recordId,
  field,
}: {
  recordId: string;
  field: string;
}) {
  const [history, setHistory] = useState<ProvenanceEntry[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!recordId || !field) return;
    getProvenanceHistory(recordId, field)
      .then(setHistory)
      .catch((err) => setError(err instanceof Error ? err.message : "load failed"));
  }, [recordId, field]);

  return (
    <div data-testid="history">
      <h2>
        history of <code>{recordId}</code>.<code>{field}</code>
      </h2>
      {error && <p style={{ color: "red" }}>{error}</p>}
      <table style={{ borderCollapse: "collapse" }}>
        <thead>
          <tr>
            <th style={th}>Timestamp</th>
            <th style={th}>Source</th>
            <th style={th}>Actor</th>
            <th style={th}>Model</th>
            <th style={th}>Cost</th>
            <th style={th}>Hash</th>
          </tr>
        </thead>
        <tbody>
          {history.map((entry, idx) => (
            <tr key={`${entry.timestamp}-${idx}`}>
              <td style={td}>{entry.timestamp}</td>
              <td style={td}>{entry.source}</td>
              <td style={td}>{entry.actor}</td>
              <td style={td}>{entry.model ?? ""}</td>
              <td style={td}>
                {entry.cost_usd === null || entry.cost_usd === undefined
                  ? "—"
                  : `$${Number(entry.cost_usd).toFixed(4)}`}
              </td>
              <td style={{ ...td, fontFamily: "monospace", fontSize: 11 }}>
                {entry.input_hash?.slice(0, 16) ?? ""}
              </td>
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
