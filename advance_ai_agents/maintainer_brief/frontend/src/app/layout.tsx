import type { Metadata } from "next";
import { Inter, Inter_Tight, Geist_Mono } from "next/font/google";
import "./globals.css";
import { AuthProvider } from "@/components/AuthProvider";
import { ProjectProvider } from "@/components/ProjectProvider";
import Header from "@/components/Header";

const inter = Inter({ subsets: ["latin"], variable: "--font-inter", display: "swap" });
const interTight = Inter_Tight({
  subsets: ["latin"],
  variable: "--font-inter-tight",
  weight: ["500", "600", "700"],
  display: "swap",
});
const geistMono = Geist_Mono({ subsets: ["latin"], variable: "--font-geist-mono", display: "swap" });

export const metadata: Metadata = {
  title: "Maintainer Intelligence Brief",
  description:
    "Ecosystem signals from GitHub, communities, and documents — extracted with Unsiloed.",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className={`${inter.variable} ${interTight.variable} ${geistMono.variable}`}>
      <body className="min-h-screen">
        <AuthProvider>
          <ProjectProvider>
            <Header />
            <main className="mx-auto max-w-5xl px-6 py-10">{children}</main>
          </ProjectProvider>
        </AuthProvider>
      </body>
    </html>
  );
}
