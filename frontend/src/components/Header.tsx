"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Database, Upload, List } from "lucide-react";
import { cn } from "@/lib/utils";

const NAV_ITEMS = [
  { href: "/", label: "Upload", icon: Upload },
  { href: "/products", label: "Product Catalog", icon: List },
];

export default function Header() {
  const pathname = usePathname();

  return (
    <header className="bg-white border-b border-gray-200 sticky top-0 z-50 shadow-sm">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          {/* Logo */}
          <Link href="/" className="flex items-center gap-2.5">
            <div className="p-1.5 bg-brand-600 rounded-lg">
              <Database className="h-5 w-5 text-white" />
            </div>
            <div>
              <span className="font-bold text-gray-900 text-lg leading-none block">
                IMDB Auto-Fill
              </span>
              <span className="text-xs text-gray-500 leading-none">
                Item Master Database
              </span>
            </div>
          </Link>

          {/* Nav */}
          <nav className="flex items-center gap-1">
            {NAV_ITEMS.map(({ href, label, icon: Icon }) => (
              <Link
                key={href}
                href={href}
                className={cn(
                  "flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors",
                  pathname === href
                    ? "bg-brand-600 text-white"
                    : "text-gray-600 hover:bg-gray-100 hover:text-gray-900"
                )}
              >
                <Icon className="h-4 w-4" />
                {label}
              </Link>
            ))}
          </nav>
        </div>
      </div>
    </header>
  );
}
