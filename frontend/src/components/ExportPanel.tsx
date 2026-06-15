"use client";

import { Download, FileSpreadsheet, FileText } from "lucide-react";
import { buildExportUrl } from "@/lib/api";
import type { ExportFormat } from "@/types/imdb";

interface ExportPanelProps {
  selectedIds: number[];
  totalCount: number;
}

export default function ExportPanel({ selectedIds, totalCount }: ExportPanelProps) {
  const handleExport = (format: ExportFormat) => {
    const url = buildExportUrl(format, selectedIds.length > 0 ? selectedIds : undefined);
    window.open(url, "_blank");
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
        className="flex items-center gap-1.5 px-3 py-2 rounded-lg border border-gray-300 bg-white hover:bg-gray-50 text-sm font-medium text-gray-700 transition-colors shadow-sm"
      >
        <FileText className="h-4 w-4 text-green-600" />
        CSV
      </button>
      <button
        onClick={() => handleExport("excel")}
        className="flex items-center gap-1.5 px-3 py-2 rounded-lg border border-gray-300 bg-white hover:bg-gray-50 text-sm font-medium text-gray-700 transition-colors shadow-sm"
      >
        <FileSpreadsheet className="h-4 w-4 text-green-700" />
        Excel
      </button>
    </div>
  );
}
