import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";

const inter = Inter({
  subsets: ["latin", "latin-ext"],
  variable: "--font-inter",
});

export const metadata: Metadata = {
  title: "Asystent Urzędu Miasta Lublin",
  description:
    "Inteligentny asystent AI pomagający mieszkańcom Lublina w sprawach urzędowych",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="pl">
      <body className={`${inter.variable} font-sans`}>{children}</body>
    </html>
  );
}
