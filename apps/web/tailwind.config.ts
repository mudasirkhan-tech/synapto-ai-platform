import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#07080e",
        panel: "#0c0d16",
        card: "#10111b",
        line: "#222436",
        brand: { DEFAULT: "#7c5cff", soft: "#a78bfa", blue: "#4f6bff" },
      },
      fontFamily: {
        sans: ["var(--font-inter)", "system-ui", "sans-serif"],
        hand: ["var(--font-hand)", "cursive"],
      },
      boxShadow: {
        glow: "0 0 24px -4px rgba(124,92,255,.55)",
      },
    },
  },
  plugins: [],
};
export default config;
