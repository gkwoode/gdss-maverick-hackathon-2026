"use client";

import { AlertTriangle } from "lucide-react";
import type { DuplicateCandidate } from "@/types/imdb";

interface DuplicateAlertProps {
  duplicates: DuplicateCandidate[];
}

export default function DuplicateAlert({ duplicates }: DuplicateAlertProps) {
  if (duplicates.length === 0) return null;

  return (
    <div className="rounded-xl border border-yellow-300 bg-yellow-50 p-4">
      <div className="flex items-start gap-3">
        <AlertTriangle className="h-5 w-5 text-yellow-600 mt-0.5 shrink-0" />
        <div className="flex-1">
          <p className="text-sm font-semibold text-yellow-800">
            {duplicates.length} potential duplicate{duplicates.length > 1 ? "s" : ""} found
          </p>
          <p className="text-xs text-yellow-700 mt-0.5">
            Review before saving to avoid duplicate entries in the IMDB.
          </p>
          <ul className="mt-2 space-y-1">
            {duplicates.map((d) => (
              <li key={d.id} className="text-xs text-yellow-800 bg-yellow-100 rounded-lg px-3 py-1.5">
                <span className="font-medium">#{d.id}</span> — {d.brand} {d.item_name}{" "}
                {d.weight ? `(${d.weight})` : ""}
                {d.barcode ? (
                  <span className="ml-1 font-mono text-yellow-600">[{d.barcode}]</span>
                ) : null}
              </li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  );
}

