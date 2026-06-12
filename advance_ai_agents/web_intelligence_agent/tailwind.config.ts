import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/app/**/*.{js,ts,jsx,tsx,mdx}", "./src/components/**/*.{js,ts,jsx,tsx,mdx}"],
  theme: {
    extend: {
      colors: {
        canvas: "#f6f3ea",
        panel: "#fffdf8",
        panel2: "#f1efe7",
        line: "rgba(24, 24, 27, 0.12)",
        text: "#1f2933",
        muted: "#64706b",
        dim: "#8a918c",
        mint: "#1fbf75",
        teal: "#16a3a3",
        amber: "#f6b73c",
        red: "#e14d4d",
        blue: "#4263eb"
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "monospace"]
      },
      boxShadow: {
        panel: "0 14px 40px rgba(42, 37, 20, 0.12)",
        focus: "0 0 0 3px rgba(31, 191, 117, 0.18)"
      }
    }
  },
  plugins: []
};

export default config;
