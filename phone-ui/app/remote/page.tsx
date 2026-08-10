import type { Metadata } from "next";
import { RemoteApp } from "@/components/remote/remote-app";

export const metadata: Metadata = { title: "Remote control", description: "Securely control your computer from your phone." };

export default function RemotePage() {
  return <RemoteApp />;
}
