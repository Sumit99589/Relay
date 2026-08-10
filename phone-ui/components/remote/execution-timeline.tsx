"use client";

import { AnimatePresence, motion } from "framer-motion";
import { Check, Circle, LoaderCircle, Minus, X } from "lucide-react";
import type { TimelineStep } from "@/lib/ui-types";

export function ExecutionTimeline({ title, steps, compact = false }: { title: string; steps: TimelineStep[]; compact?: boolean }) {
  return (
    <motion.div className={`execution ${compact ? "execution-compact" : ""}`} layout initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>
      <div className="execution-heading"><span className="execution-pulse" />{title}</div>
      <div className="execution-steps">
        <AnimatePresence initial={false}>
          {steps.map((step) => (
            <motion.div className={`execution-step ${step.state}`} key={step.id} initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: "auto" }}>
              <span className="execution-icon" aria-label={step.state}>
                {step.state === "complete" ? <Check /> : step.state === "failed" ? <X /> : step.state === "cancelled" ? <Minus /> : step.state === "running" ? <LoaderCircle className="spin" /> : <Circle />}
              </span>
              <span>{step.label}</span>
            </motion.div>
          ))}
        </AnimatePresence>
      </div>
    </motion.div>
  );
}
