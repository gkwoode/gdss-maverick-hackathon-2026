"use client";

import { cn, confidenceColor, formatConfidencePct } from "@/lib/utils";
import type { ConfidenceScores, IMDBFormData } from "@/types/imdb";

interface FieldConfig {
  key: keyof IMDBFormData;
  label: string;
  colSpan?: boolean;
  type?: "text" | "textarea";
  placeholder?: string;
  hint?: string;
}

const FIELDS: FieldConfig[] = [
  { key: "item_name", label: "Item Name", colSpan: true, placeholder: "e.g. Blue Band Original Margarine 500G Tub" },
  { key: "barcode", label: "Barcode", placeholder: "e.g. 6001255010087" },
  { key: "brand", label: "Brand", placeholder: "e.g. Blue Band" },
  { key: "manufacturer", label: "Manufacturer", placeholder: "e.g. Upfield Foods" },
  { key: "weight", label: "Weight / Unit", placeholder: "e.g. 500G, 1.5 KG, 500 ML" },
  { key: "packaging_type", label: "Packaging Type", placeholder: "e.g. TUB, BOTTLE, CAN" },
  { key: "country", label: "Country", placeholder: "e.g. Ghana, United Kingdom" },
  { key: "product_type", label: "Type", placeholder: "e.g. MARGARINE, MAYONNAISE" },
  { key: "variant", label: "Variant", placeholder: "e.g. ORIGINAL, LOW FAT (leave blank if N/A)" },
  { key: "fragrance_flavor", label: "Fragrance / Flavor", placeholder: "e.g. STRAWBERRY (leave blank if N/A)" },
  {
    key: "promotion",
    label: "Promotion",
    placeholder: "e.g. 50% OFF (leave blank if none)",
  },
  {
    key: "addons",
    label: "Add-ons",
    placeholder: "e.g. SPOON INCLUDED (leave blank if none)",
  },
  {
    key: "tagline",
    label: "Tagline",
    colSpan: true,
    type: "textarea",
    placeholder: "Short promotional tagline on the pack (leave blank if none)",
  },
];

interface IMDBFormProps {
  data: Partial<IMDBFormData>;
  confidence: Partial<ConfidenceScores>;
  onChange: (field: keyof IMDBFormData, value: string) => void;
  onSave: () => void;
  isSaving: boolean;
}

export default function IMDBForm({
  data,
  confidence,
  onChange,
  onSave,
  isSaving,
}: IMDBFormProps) {
  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        onSave();
      }}
      className="space-y-4"
    >
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        {FIELDS.map(({ key, label, type = "text", placeholder, colSpan }) => {
          const score = confidence[key as keyof ConfidenceScores] ?? 0;
          const rawVal = data[key];
          const displayVal = rawVal !== null && rawVal !== undefined ? String(rawVal) : "";
          const hasValue = displayVal.length > 0;

          return (
            <div
              key={key}
              className={cn("flex flex-col gap-1", colSpan && "sm:col-span-2")}
            >
              <div className="flex items-center justify-between">
                <label htmlFor={key} className="text-sm font-medium text-gray-700">
                  {label}
                </label>
                {hasValue && (
                  <span
                    className={cn(
                      "text-xs font-semibold px-2 py-0.5 rounded-full",
                      confidenceColor(score)
                    )}
                  >
                    {formatConfidencePct(score)}
                  </span>
                )}
              </div>

              {type === "textarea" ? (
                <textarea
                  id={key}
                  rows={2}
                  value={displayVal}
                  onChange={(e) => onChange(key, e.target.value)}
                  placeholder={placeholder}
                  className={cn(
                    "rounded-lg border px-3 py-2 text-sm text-gray-800 resize-none transition-colors focus:outline-none focus:ring-2 focus:ring-brand-500",
                    hasValue && score < 0.6 ? "border-red-300 bg-red-50" : "border-gray-300 bg-white"
                  )}
                />
              ) : (
                <input
                  id={key}
                  type="text"
                  value={displayVal}
                  onChange={(e) => onChange(key, e.target.value)}
                  placeholder={placeholder}
                  className={cn(
                    "rounded-lg border px-3 py-2 text-sm text-gray-800 transition-colors focus:outline-none focus:ring-2 focus:ring-brand-500",
                    hasValue && score < 0.6 ? "border-red-300 bg-red-50" : "border-gray-300 bg-white"
                  )}
                />
              )}
            </div>
          );
        })}
      </div>

      <button
        type="submit"
        disabled={isSaving}
        className="w-full py-3 rounded-xl bg-green-600 hover:bg-green-700 disabled:bg-green-400 text-white font-semibold transition-colors shadow-md"
      >
        {isSaving ? "Saving…" : "Save to IMDB"}
      </button>
    </form>
  );
}
