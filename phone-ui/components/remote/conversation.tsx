"use client";

import { AnimatePresence, motion } from "framer-motion";
import { CheckCircle2, Lightbulb, TriangleAlert } from "lucide-react";
import { useEffect, useRef } from "react";
import { cleanRelayText, formatTime } from "@/lib/format";
import type { ConversationItem } from "@/lib/ui-types";
import { ExecutionTimeline } from "./execution-timeline";
import { FileCard } from "./file-card";
import { MarkdownText } from "./markdown-text";

const suggestions = [
  "Find the latest PDF in Downloads",
  "Check how much disk space I have",
  "Run the build for my project",
  "Find a file and send it by email",
];

function MessageItem({ item }: { item: ConversationItem }) {
  if (item.kind === "execution") return <ExecutionTimeline title={item.title} steps={item.steps} />;
  if (item.kind === "file") return <FileCard file={item.file} />;
  if (item.kind === "connection") return (
    <motion.div className={`connection-event ${item.tone}`} initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
      <span />{item.text}<time>{formatTime(item.createdAt)}</time>
    </motion.div>
  );
  if (item.kind === "correction") return (
    <motion.div className={`correction ${item.resolved ? "resolved" : item.data.exhausted ? "exhausted" : ""}`} layout initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }}>
      <span className="correction-icon">{item.resolved ? <CheckCircle2 /> : item.data.exhausted ? <TriangleAlert /> : <Lightbulb />}</span>
      <div>
        <strong>{item.resolved ? "Found another way" : item.data.exhausted ? "Needs your attention" : "Trying another approach"}</strong>
        <p>{cleanRelayText(item.resolved?.message || item.data.message)}</p>
        {item.data.attempt ? <small>Attempt {item.data.attempt} of {item.data.max_attempts || 3}</small> : null}
      </div>
    </motion.div>
  );
  if (item.kind === "user") return (
    <motion.div className="message-row user-row" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>
      <div className="user-message"><p>{item.text}</p><time>{formatTime(item.createdAt)}</time></div>
    </motion.div>
  );
  if (item.kind === "error") return (
    <motion.div className="error-message" initial={{ opacity: 0, y: 5 }} animate={{ opacity: 1, y: 0 }}><TriangleAlert /><div><strong>Something interrupted the task</strong><p>{cleanRelayText(item.text)}</p></div></motion.div>
  );
  return (
    <motion.div className="agent-message" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>
      <MarkdownText>{item.text}</MarkdownText><time>{formatTime(item.createdAt)}</time>
    </motion.div>
  );
}

export function Conversation({ items, isWorking, onSuggestion }: { items: ConversationItem[]; isWorking: boolean; onSuggestion: (value: string) => void }) {
  const endRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [items, isWorking]);

  if (!items.length) return (
    <div className="empty-state">
      <div className="empty-orbit" aria-hidden="true"><span /><i /></div>
      <p className="kicker">Ready when you are</p>
      <h1>What should we do on your computer?</h1>
      <p className="empty-copy">Ask naturally. You’ll see each action as it happens and approve anything sensitive.</p>
      <div className="suggestions">
        {suggestions.map((suggestion) => <button type="button" key={suggestion} onClick={() => onSuggestion(suggestion)}>{suggestion}<span>↗</span></button>)}
      </div>
    </div>
  );

  return (
    <div className="conversation-list" aria-live="polite">
      <AnimatePresence initial={false}>{items.map((item) => <MessageItem item={item} key={item.id} />)}</AnimatePresence>
      {isWorking && !items.some((item) => item.kind === "execution" && item.steps.some((step) => step.state === "running")) ? (
        <div className="thinking-line"><span /><span /><span /><em>Your PC is thinking</em></div>
      ) : null}
      <div ref={endRef} />
    </div>
  );
}
