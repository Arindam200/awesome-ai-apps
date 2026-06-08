"use client";

import { useEffect, type ReactNode } from "react";
import { VeltProvider, useVeltClient } from "@veltdev/react";

function generateUserId(): string {
  if (typeof window === "undefined") return "anon";
  let id = localStorage.getItem("fs_user_id");
  if (!id) {
    id = `user_${Math.random().toString(36).slice(2, 10)}`;
    localStorage.setItem("fs_user_id", id);
  }
  return id;
}

function VeltIdentifier() {
  const { client } = useVeltClient();

  useEffect(() => {
    if (!client) return;
    const uid = generateUserId();
    client.identify({
      userId: uid,
      name: `Operator ${uid.slice(-4)}`,
      email: `${uid}@flowsentinel.local`,
    });
    client.setDocument("flowsentinel-dashboard", {
      documentName: "FlowSentinel Command Center",
    });
  }, [client]);

  return null;
}

export default function VeltWrapper({ children }: { children: ReactNode }) {
  const apiKey = process.env.NEXT_PUBLIC_VELT_API_KEY;

  if (!apiKey) {
    return <>{children}</>;
  }

  return (
    <VeltProvider apiKey={apiKey}>
      <VeltIdentifier />
      {children}
    </VeltProvider>
  );
}
