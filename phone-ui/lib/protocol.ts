export type RiskLevel = "low" | "medium" | "high";
export type PlanDecision = "approve" | "modify" | "reject";

export type RelayMessage =
  | { type: "response"; message: string }
  | { type: "final"; message: string }
  | { type: "status"; message?: string; pc_connected?: boolean }
  | { type: "confirm"; id: string; message: string }
  | { type: "pong"; message?: string }
  | FileDownloadMessage
  | FileTransferStartMessage
  | FileTransferChunkMessage
  | FileTransferEndMessage
  | FileTransferErrorMessage
  | PlanProposalMessage
  | SelfCorrectionMessage
  | SelfCorrectionResolvedMessage
  | { type: "error"; message?: string };

export type FileDownloadMessage = {
  type: "file_download";
  message?: string;
  name: string;
  size: number;
  mime?: string;
  data: string;
};

export type FileTransferStartMessage = {
  type: "file_transfer_start";
  name: string;
  size: number;
  total_chunks: number;
  mime?: string;
  checksum?: string;
};

export type FileTransferChunkMessage = {
  type: "file_transfer_chunk";
  index: number;
  data: string;
};

export type FileTransferEndMessage = {
  type: "file_transfer_end";
  checksum?: string;
  name?: string;
  size?: number;
};

export type FileTransferErrorMessage = { type: "file_transfer_error"; error?: string };

export type PlanProposalMessage = {
  type: "plan_proposal";
  id: string;
  summary: string;
  steps: string[];
  risk_level?: RiskLevel | string;
};

export type SelfCorrectionMessage = {
  type: "self_correction";
  message: string;
  attempt?: number;
  max_attempts?: number;
  tool?: string;
  error?: string;
  exhausted?: boolean;
};

export type SelfCorrectionResolvedMessage = {
  type: "self_correction_resolved";
  message: string;
  tool?: string;
  attempts?: number;
};

export type PhoneMessage =
  | { type: "chat"; message: string }
  | { type: "cancel" }
  | { type: "confirm_response"; id: string; confirmed: boolean }
  | { type: "plan_response"; id: string; decision: PlanDecision; feedback: string }
  | { type: "ping" };

export type ConnectionPhase =
  | "not_configured"
  | "connecting"
  | "connected"
  | "reconnecting"
  | "auth_failed"
  | "disconnected";

export type RelayConfig = { url: string; token: string; machineName: string };

export type AuditStatus = "success" | "error" | "cancelled" | "self_correction" | "self_correction_exhausted" | string;

export type AuditEntry = {
  id: string;
  timestamp: string;
  tool: string;
  args: Record<string, unknown>;
  result_summary: string;
  status: AuditStatus;
};

export function isRelayMessage(value: unknown): value is RelayMessage {
  return Boolean(value && typeof value === "object" && "type" in value && typeof (value as { type?: unknown }).type === "string");
}
