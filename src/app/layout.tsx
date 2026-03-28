import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import { MainNav } from "@/components/layout/main-nav";
import { AppPreferencesProvider } from "@/components/settings/app-preferences-provider";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Anti-fomo Demo",
  description: "A minimal anti-fomo workflow demo built with Next.js and Tailwind.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="zh-CN">
      <body
        className={`${geistSans.variable} ${geistMono.variable} min-h-screen antialiased`}
      >
        <AppPreferencesProvider>
          <div className="af-bg-orb" />
          <MainNav />
          {children}
        </AppPreferencesProvider>
      </body>
    </html>
  );
}
