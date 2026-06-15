"use client";

import { useState } from "react";
import { X } from "lucide-react";
import IMDBForm from "./IMDBForm";
import type { ConfidenceScores, IMDBFormData, IMDBRecord } from "@/types/imdb";

interface EditModalProps {
  record: IMDBRecord;
  onClose: () => void;
  onSave: (id: number, data: Partial<IMDBFormData>) => Promise<void>;
  isSaving: boolean;
}

export default function EditModal({ record, onClose, onSave, isSaving }: EditModalProps) {
  const [formData, setFormData] = useState<Partial<IMDBFormData>>({
    item_name: record.item_name ?? "",
    barcode: record.barcode ?? "",
    manufacturer: record.manufacturer ?? "",
    brand: record.brand ?? "",
    weight: record.weight ?? "",
    packaging_type: record.packaging_type ?? "",
    country: record.country ?? "",
    variant: record.variant ?? "",
    product_type: record.product_type ?? "",
    fragrance_flavor: record.fragrance_flavor ?? "",
    promotion: record.promotion ?? "",
    addons: record.addons ?? "",
    tagline: record.tagline ?? "",
  });

  const handleChange = (field: keyof IMDBFormData, value: string) => {
    setFormData((prev) => ({ ...prev, [field]: value }));
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-2xl max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100">
          <h2 className="text-lg font-semibold text-gray-900">Edit IMDB Record #{record.id}</h2>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg hover:bg-gray-100 transition-colors"
            aria-label="Close"
          >
            <X className="h-5 w-5 text-gray-500" />
          </button>
        </div>
        <div className="p-6">
          <IMDBForm
            data={formData}
            confidence={(record.confidence_scores as Partial<ConfidenceScores>) || {}}
            onChange={handleChange}
            onSave={() => onSave(record.id, formData)}
            isSaving={isSaving}
          />
        </div>
      </div>
    </div>
  );
}
