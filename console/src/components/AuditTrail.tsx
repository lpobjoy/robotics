import { useEffect, useState } from "react";
import { listAuditEvents } from "../api";
import type { AuditEvent } from "../types";

const POLL_INTERVAL_MS = 4000;

interface Props {
  workOrderId: number | null;
}

export function AuditTrail({ workOrderId }: Props) {
  const [events, setEvents] = useState<AuditEvent[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const result = await listAuditEvents(workOrderId ?? undefined);
        if (!cancelled) {
          setEvents(result.slice().reverse());
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
      <h2>Audit trail{workOrderId !== null ? ` (work order #${workOrderId})` : ""}</h2>
      {error && <p className="error">{error}</p>}
      {events.length === 0 ? (
        <p className="muted">No audit events yet.</p>
      ) : (
        <table>
          <thead>
            <tr>
              <th>Time</th>
              <th>Actor</th>
              <th>Action</th>
              <th>Work order</th>
              <th>Mission</th>
              <th>Detail</th>
            </tr>
          </thead>
          <tbody>
            {events.map((event) => (
              <tr key={event.id}>
                <td>{new Date(event.timestamp).toLocaleTimeString()}</td>
                <td>{event.actor}</td>
                <td>{event.action}</td>
                <td>{event.work_order_id ?? "-"}</td>
                <td>{event.mission_id ?? "-"}</td>
                <td className="detail-cell">{JSON.stringify(event.detail)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}
