import { useEffect, useState } from "react";

export interface FolioEvent {
  kind: string;
  ts: string;
  [key: string]: unknown;
}

/**
 * Subscribe to the Viewer SSE stream.
 *
 * Returns the most recent event (or `null` until one arrives) so
 * components can render lightweight indicators without buffering
 * everything in React state.
 */
export function useEventStream(): FolioEvent | null {
  const [latest, setLatest] = useState<FolioEvent | null>(null);

  useEffect(() => {
    if (typeof EventSource === "undefined") return;
    const source = new EventSource("/events", { withCredentials: true });
    const handler = (event: MessageEvent) => {
      try {
        const parsed = JSON.parse(event.data) as FolioEvent;
        setLatest(parsed);
      } catch {
        // ignore malformed frames
      }
    };
    source.onmessage = handler;
    source.addEventListener("materialize.start", handler as EventListener);
    source.addEventListener("materialize.end", handler as EventListener);
    source.addEventListener("materialize.error", handler as EventListener);
    return () => source.close();
  }, []);

  return latest;
}
