import type { Metadata } from "next";
import { Raleway } from "next/font/google";
import "./globals.css";
import AppShell from "@/components/AppShell";

const raleway = Raleway({
  subsets: ["latin"],
  variable: "--font-sans",
  weight: ["400", "600", "700"],
});

export const metadata: Metadata = {
  title: "FutureYou Admin",
  description: "FutureYou internal tools",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className={`${raleway.variable} h-full antialiased`}>
      <body className="h-full flex">
        <AppShell>{children}</AppShell>
      </body>
    </html>
  );
}
