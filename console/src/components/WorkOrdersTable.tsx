import { useEffect, useState } from "react";
import { listWorkOrders } from "../api";
import type { WorkOrder } from "../types";

const POLL_INTERVAL_MS = 4000;

interface Props {
  selectedWorkOrderId: number | null;
  onSelect: (workOrderId: number) => void;
}

export function WorkOrdersTable({ selectedWorkOrderId, onSelect }: Props) {
  const [workOrders, setWorkOrders] = useState<WorkOrder[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const result = await listWorkOrders();
        if (!cancelled) {
          setWorkOrders(result);
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
  }, []);

  return (
    <section>
      <h2>Work orders</h2>
      {error && <p className="error">Failed to load work orders: {error}</p>}
      <table>
        <thead>
          <tr>
            <th>ID</th>
            <th>Title</th>
            <th>Status</th>
            <th>Priority</th>
            <th>Capabilities</th>
          </tr>
        </thead>
        <tbody>
          {workOrders.map((wo) => (
            <tr
              key={wo.id}
              className={wo.id === selectedWorkOrderId ? "selected" : ""}
              onClick={() => onSelect(wo.id)}
            >
              <td>{wo.id}</td>
              <td>{wo.title}</td>
              <td>
                <span className={`status status-${wo.status}`}>{wo.status}</span>
              </td>
              <td>{wo.priority}</td>
              <td>{wo.required_capabilities.join(", ")}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
