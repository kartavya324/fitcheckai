import { createFileRoute, Link } from "@tanstack/react-router";
import { useState, useEffect, useRef, useCallback } from "react";
import { motion } from "framer-motion";
import {
  Upload,
  CheckCircle2,
  XCircle,
  ImageIcon,
  ArrowRight,
  RotateCcw,
  Box,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { createAvatar, getAvatarStatus } from "@/lib/api";
import { AvatarViewer3D } from "@/components/AvatarViewer3D";

export const Route = createFileRoute("/avatar")({
  head: () => ({
    meta: [
      { title: "Create Your 3D Avatar — FitCheck AI" },
      {
        name: "description",
        content:
          "Upload a full-body photo to generate your personal 3D avatar with AI.",
      },
    ],
  }),
  component: AvatarPage,
});

type Phase = "upload" | "processing" | "complete" | "error";

function AvatarPage() {
  const [phase, setPhase] = useState<Phase>("upload");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [jobId, setJobId] = useState<string | null>(null);
  const [progress, setProgress] = useState(0);
  const [stage, setStage] = useState("Starting...");
  const [avatarUrl, setAvatarUrl] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const pollIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [isDragging, setIsDragging] = useState(false);

  // Polling logic
  useEffect(() => {
    if (!jobId || phase !== "processing") return;

    pollIntervalRef.current = setInterval(async () => {
      try {
        const res = await getAvatarStatus(jobId);
        setProgress(res.progress);
        setStage(res.stage || "Processing...");

        if (res.status === "completed") {
          setAvatarUrl(res.avatar_url);
          setPhase("complete");
          if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);
        } else if (res.status === "failed") {
          setError("Avatar generation failed. Please try again.");
          setPhase("error");
          if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);
        }
      } catch {
        // Silently retry on network blips
      }
    }, 1500);

    return () => {
      if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);
    };
  }, [jobId, phase]);

  const handleFileSelect = useCallback((file: File) => {
    if (!file.type.startsWith("image/")) return;
    setSelectedFile(file);
    setPreviewUrl(URL.createObjectURL(file));
  }, []);

  const handleGenerate = useCallback(async () => {
    if (!selectedFile) return;
    try {
      setPhase("processing");
      setProgress(0);
      setStage("Starting...");
      const result = await createAvatar(selectedFile);
      setJobId(result.job_id);
    } catch (e) {
      setPhase("error");
      setError(String(e));
    }
  }, [selectedFile]);

  const handleReset = useCallback(() => {
    setPhase("upload");
    setSelectedFile(null);
    setPreviewUrl(null);
    setJobId(null);
    setProgress(0);
    setStage("Starting...");
    setAvatarUrl(null);
    setError(null);
  }, []);

  const handleDragOver = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setIsDragging(true);
    },
    [],
  );

  const handleDragLeave = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setIsDragging(false);
    },
    [],
  );

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setIsDragging(false);
      const file = e.dataTransfer.files[0];
      if (file) handleFileSelect(file);
    },
    [handleFileSelect],
  );

  return (
    <section className="mx-auto max-w-3xl px-4 py-12 sm:px-6 lg:px-8">
      {phase === "upload" && (
        <UploadPhase
          previewUrl={previewUrl}
          selectedFile={selectedFile}
          isDragging={isDragging}
          fileInputRef={fileInputRef}
          onFileSelect={handleFileSelect}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          onGenerate={handleGenerate}
        />
      )}

      {phase === "processing" && (
        <ProcessingPhase progress={progress} stage={stage} />
      )}

      {phase === "complete" && avatarUrl && (
        <CompletePhase avatarUrl={avatarUrl} onReset={handleReset} />
      )}

      {phase === "error" && (
        <ErrorPhase error={error} onReset={handleReset} />
      )}
    </section>
  );
}

/* ─── Upload Phase ───────────────────────────────────────── */

