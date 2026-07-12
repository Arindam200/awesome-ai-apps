"use client";

import { useEffect } from "react";
import { setToken } from "@/lib/api";

export default function AuthCallback() {
  useEffect(() => {
    // Token arrives in the URL fragment (#token=...) so it never hits a server log.
    const hash = window.location.hash.replace(/^#/, "");
    const token = new URLSearchParams(hash).get("token");
    if (token) setToken(token);
    // full reload so AuthProvider re-reads the token and fetches /auth/me
    window.location.href = "/";
  }, []);

  return (
    <p className="mt-[20vh] text-center font-mono text-xs uppercase tracking-[0.16em] text-faint">
      Signing you in…
    </p>
  );
}
