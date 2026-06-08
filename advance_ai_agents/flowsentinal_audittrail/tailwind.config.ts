import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        bg: "#0c0c10",
        surface: {
          1: "#13131a",
          2: "#18181f",
          3: "#1e1e28",
          4: "#252532",
        },
        border: {
          1: "rgba(255,255,255,0.06)",
          2: "rgba(255,255,255,0.10)",
          3: "rgba(255,255,255,0.14)",
        },
        violet: {
          300: "#c4b5fd",
          400: "#a78bfa",
          500: "#8b5cf6",
          600: "#7c3aed",
          700: "#6d28d9",
          900: "#2e1065",
        },
        emerald: {
          400: "#34d399",
          500: "#10b981",
        },
        amber: {
          400: "#fbbf24",
          500: "#f59e0b",
        },
        rose: {
          400: "#fb7185",
          500: "#f43f5e",
        },
        sky: {
          400: "#38bdf8",
          500: "#0ea5e9",
        },
        ink: {
          primary: "#f1f5f9",
          secondary: "#94a3b8",
          muted: "#475569",
          ghost: "#2d2d3d",
        },
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "monospace"],
      },
      borderRadius: {
        "2xl": "16px",
        "3xl": "20px",
        "4xl": "24px",
      },
      boxShadow: {
        "glow-violet": "0 0 24px rgba(139,92,246,0.15), 0 0 48px rgba(139,92,246,0.06)",
        "glow-emerald": "0 0 16px rgba(16,185,129,0.2)",
        "card": "0 1px 3px rgba(0,0,0,0.4), 0 4px 12px rgba(0,0,0,0.3)",
        "card-hover": "0 4px 16px rgba(0,0,0,0.5), 0 8px 32px rgba(0,0,0,0.3)",
        "float": "0 8px 32px rgba(0,0,0,0.6), 0 2px 8px rgba(0,0,0,0.4)",
      },
      animation: {
        "fade-in": "fadeIn 0.25s ease-out",
        "slide-up": "slideUp 0.3s cubic-bezier(0.16,1,0.3,1)",
        "slide-right": "slideRight 0.25s cubic-bezier(0.16,1,0.3,1)",
        "pulse-dot": "pulseDot 2s ease-in-out infinite",
        "shimmer": "shimmer 2s linear infinite",
        "bounce-dots": "bounceDots 1.2s ease-in-out infinite",
      },
      keyframes: {
        fadeIn: { "0%": { opacity: "0" }, "100%": { opacity: "1" } },
        slideUp: {
          "0%": { opacity: "0", transform: "translateY(12px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        slideRight: {
          "0%": { opacity: "0", transform: "translateX(-8px)" },
          "100%": { opacity: "1", transform: "translateX(0)" },
        },
        pulseDot: {
          "0%, 100%": { opacity: "1", transform: "scale(1)" },
          "50%": { opacity: "0.5", transform: "scale(0.85)" },
        },
        shimmer: {
          "0%": { backgroundPosition: "-200% 0" },
          "100%": { backgroundPosition: "200% 0" },
        },
        bounceDots: {
          "0%, 80%, 100%": { transform: "translateY(0)" },
          "40%": { transform: "translateY(-6px)" },
        },
      },
      backgroundImage: {
        "gradient-violet": "linear-gradient(135deg, #7c3aed, #8b5cf6)",
        "gradient-card": "linear-gradient(180deg, rgba(255,255,255,0.04) 0%, transparent 100%)",
        "gradient-glow": "radial-gradient(ellipse at 50% 0%, rgba(139,92,246,0.12) 0%, transparent 70%)",
      },
    },
  },
  plugins: [],
};

export default config;
