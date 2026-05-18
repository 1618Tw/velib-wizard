import type { Metadata } from "next";
import Image from "next/image";
import Link from "next/link";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import Providers from "./providers";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Vélib Wizard",
  description: "Paris Vélib' stations — live status and 2h forecast risk.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <head>
        <link rel="stylesheet" href="/maplibre-gl.css" />
      </head>
      <body className="min-h-full flex flex-col bg-white text-[var(--color-brand-dark)]">
        <Providers>
          <header className="border-b border-[var(--color-brand-border)] bg-white/85 backdrop-blur">
            <div className="max-w-7xl mx-auto px-4 h-12 flex items-center justify-between">
              <Link href="/" aria-label="The Velib Wizard — home" className="flex items-center">
                <Image
                  src="/logo-mark.png"
                  alt="The Velib Wizard"
                  width={482}
                  height={512}
                  priority
                  className="h-9 w-auto"
                />
              </Link>
              <nav className="flex gap-5 text-sm text-[var(--color-brand-dark)]/70">
                <Link href="/" className="hover:text-[var(--color-brand-dark)] transition-colors">Map</Link>
                <Link href="/network" className="hover:text-[var(--color-brand-dark)] transition-colors">Network</Link>
                <Link href="/status" className="hover:text-[var(--color-brand-dark)] transition-colors">Status</Link>
              </nav>
            </div>
          </header>
          <main className="flex-1 flex flex-col min-h-0">{children}</main>
        </Providers>
      </body>
    </html>
  );
}