function UploadPhase({
  previewUrl,
  selectedFile,
  isDragging,
  fileInputRef,
  onFileSelect,
  onDragOver,
  onDragLeave,
  onDrop,
  onGenerate,
}: {
  previewUrl: string | null;
  selectedFile: File | null;
  isDragging: boolean;
  fileInputRef: React.RefObject<HTMLInputElement | null>;
  onFileSelect: (f: File) => void;
  onDragOver: (e: React.DragEvent) => void;
  onDragLeave: (e: React.DragEvent) => void;
  onDrop: (e: React.DragEvent) => void;
  onGenerate: () => void;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4 }}
    >
      <div className="text-center">
        <h1 className="font-heading text-3xl font-bold tracking-tight text-foreground sm:text-4xl">
          Create Your 3D Avatar
        </h1>
        <p className="mx-auto mt-3 max-w-xl text-muted-foreground">
          Upload a full-body photo to generate your personal 3D avatar. Stand
          straight, face forward, good lighting.
        </p>
      </div>

      {/* Photo requirements */}
      <div className="mt-8 rounded-xl border border-border bg-card p-5">
        <p className="mb-3 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
          Photo guidelines
        </p>
        <ul className="grid gap-1.5 text-sm text-muted-foreground sm:grid-cols-2">
          {[
            "Full body visible — head to feet",
            "Face forward, standing straight",
            "Good lighting, minimal shadows",
            "Plain or simple background",
            "Colour photo (not black & white)",
          ].map((tip) => (
            <li key={tip} className="flex items-start gap-2">
              <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 shrink-0 text-emerald-500" />
              {tip}
            </li>
          ))}
        </ul>
      </div>

      {/* Upload area */}
      <div
        className={`mt-6 flex min-h-[220px] cursor-pointer flex-col items-center justify-center rounded-2xl border-2 border-dashed transition-colors ${
          isDragging
            ? "border-foreground bg-accent/50"
            : previewUrl
              ? "border-border bg-card"
              : "border-border/60 bg-card hover:border-foreground/40"
        }`}
        onClick={() => fileInputRef.current?.click()}
        onDragOver={onDragOver}
        onDragLeave={onDragLeave}
        onDrop={onDrop}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept="image/*"
          className="hidden"
          onChange={(e) => {
            const file = e.target.files?.[0];
            if (file) onFileSelect(file);
          }}
        />

        {previewUrl ? (
          <div className="flex w-full flex-col items-center gap-3 p-4">
            <img
              src={previewUrl}
              alt="Preview"
              className="max-h-[280px] rounded-xl object-contain"
            />
            <p className="text-xs text-muted-foreground">
              {selectedFile?.name}
            </p>
          </div>
        ) : (
          <div className="flex flex-col items-center gap-3 p-6 text-center">
            <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-muted">
              <ImageIcon className="h-6 w-6 text-muted-foreground" />
            </div>
            <div>
              <p className="text-sm font-medium text-foreground">
                Click to upload or drag and drop
              </p>
              <p className="mt-1 text-xs text-muted-foreground">
                JPEG, PNG, or WebP · Max 10 MB
              </p>
            </div>
          </div>
        )}
      </div>

      {/* Generate button */}
      <Button
        className="mt-6 w-full gap-2 bg-foreground text-background hover:bg-foreground/90"
        size="lg"
        disabled={!selectedFile}
        onClick={onGenerate}
      >
        Generate Avatar
        <ArrowRight className="h-4 w-4" />
      </Button>
    </motion.div>
  );
}

/* ─── Processing Phase ───────────────────────────────────── */

function ProcessingPhase({
  progress,
  stage,
}: {
  progress: number;
  stage: string;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.4 }}
      className="flex min-h-[60vh] flex-col items-center justify-center text-center"
    >
      {/* Rotating cube */}
      <div className="mb-8">
        <motion.div
          animate={{ rotateY: 360 }}
          transition={{ duration: 3, repeat: Infinity, ease: "linear" }}
          style={{ perspective: 200 }}
        >
          <Box className="h-20 w-20 text-amber-500" strokeWidth={1.5} />
        </motion.div>
      </div>

      <h2 className="font-heading text-2xl font-bold text-foreground">
        Building Your Avatar
      </h2>
      <p className="mt-2 text-sm text-muted-foreground">{stage}</p>

      {/* Progress bar */}
      <div className="mt-6 w-full max-w-sm">
        <div className="h-2.5 w-full overflow-hidden rounded-full bg-muted">
          <div
            className="h-full rounded-full bg-foreground"
            style={{
              width: `${progress}%`,
              transition: "width 0.5s ease",
            }}
          />
        </div>
        <p className="mt-2 text-sm font-medium text-foreground">{progress}%</p>
      </div>

      <p className="mt-6 max-w-xs text-xs text-muted-foreground">
        This takes about 30–60 seconds in test mode. Real GPU generation takes
        2–3 minutes.
      </p>
    </motion.div>
  );
}

/* ─── Complete Phase ─────────────────────────────────────── */

function CompletePhase({
  avatarUrl,
  onReset,
}: {
  avatarUrl: string;
  onReset: () => void;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4 }}
    >
      {/* Success banner */}
      <div className="mb-6 flex items-center gap-2 rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 dark:border-emerald-800 dark:bg-emerald-950">
        <CheckCircle2 className="h-5 w-5 text-emerald-600 dark:text-emerald-400" />
        <p className="text-sm font-medium text-emerald-700 dark:text-emerald-300">
          Your avatar is ready!
        </p>
      </div>

      {/* 3D Viewer */}
      <AvatarViewer3D glbUrl={avatarUrl} height={520} autoRotate />

      <p className="mt-3 text-center text-xs text-muted-foreground">
        Drag to rotate · Scroll to zoom
      </p>

      {/* Actions */}
      <div className="mt-6 flex gap-3">
        <Link to="/try-on" className="flex-1">
          <Button
            className="w-full gap-2 bg-foreground text-background hover:bg-foreground/90"
            size="lg"
          >
            Try On Clothes
            <ArrowRight className="h-4 w-4" />
          </Button>
        </Link>
        <Button
          variant="outline"
          size="lg"
          className="gap-2"
          onClick={onReset}
        >
          <RotateCcw className="h-4 w-4" />
          Regenerate
        </Button>
      </div>
    </motion.div>
  );
}

/* ─── Error Phase ────────────────────────────────────────── */

function ErrorPhase({
  error,
  onReset,
}: {
  error: string | null;
  onReset: () => void;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.4 }}
      className="flex min-h-[50vh] flex-col items-center justify-center text-center"
    >
      <XCircle className="h-16 w-16 text-destructive" />
      <h2 className="mt-4 font-heading text-2xl font-bold text-foreground">
        Something went wrong
      </h2>
      <p className="mt-2 max-w-sm text-sm text-muted-foreground">
        {error || "An unexpected error occurred."}
      </p>
      <Button className="mt-6 gap-2" onClick={onReset}>
        <RotateCcw className="h-4 w-4" />
        Try Again
      </Button>
    </motion.div>
  );
}
