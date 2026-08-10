"use client";

import { Check, ChevronDown, LoaderCircle, RefreshCw, RotateCcw, TriangleAlert, X } from "lucide-react";
import { formatAuditTool, formatTime, conciseArgs } from "@/lib/format";
import type { AuditEntry } from "@/lib/protocol";
import { Sheet } from "./sheet";

function statusMeta(status: string) {
  if (status === "success") return { label: "Success", Icon: Check, tone: "success" };
  if (status === "cancelled") return { label: "Cancelled", Icon: X, tone: "cancelled" };
  if (status.startsWith("self_correction")) return { label: "Retried", Icon: RotateCcw, tone: "retry" };
  return { label: "Failed", Icon: TriangleAlert, tone: "error" };
}

export function ActivitySheet({ open, onClose, entries, loading, error, onRefresh }: {
  open: boolean; onClose: () => void; entries: AuditEntry[]; loading: boolean; error: string; onRefresh: () => void;
}) {
  return (
    <Sheet open={open} onClose={onClose} eyebrow="Audit trail" title="Activity" className="activity-sheet">
      <div className="activity-toolbar"><p>Every tool your remote agent has used.</p><button type="button" onClick={onRefresh} disabled={loading}><RefreshCw className={loading ? "spin" : ""} /> Refresh</button></div>
      <div className="sheet-scroll activity-list">
        {loading && !entries.length ? <div className="sheet-empty"><LoaderCircle className="spin" /><p>Loading secure activity…</p></div> : null}
        {error ? <div className="sheet-empty error"><TriangleAlert /><p>{error}</p><button type="button" onClick={onRefresh}>Try again</button></div> : null}
        {!loading && !error && !entries.length ? <div className="sheet-empty"><span className="empty-check"><Check /></span><p>No actions yet</p><small>Your PC’s tool calls will appear here.</small></div> : null}
        {entries.map((entry) => {
          const { label, Icon, tone } = statusMeta(entry.status);
          return (
            <details className="activity-entry" key={entry.id}>
              <summary>
                <span className={`activity-icon ${tone}`}><Icon /></span>
                <span className="activity-copy"><strong>{formatAuditTool(entry.tool)}</strong><small>{conciseArgs(entry.args)}</small></span>
                <span className="activity-meta"><time>{formatTime(entry.timestamp)}</time><b className={tone}>{label}</b></span>
                <ChevronDown className="activity-chevron" />
              </summary>
              <div className="activity-detail"><div><span>Time</span><p>{new Date(entry.timestamp).toLocaleString()}</p></div><div><span>Result</span><p>{entry.result_summary || "No result detail recorded."}</p></div><div><span>Parameters</span><pre>{JSON.stringify(entry.args, null, 2)}</pre></div></div>
            </details>
          );
        })}
      </div>
    </Sheet>
  );
}
