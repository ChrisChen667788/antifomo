import type { Metadata } from "next";
import "./globals.css";
import { MainNav } from "@/components/layout/main-nav";
import { AppPreferencesProvider } from "@/components/settings/app-preferences-provider";

export const metadata: Metadata = {
  title: "Anti-FOMO",
  description:
    "Open-source AI research workspace for signal triage, WeChat-first collection, focus sessions, and action cards.",
  metadataBase: new URL("https://github.com/ChrisChen667788/antifomo"),
  openGraph: {
    title: "Anti-FOMO",
    description:
      "Open-source AI research workspace for signal triage, WeChat-first collection, focus sessions, and action cards.",
    images: [
      "https://raw.githubusercontent.com/ChrisChen667788/antifomo/main/public/github-social-preview.png",
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: "Anti-FOMO",
    description:
      "Open-source AI research workspace for signal triage, WeChat-first collection, focus sessions, and action cards.",
    images: [
      "https://raw.githubusercontent.com/ChrisChen667788/antifomo/main/public/github-social-preview.png",
    ],
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="zh-CN">
      <body className="min-h-screen antialiased">
        <AppPreferencesProvider>
          <div className="af-bg-orb" />
          <MainNav />
          {children}
        </AppPreferencesProvider>
      </body>
    </html>
  );
}
