import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useState, useCallback, useEffect, useRef } from "react";
import { motion } from "framer-motion";
import { toast } from "sonner";
import { getErrorMessage, urlToImageFile, useCreateTryOnJob, fetchProductImage } from "@/lib/api";
import {
  Upload,
  X,
  ArrowRight,
  User,
  Shirt,
  Link2,
  ImageIcon,
  Sparkles,
  Check,
  Loader2,
  Tag,
  ShoppingBag,
  AlertTriangle,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Badge } from "@/components/ui/badge";
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectLabel,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

const GROUPED_CATEGORIES = [
  {
    label: "Upper Body",
    options: [
      "T-Shirt",
      "Shirt",
      "Kurta",
      "Blazer / Jacket",
      "Hoodie / Sweatshirt",
      "Sweater",
      "Top / Blouse",
    ],
  },
  {
    label: "Lower Body",
    options: ["Jeans / Trousers", "Joggers / Sweatpants", "Shorts", "Skirt", "Palazzo / Salwar"],
  },
  {
    label: "Full Body",
    options: ["Dress / Gown", "Saree / Lehenga", "Jumpsuit / Co-ord Set"],
  },
];

const SAMPLE_PEOPLE = [
  { src: "/person-1.jpg", label: "Model 1" },
  { src: "/person-2.jpg", label: "Model 2" },
];

const SAMPLE_GARMENTS = [
  { src: "/shirt-1.jpg", name: "Navy Cotton T-Shirt", category: "T-Shirt", brand: "Sample" },
  {
    src: "/blazer-1.jpg",
    name: "Beige Linen Blazer",
    category: "Blazer / Jacket",
    brand: "Sample",
  },
];

const SUPPORTED_STORES = ["Myntra", "Amazon", "Ajio", "Flipkart"];

const STEPS = ["Upload", "Processing", "Generating", "Result"] as const;

export const Route = createFileRoute("/try-on")({
  head: () => ({
    meta: [
      { title: "Try On — FitCheck AI" },
      {
        name: "description",
        content: "Upload your photo and a clothing item to generate a virtual try-on.",
      },
    ],
  }),
  component: TryOnPage,
});

