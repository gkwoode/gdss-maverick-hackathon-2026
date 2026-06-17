"use client";

import { Trash2, Edit2, AlertTriangle, CheckCircle2, ChevronLeft, ChevronRight } from "lucide-react";
import { cn, confidenceColor, formatConfidencePct } from "@/lib/utils";
import { mediaUrl } from "@/lib/api";
import type { IMDBRecord } from "@/types/imdb";

interface ProductTableProps {
  records: IMDBRecord[];
  totalCount: number;
  page: number;
  pageSize: number;
  isLoading?: boolean;
  onPageChange: (page: number) => void;
  onDelete: (id: number) => void;
  onEdit: (record: IMDBRecord) => void;
  selectedIds: number[];
  onToggleSelect: (id: number) => void;
  onSelectAll: () => void;
}

const COL_HEADERS = [
  "Image",
  "Item Name",
  "Barcode",
  "Manufacturer",
  "Brand",
  "Weight",
  "Packaging",
  "Country",
  "Variant",
  "Type",
  "Flavor / Fragrance",
  "Promotion",
  "Add-ons",
  "Tagline",
  "Confidence",
  // "Status",
  "Actions",
];

export default function ProductTable({
  records,
  totalCount,
  page,
  pageSize,
  isLoading = false,
  onPageChange,
  onDelete,
  onEdit,
  selectedIds,
  onToggleSelect,
  onSelectAll,
}: ProductTableProps) {
  const totalPages = Math.ceil(totalCount / pageSize);
  const allSelected = records.length > 0 && records.every((r) => selectedIds.includes(r.id));

  return (
    <div className="bg-white rounded-2xl border border-gray-200 shadow-sm overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-gray-50 border-b border-gray-200">
              <th className="px-4 py-3 text-left">
                <input
                  type="checkbox"
                  checked={allSelected}
                  onChange={onSelectAll}
                  className="rounded border-gray-300"
                  aria-label="Select all"
                />
              </th>
              {COL_HEADERS.map((h) => (
                <th
                  key={h}
                  className="px-4 py-3 text-left text-xs font-semibold text-gray-600 uppercase tracking-wider whitespace-nowrap"
                >
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {isLoading && records.length === 0 && (
              Array.from({ length: 5 }).map((_, i) => (
                <tr key={i}>
                  <td className="px-4 py-3"><div className="h-4 w-4 bg-gray-200 rounded animate-pulse" /></td>
                  {COL_HEADERS.map((h) => (
                    <td key={h} className="px-4 py-3">
                      <div className="h-4 bg-gray-100 rounded animate-pulse" style={{ width: `${60 + Math.random() * 40}%` }} />
                    </td>
                  ))}
                </tr>
              ))
            )}
            {!isLoading && records.length === 0 && (
              <tr>
                <td
                  colSpan={COL_HEADERS.length + 1}
                  className="px-4 py-12 text-center text-gray-400"
                >
                  No records found. Upload product images to get started.
                </td>
              </tr>
            )}
            {records.map((rec) => (
              <tr
                key={rec.id}
                className={cn(
                  "hover:bg-gray-50 transition-colors",
                  selectedIds.includes(rec.id) && "bg-brand-50"
                )}
              >
                <td className="px-4 py-3">
                  <input
                    type="checkbox"
                    checked={selectedIds.includes(rec.id)}
                    onChange={() => onToggleSelect(rec.id)}
                    className="rounded border-gray-300"
                    aria-label={`Select ${rec.item_name ?? rec.id}`}
                  />
                </td>
                <td className="px-4 py-3 font-mono text-xs text-gray-600 whitespace-nowrap">
                  {/* Thumbnail */}
                  {rec.image_paths && rec.image_paths.length > 0 ? (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img
                      src={mediaUrl(rec.image_paths[0]) ?? ""}
                      alt="product"
                      className="h-10 w-10 object-cover rounded-lg border border-gray-200"
                    />
                  ) : (
                    <div className="h-10 w-10 rounded-lg border border-gray-200 bg-gray-50 flex items-center justify-center text-gray-300 text-xs">-</div>
                  )}
                </td>
                <td className="px-4 py-3 text-gray-700 max-w-[220px] truncate" title={rec.item_name ?? ""}>
                  {rec.item_name ?? <span className="text-gray-300">—</span>}
                </td>
                <td className="px-4 py-3 font-mono text-xs text-gray-600 whitespace-nowrap">
                  {rec.barcode ?? <span className="text-gray-300">—</span>}
                </td>
                <td className="px-4 py-3 text-gray-600 whitespace-nowrap">
                  {rec.manufacturer ?? <span className="text-gray-300">—</span>}
                </td>
                <td className="px-4 py-3 font-medium text-gray-800 whitespace-nowrap">
                  {rec.brand ?? <span className="text-gray-300">—</span>}
                </td>
                <td className="px-4 py-3 text-gray-600 whitespace-nowrap">
                  {rec.weight ?? <span className="text-gray-300">—</span>}
                </td>
                <td className="px-4 py-3 text-gray-600 whitespace-nowrap">
                  {rec.packaging_type ?? <span className="text-gray-300">—</span>}
                </td>
                <td className="px-4 py-3 text-gray-600 whitespace-nowrap">
                  {rec.country ?? <span className="text-gray-300">—</span>}
                </td>
                <td className="px-4 py-3 text-gray-600 whitespace-nowrap text-xs">
                  {rec.variant || <span className="text-gray-300">—</span>}
                </td>
                <td className="px-4 py-3 text-gray-600 whitespace-nowrap">
                  {rec.product_type ?? <span className="text-gray-300">—</span>}
                </td>
                <td className="px-4 py-3 text-gray-600 whitespace-nowrap text-xs">
                  {rec.fragrance_flavor || <span className="text-gray-300">—</span>}
                </td>
                <td className="px-4 py-3 text-gray-600 whitespace-nowrap text-xs">
                  {rec.promotion || <span className="text-gray-300">—</span>}
                </td>
                <td className="px-4 py-3 text-gray-600 whitespace-nowrap text-xs">
                  {rec.addons || <span className="text-gray-300">—</span>}
                </td>
                <td className="px-4 py-3 text-gray-600 max-w-[180px] truncate text-xs" title={rec.tagline ?? ""}>
                  {rec.tagline || <span className="text-gray-300">—</span>}
                </td>
                <td className="px-4 py-3 whitespace-nowrap">
                  <span
                    className={cn(
                      "text-xs font-semibold px-2 py-0.5 rounded-full",
                      confidenceColor(rec.overall_confidence)
                    )}
                  >
                    {formatConfidencePct(rec.overall_confidence)}
                  </span>
                </td>
                {/* <td className="px-4 py-3">
                  {rec.needs_review ? (
                    <span className="flex items-center gap-1 text-yellow-600 text-xs font-medium">
                      <AlertTriangle className="h-3.5 w-3.5" />
                      Review
                    </span>
                  ) : (
                    <span className="flex items-center gap-1 text-green-600 text-xs font-medium">
                      <CheckCircle2 className="h-3.5 w-3.5" />
                      OK
                    </span>
                  )}
                </td> */}
                <td className="px-4 py-3 whitespace-nowrap">
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => onEdit(rec)}
                      className="p-1.5 rounded-lg hover:bg-brand-50 text-brand-600 transition-colors"
                      aria-label="Edit"
                    >
                      <Edit2 className="h-4 w-4" />
                    </button>
                    <button
                      onClick={() => onDelete(rec.id)}
                      className="p-1.5 rounded-lg hover:bg-red-50 text-red-500 transition-colors"
                      aria-label="Delete"
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between px-4 py-3 border-t border-gray-100 bg-gray-50">
          <p className="text-sm text-gray-500">
            Showing{" "}
            <span className="font-medium">
              {(page - 1) * pageSize + 1}–{Math.min(page * pageSize, totalCount)}
            </span>{" "}
            of <span className="font-medium">{totalCount}</span>
          </p>
          <div className="flex items-center gap-2">
            <button
              onClick={() => onPageChange(page - 1)}
              disabled={page === 1}
              className="p-1.5 rounded-lg border border-gray-300 hover:bg-white disabled:opacity-40 transition-colors"
              aria-label="Previous"
            >
              <ChevronLeft className="h-4 w-4" />
            </button>
            <span className="text-sm text-gray-600">{page} / {totalPages}</span>
            <button
              onClick={() => onPageChange(page + 1)}
              disabled={page === totalPages}
              className="p-1.5 rounded-lg border border-gray-300 hover:bg-white disabled:opacity-40 transition-colors"
              aria-label="Next"
            >
              <ChevronRight className="h-4 w-4" />
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
