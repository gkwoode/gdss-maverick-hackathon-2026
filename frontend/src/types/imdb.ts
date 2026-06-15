/** Confidence scores for every IMDB field (0–1). */
export interface ConfidenceScores {
  item_name: number;
  barcode: number;
  manufacturer: number;
  brand: number;
  weight: number;
  packaging_type: number;
  country: number;
  variant: number;
  product_type: number;
  fragrance_flavor: number;
  promotion: number;
  addons: number;
  tagline: number;
}

/** Full 13-column IMDB record as returned by the API. */
export interface IMDBRecord {
  id: number;
  item_name: string | null;
  barcode: string | null;
  manufacturer: string | null;
  brand: string | null;
  weight: string | null;
  packaging_type: string | null;
  country: string | null;
  variant: string;
  product_type: string | null;
  fragrance_flavor: string;
  promotion: string;
  addons: string;
  tagline: string;
  image_paths: string[];
  confidence_scores: Partial<ConfidenceScores>;
  overall_confidence: number;
  needs_review: boolean;
  is_duplicate_candidate: boolean;
  duplicate_of: number | null;
  created_at: string;
  updated_at: string;
}

/** Editable fields (omits server-managed fields). */
export type IMDBFormData = Omit<
  IMDBRecord,
  | "id"
  | "overall_confidence"
  | "needs_review"
  | "is_duplicate_candidate"
  | "duplicate_of"
  | "created_at"
  | "updated_at"
>;

/** Response from the analyze / analyze_multi endpoints. */
export interface AnalyzeResult {
  extracted: Partial<IMDBFormData>;
  confidence: Partial<ConfidenceScores>;
  method: string;
  potential_duplicates: DuplicateCandidate[];
  images_processed: number;
  images_failed?: number;
}

export interface DuplicateCandidate {
  id: number;
  barcode: string | null;
  brand: string | null;
  item_name: string | null;
  weight: string | null;
  overall_confidence: number;
}

export interface PaginatedResponse<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

export type ExportFormat = "csv" | "excel";

export interface FilterParams {
  search?: string;
  brand?: string;
  type?: string;
  barcode?: string;
  needs_review?: boolean;
  page?: number;
}

