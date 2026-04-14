/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: [
          "Outfit",
          "ui-sans-serif",
          "system-ui",
          "-apple-system",
          "sans-serif",
        ],
        mono: [
          "JetBrains Mono",
          "Fira Code",
          "ui-monospace",
          "SFMono-Regular",
          "monospace",
        ],
      },
      colors: {
        surface: {
          DEFAULT: "#0c0c0e",
          raised: "#141416",
          overlay: "#1a1a1e",
        },
        border: {
          DEFAULT: "#232328",
          hover: "#2e2e35",
          active: "#3a3a42",
        },
        accent: {
          DEFAULT: "#34d399",
          dim: "#2bb380",
          muted: "rgba(52, 211, 153, 0.12)",
          glow: "rgba(52, 211, 153, 0.06)",
        },
      },
      borderRadius: {
        "2xl": "1rem",
        "3xl": "1.25rem",
      },
      boxShadow: {
        glow: "0 0 24px -4px rgba(52, 211, 153, 0.15)",
        "card": "0 1px 3px rgba(0,0,0,0.4), 0 0 0 1px rgba(255,255,255,0.03)",
        "card-hover": "0 4px 16px rgba(0,0,0,0.5), 0 0 0 1px rgba(255,255,255,0.06)",
      },
      animation: {
        "fade-in": "fadeIn 0.3s ease-out",
        "slide-up": "slideUp 0.3s ease-out",
        "pulse-slow": "pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite",
      },
      keyframes: {
        fadeIn: {
          from: { opacity: "0" },
          to: { opacity: "1" },
        },
        slideUp: {
          from: { opacity: "0", transform: "translateY(8px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
      },
    },
  },
  plugins: [],
};