function TryOnPage() {
  const navigate = useNavigate();
  const createTryOn = useCreateTryOnJob();
  const [personImage, setPersonImage] = useState<string | null>(null);
  const [personFile, setPersonFile] = useState<File | null>(null);
  const [areTipsExpanded, setAreTipsExpanded] = useState(true);
  const [clothingImage, setClothingImage] = useState<string | null>(null);
  const [garmentFile, setGarmentFile] = useState<File | null>(null);
  const [garmentInfo, setGarmentInfo] = useState<{
    name: string;
    category: string;
    brand?: string;
    sourceUrl?: string;
  } | null>(null);
  const [productUrl, setProductUrl] = useState("");
  const [fetchingUrl, setFetchingUrl] = useState(false);
  const [category, setCategory] = useState<string>("T-Shirt");
  const [loadingSample, setLoadingSample] = useState<"person" | "garment" | null>(null);
  const [poseStatus, setPoseStatus] = useState<"checking" | "full" | "upper" | null>(null);

  // Single MediaPipe Pose instance, reused across uploads to avoid WebGL context leak
  const poseRef = useRef<any>(null);

  useEffect(() => {
    if (!personImage) {
      setPoseStatus(null);
      return;
    }

    let isActive = true;
    setPoseStatus("checking");

    const checkPose = async () => {
      try {
        // Reuse existing instance; only create on first use
        if (!poseRef.current) {
          const { Pose } = await import("@mediapipe/pose");
          poseRef.current = new Pose({
            locateFile: (file: string) => `https://cdn.jsdelivr.net/npm/@mediapipe/pose/${file}`,
          });
          poseRef.current.setOptions({
            modelComplexity: 1,
            minDetectionConfidence: 0.5,
          });
        }

        // Replace onResults handler for this image
        poseRef.current.onResults((results: any) => {
          if (!isActive) return;
          const landmarks = results.poseLandmarks;
          if (!landmarks) {
            setPoseStatus("upper");
            return;
          }

          const isVisible = (lm: any) => lm?.visibility > 0.4;
          const lKnee = landmarks[25],
            rKnee = landmarks[26];
          const lAnkle = landmarks[27],
            rAnkle = landmarks[28];

          if ((isVisible(lKnee) || isVisible(rKnee)) && (isVisible(lAnkle) || isVisible(rAnkle))) {
            setPoseStatus("full");
          } else {
            setPoseStatus("upper");
          }
        });

        const img = new Image();
        img.crossOrigin = "anonymous";
        img.onload = async () => {
          if (!isActive) return;
          await poseRef.current.send({ image: img });
        };
        img.src = personImage;
      } catch (e) {
        console.error("Pose detection failed:", e);
        if (isActive) setPoseStatus(null);
      }
    };

    void checkPose();

    return () => {
      isActive = false;
    };
  }, [personImage]);

  // Close MediaPipe on component unmount
  useEffect(() => {
    return () => {
      poseRef.current?.close();
      poseRef.current = null;
    };
  }, []);

  useEffect(() => {
    return () => {
      if (personImage?.startsWith("blob:")) URL.revokeObjectURL(personImage);
      if (clothingImage?.startsWith("blob:")) URL.revokeObjectURL(clothingImage);
    };
  }, [personImage, clothingImage]);

  const setPersonFromFile = useCallback((file: File) => {
    setPersonFile(file);
    setPersonImage((prev) => {
      if (prev?.startsWith("blob:")) URL.revokeObjectURL(prev);
      return URL.createObjectURL(file);
    });
  }, []);

  const setGarmentFromFile = useCallback(
    (file: File, info?: { name: string; brand?: string; sourceUrl?: string }) => {
      setGarmentFile(file);
      setClothingImage((prev) => {
        if (prev?.startsWith("blob:")) URL.revokeObjectURL(prev);
        return URL.createObjectURL(file);
      });
      setGarmentInfo({
        name: info?.name ?? file.name.replace(/\.[^.]+$/, ""),
        category,
        brand: info?.brand,
        sourceUrl: info?.sourceUrl,
      });
    },
    [category],
  );

  const handlePersonDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      const file = e.dataTransfer.files[0];
      if (file && file.type.startsWith("image/")) {
        setPersonFromFile(file);
      }
    },
    [setPersonFromFile],
  );

  const handlePersonFile = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (file) setPersonFromFile(file);
    },
    [setPersonFromFile],
  );

  const handleClothingFile = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (file) setGarmentFromFile(file);
    },
    [setGarmentFromFile],
  );

  const handleClothingDropWrap = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      const file = e.dataTransfer.files[0];
      if (file && file.type.startsWith("image/")) {
        setGarmentFromFile(file);
      }
    },
    [setGarmentFromFile],
  );

  const handleFetchUrl = useCallback(async () => {
    if (!productUrl.trim()) return;
    setFetchingUrl(true);
    try {
      const response = await fetchProductImage(productUrl.trim());
      const file = await urlToImageFile(response.url, "fetched-product.jpg");
      setGarmentFromFile(file, { name: "Fetched Product", sourceUrl: productUrl.trim() });
      toast.success("Successfully fetched product image!");
    } catch (error) {
      toast.error(getErrorMessage(error));
    } finally {
      setFetchingUrl(false);
    }
  }, [productUrl, setGarmentFromFile]);

  const pickSamplePerson = async (src: string) => {
    setLoadingSample("person");
    try {
      const file = await urlToImageFile(src, "sample-person.jpg");
      setPersonFromFile(file);
    } catch (error) {
      toast.error(getErrorMessage(error));
    } finally {
      setLoadingSample(null);
    }
  };

  const pickSampleGarment = async (g: (typeof SAMPLE_GARMENTS)[number]) => {
    setLoadingSample("garment");
    try {
      const file = await urlToImageFile(g.src, "sample-garment.jpg");
      setGarmentFromFile(file, { name: g.name, brand: g.brand });
      setCategory(g.category);
    } catch (error) {
      toast.error(getErrorMessage(error));
    } finally {
      setLoadingSample(null);
    }
  };

  const clearPerson = () => {
    setPersonFile(null);
    if (personImage?.startsWith("blob:")) URL.revokeObjectURL(personImage);
    setPersonImage(null);
  };

  const clearClothing = () => {
    setGarmentFile(null);
    if (clothingImage?.startsWith("blob:")) URL.revokeObjectURL(clothingImage);
    setClothingImage(null);
    setGarmentInfo(null);
    setProductUrl("");
  };

  const canGenerate = Boolean(personFile && garmentFile);
  const isSubmitting = createTryOn.isPending;

  const handleGenerate = () => {
    if (!personFile || !garmentFile) return;
    createTryOn.mutate(
      {
        personFile,
        garmentFile,
        garmentCategory: category,
        clothingName: garmentInfo?.name ?? category,
      },
      {
        onSuccess: (job) => {
          navigate({
            to: "/processing",
            search: { jobId: job.job_id },
          });
        },
        onError: (error) => {
          toast.error(getErrorMessage(error));
        },
      },
    );
  };

  const currentStep = 0; // Upload step

  return (
    <div className="mx-auto max-w-6xl px-4 py-12 sm:px-6 lg:px-8">
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
        className="text-center"
      >
        <Badge variant="secondary" className="mb-4 gap-1.5">
          <Sparkles className="h-3 w-3 text-copper" />
          AI Virtual Try-On Studio
        </Badge>
        <h1 className="font-heading text-3xl font-bold tracking-tight text-foreground sm:text-5xl">
          Build your look
        </h1>
        <p className="mx-auto mt-3 max-w-xl text-muted-foreground">
          Pick a photo of yourself and any upper-body garment — by image or product link. Our AI
          handles the rest.
        </p>
      </motion.div>

      {/* Progress indicator */}
      <ProgressSteps current={currentStep} />

      <div className="mt-10 grid gap-6 lg:grid-cols-5">
        {/* Left: Person */}
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4 }}
          className="lg:col-span-2"
        >
          <SectionCard step="01" title="Your photo" subtitle="A clear front-facing shot works best">
            <UploadArea
              label="Your Photo"
              description="Drop a photo or browse from your device"
              icon={<User className="h-6 w-6" />}
              image={personImage}
              onDrop={handlePersonDrop}
              onFileSelect={handlePersonFile}
              onClear={clearPerson}
            />

            {/* Pose status banner */}
            {poseStatus === "checking" && (
              <div className="mt-4 flex items-center gap-2 rounded-lg bg-muted/50 p-3 text-sm text-muted-foreground">
                <Loader2 className="h-4 w-4 animate-spin" />
                Checking photo suitability...
              </div>
            )}
            {poseStatus === "upper" && (
              <div className="mt-4 flex items-start gap-2 rounded-lg border border-amber-500/20 bg-amber-500/10 p-3 text-sm text-amber-600 dark:text-amber-500">
                <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
                <div>
                  <p className="font-medium">
                    For best results, use a full-body photo showing head to feet
                  </p>
                  <p className="mt-1 opacity-80">
                    You can still proceed, but the generated avatar might be cropped.
                  </p>
                </div>
              </div>
            )}
            {poseStatus === "full" && (
              <div className="mt-4 flex items-center gap-2 rounded-lg border border-emerald-500/20 bg-emerald-500/10 p-3 text-sm text-emerald-600 dark:text-emerald-500">
                <CheckCircle2 className="h-4 w-4 shrink-0" />
                <span className="font-medium">Great — full body detected</span>
              </div>
            )}

            {/* Photo tips collapsible section */}
            {personImage && (
              <div className="mt-4 rounded-xl border border-border/50 bg-muted/40 p-3">
                <button
                  type="button"
                  onClick={() => setAreTipsExpanded(!areTipsExpanded)}
                  className="flex w-full items-center justify-between text-left text-xs font-semibold text-foreground/80 hover:text-foreground focus:outline-none cursor-pointer"
                >
                  <span className="flex items-center gap-1.5 select-none">
                    📸 Photo tips for best results
                  </span>
                  {areTipsExpanded ? (
                    <ChevronUp className="h-3.5 w-3.5 text-muted-foreground" />
                  ) : (
                    <ChevronDown className="h-3.5 w-3.5 text-muted-foreground" />
                  )}
                </button>
                {areTipsExpanded && (
                  <ul className="mt-2 list-disc pl-4 space-y-1 text-[11px] text-muted-foreground leading-normal">
                    <li>Stand straight, face forward</li>
                    <li>Full body or waist-up shot</li>
                    <li>Good lighting (near a window works great)</li>
                    <li>Plain or simple background</li>
                    <li>Colour photo (not black & white)</li>
                    <li>Avoid heavy shadows or backlight</li>
                  </ul>
                )}
              </div>
            )}

            <div className="mt-4">
              <p className="mb-2 text-xs font-medium uppercase tracking-wider text-muted-foreground">
                Or try a sample
              </p>
              <div className="flex gap-2">
                {SAMPLE_PEOPLE.map((p) => (
                  <button
                    key={p.src}
                    type="button"
                    disabled={loadingSample !== null}
                    onClick={() => void pickSamplePerson(p.src)}
                    className={`group relative h-16 w-16 overflow-hidden rounded-lg border-2 transition ${
                      personImage === p.src
                        ? "border-copper ring-2 ring-copper/30"
                        : "border-border hover:border-foreground/40"
                    }`}
                  >
                    <img src={p.src} alt={p.label} className="h-full w-full object-cover" />
                  </button>
                ))}
              </div>
            </div>
          </SectionCard>
        </motion.div>

        {/* Right: Clothing */}
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, delay: 0.05 }}
          className="lg:col-span-3"
        >
          <SectionCard
            step="02"
            title="Choose a garment"
            subtitle="Upload your own or paste a product link"
          >
            <Tabs defaultValue="upload" className="w-full">
              <TabsList className="grid w-full grid-cols-2">
                <TabsTrigger value="upload" className="gap-1.5">
                  <ImageIcon className="h-3.5 w-3.5" />
                  Upload
                </TabsTrigger>
                <TabsTrigger value="url" className="gap-1.5">
                  <Link2 className="h-3.5 w-3.5" />
                  Product URL
                </TabsTrigger>
              </TabsList>

              <TabsContent value="upload" className="mt-4">
                <div className="grid gap-4 sm:grid-cols-2">
                  <UploadArea
                    label="Clothing Item"
                    description="PNG/JPG. Background auto-removed."
                    icon={<Shirt className="h-6 w-6" />}
                    image={clothingImage}
                    transparent
                    onDrop={handleClothingDropWrap}
                    onFileSelect={handleClothingFile}
                    onClear={clearClothing}
                  />
                  <GarmentInfoCard info={garmentInfo} category={category} />
                </div>
              </TabsContent>

              <TabsContent value="url" className="mt-4">
                <div className="rounded-xl border border-border bg-surface p-5">
                  <label className="mb-2 block text-sm font-medium text-foreground">
                    Paste product URL
                  </label>
                  <div className="flex gap-2">
                    <Input
                      value={productUrl}
                      onChange={(e) => setProductUrl(e.target.value)}
                      placeholder="https://myntra.com/... or amazon.in/..."
                      className="bg-background"
                    />
                    <Button
                      onClick={() => void handleFetchUrl()}
                      disabled={!productUrl.trim() || fetchingUrl}
                      className="gap-1.5 min-w-[100px]"
                    >
                      {fetchingUrl ? (
                        <Loader2 className="h-4 w-4 animate-spin" />
                      ) : (
                        <ArrowRight className="h-4 w-4" />
                      )}
                      {fetchingUrl ? "Fetching" : "Fetch"}
                    </Button>
                  </div>
                  <div className="mt-3 flex flex-wrap items-center gap-2">
                    <span className="text-xs text-muted-foreground">Supported:</span>
                    {SUPPORTED_STORES.map((s) => (
                      <Badge key={s} variant="outline" className="text-xs">
                        {s}
                      </Badge>
                    ))}
                  </div>
                  {clothingImage && garmentInfo?.sourceUrl && (
                    <div className="mt-4 grid gap-4 sm:grid-cols-2">
                      <div className="relative aspect-square overflow-hidden rounded-xl border border-border bg-[conic-gradient(at_50%_50%,_var(--muted)_0deg,_var(--background)_180deg,_var(--muted)_360deg)]">
                        <img
                          src={clothingImage}
                          alt="Garment"
                          className="h-full w-full object-contain mix-blend-multiply dark:mix-blend-normal"
                        />
                      </div>
                      <GarmentInfoCard info={garmentInfo} category={category} />
                    </div>
                  )}
                </div>
              </TabsContent>
            </Tabs>

            {/* Category selector */}
            <div className="mt-5">
              <p className="mb-2 text-xs font-medium uppercase tracking-wider text-muted-foreground">
                Garment category
              </p>
              <Select
                value={category}
                onValueChange={(val) => {
                  setCategory(val);
                  if (garmentInfo) {
                    setGarmentInfo({ ...garmentInfo, category: val });
                  }
                }}
              >
                <SelectTrigger className="w-full bg-card border-border hover:border-foreground/40 transition">
                  <SelectValue placeholder="Select a category" />
                </SelectTrigger>
                <SelectContent>
                  {GROUPED_CATEGORIES.map((group) => (
                    <SelectGroup key={group.label}>
                      <SelectLabel className="text-muted-foreground text-xs uppercase tracking-wider px-2 py-1">
                        {group.label}
                      </SelectLabel>
                      {group.options.map((opt) => (
                        <SelectItem key={opt} value={opt}>
                          {opt}
                        </SelectItem>
                      ))}
                    </SelectGroup>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {/* Sample garments */}
            <div className="mt-5">
              <p className="mb-2 text-xs font-medium uppercase tracking-wider text-muted-foreground">
                Or try a sample garment
              </p>
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                {SAMPLE_GARMENTS.map((g) => {
                  const active = clothingImage === g.src;
                  return (
                    <button
                      key={g.src}
                      type="button"
                      disabled={loadingSample !== null}
                      onClick={() => void pickSampleGarment(g)}
                      className={`group relative overflow-hidden rounded-lg border-2 bg-surface transition ${
                        active
                          ? "border-copper ring-2 ring-copper/30"
                          : "border-border hover:border-foreground/40"
                      }`}
                    >
                      <div className="aspect-square">
                        <img
                          src={g.src}
                          alt={g.name}
                          className="h-full w-full object-cover transition-transform group-hover:scale-105"
                        />
                      </div>
                      <div className="p-2 text-left">
                        <p className="truncate text-xs font-medium text-foreground">{g.name}</p>
                        <p className="text-[10px] text-muted-foreground">{g.category}</p>
                      </div>
                      {active && (
                        <div className="absolute right-2 top-2 rounded-full bg-copper p-0.5 text-copper-foreground">
                          <Check className="h-3 w-3" />
                        </div>
                      )}
                    </button>
                  );
                })}
              </div>
            </div>
          </SectionCard>
        </motion.div>
      </div>

      {/* Generate CTA */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, delay: 0.2 }}
        className="mt-10 flex flex-col items-center gap-2"
      >
        <Button
          size="lg"
          disabled={!canGenerate || isSubmitting}
          onClick={handleGenerate}
          className="h-12 gap-2 bg-foreground px-8 text-base text-background hover:bg-foreground/90 disabled:opacity-40"
        >
          {isSubmitting ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Sparkles className="h-4 w-4" />
          )}
          {isSubmitting ? "Uploading…" : "Generate Look"}
          {!isSubmitting && <ArrowRight className="h-4 w-4" />}
        </Button>
        {createTryOn.isError && (
          <p className="text-center text-sm text-destructive">
            {getErrorMessage(createTryOn.error)}
          </p>
        )}
        <p className="text-xs text-muted-foreground">
          {isSubmitting
            ? "Uploading images and starting your try-on…"
            : canGenerate
              ? "Ready — your try-on will be generated in ~20 seconds"
              : "Add a photo and a garment to continue"}
        </p>
      </motion.div>
    </div>
  );
}

