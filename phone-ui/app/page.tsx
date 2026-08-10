"use client";

import Link from "next/link";
import { motion, MotionConfig } from "framer-motion";
import {
  ArrowRight, CheckCircle2, Cloud, Code2, FileDown, Files, Fingerprint,
  KeyRound, Mail, Monitor, RefreshCw, Search, ShieldCheck, Smartphone,
} from "lucide-react";
import { Brand } from "@/components/brand";
import { ThemeToggle } from "@/components/theme-toggle";
import { ProductPreview } from "@/components/landing/product-preview";

const capabilities = [
  { icon: Search, title: "Find anything", copy: "Locate files by name, date, type, or even what’s inside them." },
  { icon: FileDown, title: "Bring files with you", copy: "Transfer documents and images directly to your phone." },
  { icon: Code2, title: "Keep work moving", copy: "Check builds, inspect Git, and run approved developer workflows." },
  { icon: Mail, title: "Send from your desk", copy: "Find the right attachment and email it without opening your laptop." },
  { icon: ShieldCheck, title: "You stay in control", copy: "Review plans and explicitly approve risky or destructive actions." },
  { icon: RefreshCw, title: "Adapts when things change", copy: "The agent can diagnose a failed attempt and try a safer route." },
];

export default function LandingPage() {
  return (
    <MotionConfig reducedMotion="user">
      <main className="landing">
        <nav className="landing-nav page-width" aria-label="Main navigation">
          <Link href="/" className="brand-link"><Brand /></Link>
          <div className="landing-nav-actions">
            <ThemeToggle />
            <Link href="/remote" className="nav-open">Open remote <ArrowRight size={15} /></Link>
          </div>
        </nav>

        <section className="hero page-width">
          <div className="hero-copy">
            <motion.p className="kicker" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>Your computer, within reach.</motion.p>
            <motion.h1 initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.06 }}>
              Control your computer <em>from anywhere.</em>
            </motion.h1>
            <motion.p className="hero-lede" initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.14 }}>
              Ask in plain language. Relay finds files, runs workflows, and securely brings the result back to your phone.
            </motion.p>
            <motion.div className="hero-actions" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2 }}>
              <Link href="/remote" className="primary-cta">Control my PC <ArrowRight size={17} /></Link>
              <span className="hero-note"><ShieldCheck size={15} /> Approval built in</span>
            </motion.div>
          </div>
          <motion.div className="hero-product" initial={{ opacity: 0, y: 22 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.12, duration: 0.55 }}>
            <ProductPreview />
          </motion.div>
        </section>

        <section className="relay-path page-width" aria-labelledby="relay-path-title">
          <div className="section-intro">
            <p className="kicker">One private route</p>
            <h2 id="relay-path-title">Your request goes in. Work gets done.</h2>
          </div>
          <div className="path-diagram">
            <div className="path-node"><span><Smartphone /></span><strong>Your phone</strong><small>Natural language</small></div>
            <div className="path-line"><i /><b>Encrypted</b></div>
            <div className="path-node relay-node"><span><Cloud /></span><strong>Intelligent relay</strong><small>Reasoning & guardrails</small></div>
            <div className="path-line"><i /><b>Outbound only</b></div>
            <div className="path-node"><span><Monitor /></span><strong>Your PC</strong><small>Real execution</small></div>
          </div>
        </section>

        <section className="capability-section page-width" aria-labelledby="capabilities-title">
          <div className="section-intro split-intro">
            <div><p className="kicker">Useful by design</p><h2 id="capabilities-title">Small requests. Real outcomes.</h2></div>
            <p>Relay works with the files, tools, and developer workflows already on your computer.</p>
          </div>
          <div className="capability-list">
            {capabilities.map(({ icon: Icon, title, copy }, index) => (
              <motion.article key={title} className="capability" initial={{ opacity: 0, y: 10 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true, margin: "-80px" }} transition={{ delay: index * 0.04 }}>
                <span className="capability-number">0{index + 1}</span>
                <Icon aria-hidden="true" />
                <div><h3>{title}</h3><p>{copy}</p></div>
              </motion.article>
            ))}
          </div>
        </section>

        <section className="trust-section page-width" aria-labelledby="trust-title">
          <div className="trust-copy">
            <p className="kicker">Confidence, not blind trust</p>
            <h2 id="trust-title">You’re the final decision-maker.</h2>
            <p>Relay’s local agent makes an outbound connection—your PC never opens itself to unsolicited internet traffic. Sensitive actions pause for your approval, and every tool call is recorded.</p>
          </div>
          <div className="trust-points">
            <div><Fingerprint /><span><strong>Explicit approval</strong><small>Plans and destructive actions wait for you.</small></span></div>
            <div><KeyRound /><span><strong>Token authenticated</strong><small>Your phone and PC share a private relay secret.</small></span></div>
            <div><Files /><span><strong>Scoped access</strong><small>Choose which folders the local agent can reach.</small></span></div>
            <div><CheckCircle2 /><span><strong>Auditable actions</strong><small>See what ran, when, and whether it succeeded.</small></span></div>
          </div>
        </section>

        <section className="closing-cta page-width">
          <div><p className="kicker">Leave the laptop. Keep the access.</p><h2>Your computer is closer than you think.</h2></div>
          <Link href="/remote" className="primary-cta">Open remote <ArrowRight size={17} /></Link>
        </section>

        <footer className="landing-footer page-width">
          <Brand compact />
          <p>Intelligent remote control, from phone to PC.</p>
          <span>Built for deliberate action.</span>
        </footer>
      </main>
    </MotionConfig>
  );
}
