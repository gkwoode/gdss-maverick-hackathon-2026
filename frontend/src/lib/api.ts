import axios from "axios";
import type {
  AnalyzeResult,
  DuplicateCandidate,
  ExportFormat,
  FilterParams,
  IMDBFormData,
  IMDBRecord,
  PaginatedResponse,
} from "@/types/imdb";

const api = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api",
  timeout: 120_000,
});

// --------------------------
// Products CRUD
// --------------------------

export async function fetchProducts(
  params: FilterParams = {}
): Promise<PaginatedResponse<IMDBRecord>> {
  const { data } = await api.get<PaginatedResponse<IMDBRecord>>("/products/", { params });
  return data;
}

export async function fetchProduct(id: number): Promise<IMDBRecord> {
  const { data } = await api.get<IMDBRecord>(`/products/${id}/`);
  return data;
}

export async function createProduct(payload: Partial<IMDBFormData>): Promise<IMDBRecord> {
  const { data } = await api.post<IMDBRecord>("/products/", payload);
  return data;
}

export async function updateProduct(
  id: number,
  payload: Partial<IMDBFormData>
): Promise<IMDBRecord> {
  const { data } = await api.patch<IMDBRecord>(`/products/${id}/`, payload);
  return data;
}

export async function deleteProduct(id: number): Promise<void> {
  await api.delete(`/products/${id}/`);
}

// --------------------------
// Analyze — single image
// --------------------------

export async function analyzeImage(file: File): Promise<AnalyzeResult> {
  const form = new FormData();
  form.append("image", file);
  const { data } = await api.post<AnalyzeResult>("/products/analyze/", form);
  return data;
}

// --------------------------
// Compress image in-browser before upload
// Reduces mobile camera photos from ~5 MB → ~300 KB and converts HEIC to JPEG.
// Falls back to the original file if the canvas API is unavailable.
// --------------------------

async function compressImage(
  file: File,
  maxPx = 1920,
  quality = 0.82
): Promise<Blob> {
  return new Promise((resolve) => {
    const img = new Image();
    const objectUrl = URL.createObjectURL(file);
    img.onload = () => {
      URL.revokeObjectURL(objectUrl);
      const scale = Math.min(1, maxPx / Math.max(img.width, img.height));
      const w = Math.round(img.width * scale);
      const h = Math.round(img.height * scale);
      const canvas = document.createElement("canvas");
      canvas.width = w;
      canvas.height = h;
      const ctx = canvas.getContext("2d");
      if (!ctx) { resolve(file); return; }
      ctx.drawImage(img, 0, 0, w, h);
      canvas.toBlob(
        (blob) => resolve(blob ?? file),
        "image/jpeg",
        quality,
      );
    };
    img.onerror = () => { URL.revokeObjectURL(objectUrl); resolve(file); };
    img.src = objectUrl;
  });
}

// --------------------------
// Analyze — multiple images (aggregate across 3-4 angles of same product)
// --------------------------

export async function analyzeImages(files: File[]): Promise<AnalyzeResult> {
  const form = new FormData();
  for (const f of files) {
    const blob = await compressImage(f);
    form.append("images", blob, f.name.replace(/\.[^.]+$/, ".jpg"));
  }
  const { data } = await api.post<AnalyzeResult>("/products/analyze_multi/", form);
  return data;
}

// --------------------------
// Duplicate check
// --------------------------

export async function checkDuplicates(
  candidate: Partial<IMDBFormData> & { id?: number }
): Promise<DuplicateCandidate[]> {
  const { data } = await api.post<{ potential_duplicates: DuplicateCandidate[] }>(
    "/products/check_duplicates/",
    candidate
  );
  return data.potential_duplicates;
}

// --------------------------
// Export (predictions.csv / predictions.xlsx)
// --------------------------

export function buildExportUrl(format: ExportFormat, ids?: number[]): string {
  const base = `${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api"}/products/export/`;
  const params = new URLSearchParams({ file_format: format });
  if (ids && ids.length > 0) ids.forEach((id) => params.append("ids", String(id)));
  return `${base}?${params.toString()}`;
}

/** Convert a media path to a displayable URL.
 *  Handles data URIs (base64), absolute URLs, and legacy relative paths. */
export function mediaUrl(path: string | null | undefined): string | null {
  if (!path) return null;
  if (path.startsWith("data:") || path.startsWith("http")) return path;
  const base = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api").replace(/\/api$/, "");
  return `${base}/media/${path}`;
}

