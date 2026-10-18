import type { Metadata, Viewport } from "next";
import { Caveat, Inter, Noto_Naskh_Arabic, Noto_Nastaliq_Urdu, Noto_Sans_Devanagari, Noto_Sans_Hebrew } from "next/font/google";
import "highlight.js/styles/github-dark.css";
import "./globals.css";

const inter = Inter({ subsets: ["latin"], variable: "--font-inter" });
const hand = Caveat({ subsets: ["latin"], variable: "--font-hand" });
// Self-hosted at build time. Loaded lazily by the browser, only when a glyph from that script appears.
const nastaliq = Noto_Nastaliq_Urdu({ subsets: ["arabic"], variable: "--font-nastaliq", display: "swap", preload: false });
const naskh = Noto_Naskh_Arabic({ subsets: ["arabic"], variable: "--font-naskh", display: "swap", preload: false });
const deva = Noto_Sans_Devanagari({ subsets: ["devanagari"], variable: "--font-deva", display: "swap", preload: false });
const hebrew = Noto_Sans_Hebrew({ subsets: ["hebrew"], variable: "--font-hebrew", display: "swap", preload: false });

export const metadata: Metadata = {
  title: "Synapto — Think · Read · Create · Do More",
  description: "Your all-in-one local-first AI assistant.",
};

export const viewport: Viewport = { themeColor: "#07080e", width: "device-width", initialScale: 1 };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${inter.variable} ${hand.variable} ${nastaliq.variable} ${naskh.variable} ${deva.variable} ${hebrew.variable}`}>
      <body className="font-sans antialiased">{children}</body>
    </html>
  );
}
