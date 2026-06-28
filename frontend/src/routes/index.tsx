import { createFileRoute, Link } from "@tanstack/react-router";
import { motion } from "framer-motion";
import {
  Upload,
  Sparkles,
  Zap,
  Download,
  History,
  Shield,
  ChevronDown,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import { features, howItWorks, faqs } from "@/lib/mock-data";
import heroImg from "@/assets/hero.jpg";
import result1 from "@/assets/result-1.jpg";
import result2 from "@/assets/result-2.jpg";

const iconMap: Record<string, React.ReactNode> = {
  Upload: <Upload className="h-5 w-5" />,
  Sparkles: <Sparkles className="h-5 w-5" />,
  Zap: <Zap className="h-5 w-5" />,
  Download: <Download className="h-5 w-5" />,
  History: <History className="h-5 w-5" />,
  Shield: <Shield className="h-5 w-5" />,
};

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "FitCheck AI — Virtual Try-On Platform" },
      { name: "description", content: "AI-powered virtual try-on. Upload your photo and any clothing item to see how it looks on you before buying." },
      { property: "og:title", content: "FitCheck AI — Virtual Try-On Platform" },
      { property: "og:description", content: "AI-powered virtual try-on. Upload your photo and any clothing item to see how it looks on you before buying." },
    ],
  }),
  component: Index,
});

