import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        lublin: {
          green: "#006643",
          "green-light": "#e8f5ef",
          "green-dark": "#004d33",
          red: "#E30613",
          surface: "#F7F9F8",
          text: "#111412",
          border: "#EFF2F0",
          muted: "#6B7280",
        },
      },
      fontFamily: {
        sans: ["Inter", "Plus Jakarta Sans", "system-ui", "sans-serif"],
      },
      borderRadius: {
        "2xl": "16px",
        "3xl": "24px",
      },
    },
  },
  plugins: [],
};
export default config;
