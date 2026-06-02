import type { Metadata } from "next";
import "./globals.css";
import { MainNav } from "@/components/layout/main-nav";
import { AppPreferencesProvider } from "@/components/settings/app-preferences-provider";

export const metadata: Metadata = {
  title: "Anti-FOMO",
  description:
    "A focused workspace for collecting signals, organizing research, and turning useful information into action.",
  metadataBase: new URL("https://github.com/ChrisChen667788/antifomo"),
  openGraph: {
    title: "Anti-FOMO",
    description:
      "A focused workspace for collecting signals, organizing research, and turning useful information into action.",
    images: [
      "https://raw.githubusercontent.com/ChrisChen667788/antifomo/main/public/github-social-preview.png",
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: "Anti-FOMO",
    description:
      "A focused workspace for collecting signals, organizing research, and turning useful information into action.",
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
          <MainNav />
          {children}
        </AppPreferencesProvider>
      </body>
    </html>
  );
}
