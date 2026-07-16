import { createFileRoute, Link } from "@tanstack/react-router";
import { useState } from "react";
import { motion } from "framer-motion";
import {
  Download,
  RotateCcw,
  Share2,
  ChevronLeft,
  Check,
  Loader2,
  AlertCircle,
  Footprints,
  Upload,
  Sparkles,
} from "lucide-react";
import { z } from "zod";
import { useQuery } from "@tanstack/react-query";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { getJob, jobQueryKeys, loadTryOnSession, useTryFootwear, getErrorMessage } from "@/lib/api";
import { AvatarViewer } from "@/components/AvatarViewer";

const resultsSearchSchema = z.object({
  jobId: z.string().min(1),
});

export const Route = createFileRoute("/results")({
  validateSearch: resultsSearchSchema,
  head: () => ({
    meta: [
      { title: "Your Result — FitCheck AI" },
      { name: "description", content: "View and download your AI-generated virtual try-on result." },
    ],
  }),
  component: ResultsPage,
});

function ResultsPage() {
  const { jobId } = Route.useSearch();
  const [copied, setCopied] = useState(false);
  const [downloading, setDownloading] = useState(false);

  const handleDownload = async (url: string) => {
    setDownloading(true);
    try {
      const res = await fetch(url);
      const blob = await res.blob();
      const objectUrl = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = objectUrl;
      a.download = url.match(/\.(glb|gltf)/i) ? "fitcheck-result.glb" : "fitcheck-result.jpg";
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(objectUrl);
    } catch {
      // fallback: open in new tab
      window.open(url, "_blank");
    } finally {
      setDownloading(false);
    }
  };

  const { data: job, isLoading, isError } = useQuery({
    queryKey: jobQueryKeys.detail(jobId),
    queryFn: () => getJob(jobId),
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      if (status === "completed" || status === "failed") return false;
      return 2000;
    },
  });

  const session = loadTryOnSession(jobId);

  const handleShare = () => {
    navigator.clipboard.writeText(window.location.href);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  if (!jobId) {
    return (
      <ResultsFallback
        title="No result to show"
        description="Complete a try-on to see your results here."
      />
    );
  }

  if (isLoading) {
    return (
      <ResultsFallback
        title="Loading result…"
        icon={<Loader2 className="h-8 w-8 animate-spin text-copper" />}
      />
    );
  }

  if (isError || !session) {
    return (
      <ResultsFallback
        title="Result unavailable"
        description="We could not load your try-on session. Start a new try-on."
        icon={<AlertCircle className="h-8 w-8 text-destructive" />}
        action={
          <Link to="/try-on">
            <Button>Try On Again</Button>
          </Link>
        }
      />
    );
  }

  const clothingName = session.clothingName;
  const personImage = session.personImageUrl;
  const resultImage = session.garmentImageUrl;

  return (
    <div className="mx-auto max-w-5xl px-4 py-12 sm:px-6 lg:px-8">
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
      >
        <div className="flex flex-wrap items-center justify-between gap-4">
          <Link
            to="/try-on"
            className="flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground"
          >
            <ChevronLeft className="h-4 w-4" />
            Back to Try-On
          </Link>
          <div className="flex gap-2">
            <Button variant="outline" size="sm" onClick={handleShare}>
              {copied ? <Check className="mr-1.5 h-4 w-4" /> : <Share2 className="mr-1.5 h-4 w-4" />}
              {copied ? "Copied" : "Share"}
            </Button>
            <Button
              variant="outline"
              size="sm"
              disabled={!job?.result_url || downloading}
              onClick={() => job?.result_url && void handleDownload(job.result_url)}
            >
              {downloading ? <Loader2 className="mr-1.5 h-4 w-4 animate-spin" /> : <Download className="mr-1.5 h-4 w-4" />}
              {downloading ? "Saving..." : "Download"}
            </Button>
          </div>
        </div>

        <div className="mt-8 text-center">
          <h1 className="font-heading text-2xl font-bold text-foreground sm:text-3xl">
            Your Try-On Result
          </h1>
          <p className="mt-2 text-muted-foreground">{clothingName}</p>
          {job?.status === "failed" && (
            <p className="mt-2 text-sm font-medium text-destructive">
              Generation failed. Please try again.
            </p>
          )}
        </div>

        <div className="mt-10 grid gap-6 md:grid-cols-3">
          <motion.div
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.5, delay: 0.1 }}
            className="flex flex-col gap-6 md:col-span-1"
          >
            <div className="overflow-hidden rounded-2xl border border-border bg-card">
              <div className="relative aspect-square md:aspect-[3/4]">
                <img src={personImage} alt="Before" className="h-full w-full object-cover" />
                <div className="absolute left-3 top-3 rounded-lg bg-background/90 px-2.5 py-1 text-xs font-medium text-foreground backdrop-blur-sm">
                  Before
                </div>
              </div>
            </div>

            <div className="overflow-hidden rounded-2xl border border-border bg-card">
              <div className="relative aspect-square md:aspect-[3/4]">
                <img src={resultImage} alt="Garment" className="h-full w-full object-cover" />
                <div className="absolute left-3 top-3 rounded-lg bg-copper/90 px-2.5 py-1 text-xs font-medium text-copper-foreground backdrop-blur-sm">
                  Garment
                </div>
              </div>
            </div>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.5, delay: 0.2 }}
            className="relative overflow-hidden rounded-2xl border border-border bg-card md:col-span-2 min-h-[400px] flex items-center justify-center bg-muted/30"
          >
            {job?.status === "completed" && job?.result_url ? (
              <>
                {job.result_url.match(/\.(glb|gltf)($|\?)/i) ? (
                  <div className="absolute inset-0 h-full w-full">
                    <AvatarViewer url={job.result_url} />
                  </div>
                ) : (
                  <img src={job.result_url} alt="After" className="h-full w-full object-cover" />
                )}
                <div className="absolute left-4 top-4 rounded-lg bg-foreground/90 px-3 py-1.5 text-sm font-semibold text-background backdrop-blur-sm shadow-sm z-10">
                  After
                </div>
              </>
            ) : job?.status === "failed" ? (
              <div className="flex flex-col items-center justify-center text-center p-6">
                <AlertCircle className="h-10 w-10 text-destructive mb-4" />
                <p className="text-lg font-medium text-foreground">Generation Failed</p>
                <p className="text-sm text-muted-foreground mt-1">We couldn't process this image.</p>
              </div>
            ) : (
              <div className="flex flex-col items-center justify-center text-center p-6">
                <Loader2 className="h-10 w-10 animate-spin text-copper mb-4" />
                <p className="text-lg font-medium text-foreground">Generating...</p>
                <p className="text-sm text-muted-foreground mt-1">
                  {job?.stage ? `Stage: ${job.stage}` : "Preparing"} ({job?.progress || 0}%)
                </p>
              </div>
            )}
          </motion.div>
        </div>

        {job?.status === "completed" &&
          job?.result_url &&
          !job.result_url.match(/\.(glb|gltf)($|\?)/i) && (
            <FootwearSection personImageUrl={job.result_url} />
          )}

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.4 }}
          className="mt-10 flex flex-wrap justify-center gap-4"
        >
          <Link to="/try-on">
            <Button size="lg" variant="outline" className="gap-2">
              <RotateCcw className="h-4 w-4" />
              Try Another Outfit
            </Button>
          </Link>
          <Button
            size="lg"
            className="gap-2 bg-foreground text-background hover:bg-foreground/90"
            disabled={!job?.result_url || downloading}
            onClick={() => job?.result_url && void handleDownload(job.result_url)}
          >
            {downloading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Download className="h-4 w-4" />}
            {downloading ? "Saving..." : "Download Result"}
          </Button>
        </motion.div>
      </motion.div>
    </div>
  );
}

