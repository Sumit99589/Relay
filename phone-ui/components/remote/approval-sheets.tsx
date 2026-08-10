"use client";

import { motion } from "framer-motion";
import { AlertOctagon, Check, FilePenLine, ShieldAlert, ShieldCheck, X } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import type { PlanDecision, RiskLevel } from "@/lib/protocol";
import type { PendingConfirmation, PendingPlan } from "@/lib/ui-types";
import { MarkdownText } from "./markdown-text";
import { Sheet } from "./sheet";

function risk(value?: string): RiskLevel {
  return value === "high" || value === "medium" ? value : "low";
}

function HoldButton({ onComplete }: { onComplete: () => void }) {
  const [holding, setHolding] = useState(false);
  const [hint, setHint] = useState(false);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const cancel = useCallback(() => {
    if (timer.current) clearTimeout(timer.current);
    timer.current = null;
    if (holding) setHint(true);
    setHolding(false);
  }, [holding]);

  const start = useCallback(() => {
    if (timer.current) return;
    setHint(false);
    setHolding(true);
    timer.current = setTimeout(() => { timer.current = null; setHolding(false); onComplete(); }, 1500);
  }, [onComplete]);

  useEffect(() => () => { if (timer.current) clearTimeout(timer.current); }, []);

  return (
    <div className="hold-wrap">
      <button
        type="button" className="plan-approve high"
        onPointerDown={(event) => { event.currentTarget.setPointerCapture(event.pointerId); start(); }}
        onPointerUp={cancel} onPointerCancel={cancel} onPointerLeave={cancel}
        onKeyDown={(event) => { if (event.key === " " || event.key === "Enter") { event.preventDefault(); start(); } }}
        onKeyUp={(event) => { if (event.key === " " || event.key === "Enter") cancel(); }}
      >
        <motion.i initial={false} animate={{ width: holding ? "100%" : "0%" }} transition={{ duration: holding ? 1.5 : 0.15, ease: "linear" }} />
        <span><ShieldAlert /> Hold to approve</span>
      </button>
      {hint ? <motion.small initial={{ opacity: 0, y: -3 }} animate={{ opacity: 1, y: 0 }}>Keep holding for 1.5 seconds</motion.small> : null}
    </div>
  );
}

export function PlanSheet({ plan, onRespond }: { plan: PendingPlan | null; onRespond: (decision: PlanDecision, feedback?: string) => void }) {
  const [modifying, setModifying] = useState(false);
  const [feedback, setFeedback] = useState("");
  const riskLevel = risk(plan?.risk_level);
  return (
    <Sheet open={Boolean(plan)} onClose={() => onRespond("reject")} eyebrow="Approval required" title="Review the plan" className={`plan-sheet risk-${riskLevel}`}>
      {plan ? <>
        <div className="plan-risk-line"><span className={`risk-mark ${riskLevel}`}>{riskLevel === "low" ? <ShieldCheck /> : <ShieldAlert />}</span><div><strong>{riskLevel[0].toUpperCase() + riskLevel.slice(1)} risk</strong><small>{riskLevel === "high" ? "This plan may make irreversible or external changes." : riskLevel === "medium" ? "Review the affected files or services before continuing." : "Read-only or easily reversible actions."}</small></div></div>
        <div className="plan-summary"><p>{plan.summary || "The agent has proposed the following steps."}</p></div>
        <ol className="plan-steps">{plan.steps.map((step, index) => <li key={`${index}-${step}`}><span>{index + 1}</span><p>{step}</p></li>)}</ol>
        {modifying ? (
          <div className="plan-feedback"><label htmlFor="plan-feedback">What should change?</label><textarea id="plan-feedback" autoFocus rows={3} value={feedback} onChange={(event) => setFeedback(event.target.value)} placeholder="For example: skip the email and only download the file…" /><div><button type="button" className="text-button" onClick={() => setModifying(false)}>Back</button><button type="button" className="primary-button" disabled={!feedback.trim()} onClick={() => onRespond("modify", feedback.trim())}>Send feedback</button></div></div>
        ) : (
          <div className="plan-actions">
            <button type="button" className="plan-reject" onClick={() => onRespond("reject")}><X /> Reject</button>
            <button type="button" className="plan-modify" onClick={() => setModifying(true)}><FilePenLine /> Modify</button>
            {riskLevel === "high" ? <HoldButton onComplete={() => onRespond("approve")} /> : <motion.button whileTap={{ scale: 0.97 }} type="button" className="plan-approve" onClick={() => onRespond("approve")}><Check /> Approve plan</motion.button>}
          </div>
        )}
      </> : null}
    </Sheet>
  );
}

export function ConfirmationSheet({ confirmation, onRespond }: { confirmation: PendingConfirmation | null; onRespond: (confirmed: boolean) => void }) {
  return (
    <Sheet open={Boolean(confirmation)} onClose={() => onRespond(false)} eyebrow="Destructive action" title="Confirm exactly what happens" className="confirm-sheet">
      {confirmation ? <>
        <div className="confirm-warning"><span><AlertOctagon /></span><div><strong>This action needs your permission</strong><p>Check the target carefully. Destructive changes may not be recoverable.</p></div></div>
        <div className="confirm-description"><MarkdownText>{confirmation.message}</MarkdownText></div>
        <div className="confirm-actions"><button type="button" className="secondary-button" onClick={() => onRespond(false)}>Cancel</button><motion.button whileTap={{ scale: 0.97 }} type="button" className="danger-button" onClick={() => onRespond(true)}>Yes, proceed</motion.button></div>
      </> : null}
    </Sheet>
  );
}
