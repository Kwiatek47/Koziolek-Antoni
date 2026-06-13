import type { Metadata } from "next";
import "./globals.css";

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
    <html lang="pl" suppressHydrationWarning>
      <body className="font-sans">{children}</body>
    </html>
  );
}
