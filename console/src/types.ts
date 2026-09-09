export type WorkOrderStatus =
  | "Draft"
  | "Released"
  | "Dispatched"
  | "InProgress"
  | "AwaitingHuman"
  | "Completed"
  | "Failed"
  | "Cancelled";

export interface WorkOrder {
  id: number;
  title: string;
  description: string;
  asset_id: number;
  required_capabilities: string[];
  priority: string;
  status: WorkOrderStatus;
  created_at: string;
  updated_at: string;
}

export type MissionStatusValue =
  | "pending"
  | "dispatched"
  | "in_progress"
  | "paused"
  | "completed"
  | "failed"
  | "aborted";

export interface MissionStatusReport {
  mission_id: string;
  status: MissionStatusValue;
  detail: string;
}

export interface AuditEvent {
  id: string;
  timestamp: string;
  actor: string;
  action: string;
  work_order_id: number | null;
  mission_id: string | null;
  detail: Record<string, unknown>;
}
