"use client";

import { MotionConfig } from "framer-motion";
import { useCallback, useState } from "react";
import { useRemoteController } from "@/hooks/use-remote-controller";
import { ActivitySheet } from "./activity-sheet";
import { AppHeader } from "./app-header";
import { ConfirmationSheet, PlanSheet } from "./approval-sheets";
import { Composer } from "./composer";
import { ConnectionBanner } from "./connection-banner";
import { ContextPanel } from "./context-panel";
import { Conversation } from "./conversation";
import { SettingsSheet } from "./settings-sheet";

export function RemoteApp() {
  const controller = useRemoteController();
  const [draft, setDraft] = useState("");
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [activityOpen, setActivityOpen] = useState(false);

  const openActivity = useCallback(() => {
    setActivityOpen(true);
    void controller.fetchAuditLog();
  }, [controller]);

  return (
    <MotionConfig reducedMotion="user">
      <main className="remote-app">
        <AppHeader
          machineName={controller.config.machineName}
          phase={controller.phase}
          pcConnected={controller.pcConnected}
          onActivity={openActivity}
          onSettings={() => setSettingsOpen(true)}
          onReconnect={controller.reconnect}
        />
        <div className="remote-layout">
          <section className="chat-shell" aria-label="Remote computer conversation">
            <ConnectionBanner phase={controller.phase} pcConnected={controller.pcConnected} onSettings={() => setSettingsOpen(true)} onReconnect={controller.reconnect} />
            <div className="conversation-scroll">
              <Conversation items={controller.messages} isWorking={controller.isWorking} onSuggestion={setDraft} />
            </div>
            <Composer phase={controller.phase} pcConnected={controller.pcConnected} draft={draft} onDraftChange={setDraft} onSend={controller.sendChat} isWorking={controller.isWorking} onStop={controller.cancelCurrentRequest} />
          </section>
          <ContextPanel items={controller.messages} phase={controller.phase} pcConnected={controller.pcConnected} machineName={controller.config.machineName} onActivity={openActivity} />
        </div>

        <SettingsSheet key={settingsOpen ? `open-${controller.config.url}-${controller.config.machineName}` : "closed"} open={settingsOpen} onClose={() => setSettingsOpen(false)} config={controller.config} phase={controller.phase} pcConnected={controller.pcConnected} onSave={controller.saveConfig} onReconnect={controller.reconnect} />
        <ActivitySheet open={activityOpen} onClose={() => setActivityOpen(false)} entries={controller.auditEntries} loading={controller.auditLoading} error={controller.auditError} onRefresh={controller.fetchAuditLog} />
        <PlanSheet key={controller.pendingPlan?.id || "no-plan"} plan={controller.pendingPlan} onRespond={controller.respondToPlan} />
        <ConfirmationSheet confirmation={controller.pendingConfirmation} onRespond={controller.respondToConfirmation} />
      </main>
    </MotionConfig>
  );
}
