"use client";

import { ArrowUp, Square, WifiOff } from "lucide-react";
import { motion } from "framer-motion";
import { useEffect, useRef, useState } from "react";
import type { ConnectionPhase } from "@/lib/protocol";

export function Composer({ phase, pcConnected, draft, onDraftChange, onSend, isWorking, onStop }: {
  phase: ConnectionPhase;
  pcConnected: boolean | null;
  draft: string;
  onDraftChange: (value: string) => void;
  onSend: (value: string) => boolean;
  isWorking: boolean;
  onStop: () => boolean;
}) {
  const ref = useRef<HTMLTextAreaElement>(null);
  const [sendError, setSendError] = useState("");
  const relayReady = phase === "connected";

  useEffect(() => {
    if (!ref.current) return;
    ref.current.style.height = "auto";
    ref.current.style.height = `${Math.min(ref.current.scrollHeight, 112)}px`;
  }, [draft]);

  function submit() {
    if (!draft.trim()) return;
    if (!onSend(draft)) {
      setSendError("Connect to your relay before sending.");
      return;
    }
    setSendError("");
    onDraftChange("");
  }

  return (
    <div className="composer-wrap">
      {pcConnected === false && relayReady ? <div className="composer-offline"><WifiOff /> Your PC is offline, but the relay is still reachable.</div> : null}
      <div className={`composer ${relayReady ? "" : "disabled"}`}>
        <textarea
          ref={ref}
          rows={1}
          value={draft}
          onChange={(event) => onDraftChange(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter" && !event.shiftKey) {
              event.preventDefault();
              submit();
            }
          }}
          placeholder={relayReady ? "Ask your PC to do something…" : phase === "not_configured" ? "Configure your relay to begin…" : "Waiting for relay connection…"}
          aria-label="Message your PC"
          disabled={!relayReady}
        />
        {isWorking ? (
          <motion.button whileTap={{ scale: 0.9 }} type="button" className="composer-stop" onClick={onStop} disabled={!relayReady} aria-label="Stop current request" title="Stop current request"><Square fill="currentColor" /></motion.button>
        ) : (
          <motion.button whileTap={{ scale: 0.9 }} type="button" onClick={submit} disabled={!relayReady || !draft.trim()} aria-label="Send request"><ArrowUp /></motion.button>
        )}
      </div>
      <div className="composer-meta"><span>{sendError || "Enter to send · Shift + Enter for a new line"}</span><span className="desktop-only">Actions remain visible as they run</span></div>
    </div>
  );
}
