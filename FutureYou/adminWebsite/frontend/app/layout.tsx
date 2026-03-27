import type { Metadata } from "next";
import { Raleway } from "next/font/google";
import "./globals.css";
import Sidebar from "@/components/Sidebar";
import { Toaster } from "@/components/ui/sonner";

const raleway = Raleway({ subsets: ["latin"], variable: "--font-sans", weight: ["400", "600", "700"] });

export const metadata: Metadata = {
  title: "FutureYou Admin",
  description: "FutureYou internal tools",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className={`${raleway.variable} h-full antialiased`}>
      <body className="min-h-full flex">
        <Sidebar />
        <main className="flex-1 bg-gray-50 overflow-auto">{children}</main>
        <Toaster position="top-right" richColors />
      </body>
    </html>
  );
}
