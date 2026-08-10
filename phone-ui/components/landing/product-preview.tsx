"use client";

import { AnimatePresence, motion } from "framer-motion";
import { Check, FileText, LoaderCircle, Monitor, Send, Smartphone } from "lucide-react";
import { useEffect, useState } from "react";

const stages = [
  { label: "Located Downloads", done: true },
  { label: "Found Q3-forecast.pdf", done: true },
  { label: "Preparing secure transfer", done: false },
];

export function ProductPreview() {
  const [active, setActive] = useState(0);

  useEffect(() => {
    const timer = window.setInterval(() => setActive((value) => (value + 1) % 3), 2200);
    return () => window.clearInterval(timer);
  }, []);

  return (
    <div className="product-preview" aria-label="Preview of a remote computer task">
      <div className="preview-topbar">
        <span className="preview-machine"><span className="status-light online" /><Monitor size={14} /> Vansh’s MacBook</span>
        <span className="preview-secure">Secure session</span>
      </div>
      <div className="preview-chat">
        <motion.div className="preview-user" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>
          Find the latest forecast PDF and send it to my phone.
        </motion.div>
        <div className="preview-execution">
          <span className="eyebrow">Working on your PC</span>
          {stages.map((stage, index) => {
            const complete = index < active || (active === 2 && index < 2) || stage.done;
            const running = index === 2;
            return (
              <div className="preview-step" key={stage.label}>
                <span className={`preview-step-icon ${complete ? "complete" : ""}`}>
                  {complete ? <Check size={13} /> : running ? <LoaderCircle className="spin" size={13} /> : null}
                </span>
                <span>{stage.label}</span>
              </div>
            );
          })}
        </div>
        <AnimatePresence mode="wait">
          <motion.div
            className="preview-file"
            key={active}
            initial={{ opacity: 0, y: 5 }}
            animate={{ opacity: active === 2 ? 1 : 0.45, y: 0 }}
            exit={{ opacity: 0 }}
          >
            <span className="preview-file-icon"><FileText size={19} /></span>
            <span><strong>Q3-forecast.pdf</strong><small>2.4 MB · Ready to download</small></span>
            <span className="preview-download">Download</span>
          </motion.div>
        </AnimatePresence>
      </div>
      <div className="preview-composer"><span>Ask your PC to do something…</span><Send size={15} /></div>
      <div className="preview-route" aria-hidden="true"><Smartphone size={14} /><span /><Monitor size={14} /></div>
    </div>
  );
}
