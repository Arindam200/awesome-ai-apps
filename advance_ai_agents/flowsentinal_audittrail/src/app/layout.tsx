import type { Metadata } from "next";
import "./globals.css";
import VeltWrapper from "@/components/providers/VeltWrapper";

export const metadata: Metadata = {
  title: "FlowSentinel — AI Workflow Command Center",
  description: "Orchestrate AI workflows with n8n, audit with Velt, and power reasoning with Nebius LLMs",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <VeltWrapper>{children}</VeltWrapper>
      </body>
    </html>
  );
}
