import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import Link from "next/link";
import "./globals.css";

const geistSans = Geist({ variable: "--font-geist-sans", subsets: ["latin"] });
const geistMono = Geist_Mono({ variable: "--font-geist-mono", subsets: ["latin"] });

export const metadata: Metadata = {
  title: "civic-evals — reliability dashboard",
  description:
    "Measuring how reliably LLMs answer civic information questions across providers, personas, and task types.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}>
      <body className="min-h-full flex flex-col text-zinc-900 dark:text-zinc-100">
        <SiteNav />
        {children}
      </body>
    </html>
  );
}

function SiteNav() {
  return (
    <header className="glass-nav sticky top-0 z-30">
      <div className="mx-auto max-w-6xl px-6 h-14 flex items-center justify-between">
        <Link href="/" className="group flex items-center gap-2.5">
          <span className="ombre-fill grid h-7 w-7 place-items-center rounded-lg text-[13px] font-bold shadow-sm shadow-blue-500/30">
            ce
          </span>
          <span className="font-semibold tracking-tight">
            <span className="ombre-text">civic</span>
            <span className="text-zinc-400 dark:text-zinc-500">-evals</span>
          </span>
        </Link>
        <nav className="flex items-center gap-5 text-sm text-zinc-500 dark:text-zinc-400">
          <Link
            href="/"
            className="hidden sm:inline hover:text-blue-700 dark:hover:text-blue-300 transition-colors"
          >
            Dashboard
          </Link>
          <a
            href="https://inspect.aisi.org.uk/"
            className="hidden sm:inline hover:text-blue-700 dark:hover:text-blue-300 transition-colors"
          >
            inspect-ai
          </a>
          <a
            href="https://github.com/justinshenk/civic-evals"
            className="ombre-fill rounded-full px-3.5 py-1.5 text-xs font-medium text-white shadow-sm shadow-blue-500/30 transition-transform hover:-translate-y-0.5"
          >
            GitHub →
          </a>
        </nav>
      </div>
    </header>
  );
}
