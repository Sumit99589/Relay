import type { PlanProposalMessage, SelfCorrectionMessage, SelfCorrectionResolvedMessage } from "./protocol";

export type TimelineStep = {
  id: string;
  label: string;
  detail?: string;
  state: "complete" | "running" | "failed" | "cancelled";
};

export type FileResult = {
  name: string;
  size: number;
  mime: string;
  url?: string;
  imageUrl?: string;
  percent: number;
  receivedChunks?: number;
  totalChunks?: number;
  status: "transferring" | "ready" | "error";
  checksum: "pending" | "verified" | "mismatch" | "skipped";
  error?: string;
};

type BaseItem = { id: string; createdAt: Date };

export type ConversationItem =
  | (BaseItem & { kind: "user"; text: string })
  | (BaseItem & { kind: "final"; text: string })
  | (BaseItem & { kind: "error"; text: string })
  | (BaseItem & { kind: "connection"; text: string; tone: "neutral" | "positive" | "warning" })
  | (BaseItem & { kind: "execution"; title: string; steps: TimelineStep[] })
  | (BaseItem & { kind: "file"; file: FileResult })
  | (BaseItem & { kind: "correction"; data: SelfCorrectionMessage; resolved?: SelfCorrectionResolvedMessage });

export type PendingPlan = PlanProposalMessage;
export type PendingConfirmation = { id: string; message: string };
