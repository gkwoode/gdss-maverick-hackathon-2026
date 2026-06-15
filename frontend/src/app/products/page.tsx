"use client";

import { useCallback, useEffect, useState } from "react";
import toast from "react-hot-toast";
import { Search, SlidersHorizontal, RefreshCw } from "lucide-react";
import ProductTable from "@/components/ProductTable";
import ExportPanel from "@/components/ExportPanel";
import EditModal from "@/components/EditModal";
import { deleteProduct, fetchProducts, updateProduct } from "@/lib/api";
import type { FilterParams, IMDBFormData, IMDBRecord } from "@/types/imdb";

export default function ProductsPage() {
  const [records, setRecords] = useState<IMDBRecord[]>([]);
  const [totalCount, setTotalCount] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [page, setPage] = useState(1);
  const PAGE_SIZE = 20;

  const [filters, setFilters] = useState<FilterParams>({});
  const [searchInput, setSearchInput] = useState("");

  const [selectedIds, setSelectedIds] = useState<number[]>([]);
  const [editRecord, setEditRecord] = useState<IMDBRecord | null>(null);
  const [isSaving, setIsSaving] = useState(false);

  const load = useCallback(async () => {
    setIsLoading(true);
    try {
      const res = await fetchProducts({ ...filters, page });
      setRecords(res.results);
      setTotalCount(res.count);
    } catch {
      toast.error("Failed to load records.");
    } finally {
      setIsLoading(false);
    }
  }, [filters, page]);

  useEffect(() => {
    load();
  }, [load]);

  const handleSearch = () => {
    setFilters((prev) => ({ ...prev, search: searchInput }));
    setPage(1);
  };

  const handleDelete = async (id: number) => {
    if (!window.confirm("Delete this record? This cannot be undone.")) return;
    try {
      await deleteProduct(id);
      toast.success("Record deleted.");
      load();
    } catch {
      toast.error("Delete failed.");
    }
  };

  const handleSaveEdit = async (id: number, data: Partial<IMDBFormData>) => {
    setIsSaving(true);
    try {
      await updateProduct(id, data);
      toast.success("Record updated.");
      setEditRecord(null);
      load();
    } catch {
      toast.error("Update failed.");
    } finally {
      setIsSaving(false);
    }
  };

  const handleToggleSelect = (id: number) => {
    setSelectedIds((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]
    );
  };

  const handleSelectAll = () => {
    if (records.every((r) => selectedIds.includes(r.id))) {
      setSelectedIds((prev) => prev.filter((id) => !records.map((r) => r.id).includes(id)));
    } else {
      setSelectedIds((prev) => Array.from(new Set([...prev, ...records.map((r) => r.id)])));
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Product Catalog</h1>
          <p className="text-sm text-gray-500 mt-0.5">
            {totalCount} IMDB record{totalCount !== 1 ? "s" : ""}
          </p>
        </div>
        <div className="flex items-center gap-3 flex-wrap">
          <ExportPanel selectedIds={selectedIds} totalCount={totalCount} />
          <button
            onClick={load}
            className="p-2 rounded-lg border border-gray-300 bg-white hover:bg-gray-50 transition-colors shadow-sm"
            aria-label="Refresh"
          >
            <RefreshCw className={`h-4 w-4 text-gray-600 ${isLoading ? "animate-spin" : ""}`} />
          </button>
        </div>
      </div>

      {/* Filters */}
      <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-4 flex flex-col sm:flex-row gap-3">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
          <input
            type="text"
            placeholder="Search by product name, brand, or barcode…"
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleSearch()}
            className="w-full pl-9 pr-4 py-2 rounded-lg border border-gray-300 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
          />
        </div>

        <select
          value={filters.needs_review === undefined ? "" : String(filters.needs_review)}
          onChange={(e) => {
            const val = e.target.value;
            setFilters((prev) => ({
              ...prev,
              needs_review: val === "" ? undefined : val === "true",
            }));
            setPage(1);
          }}
          className="px-3 py-2 rounded-lg border border-gray-300 text-sm text-gray-700 focus:outline-none focus:ring-2 focus:ring-brand-500 bg-white"
        >
          <option value="">All statuses</option>
          <option value="false">OK only</option>
          <option value="true">Needs Review</option>
        </select>

        <button
          onClick={handleSearch}
          className="flex items-center gap-2 px-4 py-2 rounded-lg bg-brand-600 hover:bg-brand-700 text-white text-sm font-medium transition-colors shadow-sm"
        >
          <SlidersHorizontal className="h-4 w-4" />
          Filter
        </button>
      </div>

      {/* Table */}
      <ProductTable
        records={records}
        totalCount={totalCount}
        page={page}
        pageSize={PAGE_SIZE}
        onPageChange={setPage}
        onDelete={handleDelete}
        onEdit={setEditRecord}
        selectedIds={selectedIds}
        onToggleSelect={handleToggleSelect}
        onSelectAll={handleSelectAll}
      />

      {/* Edit modal */}
      {editRecord && (
        <EditModal
          record={editRecord}
          onClose={() => setEditRecord(null)}
          onSave={handleSaveEdit}
          isSaving={isSaving}
        />
      )}
    </div>
  );
}
