import { Check, Clock3, FileDown, LockKeyhole, MonitorCheck } from "lucide-react";
import type { ConnectionPhase } from "@/lib/protocol";
import type { ConversationItem } from "@/lib/ui-types";
import { ExecutionTimeline } from "./execution-timeline";

export function ContextPanel({ items, phase, pcConnected, machineName, onActivity }: {
  items: ConversationItem[]; phase: ConnectionPhase; pcConnected: boolean | null; machineName: string; onActivity: () => void;
}) {
  const latestExecution = [...items].reverse().find((item) => item.kind === "execution");
  const completedFiles = items.filter((item) => item.kind === "file" && item.file.status === "ready").length;
  const completedSteps = items.reduce((count, item) => count + (item.kind === "execution" ? item.steps.filter((step) => step.state === "complete").length : 0), 0);

  return (
    <aside className="context-panel">
      <div className="context-heading"><div><p className="kicker">Live session</p><h2>On your computer</h2></div><span className={`live-mark ${phase === "connected" && pcConnected ? "active" : ""}`}>Live</span></div>
      {latestExecution?.kind === "execution" ? <ExecutionTimeline compact title={latestExecution.title} steps={latestExecution.steps.slice(-5)} /> : (
        <div className="context-idle"><span><MonitorCheck /></span><strong>{pcConnected ? `${machineName} is ready` : "Waiting for your PC"}</strong><p>Current tool activity will appear here while Relay works.</p></div>
      )}
      <div className="session-summary">
        <div><span><Check /></span><p><strong>{completedSteps}</strong><small>Steps completed</small></p></div>
        <div><span><FileDown /></span><p><strong>{completedFiles}</strong><small>Files received</small></p></div>
      </div>
      <button type="button" className="context-activity" onClick={onActivity}><Clock3 /><span><strong>Open full activity</strong><small>Review every recorded tool call</small></span><b>→</b></button>
      <div className="context-security"><LockKeyhole /><div><strong>Approval stays with you</strong><p>Plans, overwrites, and deletions pause before anything happens.</p></div></div>
    </aside>
  );
}
