import type { AuditEvent, MissionStatusReport, WorkOrder } from "./types";

const EAM_URL = import.meta.env.VITE_EAM_URL ?? "http://localhost:8000";
const HTTP_API_URL = import.meta.env.VITE_HTTP_API_URL ?? "http://localhost:8001";

async function get<T>(url: string): Promise<T> {
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`GET ${url} failed: ${response.status}`);
  }
  return response.json() as Promise<T>;
}

async function post<T>(url: string): Promise<T> {
  const response = await fetch(url, { method: "POST" });
  if (!response.ok) {
    throw new Error(`POST ${url} failed: ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export function listWorkOrders(): Promise<WorkOrder[]> {
  return get<WorkOrder[]>(`${EAM_URL}/api/work-orders`);
}

export function getMissionStatus(workOrderId: number): Promise<MissionStatusReport | null> {
  return fetch(`${HTTP_API_URL}/work-orders/${workOrderId}/mission-status`).then((response) => {
    if (response.status === 404) {
      return null;
    }
    if (!response.ok) {
      throw new Error(`mission-status failed: ${response.status}`);
    }
    return response.json() as Promise<MissionStatusReport>;
  });
}

export function listAuditEvents(workOrderId?: number): Promise<AuditEvent[]> {
  const query = workOrderId !== undefined ? `?work_order_id=${workOrderId}` : "";
  return get<AuditEvent[]>(`${HTTP_API_URL}/audit${query}`);
}

export function approveEscalation(workOrderId: number): Promise<WorkOrder> {
  return post<WorkOrder>(`${HTTP_API_URL}/work-orders/${workOrderId}/approve`);
}

export function abortEscalation(workOrderId: number): Promise<WorkOrder> {
  return post<WorkOrder>(`${HTTP_API_URL}/work-orders/${workOrderId}/abort`);
}
