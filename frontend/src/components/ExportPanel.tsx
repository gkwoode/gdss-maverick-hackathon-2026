"use client";

import { useState } from "react";
import { FileSpreadsheet, FileText, Loader2 } from "lucide-react";
import { buildExportUrl } from "@/lib/api";
import type { ExportFormat } from "@/types/imdb";

interface ExportPanelProps {
  selectedIds: number[];
  totalCount: number;
}

export default function ExportPanel({ selectedIds, totalCount }: ExportPanelProps) {
  const [loading, setLoading] = useState<ExportFormat | null>(null);

  const handleExport = async (format: ExportFormat) => {
    const url = buildExportUrl(format, selectedIds.length > 0 ? selectedIds : undefined);
    setLoading(format);
    try {
      const response = await fetch(url);
      if (!response.ok) throw new Error(`Export failed: ${response.status}`);
      const blob = await response.blob();
      const objectUrl = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = objectUrl;
      a.download = format === "csv" ? "predictions.csv" : "predictions.xlsx";
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(objectUrl);
    } catch (err) {
      console.error("Export failed", err);
      alert("Export failed. Make sure the backend is running.");
    } finally {
      setLoading(null);
    }
  };

  const label =
    selectedIds.length > 0
      ? `Export ${selectedIds.length} selected`
      : `Export all ${totalCount} records`;

  return (
    <div className="flex items-center gap-2">
      <span className="text-sm text-gray-500">{label}</span>
      <button
        onClick={() => handleExport("csv")}
        disabled={loading !== null}
        className="flex items-center gap-1.5 px-3 py-2 rounded-lg border border-gray-300 bg-white hover:bg-gray-50 text-sm font-medium text-gray-700 transition-colors shadow-sm disabled:opacity-50 disabled:cursor-not-allowed"
      >
        {loading === "csv" ? (
          <Loader2 className="h-4 w-4 animate-spin" />
        ) : (
          <FileText className="h-4 w-4 text-green-600" />
        )}
        CSV
      </button>
      <button
        onClick={() => handleExport("excel")}
        disabled={loading !== null}
        className="flex items-center gap-1.5 px-3 py-2 rounded-lg border border-gray-300 bg-white hover:bg-gray-50 text-sm font-medium text-gray-700 transition-colors shadow-sm disabled:opacity-50 disabled:cursor-not-allowed"
      >
        {loading === "excel" ? (
          <Loader2 className="h-4 w-4 animate-spin" />
        ) : (
          <FileSpreadsheet className="h-4 w-4 text-green-700" />
        )}
        Excel
      </button>
    </div>
  );
}
