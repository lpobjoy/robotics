import { useEffect, useState } from "react";
import { getMissionStatus } from "../api";
import type { MissionStatusReport } from "../types";

const POLL_INTERVAL_MS = 3000;

interface Props {
  workOrderId: number | null;
}

export function MissionStatus({ workOrderId }: Props) {
  const [status, setStatus] = useState<MissionStatusReport | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (workOrderId === null) {
      setStatus(null);
      return;
    }

    let cancelled = false;

    async function load() {
      try {
        const result = await getMissionStatus(workOrderId!);
        if (!cancelled) {
          setStatus(result);
          setError(null);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : String(err));
        }
      }
    }

    load();
    const interval = setInterval(load, POLL_INTERVAL_MS);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [workOrderId]);

  return (
    <section>
      <h2>Mission status</h2>
      {workOrderId === null && <p className="muted">Select a work order to see its mission.</p>}
      {error && <p className="error">{error}</p>}
      {workOrderId !== null && !error && status === null && (
        <p className="muted">No mission dispatched for work order #{workOrderId} yet.</p>
      )}
      {status && (
        <dl className="mission-status">
          <dt>Mission</dt>
          <dd>{status.mission_id}</dd>
          <dt>Status</dt>
          <dd>
            <span className={`status status-${status.status}`}>{status.status}</span>
          </dd>
          {status.detail && (
            <>
              <dt>Detail</dt>
              <dd>{status.detail}</dd>
            </>
          )}
        </dl>
      )}
    </section>
  );
}