function ProgressSteps({ current }: { current: number }) {
  return (
    <div className="mx-auto mt-10 max-w-3xl">
      <div className="flex items-center justify-between">
        {STEPS.map((label, i) => {
          const done = i < current;
          const active = i === current;
          return (
            <div key={label} className="flex flex-1 items-center last:flex-none">
              <div className="flex flex-col items-center">
                <div
                  className={`flex h-9 w-9 items-center justify-center rounded-full border text-xs font-semibold transition ${
                    done
                      ? "border-copper bg-copper text-copper-foreground"
                      : active
                        ? "border-foreground bg-foreground text-background"
                        : "border-border bg-card text-muted-foreground"
                  }`}
                >
                  {done ? <Check className="h-4 w-4" /> : i + 1}
                </div>
                <span
                  className={`mt-2 text-xs font-medium ${
                    active || done ? "text-foreground" : "text-muted-foreground"
                  }`}
                >
                  {label}
                </span>
              </div>
              {i < STEPS.length - 1 && (
                <div className="mx-2 h-px flex-1 bg-border sm:mx-4">
                  <div
                    className={`h-full transition-all ${done ? "bg-copper" : "bg-transparent"}`}
                  />
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

function SectionCard({
  step,
  title,
  subtitle,
  children,
}: {
  step: string;
  title: string;
  subtitle: string;
  children: React.ReactNode;
}) {
  return (
    <div className="rounded-2xl border border-border bg-card p-5 shadow-sm sm:p-6">
      <div className="mb-4 flex items-baseline gap-3">
        <span className="font-heading text-xs font-semibold text-copper">{step}</span>
        <div>
          <h2 className="font-heading text-lg font-semibold text-foreground">{title}</h2>
          <p className="text-xs text-muted-foreground">{subtitle}</p>
        </div>
      </div>
      {children}
    </div>
  );
}

function GarmentInfoCard({
  info,
  category,
}: {
  info: { name: string; category: string; brand?: string; sourceUrl?: string } | null;
  category: string;
}) {
  if (!info) {
    return (
      <div className="flex aspect-square flex-col items-center justify-center rounded-xl border border-dashed border-border bg-surface p-4 text-center">
        <Tag className="h-5 w-5 text-muted-foreground" />
        <p className="mt-2 text-sm font-medium text-foreground">No garment selected</p>
        <p className="mt-1 text-xs text-muted-foreground">
          Upload an image or paste a product URL to see details here.
        </p>
      </div>
    );
  }
  return (
    <div className="flex aspect-square flex-col justify-between rounded-xl border border-border bg-surface p-4">
      <div>
        <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
          <ShoppingBag className="h-3 w-3" />
          {info.brand || "Uploaded"}
        </div>
        <h3 className="mt-2 font-heading text-base font-semibold leading-tight text-foreground">
          {info.name}
        </h3>
        <Badge variant="secondary" className="mt-2 text-xs">
          {info.category || category}
        </Badge>
      </div>
      <div className="space-y-1.5 text-xs">
        <Row label="Background" value="Auto-removed" />
        <Row label="Fit detection" value="Upper body" />
        {info.sourceUrl && (
          <Row
            label="Source"
            value={
              <span className="truncate text-foreground" title={info.sourceUrl}>
                {new URL(info.sourceUrl).hostname.replace("www.", "")}
              </span>
            }
          />
        )}
      </div>
    </div>
  );
}

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-2 border-t border-border pt-1.5">
      <span className="text-muted-foreground">{label}</span>
      <span className="font-medium text-foreground">{value}</span>
    </div>
  );
}

function UploadArea({
  label,
  description,
  icon,
  image,
  transparent,
  onDrop,
  onFileSelect,
  onClear,
}: {
  label: string;
  description: string;
  icon: React.ReactNode;
  image: string | null;
  transparent?: boolean;
  onDrop: (e: React.DragEvent) => void;
  onFileSelect: (e: React.ChangeEvent<HTMLInputElement>) => void;
  onClear: () => void;
}) {
  const [dragOver, setDragOver] = useState(false);

  return (
    <div
      onDragOver={(e) => {
        e.preventDefault();
        setDragOver(true);
      }}
      onDragLeave={() => setDragOver(false)}
      onDrop={(e) => {
        setDragOver(false);
        onDrop(e);
      }}
      className={`relative overflow-hidden rounded-2xl border-2 border-dashed transition-colors ${
        dragOver
          ? "border-copper bg-copper/5"
          : "border-border bg-surface hover:border-foreground/30"
      }`}
    >
      {image ? (
        <div className="relative aspect-square">
          {transparent ? (
            <div
              className="h-full w-full"
              style={{
                backgroundImage:
                  "linear-gradient(45deg, var(--muted) 25%, transparent 25%), linear-gradient(-45deg, var(--muted) 25%, transparent 25%), linear-gradient(45deg, transparent 75%, var(--muted) 75%), linear-gradient(-45deg, transparent 75%, var(--muted) 75%)",
                backgroundSize: "16px 16px",
                backgroundPosition: "0 0, 0 8px, 8px -8px, -8px 0",
              }}
            >
              <img
                src={image}
                alt={label}
                className="h-full w-full object-contain mix-blend-multiply dark:mix-blend-normal"
              />
            </div>
          ) : (
            <img src={image} alt={label} className="h-full w-full object-cover" />
          )}
          <button
            onClick={onClear}
            className="absolute right-3 top-3 rounded-full bg-background/90 p-1.5 text-foreground backdrop-blur-sm transition-colors hover:bg-destructive hover:text-destructive-foreground"
          >
            <X className="h-4 w-4" />
          </button>
          <div className="absolute bottom-3 left-3 rounded-lg bg-background/90 px-2.5 py-1 text-xs font-medium text-foreground backdrop-blur-sm">
            {transparent ? "Background removed" : label}
          </div>
        </div>
      ) : (
        <label className="flex aspect-square cursor-pointer flex-col items-center justify-center p-8">
          <div className="flex h-14 w-14 items-center justify-center rounded-xl bg-secondary text-foreground">
            {icon}
          </div>
          <p className="mt-4 font-heading text-base font-semibold text-foreground">{label}</p>
          <p className="mt-1 text-center text-sm text-muted-foreground">{description}</p>
          <div className="mt-4 flex items-center gap-2 rounded-lg bg-secondary px-4 py-2 text-sm font-medium text-foreground">
            <Upload className="h-4 w-4" />
            Click or drag to upload
          </div>
          <input type="file" accept="image/*" onChange={onFileSelect} className="hidden" />
        </label>
      )}
    </div>
  );
}