function Index() {
  return (
    <>
      {/* Hero Section */}
      <section className="relative overflow-hidden border-b border-border">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <div className="grid min-h-[85vh] items-center gap-12 lg:grid-cols-2">
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6 }}
              className="flex flex-col justify-center py-16 lg:py-0"
            >
              <div className="inline-flex w-fit items-center gap-2 rounded-full border border-border bg-surface px-3 py-1.5 text-xs font-medium text-muted-foreground">
                <Sparkles className="h-3 w-3" />
                AI-Powered Fashion Tech
              </div>
              <h1 className="mt-6 font-heading text-4xl font-bold tracking-tight text-foreground sm:text-5xl lg:text-6xl">
                See How Every
                <br />
                <span className="text-copper">Outfit Looks</span> on You
              </h1>
              <p className="mt-6 max-w-lg text-lg leading-relaxed text-muted-foreground">
                Upload your photo and any upper-body clothing item. Our AI generates a
                photorealistic try-on in seconds — so you shop with confidence.
              </p>
              <div className="mt-8 flex flex-wrap gap-4">
                <Link to="/try-on">
                  <Button
                    size="lg"
                    className="bg-foreground text-background hover:bg-foreground/90"
                  >
                    Try It Now
                  </Button>
                </Link>
                <Link to="/history">
                  <Button variant="outline" size="lg">
                    View Examples
                  </Button>
                </Link>
              </div>
              <div className="mt-10 flex items-center gap-6 text-sm text-muted-foreground">
                <div className="flex -space-x-2">
                  <div className="h-8 w-8 rounded-full border-2 border-background bg-secondary" />
                  <div className="h-8 w-8 rounded-full border-2 border-background bg-secondary" />
                  <div className="h-8 w-8 rounded-full border-2 border-background bg-secondary" />
                </div>
                <span>Trusted by 10,000+ fashion enthusiasts</span>
              </div>
            </motion.div>

            <motion.div
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ duration: 0.8, delay: 0.2 }}
              className="relative hidden lg:block"
            >
              <div className="relative overflow-hidden rounded-2xl border border-border">
                <img
                  src={heroImg}
                  alt="AI Fashion Try-On Visualization"
                  className="h-auto w-full object-cover"
                  width={1536}
                  height={1024}
                />
              </div>
              <div className="absolute -bottom-4 -left-4 rounded-xl border border-border bg-card p-4 shadow-lg">
                <div className="flex items-center gap-3">
                  <div className="flex h-10 w-10 items-center justify-center rounded-full bg-copper/10">
                    <Sparkles className="h-5 w-5 text-copper" />
                  </div>
                  <div>
                    <p className="text-sm font-medium text-foreground">AI Generated</p>
                    <p className="text-xs text-muted-foreground">in 23 seconds</p>
                  </div>
                </div>
              </div>
            </motion.div>
          </div>
        </div>
      </section>

      {/* Product Demo */}
      <section className="border-b border-border py-24">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.6 }}
            className="text-center"
          >
            <h2 className="font-heading text-3xl font-bold tracking-tight text-foreground sm:text-4xl">
              Before & After
            </h2>
            <p className="mx-auto mt-4 max-w-2xl text-lg text-muted-foreground">
              See the transformation from a simple photo to a realistic try-on result.
            </p>
          </motion.div>

          <div className="mt-16 grid gap-8 md:grid-cols-2">
            <DemoCard
              beforeLabel="Original Photo"
              afterLabel="AI Try-On Result"
              resultImage={result1}
              clothing="Navy Cotton T-Shirt"
            />
            <DemoCard
              beforeLabel="Original Photo"
              afterLabel="AI Try-On Result"
              resultImage={result2}
              clothing="Beige Linen Blazer"
            />
          </div>
        </div>
      </section>

      {/* Features */}
      <section className="border-b border-border py-24">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.6 }}
            className="text-center"
          >
            <h2 className="font-heading text-3xl font-bold tracking-tight text-foreground sm:text-4xl">
              Everything You Need
            </h2>
            <p className="mx-auto mt-4 max-w-2xl text-lg text-muted-foreground">
              A complete virtual try-on experience built with modern AI technology.
            </p>
          </motion.div>

          <div className="mt-16 grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
            {features.map((feature, i) => (
              <motion.div
                key={feature.title}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ duration: 0.5, delay: i * 0.1 }}
                className="group rounded-2xl border border-border bg-card p-6 transition-colors hover:border-foreground/20"
              >
                <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-secondary text-foreground">
                  {iconMap[feature.icon]}
                </div>
                <h3 className="mt-4 font-heading text-lg font-semibold text-foreground">
                  {feature.title}
                </h3>
                <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
                  {feature.description}
                </p>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* How It Works */}
      <section className="border-b border-border py-24">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.6 }}
            className="text-center"
          >
            <h2 className="font-heading text-3xl font-bold tracking-tight text-foreground sm:text-4xl">
              How It Works
            </h2>
            <p className="mx-auto mt-4 max-w-2xl text-lg text-muted-foreground">
              Four simple steps to your perfect virtual try-on.
            </p>
          </motion.div>

          <div className="mt-16 grid gap-8 sm:grid-cols-2 lg:grid-cols-4">
            {howItWorks.map((step, i) => (
              <motion.div
                key={step.step}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ duration: 0.5, delay: i * 0.1 }}
                className="relative"
              >
                <span className="font-heading text-6xl font-bold text-border">
                  {step.step}
                </span>
                <h3 className="mt-4 font-heading text-lg font-semibold text-foreground">
                  {step.title}
                </h3>
                <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
                  {step.description}
                </p>
                {i < howItWorks.length - 1 && (
                  <div className="absolute -right-4 top-8 hidden lg:block">
                    <ChevronDown className="h-5 w-5 rotate-[-90deg] text-border" />
                  </div>
                )}
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* FAQ */}
      <section className="border-b border-border py-24">
        <div className="mx-auto max-w-3xl px-4 sm:px-6 lg:px-8">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.6 }}
            className="text-center"
          >
            <h2 className="font-heading text-3xl font-bold tracking-tight text-foreground sm:text-4xl">
              Frequently Asked Questions
            </h2>
            <p className="mx-auto mt-4 max-w-xl text-lg text-muted-foreground">
              Got questions? We have answers.
            </p>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.6, delay: 0.2 }}
            className="mt-12"
          >
            <Accordion type="single" collapsible className="w-full">
              {faqs.map((faq, i) => (
                <AccordionItem key={i} value={`item-${i}`} className="border-border">
                  <AccordionTrigger className="text-left text-foreground hover:no-underline">
                    {faq.question}
                  </AccordionTrigger>
                  <AccordionContent className="text-muted-foreground">
                    {faq.answer}
                  </AccordionContent>
                </AccordionItem>
              ))}
            </Accordion>
          </motion.div>
        </div>
      </section>

      {/* CTA */}
      <section className="py-24">
        <div className="mx-auto max-w-4xl px-4 text-center sm:px-6 lg:px-8">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.6 }}
          >
            <h2 className="font-heading text-3xl font-bold tracking-tight text-foreground sm:text-4xl">
              Ready to Try It On?
            </h2>
            <p className="mx-auto mt-4 max-w-xl text-lg text-muted-foreground">
              Join thousands of fashion enthusiasts who never buy blind again.
            </p>
            <div className="mt-8 flex justify-center gap-4">
              <Link to="/try-on">
                <Button
                  size="lg"
                  className="bg-foreground text-background hover:bg-foreground/90"
                >
                  Start Your Try-On
                </Button>
              </Link>
            </div>
          </motion.div>
        </div>
      </section>
    </>
  );
}

function DemoCard({
  beforeLabel,
  afterLabel,
  resultImage,
  clothing,
}: {
  beforeLabel: string;
  afterLabel: string;
  resultImage: string;
  clothing: string;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true }}
      transition={{ duration: 0.6 }}
      className="overflow-hidden rounded-2xl border border-border bg-card"
    >
      <div className="relative aspect-square overflow-hidden">
        <img
          src={resultImage}
          alt={afterLabel}
          className="h-full w-full object-cover"
          width={1024}
          height={1024}
        />
        <div className="absolute bottom-4 left-4 rounded-lg bg-background/90 px-3 py-1.5 text-xs font-medium text-foreground backdrop-blur-sm">
          {afterLabel}
        </div>
      </div>
      <div className="p-4">
        <p className="text-sm font-medium text-foreground">{clothing}</p>
        <p className="text-xs text-muted-foreground">AI-generated in 23 seconds</p>
      </div>
    </motion.div>
  );
}
