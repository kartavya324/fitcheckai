import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { motion } from "framer-motion";
import { Palette, Upload, Loader2, Info, Check, X } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import {
  useColorAnalysis,
  getErrorMessage,
  type ColorAnalysis,
  type ColorSwatch,
} from "@/lib/api";

export const Route = createFileRoute("/colors")({
  head: () => ({
    meta: [
      { title: "Your Colors — FitCheck AI" },
      { name: "description", content: "Find the colors that suit your skin tone." },
    ],
  }),
  component: ColorsPage,
});

function ColorsPage() {
  const [preview, setPreview] = useState<string | null>(null);
  const [result, setResult] = useState<ColorAnalysis | null>(null);
  const analysis = useColorAnalysis();

  const onPick = (file: File) => {
    setPreview((p) => {
      if (p?.startsWith("blob:")) URL.revokeObjectURL(p);
      return URL.createObjectURL(file);
    });
    setResult(null);
    analysis.mutate(file, {
      onSuccess: setResult,
      onError: (e) => toast.error(getErrorMessage(e)),
    });
  };

  return (
    <div className="mx-auto max-w-3xl px-4 py-12 sm:px-6">
      <div className="text-center">
        <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl bg-secondary">
          <Palette className="h-6 w-6 text-foreground" />
        </div>
        <h1 className="mt-4 font-heading text-3xl font-bold text-foreground">Your colors</h1>
        <p className="mx-auto mt-2 max-w-md text-muted-foreground">
          Upload a well-lit, front-facing photo and we'll find the colors that flatter your skin tone.
        </p>
      </div>

      <div className="mt-8 grid gap-6 sm:grid-cols-[220px_1fr]">
        {/* Upload */}
        <div>
          <label className="flex aspect-[3/4] cursor-pointer flex-col items-center justify-center overflow-hidden rounded-2xl border-2 border-dashed border-border bg-card hover:border-foreground/30">
            {preview ? (
              <img src={preview} alt="You" className="h-full w-full object-cover" />
            ) : (
              <>
                <Upload className="h-6 w-6 text-muted-foreground" />
                <span className="mt-2 px-4 text-center text-xs text-muted-foreground">
                  Upload a face photo
                </span>
              </>
            )}
            <input
              type="file"
              accept="image/*"
              className="hidden"
              onChange={(e) => {
                const f = e.target.files?.[0];
                if (f) onPick(f);
              }}
            />
          </label>
          {result && (
            <div className="mt-3 flex items-center gap-2 rounded-lg border border-border bg-card px-3 py-2 text-xs">
              <span
                className="h-5 w-5 rounded-full border border-border"
                style={{ background: result.skin_hex }}
              />
              <span className="text-muted-foreground">
                Skin tone {result.skin_hex}
                {!result.used_face && " · face not detected"}
              </span>
            </div>
          )}
        </div>

        {/* Result */}
        <div>
          {analysis.isPending ? (
            <div className="flex h-40 flex-col items-center justify-center gap-2 text-muted-foreground">
              <Loader2 className="h-5 w-5 animate-spin" />
              <span className="text-sm">Reading your colors…</span>
            </div>
          ) : result ? (
            <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="space-y-5">
              <div>
                <div className="flex flex-wrap items-baseline gap-2">
                  <h2 className="font-heading text-2xl font-bold text-foreground">{result.season}</h2>
                  <span className="rounded-full bg-secondary px-2 py-0.5 text-xs font-medium capitalize text-foreground">
                    {result.undertone} · {result.depth}
                  </span>
                </div>
                <p className="mt-1 text-sm text-muted-foreground">{result.description}</p>
              </div>

              <Swatches title="Your best colors" icon={<Check className="h-3.5 w-3.5 text-emerald-500" />} colors={result.palette} />
              <Swatches title="Best avoided" icon={<X className="h-3.5 w-3.5 text-destructive" />} colors={result.avoid} muted />

              <p className="flex items-start gap-1.5 rounded-lg border border-border bg-muted/30 p-3 text-xs text-muted-foreground">
                <Info className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                {result.disclaimer}
              </p>
            </motion.div>
          ) : (
            <div className="flex h-40 items-center justify-center rounded-xl border border-dashed border-border text-center text-sm text-muted-foreground">
              Your palette will appear here.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function Swatches({
  title,
  icon,
  colors,
  muted,
}: {
  title: string;
  icon: React.ReactNode;
  colors: ColorSwatch[];
  muted?: boolean;
}) {
  return (
    <div>
      <p className="mb-2 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
        {icon} {title}
      </p>
      <div className="grid grid-cols-4 gap-2 sm:grid-cols-5">
        {colors.map((c) => (
          <div key={c.hex} className={`text-center ${muted ? "opacity-70" : ""}`}>
            <div
              className="aspect-square w-full rounded-lg border border-border shadow-sm"
              style={{ background: c.hex }}
              title={`${c.name} ${c.hex}`}
            />
            <p className="mt-1 truncate text-[10px] text-muted-foreground">{c.name}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
