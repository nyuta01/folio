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

  const indicatorClass = running
    ? "pulse running"
    : event?.kind === "materialize.start"
      ? "pulse running"
      : event
        ? "pulse"
        : "pulse idle";

  const statusText = running
    ? "running…"
    : event
      ? `${event.kind} · ${formatTime(event.ts)}`
      : "idle";

  const targets = Object.entries(status);

  return (
    <div data-testid="dashboard">
      <div className="dash-toolbar">
        <h2 className="page-h2">materialization status</h2>
        <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
          <div className="dash-status">
            <span className={indicatorClass} />
            <span className="mono" style={{ fontSize: 11.5 }}>
              {statusText}
            </span>
          </div>
          <button
            className="btn btn-primary"
            data-testid="materialize-all"
            onClick={runAll}
            disabled={running}
          >
            {running ? "Materializing…" : "Materialize all"}
          </button>
        </div>
      </div>

      {error && (
        <div className="card" style={{ padding: 12, color: "var(--danger)", fontSize: 12 }}>
          {error}
        </div>
      )}

      {targets.length === 0 ? (
        <div className="card empty">
          <div className="empty-mark">∅</div>
          <div>No derivations declared in this sheet.</div>
        </div>
      ) : (
        <div className="dash-grid">
          {targets.map(([target, info]) => {
            const ai = info.ai_count ?? 0;
            const imp = info.import_count ?? 0;
            const human = info.human_count ?? 0;
            const none = info.none_count ?? 0;
            const kind = info.derivation_kind ?? "—";
            return (
              <div className="dash-card" key={target}>
                <div className="dash-card-head">
                  <span className="dash-card-name">{target}</span>
                  <span className={`dash-card-kind kind-text-${kind}`}>
                    <span className={`kind-dot kind-${kind}`} />
                    {kind}
                  </span>
                </div>
                <div className="dash-counts">
                  <Count n={ai} label="ai" dim={ai === 0} />
                  <Count n={imp} label="import" dim={imp === 0} />
                  <Count n={human} label="human" dim={human === 0} />
                  <Count n={none} label="none" dim={none === 0} />
                </div>
                <div className="dash-card-foot">
                  last run · {info.last_run ? formatTime(info.last_run) : "never"}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

function Count({
  n,
  label,
  dim,
}: {
  n: number;
  label: string;
  dim: boolean;
}) {
  return (
    <div className={`dash-count${dim ? " dim" : ""}`}>
      <span className="n">{n}</span>
      <span className="label">{label}</span>
    </div>
  );
}

function formatTime(iso: string): string {
  try {
    const date = new Date(iso);
    return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
  } catch {
    return iso;
  }
}
