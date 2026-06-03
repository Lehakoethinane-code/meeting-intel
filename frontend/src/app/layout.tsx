import type { Metadata } from "next";
import { Geist } from "next/font/google";
import { Toaster } from "@/components/ui/sonner";
import "./globals.css";

const geist = Geist({ variable: "--font-geist-sans", subsets: ["latin"] });

export const metadata: Metadata = {
  title: "Meeting Intelligence — TaxConsulting SA",
  description: "Review and approve AI-extracted meeting notes.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${geist.variable} h-full antialiased`}>
      <body className="min-h-full bg-[#F0F2F5]">
        {children}
        <Toaster richColors position="bottom-right" />
      </body>
    </html>
  );
}
