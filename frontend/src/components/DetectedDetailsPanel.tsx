import { motion } from "framer-motion";
import { Palette, User, Loader2 } from "lucide-react";
import type { AvatarAnalysis } from "@/lib/api";

interface DetectedDetailsPanelProps {
  analysis: AvatarAnalysis | null;
}

export function DetectedDetailsPanel({ analysis }: DetectedDetailsPanelProps) {
  const isLoading = !analysis;
  const colors = analysis?.dominant_colors ?? [];
  const faceUrl = analysis?.face_thumbnail_url ?? null;

  return (
    <motion.div
      // Slide vertically: an x-offset overflows the viewport on mobile
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, delay: 0.2 }}
      className="flex flex-col gap-4"
    >
      {/* Header */}
      <div className="rounded-xl border border-border bg-card p-4">
        <h3 className="flex items-center gap-2 text-sm font-semibold uppercase tracking-wider text-muted-foreground">
          <Palette className="h-4 w-4" />
          Detected Details
        </h3>
      </div>

      {/* Face Thumbnail */}
      <div className="rounded-xl border border-border bg-card p-5">
        <p className="mb-3 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
          Face
        </p>
        <div className="flex items-center justify-center">
          {isLoading ? (
            <div className="flex h-20 w-20 items-center justify-center rounded-full border-2 border-dashed border-border bg-muted">
              <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
            </div>
          ) : faceUrl ? (
            <div className="relative">
              <img
                src={faceUrl}
                alt="Detected face"
                className="h-20 w-20 rounded-full border-2 border-border object-cover shadow-sm"
              />
              <div className="absolute -bottom-1 -right-1 flex h-5 w-5 items-center justify-center rounded-full bg-emerald-500 shadow">
                <svg className="h-3 w-3 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                </svg>
              </div>
            </div>
          ) : (
            <div className="flex h-20 w-20 items-center justify-center rounded-full border-2 border-border bg-muted">
              <User className="h-8 w-8 text-muted-foreground" />
            </div>
          )}
        </div>
      </div>

      {/* Clothing Colors */}
      <div className="rounded-xl border border-border bg-card p-5">
        <p className="mb-3 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
          Clothing Colors
        </p>

        {isLoading ? (
          <div className="flex flex-col items-center gap-2 py-4">
            <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
            <p className="text-xs text-muted-foreground">Analyzing...</p>
          </div>
        ) : colors.length > 0 ? (
          <div className="space-y-2.5">
            {colors.map((color, i) => (
              <div key={i} className="flex items-center gap-3">
                {/* Color swatch */}
                <div
                  className="h-8 w-8 shrink-0 rounded-lg border border-border shadow-sm"
                  style={{ backgroundColor: color.hex }}
                />
                {/* Info */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between">
                    <span className="font-mono text-xs font-medium text-foreground">
                      {color.hex}
                    </span>
                    <span className="text-xs text-muted-foreground">
                      {color.percentage}%
                    </span>
                  </div>
                  {/* Percentage bar */}
                  <div className="mt-1 h-1.5 w-full overflow-hidden rounded-full bg-muted">
                    <motion.div
                      initial={{ width: 0 }}
                      animate={{ width: `${color.percentage}%` }}
                      transition={{ duration: 0.6, delay: 0.3 + i * 0.1 }}
                      className="h-full rounded-full"
                      style={{ backgroundColor: color.hex }}
                    />
                  </div>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <p className="py-4 text-center text-xs text-muted-foreground">
            No clothing colors detected
          </p>
        )}
      </div>

      {/* Color palette strip */}
      {colors.length > 0 && (
        <div className="flex overflow-hidden rounded-lg border border-border">
          {colors.map((color, i) => (
            <div
              key={i}
              className="h-3"
              style={{
                backgroundColor: color.hex,
                width: `${color.percentage}%`,
                minWidth: "8%",
              }}
            />
          ))}
        </div>
      )}
    </motion.div>
  );
}
