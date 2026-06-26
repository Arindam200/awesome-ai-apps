import type { Metadata } from "next";
import "./globals.css";
import { ProjectProvider } from "@/components/ProjectProvider";
import Header from "@/components/Header";

export const metadata: Metadata = {
  title: "Maintainer Intelligence Brief",
  description:
    "Ecosystem signals from GitHub, communities, and documents — extracted with Unsiloed.",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body className="min-h-screen">
        <ProjectProvider>
          <Header />
          <main className="mx-auto max-w-5xl px-6 py-10">{children}</main>
        </ProjectProvider>
      </body>
    </html>
  );
}
