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
  Shirt,
  Loader2,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { createAvatar, getAvatarStatus, createAvatarTryon } from "@/lib/api";
import { normalizeImageFile } from "@/lib/image";
import type { AvatarAnalysis } from "@/lib/api";
import { AvatarViewer3D } from "@/components/AvatarViewer3D";
import { DetectedDetailsPanel } from "@/components/DetectedDetailsPanel";

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

/** localStorage key for restoring the last generated avatar across reloads */
const AVATAR_STORAGE_KEY = "fitcheck:last-avatar";

interface StoredAvatar {
  sessionId: string;
  avatarUrl: string;
  analysis: AvatarAnalysis | null;
  savedAt: number;
}

function loadStoredAvatar(): StoredAvatar | null {
  try {
    const raw = localStorage.getItem(AVATAR_STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as StoredAvatar;
    if (!parsed.sessionId || !parsed.avatarUrl) return null;
    return parsed;
  } catch {
    return null;
  }
}

function AvatarPage() {
  const [phase, setPhase] = useState<Phase>("upload");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [backFile, setBackFile] = useState<File | null>(null);
  const [backPreview, setBackPreview] = useState<string | null>(null);
  const [jobId, setJobId] = useState<string | null>(null);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [progress, setProgress] = useState(0);
  const [stage, setStage] = useState("Starting...");
  const [avatarUrl, setAvatarUrl] = useState<string | null>(null);
  const [analysis, setAnalysis] = useState<AvatarAnalysis | null>(null);
  const [error, setError] = useState<string | null>(null);
  const pollIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [isDragging, setIsDragging] = useState(false);

  // Restore the last avatar after a reload (SaaS: don't lose work on refresh)
  useEffect(() => {
    const stored = loadStoredAvatar();
    if (stored) {
      setSessionId(stored.sessionId);
      setAvatarUrl(stored.avatarUrl);
      setAnalysis(stored.analysis);
      setPhase("complete");
    }
  }, []);

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
          setAnalysis(res.analysis ?? null);
          setPhase("complete");
          if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);
          // Persist so a page reload restores this avatar
          try {
            if (res.avatar_url && sessionId) {
              localStorage.setItem(
                AVATAR_STORAGE_KEY,
                JSON.stringify({
                  sessionId,
                  avatarUrl: res.avatar_url,
                  analysis: res.analysis ?? null,
                  savedAt: Date.now(),
                } satisfies StoredAvatar),
              );
            }
          } catch {
            // Storage full/blocked — persistence is best-effort
          }
        } else if (res.status === "failed") {
          setError(
            res.error?.message ??
              "Avatar generation failed. Please try again.",
          );
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
  }, [jobId, phase, sessionId]);

  const handleFileSelect = useCallback(async (file: File) => {
    if (!file.type.startsWith("image/") && !/\.(heic|heif)$/i.test(file.name)) return;
    // Normalize on-device: HEIC → JPEG, EXIF baked, huge photos downscaled
    const normalized = await normalizeImageFile(file);
    setSelectedFile(normalized);
    setPreviewUrl(URL.createObjectURL(normalized));
  }, []);

  const handleBackSelect = useCallback(async (file: File) => {
    if (!file.type.startsWith("image/") && !/\.(heic|heif)$/i.test(file.name)) return;
    const normalized = await normalizeImageFile(file);
    setBackFile(normalized);
    setBackPreview((prev) => {
      if (prev?.startsWith("blob:")) URL.revokeObjectURL(prev);
      return URL.createObjectURL(normalized);
    });
  }, []);

  const handleGenerate = useCallback(async () => {
    if (!selectedFile) return;
    try {
      setPhase("processing");
      setProgress(0);
      setStage("Starting...");
      const result = await createAvatar(selectedFile, backFile);
      setJobId(result.job_id);
      setSessionId(result.session_id);
    } catch (e) {
      setPhase("error");
      setError(String(e));
    }
  }, [selectedFile]);

  const handleReset = useCallback(() => {
    try {
      localStorage.removeItem(AVATAR_STORAGE_KEY);
    } catch {
      // best-effort
    }
    setPhase("upload");
    setSelectedFile(null);
    setPreviewUrl(null);
    setBackFile(null);
    setBackPreview(null);
    setJobId(null);
    setSessionId(null);
    setProgress(0);
    setStage("Starting...");
    setAvatarUrl(null);
    setAnalysis(null);
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

  // Widen layout when showing the complete phase (3D viewer + details panel)
  const isComplete = phase === "complete" && avatarUrl;
  const maxWidth = isComplete ? "max-w-6xl" : "max-w-3xl";

  return (
    <section className={`mx-auto ${maxWidth} px-4 py-12 sm:px-6 lg:px-8`}>
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
          backPreview={backPreview}
          onBackSelect={handleBackSelect}
        />
      )}

      {phase === "processing" && (
        <ProcessingPhase progress={progress} stage={stage} />
      )}

      {isComplete && (
        <CompletePhase
          avatarUrl={avatarUrl}
          sessionId={sessionId}
          analysis={analysis}
          onReset={handleReset}
        />
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
  backPreview,
  onBackSelect,
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
  backPreview: string | null;
  onBackSelect: (f: File) => void;
}) {
  const [showTips, setShowTips] = useState(false);
  const backInputRef = useRef<HTMLInputElement>(null);

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

      {/* Upload area */}
      <div
        className={`mt-8 flex min-h-[220px] cursor-pointer flex-col items-center justify-center rounded-2xl border-2 border-dashed transition-colors ${
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
          accept="image/*,.heic,.heif"
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

      {/* Collapsible Photo Tips Card */}
      <div className="mt-6 rounded-xl border border-border bg-muted/30 p-4">
        <div className="flex items-center justify-between">
          <span className="text-sm font-semibold text-foreground flex items-center gap-2">
            <span>📸</span> Photo tips for best results
          </span>
          <Button
            variant="ghost"
            size="sm"
            onClick={(e) => {
              e.stopPropagation();
              setShowTips(!showTips);
            }}
            className="h-8 px-3 text-xs text-muted-foreground hover:text-foreground"
          >
            {showTips ? "Hide tips" : "Show tips"}
          </Button>
        </div>

        {showTips && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            className="mt-4 border-t border-border/60 pt-4"
          >
            <div className="grid gap-6 sm:grid-cols-2 text-sm">
              <div>
                <p className="font-semibold text-foreground mb-2">Do's:</p>
                <ul className="space-y-2 text-muted-foreground">
                  <li>✅ Stand in front of a plain white or light wall</li>
                  <li>✅ Full body visible — head to feet in frame</li>
                  <li>✅ Stand straight, arms slightly away from body</li>
                  <li>✅ Face forward toward the camera</li>
                  <li>✅ Good lighting — near a window or bright room</li>
                  <li>✅ Colour photo with no filters</li>
                  <li>✅ Wear fitted clothes (not oversized/baggy)</li>
                  <li>✅ No other people in the photo</li>
                </ul>
              </div>
              <div>
                <p className="font-semibold text-foreground mb-2">Avoid:</p>
                <ul className="space-y-2 text-muted-foreground">
                  <li>❌ Avoid: dark backgrounds</li>
                  <li>❌ Avoid: objects near your head (caps, bags)</li>
                  <li>❌ Avoid: sitting or crouching poses</li>
                  <li>❌ Avoid: heavy shadows across body</li>
                </ul>
              </div>
            </div>
            
            <p className="mt-4 text-xs text-muted-foreground/80 border-t border-border/40 pt-3 italic">
              Best results: stand 6-8 feet from camera, use your phone's portrait mode or timer
            </p>
          </motion.div>
        )}
      </div>

      {/* Optional back photo — for a real back instead of a synthesized one */}
      <div className="mt-6 rounded-xl border border-border bg-muted/20 p-4">
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={() => backInputRef.current?.click()}
            className="flex h-16 w-16 shrink-0 items-center justify-center overflow-hidden rounded-lg border border-dashed border-border bg-card hover:border-foreground/40"
          >
            {backPreview ? (
              <img src={backPreview} alt="Back" className="h-full w-full object-cover" />
            ) : (
              <Upload className="h-5 w-5 text-muted-foreground" />
            )}
          </button>
          <div className="min-w-0">
            <p className="text-sm font-medium text-foreground">
              Add a back photo{" "}
              <span className="font-normal text-muted-foreground">(optional)</span>
            </p>
            <p className="mt-0.5 text-xs text-muted-foreground">
              {backPreview
                ? "Back photo added — your avatar's back will use it."
                : "Same pose, from behind. Gives a real back instead of a synthesized one."}
            </p>
          </div>
          <input
            ref={backInputRef}
            type="file"
            accept="image/*,.heic,.heif"
            className="hidden"
            onChange={(e) => {
              const file = e.target.files?.[0];
              if (file) onBackSelect(file);
            }}
          />
        </div>
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

const getStageMessage = (progress: number, stage: string) => {
  if (progress < 15) return {
    title: "Preprocessing your photo...",
    detail: "Removing background and preparing image",
    eta: "~10 seconds"
  }
  if (progress < 30) return {
    title: "Analysing your photo...", 
    detail: "Detecting body pose and proportions",
    eta: "~20 seconds"
  }
  if (progress < 70) return {
    title: "Building your 3D mesh...",
    detail: "Reconstructing body shape from photo",
    eta: "3-5 minutes remaining"
  }
  if (progress < 85) return {
    title: "Applying your appearance...",
    detail: "Projecting clothing and skin colors onto mesh",
    eta: "~30 seconds"
  }
  if (progress < 95) return {
    title: "Finalising avatar...",
    detail: "Optimising mesh and exporting",
    eta: "Almost done!"
  }
  return {
    title: "Almost ready!",
    detail: "Preparing your avatar viewer",
    eta: "Seconds away..."
  }
}

function ProcessingPhase({
  progress,
  stage,
}: {
  progress: number;
  stage: string;
}) {
  const msg = getStageMessage(progress, stage);

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

      <h2 className="font-heading text-2xl font-bold text-foreground flex items-center justify-center gap-2">
        {msg.title}
        <span className="h-2 w-2 rounded-full bg-amber-500 animate-pulse" />
      </h2>
      <p className="mt-2 text-sm text-muted-foreground">{msg.detail}</p>

      {/* ETA badge */}
      <div className="mt-3 rounded-full bg-muted px-3 py-1 text-xs font-medium text-muted-foreground">
        ETA: {msg.eta}
      </div>

      {/* Progress bar */}
      <div className="mt-8 w-full max-w-sm">
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
  sessionId,
  analysis,
  onReset,
}: {
  avatarUrl: string;
  sessionId: string | null;
  analysis: AvatarAnalysis | null;
  onReset: () => void;
}) {
  const [tryonAvatarUrl, setTryonAvatarUrl] = useState<string | null>(null);
  const [tryonImageUrl, setTryonImageUrl] = useState<string | null>(null);
  const [showTryon, setShowTryon] = useState(true);

  const displayedUrl = tryonAvatarUrl && showTryon ? tryonAvatarUrl : avatarUrl;

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
          {tryonAvatarUrl && showTryon
            ? "Here's your new outfit!"
            : "Your avatar is ready!"}
        </p>
      </div>

      {/* Two-column layout: 3D Viewer + Detected Details */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[1fr_280px]">
        {/* Left: 3D Viewer */}
        <div>
          <AvatarViewer3D glbUrl={displayedUrl} height={520} />

          {/* Original / New outfit toggle */}
          {tryonAvatarUrl && (
            <div className="mt-3 flex justify-center gap-2">
              <button
                type="button"
                onClick={() => setShowTryon(false)}
                className={`rounded-full border px-4 py-1.5 text-xs font-medium transition-colors ${
                  !showTryon
                    ? "border-foreground bg-foreground text-background"
                    : "border-border bg-card text-muted-foreground hover:text-foreground"
                }`}
              >
                Original
              </button>
              <button
                type="button"
                onClick={() => setShowTryon(true)}
                className={`rounded-full border px-4 py-1.5 text-xs font-medium transition-colors ${
                  showTryon
                    ? "border-foreground bg-foreground text-background"
                    : "border-border bg-card text-muted-foreground hover:text-foreground"
                }`}
              >
                New Outfit
              </button>
            </div>
          )}

          <p className="mt-3 text-center text-xs text-muted-foreground">
            Drag to rotate · Scroll to zoom
          </p>
        </div>

        {/* Right: Detected Details Panel */}
        <DetectedDetailsPanel analysis={analysis} />
      </div>

      {/* Try clothes on this avatar */}
      {sessionId && (
        <AvatarTryOnPanel
          sessionId={sessionId}
          tryonImageUrl={tryonImageUrl}
          onComplete={(glbUrl, imageUrl) => {
            setTryonAvatarUrl(glbUrl);
            setTryonImageUrl(imageUrl);
            setShowTryon(true);
          }}
        />
      )}

      {/* Actions — wraps on narrow screens instead of overflowing */}
      <div className="mt-6 flex flex-wrap gap-3">
        <Link to="/try-on" className="min-w-[200px] flex-1">
          <Button
            className="w-full gap-2 bg-foreground text-background hover:bg-foreground/90"
            size="lg"
          >
            2D Photo Try-On
            <ArrowRight className="h-4 w-4" />
          </Button>
        </Link>
        <Button
          variant="outline"
          size="lg"
          className="flex-1 gap-2 sm:flex-none"
          onClick={onReset}
        >
          <RotateCcw className="h-4 w-4" />
          Regenerate
        </Button>
      </div>
    </motion.div>
  );
}

/* ─── Avatar Try-On Panel ────────────────────────────────── */

const GARMENT_CATEGORIES = [
  { value: "upper_body", label: "Top" },
  { value: "lower_body", label: "Bottom" },
  { value: "dresses", label: "Dress" },
] as const;

function AvatarTryOnPanel({
  sessionId,
  tryonImageUrl,
  onComplete,
}: {
  sessionId: string;
  tryonImageUrl: string | null;
  onComplete: (glbUrl: string, imageUrl: string | null) => void;
}) {
  const [garmentFile, setGarmentFile] = useState<File | null>(null);
  const [garmentPreview, setGarmentPreview] = useState<string | null>(null);
  const [category, setCategory] = useState<string>("upper_body");
  const [state, setState] = useState<"idle" | "processing" | "error">("idle");
  const [progress, setProgress] = useState(0);
  const [stage, setStage] = useState("");
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Clear the poll on unmount
  useEffect(() => {
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, []);

  const handleGarmentSelect = async (file: File) => {
    if (!file.type.startsWith("image/") && !/\.(heic|heif)$/i.test(file.name)) return;
    const normalized = await normalizeImageFile(file);
    setGarmentFile(normalized);
    setGarmentPreview((prev) => {
      if (prev?.startsWith("blob:")) URL.revokeObjectURL(prev);
      return URL.createObjectURL(normalized);
    });
  };

  const handleTryOn = async () => {
    if (!garmentFile) return;
    setState("processing");
    setProgress(0);
    setStage("Starting...");
    setError(null);

    try {
      const { job_id } = await createAvatarTryon(sessionId, garmentFile, category);

      pollRef.current = setInterval(async () => {
        try {
          const res = await getAvatarStatus(job_id);
          setProgress(res.progress);
          setStage(res.stage || "Processing...");

          if (res.status === "completed" && res.avatar_url) {
            if (pollRef.current) clearInterval(pollRef.current);
            setState("idle");
            onComplete(res.avatar_url, res.tryon_image_url ?? null);
          } else if (res.status === "failed") {
            if (pollRef.current) clearInterval(pollRef.current);
            setState("error");
            setError(res.error?.message ?? "Try-on failed. Please try again.");
          }
        } catch {
          // Silently retry on network blips
        }
      }, 2000);
    } catch (e) {
      setState("error");
      setError(String(e));
    }
  };

  return (
    <div className="mt-6 rounded-2xl border border-border bg-card p-5">
      <div className="flex items-center gap-2">
        <Shirt className="h-4 w-4 text-muted-foreground" />
        <h3 className="text-sm font-semibold uppercase tracking-wide text-foreground">
          Try Clothes On This Avatar
        </h3>
      </div>
      <p className="mt-1 text-xs text-muted-foreground">
        Upload a garment photo — we dress your photo with AI, then wrap the
        outfit onto your 3D avatar.
      </p>

      <input
        ref={inputRef}
        type="file"
        accept="image/*,.heic,.heif"
        className="hidden"
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) handleGarmentSelect(file);
        }}
      />

      {state === "processing" ? (
        <div className="mt-4 flex flex-col items-center gap-3 py-4">
          <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
          <p className="text-sm text-muted-foreground">{stage}</p>
          <div className="h-1.5 w-full max-w-xs overflow-hidden rounded-full bg-muted">
            <div
              className="h-full rounded-full bg-foreground transition-all duration-500"
              style={{ width: `${progress}%` }}
            />
          </div>
          <p className="text-xs text-muted-foreground">
            {progress}% · takes 1–3 minutes
          </p>
        </div>
      ) : (
        <div className="mt-4 flex flex-wrap items-center gap-4">
          {/* Garment thumbnail / upload button */}
          <button
            type="button"
            onClick={() => inputRef.current?.click()}
            className="flex h-20 w-20 shrink-0 items-center justify-center overflow-hidden rounded-xl border border-dashed border-border bg-muted/30 hover:border-foreground/40"
          >
            {garmentPreview ? (
              <img
                src={garmentPreview}
                alt="Garment"
                className="h-full w-full object-cover"
              />
            ) : (
              <Upload className="h-5 w-5 text-muted-foreground" />
            )}
          </button>

          {/* Category pills */}
          <div className="flex gap-2">
            {GARMENT_CATEGORIES.map((c) => (
              <button
                key={c.value}
                type="button"
                onClick={() => setCategory(c.value)}
                className={`rounded-full border px-4 py-1.5 text-xs font-medium transition-colors ${
                  category === c.value
                    ? "border-foreground bg-foreground text-background"
                    : "border-border bg-card text-muted-foreground hover:text-foreground"
                }`}
              >
                {c.label}
              </button>
            ))}
          </div>

          <Button
            className="ml-auto gap-2 bg-foreground text-background hover:bg-foreground/90"
            disabled={!garmentFile}
            onClick={handleTryOn}
          >
            <Shirt className="h-4 w-4" />
            Try It On
          </Button>
        </div>
      )}

      {state === "error" && error && (
        <p className="mt-3 text-xs text-destructive">{error}</p>
      )}

      {/* 2D dressed-photo preview from the last successful try-on */}
      {tryonImageUrl && state === "idle" && (
        <div className="mt-4 flex items-center gap-3 border-t border-border/60 pt-4">
          <img
            src={tryonImageUrl}
            alt="Try-on result"
            className="h-24 rounded-lg border border-border object-contain"
          />
          <p className="text-xs text-muted-foreground">
            2D try-on result used to texture your avatar. Toggle
            "Original / New Outfit" under the viewer to compare.
          </p>
        </div>
      )}
    </div>
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
