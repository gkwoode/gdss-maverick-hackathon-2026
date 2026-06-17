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
// Analyze — multiple images (aggregate across 3-4 angles of same product)
// --------------------------

export async function analyzeImages(files: File[]): Promise<AnalyzeResult> {
  const form = new FormData();
  files.forEach((f) => form.append("images", f));
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

/** Convert a relative media path (e.g. "product_images/abc.jpg") to a full URL. */
export function mediaUrl(path: string | null | undefined): string | null {
  if (!path) return null;
  if (path.startsWith("http")) return path;
  const base = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api").replace(/\/api$/, "");
  return `${base}/media/${path}`;
}

