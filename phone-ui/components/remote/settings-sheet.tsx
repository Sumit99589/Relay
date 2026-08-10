"use client";

import { Eye, EyeOff, Link2, Monitor, RotateCw, ShieldCheck } from "lucide-react";
import { useState } from "react";
import { useTheme } from "@/components/theme-provider";
import type { ConnectionPhase, RelayConfig } from "@/lib/protocol";
import { Sheet } from "./sheet";

export function SettingsSheet({ open, onClose, config, phase, pcConnected, onSave, onReconnect }: {
  open: boolean; onClose: () => void; config: RelayConfig; phase: ConnectionPhase; pcConnected: boolean | null;
  onSave: (config: RelayConfig) => void; onReconnect: () => void;
}) {
  const [url, setUrl] = useState(config.url);
  const [token, setToken] = useState("");
  const [machineName, setMachineName] = useState(config.machineName);
  const [showToken, setShowToken] = useState(false);
  const { theme, setTheme } = useTheme();

  const tokenHint = config.token ? `Saved securely in this browser · ending ${config.token.slice(-4)}` : "Not configured";

  return (
    <Sheet open={open} onClose={onClose} eyebrow="Connection & preferences" title="Settings" className="settings-sheet">
      <div className="sheet-scroll settings-content">
        <section className="setting-section">
          <div className="setting-section-title"><Link2 /><span><strong>Relay connection</strong><small>The cloud relay your phone and PC connect through.</small></span></div>
          <label className="field"><span>WebSocket URL</span><input value={url} onChange={(event) => setUrl(event.target.value)} placeholder="wss://your-relay.example.com" inputMode="url" autoCapitalize="none" autoCorrect="off" /></label>
          <label className="field"><span>Authentication token</span><div className="password-field"><input type={showToken ? "text" : "password"} value={token} onChange={(event) => setToken(event.target.value)} placeholder={config.token ? "Enter a new token to replace it" : "Your shared secret"} autoComplete="new-password" /><button type="button" onClick={() => setShowToken((value) => !value)} aria-label={showToken ? "Hide new token" : "Show new token"}>{showToken ? <EyeOff /> : <Eye />}</button></div><small>{tokenHint}</small></label>
        </section>
        <section className="setting-section">
          <div className="setting-section-title"><Monitor /><span><strong>This computer</strong><small>A friendly local label; it is never sent to the relay.</small></span></div>
          <label className="field"><span>Computer name</span><input value={machineName} onChange={(event) => setMachineName(event.target.value)} placeholder="My computer" /></label>
          <div className="connection-facts"><div><span>Relay</span><strong className={phase === "connected" ? "good" : ""}>{phase.replaceAll("_", " ")}</strong></div><div><span>PC agent</span><strong className={pcConnected ? "good" : ""}>{pcConnected === null ? "Unknown" : pcConnected ? "Connected" : "Offline"}</strong></div></div>
          <button type="button" className="secondary-button" onClick={onReconnect}><RotateCw /> Reconnect now</button>
        </section>
        <section className="setting-section">
          <div className="setting-section-title"><ShieldCheck /><span><strong>Appearance</strong><small>Light is the default; your choice stays on this device.</small></span></div>
          <div className="theme-options" role="radiogroup" aria-label="Color theme"><button type="button" role="radio" aria-checked={theme === "light"} className={theme === "light" ? "selected" : ""} onClick={() => setTheme("light")}><i className="theme-swatch light" />Light</button><button type="button" role="radio" aria-checked={theme === "dark"} className={theme === "dark" ? "selected" : ""} onClick={() => setTheme("dark")}><i className="theme-swatch dark" />Dark</button></div>
        </section>
      </div>
      <footer className="sheet-footer"><button type="button" className="primary-button" onClick={() => { onSave({ url, token, machineName }); onClose(); }} disabled={!url.trim() || (!token.trim() && !config.token)}>Save & reconnect</button></footer>
    </Sheet>
  );
}
