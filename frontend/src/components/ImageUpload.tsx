"use client";

import { useCallback, useEffect, useState } from "react";
import { useDropzone } from "react-dropzone";
import { X, Loader2, Upload, Images } from "lucide-react";
import { cn } from "@/lib/utils";

interface ImageUploadProps {
  onAnalyze: (files: File[]) => Promise<void>;
  isLoading: boolean;
}

interface Preview {
  file: File;
  url: string;
}

export default function ImageUpload({ onAnalyze, isLoading }: ImageUploadProps) {
  const [previews, setPreviews] = useState<Preview[]>([]);
  const [mobile, setMobile] = useState(false);

  useEffect(() => {
    setMobile(/Mobi|Android|iPhone|iPad|iPod/i.test(navigator.userAgent));
  }, []);

  const maxFiles = mobile ? 5 : 10;

  const onDrop = useCallback((accepted: File[]) => {
    const next = accepted.map((f) => ({
      file: f,
      url: URL.createObjectURL(f),
    }));
    setPreviews((prev) => {
      prev.forEach((p) => URL.revokeObjectURL(p.url));
      return next;
    });
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { "image/*": [".jpg", ".jpeg", ".png", ".webp", ".heic"] },
    maxFiles,
    maxSize: 20 * 1024 * 1024,
    disabled: isLoading,
  });

  const removeImage = (index: number) => {
    setPreviews((prev) => {
      URL.revokeObjectURL(prev[index].url);
      return prev.filter((_, i) => i !== index);
    });
  };

  const handleAnalyze = async () => {
    if (previews.length > 0) {
      await onAnalyze(previews.map((p) => p.file));
    }
  };

  return (
    <div className="space-y-4">
      {/* Drop zone */}
      <div
        {...getRootProps()}
        className={cn(
          "border-2 border-dashed rounded-2xl p-8 text-center cursor-pointer transition-all duration-200",
          isDragActive
            ? "border-brand-500 bg-brand-50 scale-[1.01]"
            : "border-gray-300 bg-gray-50 hover:border-brand-400 hover:bg-brand-50",
          isLoading && "pointer-events-none opacity-60"
        )}
      >
        <input {...getInputProps()} />
        <div className="flex flex-col items-center gap-3">
          <div className="p-3 bg-white rounded-full shadow-sm">
            <Images className="h-8 w-8 text-brand-500" />
          </div>
          <div>
            <p className="font-semibold text-gray-700">
              {isDragActive ? "Drop images here" : "Upload product images"}
            </p>
            <p className="text-sm text-gray-500 mt-0.5">
              Add <strong>3–{maxFiles} images</strong> of different sides for best results.
              {!mobile && (
                <> Drag &amp; drop or{" "}
                  <span className="text-brand-600 font-medium">browse</span>.
                </>
              )}
            </p>
            <p className="text-xs text-gray-400 mt-1">
              JPG, PNG, WebP · max 20 MB each · up to {maxFiles} files
            </p>
          </div>
        </div>
      </div>

      {/* Image thumbnails */}
      {previews.length > 0 && (
        <div className="grid grid-cols-5 gap-2">
          {previews.map((p, i) => (
            <div key={i} className="relative group rounded-xl overflow-hidden border border-gray-200 bg-white aspect-square">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={p.url}
                alt={`Product image ${i + 1}`}
                className="w-full h-full object-cover"
              />
              {!isLoading && (
                <button
                  type="button"
                  onClick={(e) => { e.stopPropagation(); removeImage(i); }}
                  className="absolute top-1 right-1 p-1 bg-white/80 rounded-full shadow opacity-0 group-hover:opacity-100 transition-opacity"
                  aria-label={`Remove image ${i + 1}`}
                >
                  <X className="h-3 w-3 text-gray-700" />
                </button>
              )}
              <div className="absolute bottom-0 inset-x-0 bg-black/30 text-white text-[10px] text-center py-0.5">
                Side {i + 1}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Analyze button */}
      {previews.length > 0 && (
        <button
          type="button"
          onClick={handleAnalyze}
          disabled={isLoading}
          className={cn(
            "w-full flex items-center justify-center gap-2 py-3 px-6 rounded-xl font-semibold text-white transition-all duration-200",
            isLoading
              ? "bg-brand-400 cursor-not-allowed"
              : "bg-brand-600 hover:bg-brand-700 active:scale-[0.98] shadow-md hover:shadow-lg"
          )}
        >
          {isLoading ? (
            <>
              <Loader2 className="h-5 w-5 animate-spin" />
              Analyzing {previews.length} image{previews.length > 1 ? "s" : ""}…
            </>
          ) : (
            <>
              <Upload className="h-5 w-5" />
              Extract IMDB Attributes ({previews.length} image{previews.length > 1 ? "s" : ""})
            </>
          )}
        </button>
      )}
    </div>
  );
}
