import { KeyRound, PlugZap, RotateCw, WifiOff } from "lucide-react";
import type { ConnectionPhase } from "@/lib/protocol";

export function ConnectionBanner({ phase, pcConnected, onSettings, onReconnect }: {
  phase: ConnectionPhase; pcConnected: boolean | null; onSettings: () => void; onReconnect: () => void;
}) {
  if (phase === "connected" && pcConnected !== false) return null;
  if (phase === "connected" && pcConnected === false) return (
    <div className="connection-banner pc-offline"><WifiOff /><span><strong>Your PC is offline</strong><small>Start the local agent on your computer to reconnect.</small></span></div>
  );
  if (phase === "not_configured") return (
    <div className="connection-banner"><PlugZap /><span><strong>Connect your relay</strong><small>Add your relay address and private token to start.</small></span><button type="button" onClick={onSettings}>Open settings</button></div>
  );
  if (phase === "auth_failed") return (
    <div className="connection-banner error"><KeyRound /><span><strong>Authentication failed</strong><small>Your saved token was not accepted by the relay.</small></span><button type="button" onClick={onSettings}>Update token</button></div>
  );
  return (
    <div className="connection-banner"><RotateCw className={phase === "connecting" || phase === "reconnecting" ? "spin" : ""} /><span><strong>{phase === "reconnecting" ? "Reconnecting to relay" : "Connecting to relay"}</strong><small>Your conversation will be ready when the connection returns.</small></span>{phase === "disconnected" ? <button type="button" onClick={onReconnect}>Try again</button> : null}</div>
  );
}
