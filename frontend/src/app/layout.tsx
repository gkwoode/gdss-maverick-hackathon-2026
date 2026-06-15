import type { Metadata } from "next";
import { Inter } from "next/font/google";
import { Toaster } from "react-hot-toast";
import Header from "@/components/Header";
import "./globals.css";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "IMDB Auto-Fill — Item Master Database",
  description:
    "Upload a product image and automatically extract all 10 IMDB attributes using AI vision analysis.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className={`${inter.className} bg-gray-50 min-h-screen`}>
        <Header />
        <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          {children}
        </main>
        <Toaster
          position="top-right"
          toastOptions={{
            style: { borderRadius: "12px", fontSize: "14px" },
          }}
        />
      </body>
    </html>
  );
}
