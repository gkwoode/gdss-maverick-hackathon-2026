"use client";

import { useState } from "react";
import toast from "react-hot-toast";
import { CheckCircle2, Sparkles, Info, AlertCircle } from "lucide-react";
import ImageUpload from "@/components/ImageUpload";
import IMDBForm from "@/components/IMDBForm";
import DuplicateAlert from "@/components/DuplicateAlert";
import { analyzeImages, createProduct } from "@/lib/api";
import type {
  ConfidenceScores,
  DuplicateCandidate,
  IMDBFormData,
} from "@/types/imdb";
import axios from "axios";

const EMPTY_FORM: Partial<IMDBFormData> = {
  item_name: "",
  barcode: "",
  manufacturer: "",
  brand: "",
  weight: "",
  packaging_type: "",
  country: "",
  variant: "",
  product_type: "",
  fragrance_flavor: "",
  promotion: "",
  addons: "",
  tagline: "",
  image_paths: [],
  confidence_scores: {},
};

export default function UploadPage() {
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [hasAnalyzed, setHasAnalyzed] = useState(false);
  const [analyzeError, setAnalyzeError] = useState<string | null>(null);
  const [formData, setFormData] = useState<Partial<IMDBFormData>>(EMPTY_FORM);
  const [confidence, setConfidence] = useState<Partial<ConfidenceScores>>({});
  const [duplicates, setDuplicates] = useState<DuplicateCandidate[]>([]);
  const [method, setMethod] = useState<string | null>(null);
  const [imagesProcessed, setImagesProcessed] = useState(0);
  const [saved, setSaved] = useState(false);

  const handleAnalyze = async (files: File[]) => {
    setIsAnalyzing(true);
    setSaved(false);
    setAnalyzeError(null);
    try {
      const result = await analyzeImages(files);
      const { confidence: conf, method: m, potential_duplicates: dups, extracted, images_processed } = result;
      setFormData({ ...EMPTY_FORM, ...extracted });
      setConfidence(conf);
      setDuplicates(dups);
      setMethod(m);
      setImagesProcessed(images_processed);
      setHasAnalyzed(true);
      toast.success(
        `Extracted from ${images_processed} image${images_processed > 1 ? "s" : ""}! Review and save.`
      );
    } catch (err: unknown) {
      let msg = "Image analysis failed. Make sure the backend is running.";
      if (axios.isAxiosError(err)) {
        const detail = err.response?.data?.error || err.response?.data?.detail || err.message;
        msg = `Analysis failed: ${detail}`;
      }
      setAnalyzeError(msg);
      toast.error(msg, { duration: 6000 });
    } finally {
      setIsAnalyzing(false);
    }
  };

  const handleFieldChange = (field: keyof IMDBFormData, value: string) => {
    setFormData((prev) => ({ ...prev, [field]: value }));
  };

  const handleSave = async () => {
    setIsSaving(true);
    try {
      await createProduct({ ...formData, confidence_scores: confidence });
      toast.success("Product saved to IMDB!");
      setSaved(true);
      setHasAnalyzed(false);
      setFormData(EMPTY_FORM);
      setConfidence({});
      setDuplicates([]);
      setMethod(null);
      setImagesProcessed(0);
    } catch (err: unknown) {
      let msg = "Failed to save. Please review required fields and try again.";
      if (axios.isAxiosError(err)) {
        const detail = err.response?.data?.error || err.response?.data?.detail || err.message;
        msg = `Save failed: ${detail}`;
      }
      toast.error(msg, { duration: 6000 });
    } finally {
      setIsSaving(false);
    }
  };

  const hasExtracted = hasAnalyzed;

  return (
    <div className="space-y-8">
      {/* Hero */}
      <div className="text-center space-y-2">
        <div className="inline-flex items-center gap-2 px-3 py-1 bg-brand-100 text-brand-700 rounded-full text-sm font-medium">
          <Sparkles className="h-4 w-4" />
          AI-Powered Product Cataloging
        </div>
        <h1 className="text-3xl font-bold text-gray-900">Upload → Extract → Save</h1>
        <p className="text-gray-500 max-w-xl mx-auto text-sm">
          Upload <strong>3–10 images</strong> of different product sides. The AI aggregates
          evidence across all images to fill all 13 IMDB columns.
        </p>
      </div>

      {/* Multi-image tip */}
      <div className="flex items-start gap-3 bg-blue-50 border border-blue-200 rounded-xl px-4 py-3">
        <Info className="h-4 w-4 text-blue-600 mt-0.5 shrink-0" />
        <p className="text-xs text-blue-700">
          <strong>Tip:</strong> One image may not show all details. Upload the front, back,
          side, and base images together — the AI merges results for better coverage.
        </p>
      </div>

      {saved && (
        <div className="flex items-center gap-3 bg-green-50 border border-green-200 rounded-xl px-4 py-3">
          <CheckCircle2 className="h-5 w-5 text-green-600 shrink-0" />
          <p className="text-sm text-green-800 font-medium">
            Product saved! Upload the next product&apos;s images to continue.
          </p>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 items-start">
        {/* Left: upload */}
        <div className="bg-white rounded-2xl border border-gray-200 shadow-sm p-6 space-y-4">
          <h2 className="text-lg font-semibold text-gray-800">Product Images</h2>
          <ImageUpload onAnalyze={handleAnalyze} isLoading={isAnalyzing} />
          {method && imagesProcessed > 0 && (
            <p className="text-xs text-gray-400 text-center">
              Aggregated from{" "}
              <span className="font-semibold text-gray-600">{imagesProcessed} image{imagesProcessed > 1 ? "s" : ""}</span>{" "}
              using{" "}
              <span className="font-semibold text-gray-600">
                {method === "gpt4o" ? "GPT-4o Vision" : method === "ocr" ? "OCR" : method}
              </span>
            </p>
          )}
        </div>

        {/* Right: extracted form */}
        <div className="bg-white rounded-2xl border border-gray-200 shadow-sm p-6 space-y-4">
          <h2 className="text-lg font-semibold text-gray-800">
            13 IMDB Attributes{" "}
            {hasExtracted && (
              <span className="text-sm font-normal text-gray-400">— edit before saving</span>
            )}
          </h2>

          {duplicates.length > 0 && <DuplicateAlert duplicates={duplicates} />}

          {analyzeError && !hasExtracted && (
            <div className="flex items-start gap-3 bg-red-50 border border-red-200 rounded-xl px-4 py-3">
              <AlertCircle className="h-4 w-4 text-red-600 mt-0.5 shrink-0" />
              <p className="text-xs text-red-700">{analyzeError}</p>
            </div>
          )}

          {hasExtracted ? (
            <IMDBForm
              data={formData}
              confidence={confidence}
              onChange={handleFieldChange}
              onSave={handleSave}
              isSaving={isSaving}
            />
          ) : (
            <div className="flex flex-col items-center justify-center py-16 text-center text-gray-400 space-y-2">
              <p className="text-sm">
                Upload product images and click <strong>Extract</strong> to auto-fill all 13 IMDB attributes.
              </p>
            </div>
          )}
        </div>
      </div>

      {/* Feature cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 pt-2">
        {[
          {
            title: "Multi-Image Aggregation",
            desc: "Upload 3–4 images of different angles. Results are merged field-by-field using the highest-confidence extraction.",
          },
          {
            title: "13-Column Schema",
            desc: "ITEM_NAME, BARCODE, BRAND, WEIGHT, PACKAGING TYPE, COUNTRY, VARIANT, TYPE, FLAVOR, PROMOTION, ADDONS, TAGLINE.",
          },
          {
            title: "predictions.csv / .xlsx",
            desc: "Export matches the ground-truth column order and naming convention for direct submission.",
          },
        ].map((card) => (
          <div key={card.title} className="bg-white rounded-xl border border-gray-200 p-4 shadow-sm">
            <h3 className="font-semibold text-gray-800 text-sm">{card.title}</h3>
            <p className="text-xs text-gray-500 mt-1">{card.desc}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

