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
      .catch((err) =>
        setError(err instanceof Error ? err.message : "load failed"),
      );
  }, [recordId, field]);

  return (
    <div data-testid="history">
      <h2 className="page-h2">
        history · <code>{recordId}</code> <code>.{field}</code>
      </h2>

      {error && (
        <div className="card" style={{ padding: 12, color: "var(--danger)", fontSize: 12 }}>
          {error}
        </div>
      )}

      {history.length === 0 ? (
        <div className="card empty">
          <div className="empty-mark">∅</div>
          <div>No provenance entries yet for this cell.</div>
        </div>
      ) : (
        <div className="card" style={{ padding: 22 }}>
          <div className="timeline">
            {history.map((entry, idx) => (
              <div
                className="timeline-entry"
                key={`${entry.timestamp}-${idx}`}
                data-source={entry.source}
              >
                <div className="timeline-head">
                  <span className={`kind-text-${entry.source}`}>
                    {entry.source}
                  </span>
                  <span className="actor">{entry.actor}</span>
                  <span className="when">{formatStamp(entry.timestamp)}</span>
                </div>
                <div className="timeline-meta">
                  {entry.model && (
                    <span>
                      <span className="key">model</span>
                      <span className="v-mono">{entry.model}</span>
                    </span>
                  )}
                  {entry.cost_usd !== null && entry.cost_usd !== undefined && (
                    <span>
                      <span className="key">cost</span>
                      <span className="v-mono">
                        ${Number(entry.cost_usd).toFixed(4)}
                      </span>
                    </span>
                  )}
                  {entry.input_hash && (
                    <span>
                      <span className="key">hash</span>
                      <span className="v-mono">
                        {entry.input_hash.replace("sha256:", "").slice(0, 12)}…
                      </span>
                    </span>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function formatStamp(iso: string): string {
  try {
    const date = new Date(iso);
    return date.toLocaleString([], {
      month: "short",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });
  } catch {
    return iso;
  }
}
