import { useEffect, useState } from "react";
import { getCoalitionMap, postCoalitionMap } from "../lib/api.js";

/**
 * Polls GET /v1/coalition-map/:id; on first 404 triggers POST once to enqueue generation.
 * Stops after 12 attempts (~60s at 5s interval).
 */
export function useCoalitionMapPoll(receiptId, enabled) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!receiptId || !enabled) {
      setData(null);
      setLoading(false);
      return undefined;
    }

    let cancelled = false;
    let attempts = 0;
    let timerId;
    setLoading(true);

    const step = async () => {
      attempts += 1;
      try {
        const row = await getCoalitionMap(receiptId);
        if (cancelled) return;
        if (row) {
          setData(row);
          setLoading(false);
          return;
        }
        if (attempts === 1) {
          const kicked = await postCoalitionMap(receiptId);
          if (cancelled) return;
          if (kicked) {
            setData(kicked);
            setLoading(false);
            return;
          }
        }
        if (attempts < 12) {
          timerId = window.setTimeout(step, 5000);
        } else {
          setLoading(false);
        }
      } catch {
        if (cancelled) return;
        if (attempts < 12) {
          timerId = window.setTimeout(step, 5000);
        } else {
          setLoading(false);
        }
      }
    };

    step();
    return () => {
      cancelled = true;
      if (timerId) window.clearTimeout(timerId);
    };
  }, [receiptId, enabled]);

  return { data, loading: loading && !data };
}
