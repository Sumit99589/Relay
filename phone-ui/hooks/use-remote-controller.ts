"use client";

import SparkMD5 from "spark-md5";
import { useCallback, useEffect, useRef, useState } from "react";
import { cleanRelayText } from "@/lib/format";
import type {
  AuditEntry, ConnectionPhase, FileDownloadMessage, FileTransferChunkMessage,
  FileTransferEndMessage, FileTransferErrorMessage, FileTransferStartMessage,
  PlanDecision, RelayConfig, RelayMessage,
} from "@/lib/protocol";
import { RelayClient, toHttpBase } from "@/lib/relay-client";
import type { ConversationItem, FileResult, PendingConfirmation, PendingPlan, TimelineStep } from "@/lib/ui-types";

type ActiveTransfer = {
  key: string;
  messageId: string;
  name: string;
  size: number;
  mime: string;
  checksum?: string;
  totalChunks: number;
  receivedCount: number;
  chunks: Array<Uint8Array | undefined>;
};

const DEFAULT_CONFIG: RelayConfig = { url: "", token: "", machineName: "My computer" };

function id(prefix: string) {
  return `${prefix}-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
}

function dataUrlFor(file: FileDownloadMessage) {
  const mime = file.mime || "application/octet-stream";
  return `data:${mime};base64,${file.data}`;
}

function decodeChunk(value: string) {
  const binary = window.atob(value);
  const bytes = new Uint8Array(binary.length);
  for (let index = 0; index < binary.length; index += 1) bytes[index] = binary.charCodeAt(index);
  return bytes;
}

export function useRemoteController() {
  const [phase, setPhase] = useState<ConnectionPhase>("not_configured");
  const [pcConnected, setPcConnected] = useState<boolean | null>(null);
  const [config, setConfig] = useState<RelayConfig>(DEFAULT_CONFIG);
  const [messages, setMessages] = useState<ConversationItem[]>([]);
  const [pendingPlan, setPendingPlan] = useState<PendingPlan | null>(null);
  const [pendingConfirmation, setPendingConfirmation] = useState<PendingConfirmation | null>(null);
  const [isWorking, setIsWorking] = useState(false);
  const [auditEntries, setAuditEntries] = useState<AuditEntry[]>([]);
  const [auditLoading, setAuditLoading] = useState(false);
  const [auditError, setAuditError] = useState("");

  const clientRef = useRef<RelayClient | null>(null);
  const configRef = useRef<RelayConfig>(DEFAULT_CONFIG);
  const currentExecutionRef = useRef<string | null>(null);
  const activeTransferRef = useRef<ActiveTransfer | null>(null);
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const objectUrlsRef = useRef<string[]>([]);
  const stopRequestedRef = useRef(false);

  const addItem = useCallback((item: ConversationItem) => setMessages((items) => [...items, item]), []);

  const finishExecution = useCallback((status: "complete" | "failed" | "cancelled" = "complete") => {
    const executionId = currentExecutionRef.current;
    if (!executionId) return;
    setMessages((items) => items.map((item) => {
      if (item.id !== executionId || item.kind !== "execution") return item;
      return {
        ...item,
        steps: item.steps.map((step) => step.state === "running" ? { ...step, state: status } : step),
      };
    }));
    currentExecutionRef.current = null;
  }, []);

  const cancelRequestTimeout = useCallback(() => {
    if (timeoutRef.current) clearTimeout(timeoutRef.current);
    timeoutRef.current = null;
  }, []);

  const resetRequestTimeout = useCallback(() => {
    cancelRequestTimeout();
    timeoutRef.current = setTimeout(() => {
      finishExecution("failed");
      setIsWorking(false);
      addItem({ id: id("timeout"), kind: "error", text: "This request took too long. Check the connection and try again.", createdAt: new Date() });
    }, 45_000);
  }, [addItem, cancelRequestTimeout, finishExecution]);

  const addExecutionStep = useCallback((rawText: string) => {
    const label = cleanRelayText(rawText) || "Working on your request";
    const step: TimelineStep = { id: id("step"), label, state: "running" };
    const executionId = currentExecutionRef.current;

    if (!executionId) {
      const nextId = id("execution");
      currentExecutionRef.current = nextId;
      addItem({ id: nextId, kind: "execution", title: "Working on your computer", steps: [step], createdAt: new Date() });
      return;
    }

    setMessages((items) => items.map((item) => {
      if (item.id !== executionId || item.kind !== "execution") return item;
      const steps = item.steps.map((existing) => existing.state === "running" ? { ...existing, state: "complete" as const } : existing);
      return { ...item, steps: [...steps, step] };
    }));
  }, [addItem]);

  const updateFile = useCallback((messageId: string, updater: (file: FileResult) => FileResult) => {
    setMessages((items) => items.map((item) => item.id === messageId && item.kind === "file" ? { ...item, file: updater(item.file) } : item));
  }, []);

  const startTransfer = useCallback((data: FileTransferStartMessage) => {
    const key = `${data.name}:${data.size}:${data.total_chunks}`;
    const active = activeTransferRef.current;
    if (active?.key === key) return; // relay and PC agent can both emit the same start event

    if (active) {
      updateFile(active.messageId, (file) => ({ ...file, status: "error", error: "A new transfer started before this one completed." }));
    }

    const messageId = id("file");
    activeTransferRef.current = {
      key,
      messageId,
      name: data.name,
      size: data.size,
      mime: data.mime || "application/octet-stream",
      checksum: data.checksum,
      totalChunks: data.total_chunks,
      receivedCount: 0,
      chunks: new Array(data.total_chunks),
    };
    addItem({
      id: messageId,
      kind: "file",
      createdAt: new Date(),
      file: {
        name: data.name, size: data.size, mime: data.mime || "application/octet-stream",
        percent: 0, receivedChunks: 0, totalChunks: data.total_chunks,
        status: "transferring", checksum: data.checksum ? "pending" : "skipped",
      },
    });
  }, [addItem, updateFile]);

  const receiveChunk = useCallback((data: FileTransferChunkMessage) => {
    const transfer = activeTransferRef.current;
    if (!transfer || data.index < 0 || data.index >= transfer.totalChunks) return;
    if (!transfer.chunks[data.index]) {
      transfer.chunks[data.index] = decodeChunk(data.data);
      transfer.receivedCount += 1;
    }
    const percent = Math.round((transfer.receivedCount / transfer.totalChunks) * 100);
    updateFile(transfer.messageId, (file) => ({ ...file, percent, receivedChunks: transfer.receivedCount }));
  }, [updateFile]);

  const endTransfer = useCallback((data: FileTransferEndMessage) => {
    const transfer = activeTransferRef.current;
    if (!transfer) return;
    activeTransferRef.current = null;

    try {
      const missing = transfer.chunks.findIndex((chunk) => !chunk);
      if (missing >= 0) throw new Error(`Chunk ${missing + 1} did not arrive.`);
      const chunks = transfer.chunks as Uint8Array[];
      const buffers = chunks.map((chunk) => chunk.buffer.slice(chunk.byteOffset, chunk.byteOffset + chunk.byteLength) as ArrayBuffer);
      const blob = new Blob(buffers, { type: transfer.mime });
      const url = URL.createObjectURL(blob);
      objectUrlsRef.current.push(url);

      const expected = data.checksum || transfer.checksum;
      let checksum: FileResult["checksum"] = "skipped";
      if (expected) {
        const spark = new SparkMD5.ArrayBuffer();
        chunks.forEach((chunk) => spark.append(chunk.buffer as ArrayBuffer));
        checksum = spark.end() === expected ? "verified" : "mismatch";
      }
      updateFile(transfer.messageId, (file) => ({
        ...file, status: "ready", percent: 100, receivedChunks: transfer.totalChunks,
        url, imageUrl: transfer.mime.startsWith("image/") ? url : undefined, checksum,
      }));
    } catch (error) {
      updateFile(transfer.messageId, (file) => ({ ...file, status: "error", error: error instanceof Error ? error.message : "Could not assemble this file." }));
    }
  }, [updateFile]);

  const failTransfer = useCallback((data: FileTransferErrorMessage) => {
    const transfer = activeTransferRef.current;
    if (transfer) {
      updateFile(transfer.messageId, (file) => ({ ...file, status: "error", error: data.error || "The transfer failed." }));
      activeTransferRef.current = null;
    } else {
      addItem({ id: id("file-error"), kind: "error", text: data.error || "The file transfer failed.", createdAt: new Date() });
    }
  }, [addItem, updateFile]);

  const handleMessage = useCallback((data: RelayMessage) => {
    switch (data.type) {
      case "response":
        if (stopRequestedRef.current) break;
        setIsWorking(true);
        addExecutionStep(data.message);
        resetRequestTimeout();
        break;
      case "final":
        stopRequestedRef.current = false;
        cancelRequestTimeout();
        finishExecution();
        setIsWorking(false);
        addItem({ id: id("final"), kind: "final", text: data.message, createdAt: new Date() });
        break;
      case "status":
        if (typeof data.pc_connected === "boolean") setPcConnected(data.pc_connected);
        if (data.message) addItem({
          id: id("connection"), kind: "connection", text: cleanRelayText(data.message), createdAt: new Date(),
          tone: data.pc_connected === true ? "positive" : data.pc_connected === false ? "warning" : "neutral",
        });
        break;
      case "confirm":
        cancelRequestTimeout();
        setPendingConfirmation({ id: data.id, message: data.message });
        setIsWorking(false);
        break;
      case "file_download": {
        const url = dataUrlFor(data);
        addItem({ id: id("file"), kind: "file", createdAt: new Date(), file: {
          name: data.name, size: data.size, mime: data.mime || "application/octet-stream",
          url, imageUrl: (data.mime || "").startsWith("image/") ? url : undefined,
          percent: 100, status: "ready", checksum: "skipped",
        } });
        break;
      }
      case "file_transfer_start":
        startTransfer(data);
        break;
      case "file_transfer_chunk":
        receiveChunk(data);
        break;
      case "file_transfer_end":
        endTransfer(data);
        break;
      case "file_transfer_error":
        failTransfer(data);
        break;
      case "plan_proposal":
        cancelRequestTimeout();
        finishExecution();
        setPendingPlan(data);
        setIsWorking(false);
        break;
      case "self_correction":
        setIsWorking(!data.exhausted);
        resetRequestTimeout();
        addItem({ id: id("correction"), kind: "correction", data, createdAt: new Date() });
        break;
      case "self_correction_resolved":
        setMessages((items) => {
          const index = items.findLastIndex((item) => item.kind === "correction" && !item.resolved);
          if (index < 0) return [...items, { id: id("correction"), kind: "connection", text: cleanRelayText(data.message), tone: "positive", createdAt: new Date() }];
          return items.map((item, itemIndex) => itemIndex === index && item.kind === "correction" ? { ...item, resolved: data } : item);
        });
        break;
      case "error":
        cancelRequestTimeout();
        finishExecution("failed");
        setIsWorking(false);
        addItem({ id: id("error"), kind: "error", text: data.message || "The relay reported an unknown error.", createdAt: new Date() });
        break;
      case "pong":
        break;
    }
  }, [addExecutionStep, addItem, cancelRequestTimeout, endTransfer, failTransfer, finishExecution, receiveChunk, resetRequestTimeout, startTransfer]);

  useEffect(() => {
    const objectUrls = objectUrlsRef.current;
    const saved: RelayConfig = {
      url: window.localStorage.getItem("relay_url") || "",
      token: window.localStorage.getItem("auth_token") || "",
      machineName: window.localStorage.getItem("machine_name") || "My computer",
    };
    setConfig(saved);
    configRef.current = saved;

    const client = new RelayClient({
      onMessage: handleMessage,
      onPhaseChange: (nextPhase) => {
        setPhase(nextPhase);
        if (nextPhase === "auth_failed") {
          setIsWorking(false);
          addItem({ id: id("auth"), kind: "error", text: "Authentication failed. Update your relay token in Settings.", createdAt: new Date() });
        }
      },
      onProtocolError: (message) => addItem({ id: id("protocol"), kind: "error", text: message, createdAt: new Date() }),
    });
    clientRef.current = client;
    client.connect(saved);

    return () => {
      client.disconnect();
      cancelRequestTimeout();
      objectUrls.forEach((url) => URL.revokeObjectURL(url));
    };
  }, [addItem, cancelRequestTimeout, handleMessage]);

  const sendChat = useCallback((text: string) => {
    const message = text.trim();
    if (!message || phase !== "connected") return false;
    if (!clientRef.current?.send({ type: "chat", message })) return false;
    stopRequestedRef.current = false;
    addItem({ id: id("user"), kind: "user", text: message, createdAt: new Date() });
    setIsWorking(true);
    resetRequestTimeout();
    return true;
  }, [addItem, phase, resetRequestTimeout]);

  const cancelCurrentRequest = useCallback(() => {
    if (!isWorking || !clientRef.current?.send({ type: "cancel" })) return false;
    stopRequestedRef.current = true;
    cancelRequestTimeout();
    finishExecution("cancelled");
    setPendingPlan(null);
    setPendingConfirmation(null);
    setIsWorking(false);
    addItem({ id: id("stopped"), kind: "connection", text: "Stopping the current task…", tone: "neutral", createdAt: new Date() });
    return true;
  }, [addItem, cancelRequestTimeout, finishExecution, isWorking]);

  const respondToConfirmation = useCallback((confirmed: boolean) => {
    if (!pendingConfirmation) return;
    clientRef.current?.send({ type: "confirm_response", id: pendingConfirmation.id, confirmed });
    addItem({
      id: id("confirm-result"), kind: "connection", createdAt: new Date(),
      text: confirmed ? "Action approved. Continuing on your computer." : "Action cancelled.",
      tone: confirmed ? "positive" : "neutral",
    });
    setPendingConfirmation(null);
    setIsWorking(confirmed);
    if (confirmed) resetRequestTimeout();
  }, [addItem, pendingConfirmation, resetRequestTimeout]);

  const respondToPlan = useCallback((decision: PlanDecision, feedback = "") => {
    if (!pendingPlan) return;
    clientRef.current?.send({ type: "plan_response", id: pendingPlan.id, decision, feedback });
    addItem({
      id: id("plan-result"), kind: "connection", createdAt: new Date(),
      text: decision === "approve" ? "Plan approved. Execution is starting." : decision === "modify" ? `Plan feedback sent: ${feedback}` : "Plan rejected. No action was taken.",
      tone: decision === "approve" ? "positive" : "neutral",
    });
    setPendingPlan(null);
    setIsWorking(decision !== "reject");
    if (decision !== "reject") resetRequestTimeout();
  }, [addItem, pendingPlan, resetRequestTimeout]);

  const saveConfig = useCallback((next: RelayConfig) => {
    const complete = { ...next, token: next.token || configRef.current.token };
    window.localStorage.setItem("relay_url", complete.url.trim());
    window.localStorage.setItem("auth_token", complete.token.trim());
    window.localStorage.setItem("machine_name", complete.machineName.trim() || "My computer");
    configRef.current = complete;
    setConfig(complete);
    setPcConnected(null);
    clientRef.current?.connect(complete);
  }, []);

  const reconnect = useCallback(() => {
    setPcConnected(null);
    clientRef.current?.connect(configRef.current);
  }, []);

  const fetchAuditLog = useCallback(async () => {
    const current = configRef.current;
    if (!current.url || !current.token) {
      setAuditError("Configure your relay before viewing activity.");
      return;
    }
    setAuditLoading(true);
    setAuditError("");
    try {
      const response = await fetch(`${toHttpBase(current.url)}/audit-log?token=${encodeURIComponent(current.token)}`);
      if (!response.ok) throw new Error(response.status === 401 ? "Authentication failed." : `Relay returned ${response.status}.`);
      const body = await response.json() as { log?: AuditEntry[] };
      setAuditEntries([...(body.log || [])].reverse());
    } catch (error) {
      setAuditError(error instanceof Error ? error.message : "Could not load activity.");
    } finally {
      setAuditLoading(false);
    }
  }, []);

  return {
    phase, pcConnected, config, messages, pendingPlan, pendingConfirmation, isWorking,
    auditEntries, auditLoading, auditError, sendChat, cancelCurrentRequest, respondToConfirmation, respondToPlan,
    saveConfig, reconnect, fetchAuditLog,
  };
}
