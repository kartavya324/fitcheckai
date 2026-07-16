import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { motion } from "framer-motion";
import { Ruler, Sparkles, Loader2, Info } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  useSizeRecommendation,
  getErrorMessage,
  type SizeResponse,
} from "@/lib/api";

export const Route = createFileRoute("/size")({
  head: () => ({
    meta: [
      { title: "Find My Size — FitCheck AI" },
      {
        name: "description",
        content: "Get your recommended clothing size per brand from your measurements.",
      },
    ],
  }),
  component: SizePage,
});

const BRANDS = ["Generic", "Zara", "H&M", "Uniqlo", "Nike", "Adidas", "Levi's", "Roadster", "Allen Solly"];

function SizePage() {
  const [height, setHeight] = useState("");
  const [weight, setWeight] = useState("");
  const [sex, setSex] = useState<"male" | "female">("male");
  const [fit, setFit] = useState<"fitted" | "regular" | "relaxed">("regular");
  const [brand, setBrand] = useState("Generic");
  const [result, setResult] = useState<SizeResponse | null>(null);
  const rec = useSizeRecommendation();

  const submit = () => {
    const h = parseFloat(height);
    const w = parseFloat(weight);
    if (!h || !w) {
      toast.error("Enter your height and weight");
      return;
    }
    rec.mutate(
      {
        height_cm: h,
        weight_kg: w,
        sex,
        fit_preference: fit,
        brand: brand === "Generic" ? null : brand,
      },
      {
        onSuccess: setResult,
        onError: (e) => toast.error(getErrorMessage(e)),
      },
    );
  };

  return (
    <div className="mx-auto max-w-3xl px-4 py-12 sm:px-6">
      <div className="text-center">
        <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl bg-secondary">
          <Ruler className="h-6 w-6 text-foreground" />
        </div>
        <h1 className="mt-4 font-heading text-3xl font-bold text-foreground">Find my size</h1>
        <p className="mx-auto mt-2 max-w-md text-muted-foreground">
          Enter your details and we'll recommend a size — adjusted for the brand and how you like clothes to fit.
        </p>
      </div>

      {/* Form */}
      <div className="mt-8 rounded-2xl border border-border bg-card p-5 sm:p-6">
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Height (cm)">
            <Input type="number" inputMode="numeric" value={height} onChange={(e) => setHeight(e.target.value)} placeholder="178" />
          </Field>
          <Field label="Weight (kg)">
            <Input type="number" inputMode="numeric" value={weight} onChange={(e) => setWeight(e.target.value)} placeholder="75" />
          </Field>
          <Field label="Sex">
            <Select value={sex} onValueChange={(v) => setSex(v as "male" | "female")}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="male">Male</SelectItem>
                <SelectItem value="female">Female</SelectItem>
              </SelectContent>
            </Select>
          </Field>
          <Field label="Fit preference">
            <Select value={fit} onValueChange={(v) => setFit(v as typeof fit)}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="fitted">Fitted</SelectItem>
                <SelectItem value="regular">Regular</SelectItem>
                <SelectItem value="relaxed">Relaxed</SelectItem>
              </SelectContent>
            </Select>
          </Field>
          <Field label="Brand">
            <Select value={brand} onValueChange={setBrand}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>
                {BRANDS.map((b) => (
                  <SelectItem key={b} value={b}>{b}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </Field>
        </div>
        <Button onClick={submit} disabled={rec.isPending} className="mt-5 w-full gap-2 bg-foreground text-background hover:bg-foreground/90" size="lg">
          {rec.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
          {rec.isPending ? "Calculating…" : "Recommend my size"}
        </Button>
      </div>

      {/* Result */}
      {result && (
        <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} className="mt-6 space-y-4">
          <div className="grid gap-4 sm:grid-cols-2">
            {result.recommendations.map((r) => (
              <div key={r.category} className="rounded-2xl border border-border bg-card p-5 text-center">
                <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
                  {r.category === "tops" ? "Tops" : "Bottoms"}
                </p>
                <p className="mt-1 font-heading text-4xl font-bold text-foreground">{r.size}</p>
                {r.between_size && (
                  <p className="mt-1 text-xs text-copper">You're between sizes — {r.between_size} may also work</p>
                )}
                <p className="mt-2 text-xs text-muted-foreground">
                  {r.category === "tops" ? "Chest" : "Waist"} {r.range_cm[0]}–{r.range_cm[1] ?? "+"} cm
                </p>
              </div>
            ))}
          </div>

          <div className="rounded-xl border border-border bg-muted/30 p-4 text-sm">
            <p className="text-muted-foreground">
              Estimated chest <span className="font-medium text-foreground">~{result.measurements.chest_cm} cm</span>,
              waist <span className="font-medium text-foreground">~{result.measurements.waist_cm} cm</span>
              {" "}(BMI {result.measurements.bmi}) · {result.brand}
            </p>
            {result.notes.length > 0 && (
              <ul className="mt-2 space-y-1">
                {result.notes.map((n, i) => (
                  <li key={i} className="text-xs text-foreground">• {n}</li>
                ))}
              </ul>
            )}
            <p className="mt-3 flex items-start gap-1.5 border-t border-border/60 pt-3 text-xs text-muted-foreground">
              <Info className="mt-0.5 h-3.5 w-3.5 shrink-0" />
              {result.disclaimer}
            </p>
          </div>
        </motion.div>
      )}
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <label className="mb-1.5 block text-sm font-medium text-foreground">{label}</label>
      {children}
    </div>
  );
}
