"use client";

import Link from "next/link";
import { Clock3, Monitor, RotateCw, Settings2 } from "lucide-react";
import { motion } from "framer-motion";
import { Brand } from "@/components/brand";
import { ThemeToggle } from "@/components/theme-toggle";
import type { ConnectionPhase } from "@/lib/protocol";

function phaseLabel(phase: ConnectionPhase) {
  return {
    not_configured: "Setup needed", connecting: "Connecting", connected: "Relay online",
    reconnecting: "Reconnecting", auth_failed: "Auth failed", disconnected: "Disconnected",
  }[phase];
}

export function AppHeader({ machineName, phase, pcConnected, onActivity, onSettings, onReconnect }: {
  machineName: string;
  phase: ConnectionPhase;
  pcConnected: boolean | null;
  onActivity: () => void;
  onSettings: () => void;
  onReconnect: () => void;
}) {
  const machineState = pcConnected === true ? "online" : pcConnected === false ? "offline" : "unknown";
  return (
    <header className="app-header">
      <div className="app-header-inner">
        <Link href="/" className="app-brand"><Brand compact /></Link>
        <div className="machine-summary">
          <span className={`machine-icon ${machineState}`}><Monitor /></span>
          <span><strong>{machineName || "My computer"}</strong><small><i className={`status-light ${machineState}`} />{pcConnected === true ? "PC connected" : pcConnected === false ? "PC offline" : phaseLabel(phase)}</small></span>
        </div>
        <div className="header-status desktop-only">
          <span className={`status-light ${phase === "connected" ? "online" : phase === "reconnecting" || phase === "connecting" ? "pending" : "offline"}`} />
          <span><small>Relay</small><strong>{phaseLabel(phase)}</strong></span>
          {(phase === "auth_failed" || phase === "disconnected") ? <button type="button" onClick={onReconnect} aria-label="Reconnect"><RotateCw /></button> : null}
        </div>
        <div className="app-header-actions">
          <ThemeToggle />
          <motion.button whileTap={{ scale: 0.92 }} className="icon-button" type="button" onClick={onActivity} aria-label="Open activity"><Clock3 /></motion.button>
          <motion.button whileTap={{ scale: 0.92 }} className="icon-button" type="button" onClick={onSettings} aria-label="Open settings"><Settings2 /></motion.button>
        </div>
      </div>
    </header>
  );
}
