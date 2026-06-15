import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function confidenceColor(score: number): string {
  if (score >= 0.8) return "text-green-600 bg-green-50";
  if (score >= 0.6) return "text-yellow-600 bg-yellow-50";
  return "text-red-600 bg-red-50";
}

export function confidenceLabel(score: number): string {
  if (score >= 0.8) return "High";
  if (score >= 0.6) return "Medium";
  return "Low";
}

export function formatConfidencePct(score: number): string {
  return `${Math.round(score * 100)}%`;
}
