import { useEffect, useState } from "react";
import { abortEscalation, approveEscalation, listWorkOrders } from "../api";
import type { WorkOrder } from "../types";

const POLL_INTERVAL_MS = 4000;

export function EscalationQueue() {
  const [escalated, setEscalated] = useState<WorkOrder[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<number | null>(null);

  async function refresh() {
    try {
      const all = await listWorkOrders();
      setEscalated(all.filter((wo) => wo.status === "AwaitingHuman"));
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }

  useEffect(() => {
    refresh();
    const interval = setInterval(refresh, POLL_INTERVAL_MS);
    return () => clearInterval(interval);
  }, []);

  async function handleApprove(workOrderId: number) {
    setBusyId(workOrderId);
    try {
      await approveEscalation(workOrderId);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusyId(null);
    }
  }

  async function handleAbort(workOrderId: number) {
    setBusyId(workOrderId);
    try {
      await abortEscalation(workOrderId);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusyId(null);
    }
  }

  return (
    <section>
      <h2>Escalation queue</h2>
      {error && <p className="error">{error}</p>}
      {escalated.length === 0 ? (
        <p className="muted">Nothing awaiting a human right now.</p>
      ) : (
        <ul className="escalation-list">
          {escalated.map((wo) => (
            <li key={wo.id}>
              <span>
                #{wo.id} {wo.title}
              </span>
              <div className="escalation-actions">
                <button disabled={busyId === wo.id} onClick={() => handleApprove(wo.id)}>
                  Approve
                </button>
                <button
                  disabled={busyId === wo.id}
                  className="danger"
                  onClick={() => handleAbort(wo.id)}
                >
                  Abort
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
