import type { Metadata } from "next";
import { VeltWorkspace } from "@/components/VeltWorkspace";
import "./globals.css";

export const metadata: Metadata = {
  title: "Signals",
  description: "Nebius-powered web intelligence from live Olostep evidence, Mastra workflows, and Velt collaboration."
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <VeltWorkspace>{children}</VeltWorkspace>
      </body>
    </html>
  );
}
