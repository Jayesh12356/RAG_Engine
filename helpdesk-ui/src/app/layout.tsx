import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import Nav from "@/components/nav";

const inter = Inter({ 
  subsets: ["latin"],
  display: "swap",
  variable: "--font-inter",
});

export const metadata: Metadata = {
  title: "IT Helpdesk — RAG Intelligence",
  description: "Intelligent IT Helpdesk powered by RAG, multi-provider LLMs, and real-time document retrieval",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className={`${inter.variable} bg-slate-50 text-slate-900`}>
      <body className={`${inter.className} antialiased`}>
        <Nav />
        <main className="max-w-[1400px] mx-auto px-4 sm:px-6 lg:px-8 min-h-[calc(100vh-var(--nav-height))] pb-20">
          {children}
        </main>
      </body>
    </html>
  );
}
