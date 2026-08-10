"use client";

import { AnimatePresence, motion } from "framer-motion";
import { X } from "lucide-react";
import { useEffect } from "react";

export function Sheet({ open, onClose, title, eyebrow, children, className = "" }: {
  open: boolean; onClose: () => void; title: string; eyebrow?: string; children: React.ReactNode; className?: string;
}) {
  useEffect(() => {
    if (!open) return;
    const onKey = (event: KeyboardEvent) => event.key === "Escape" && onClose();
    document.addEventListener("keydown", onKey);
    document.body.classList.add("sheet-open");
    return () => { document.removeEventListener("keydown", onKey); document.body.classList.remove("sheet-open"); };
  }, [onClose, open]);

  return (
    <AnimatePresence>
      {open ? (
        <motion.div className="sheet-layer" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
          <motion.button className="sheet-backdrop" onClick={onClose} aria-label="Close dialog" />
          <motion.section
            role="dialog" aria-modal="true" aria-labelledby="sheet-title"
            className={`sheet ${className}`}
            initial={{ y: "100%", opacity: 0.5 }} animate={{ y: 0, opacity: 1 }} exit={{ y: "100%", opacity: 0.5 }}
            transition={{ type: "spring", damping: 30, stiffness: 340 }}
          >
            <span className="sheet-handle" aria-hidden="true" />
            <header className="sheet-header"><div>{eyebrow ? <p>{eyebrow}</p> : null}<h2 id="sheet-title">{title}</h2></div><button type="button" className="icon-button" onClick={onClose} aria-label="Close"><X /></button></header>
            {children}
          </motion.section>
        </motion.div>
      ) : null}
    </AnimatePresence>
  );
}
