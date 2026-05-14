import type { Metadata } from "next";
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
      <body className="min-h-full flex flex-col bg-zinc-50 dark:bg-zinc-950 text-zinc-900 dark:text-zinc-100">
        <Providers>
          <header className="border-b border-zinc-200 dark:border-zinc-800 bg-white/70 dark:bg-zinc-950/70 backdrop-blur">
            <div className="max-w-7xl mx-auto px-4 h-12 flex items-center justify-between">
              <Link href="/" className="font-semibold tracking-tight">
                Vélib Wizard
              </Link>
              <nav className="flex gap-4 text-sm text-zinc-600 dark:text-zinc-400">
                <Link href="/" className="hover:text-zinc-900 dark:hover:text-zinc-100">Map</Link>
                <Link href="/network" className="hover:text-zinc-900 dark:hover:text-zinc-100">Network</Link>
              </nav>
            </div>
          </header>
          <main className="flex-1 flex flex-col min-h-0">{children}</main>
        </Providers>
      </body>
    </html>
  );
}
