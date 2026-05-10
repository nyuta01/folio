import { useEffect, useRef, useState } from "react";
import type { FolioEvent } from "./types";

/**
 * Subscribe to the Viewer SSE stream.
 *
 * Returns the most recent event plus a callback to fetch the running log.
 * Components that only need the latest re-render on every frame; the log
 * can be peeked synchronously without re-rendering.
 */
export function useEventStream(): {
  latest: FolioEvent | null;
  log: () => FolioEvent[];
} {
  const [latest, setLatest] = useState<FolioEvent | null>(null);
  const logRef = useRef<FolioEvent[]>([]);

  useEffect(() => {
    if (typeof EventSource === "undefined") return;
    const source = new EventSource("/events", { withCredentials: true });
    const handler = (event: MessageEvent) => {
      try {
        const parsed = JSON.parse(event.data) as FolioEvent;
        logRef.current = [...logRef.current.slice(-499), parsed];
        setLatest(parsed);
      } catch {
        // ignore malformed
      }
    };
    source.onmessage = handler;
    [
      "materialize.start",
      "materialize.end",
      "materialize.error",
    ].forEach((kind) => source.addEventListener(kind, handler as EventListener));
    return () => source.close();
  }, []);

  return { latest, log: () => logRef.current };
}
