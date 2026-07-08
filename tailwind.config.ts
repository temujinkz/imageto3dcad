import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bone: "#faf9f6",
        card: "#ffffff",
        ink: "#1a1a17",
        muted: "#78716c",
        line: "#ece9e2",
        accent: {
          DEFAULT: "#f2612f",
          soft: "#ff8a4b"
        }
      },
      fontFamily: {
        sans: ["var(--font-geist)", "ui-sans-serif", "system-ui", "-apple-system", "sans-serif"],
        mono: ["var(--font-geist-mono)", "ui-monospace", "monospace"]
      },
      borderRadius: {
        card: "20px"
      },
      boxShadow: {
        card: "0 1px 2px rgba(20,16,10,0.04), 0 12px 34px rgba(20,16,10,0.05)",
        soft: "0 18px 45px rgba(15, 23, 42, 0.08)"
      }
    }
  },
  plugins: []
};

export default config;
