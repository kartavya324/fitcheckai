import { createFileRoute, Link } from "@tanstack/react-router";
import { useState } from "react";
import { motion } from "framer-motion";
import { Download, RotateCcw, Share2, ChevronLeft, Check, Loader2, AlertCircle } from "lucide-react";
import { z } from "zod";
import { useQuery } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { getJob, jobQueryKeys, loadTryOnSession } from "@/lib/api";
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