function FootwearSection({ personImageUrl }: { personImageUrl: string }) {
  const [shoeFile, setShoeFile] = useState<File | null>(null);
  const [shoePreview, setShoePreview] = useState<string | null>(null);
  const [resultUrl, setResultUrl] = useState<string | null>(null);
  const tryFoot = useTryFootwear();

  const pickShoe = (file: File) => {
    setShoeFile(file);
    setShoePreview((prev) => {
      if (prev?.startsWith("blob:")) URL.revokeObjectURL(prev);
      return URL.createObjectURL(file);
    });
    setResultUrl(null);
  };

  const apply = () => {
    if (!shoeFile) return;
    tryFoot.mutate(
      { personImageUrl, shoeFile },
      {
        onSuccess: (r) => setResultUrl(r.result_url),
        onError: (e) => toast.error(getErrorMessage(e)),
      },
    );
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, delay: 0.3 }}
      className="mt-10 rounded-2xl border border-border bg-card p-5 sm:p-6"
    >
      <div className="mb-4 flex items-center gap-2">
        <Footprints className="h-5 w-5 text-copper" />
        <h2 className="font-heading text-lg font-semibold text-foreground">
          Add footwear
        </h2>
        <span className="rounded-full bg-secondary px-2 py-0.5 text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
          Beta
        </span>
      </div>
      <p className="mb-4 text-sm text-muted-foreground">
        Upload a shoe or slipper (a transparent PNG works best) to place it on the feet.
      </p>

      <div className="grid gap-4 sm:grid-cols-2">
        <label className="flex cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed border-border bg-surface p-6 text-center transition-colors hover:border-foreground/30">
          {shoePreview ? (
            <img src={shoePreview} alt="Shoe" className="max-h-28 object-contain" />
          ) : (
            <>
              <Upload className="h-6 w-6 text-muted-foreground" />
              <p className="mt-2 text-sm font-medium text-foreground">Upload shoe image</p>
              <p className="mt-1 text-xs text-muted-foreground">PNG or JPG</p>
            </>
          )}
          <input
            type="file"
            accept="image/*"
            className="hidden"
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) pickShoe(f);
            }}
          />
        </label>

        <div className="relative flex items-center justify-center overflow-hidden rounded-xl border border-border bg-muted/30">
          {resultUrl ? (
            <img src={resultUrl} alt="With footwear" className="h-full w-full object-cover" />
          ) : tryFoot.isPending ? (
            <div className="flex flex-col items-center gap-2 p-6 text-center">
              <Loader2 className="h-6 w-6 animate-spin text-copper" />
              <p className="text-sm text-muted-foreground">Placing footwear…</p>
            </div>
          ) : (
            <p className="p-6 text-center text-sm text-muted-foreground">
              Your look with the new footwear will appear here.
            </p>
          )}
        </div>
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-3">
        <Button onClick={apply} disabled={!shoeFile || tryFoot.isPending} className="gap-2">
          {tryFoot.isPending ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Sparkles className="h-4 w-4" />
          )}
          {tryFoot.isPending ? "Applying…" : "Apply footwear"}
        </Button>
        {resultUrl && (
          <a href={resultUrl} download="fitcheck-footwear.jpg">
            <Button variant="outline" className="gap-2">
              <Download className="h-4 w-4" />
              Download
            </Button>
          </a>
        )}
      </div>
    </motion.div>
  );
}

function ResultsFallback({
  title,
  description,
  icon,
  action,
}: {
  title: string;
  description?: string;
  icon?: React.ReactNode;
  action?: React.ReactNode;
}) {
  return (
    <div className="flex min-h-[50vh] flex-col items-center justify-center px-4 text-center">
      {icon && <div className="mb-4">{icon}</div>}
      <h1 className="font-heading text-2xl font-bold text-foreground">{title}</h1>
      {description && <p className="mt-2 max-w-md text-muted-foreground">{description}</p>}
      {action && <div className="mt-6">{action}</div>}
    </div>
  );
}
