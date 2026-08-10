import { MonitorUp } from "lucide-react";

export function Brand({ compact = false }: { compact?: boolean }) {
  return (
    <span className="brand" aria-label="Relay home">
      <span className="brand-mark" aria-hidden="true"><MonitorUp size={compact ? 17 : 19} strokeWidth={2.2} /></span>
      <span className="brand-word">Relay</span>
    </span>
  );
}
