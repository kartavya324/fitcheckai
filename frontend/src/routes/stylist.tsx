import { createFileRoute } from "@tanstack/react-router";
import { useState, useRef, useEffect } from "react";
import { motion } from "framer-motion";
import { Sparkles, Send, Loader2, ShoppingBag, ExternalLink } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  useStylistChat,
  getErrorMessage,
  type StylistMessage,
  type StylistProduct,
} from "@/lib/api";

export const Route = createFileRoute("/stylist")({
  head: () => ({
    meta: [
      { title: "AI Stylist — FitCheck AI" },
      {
        name: "description",
        content: "Chat with an AI stylist that finds real clothing to buy within your budget.",
      },
    ],
  }),
  component: StylistPage,
});

interface ChatTurn {
  role: "user" | "assistant";
  content: string;
  products?: StylistProduct[];
}

const SUGGESTIONS = [
  "Find me a black hoodie under ₹2500",
  "Formal shoes for a wedding under ₹4000",
  "A linen shirt for summer",
];

function StylistPage() {
  const [turns, setTurns] = useState<ChatTurn[]>([]);
  const [input, setInput] = useState("");
  const chat = useStylistChat();
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [turns, chat.isPending]);

  const send = (text: string) => {
    const message = text.trim();
    if (!message || chat.isPending) return;

    const nextTurns: ChatTurn[] = [...turns, { role: "user", content: message }];
    setTurns(nextTurns);
    setInput("");

    const history: StylistMessage[] = nextTurns.map((t) => ({
      role: t.role,
      content: t.content,
    }));

    chat.mutate(history, {
      onSuccess: (res) => {
        setTurns((prev) => [
          ...prev,
          { role: "assistant", content: res.reply, products: res.products },
        ]);
      },
      onError: (e) => toast.error(getErrorMessage(e)),
    });
  };

  return (
    <div className="mx-auto flex h-[calc(100vh-4rem)] max-w-3xl flex-col px-4 py-6 sm:px-6">
      <div className="mb-4 flex items-center gap-2">
        <Sparkles className="h-5 w-5 text-copper" />
        <h1 className="font-heading text-xl font-bold text-foreground">AI Stylist</h1>
      </div>

      {/* Conversation */}
      <div ref={scrollRef} className="flex-1 space-y-4 overflow-y-auto pb-4">
        {turns.length === 0 && (
          <div className="flex h-full flex-col items-center justify-center text-center">
            <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-secondary">
              <ShoppingBag className="h-6 w-6 text-foreground" />
            </div>
            <p className="mt-4 max-w-sm text-muted-foreground">
              Tell me what you're looking for and your budget — I'll find real
              options you can buy.
            </p>
            <div className="mt-5 flex flex-wrap justify-center gap-2">
              {SUGGESTIONS.map((s) => (
                <button
                  key={s}
                  onClick={() => send(s)}
                  className="rounded-full border border-border bg-card px-3 py-1.5 text-sm text-foreground transition hover:border-foreground/40"
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}

        {turns.map((turn, i) => (
          <motion.div
            key={i}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            className={turn.role === "user" ? "flex justify-end" : "flex justify-start"}
          >
            <div className={turn.role === "user" ? "max-w-[85%]" : "w-full max-w-[95%]"}>
              <div
                className={`rounded-2xl px-4 py-2.5 text-sm ${
                  turn.role === "user"
                    ? "bg-foreground text-background"
                    : "bg-card border border-border text-foreground"
                }`}
              >
                <p className="whitespace-pre-wrap leading-relaxed">{turn.content}</p>
              </div>
              {turn.products && turn.products.length > 0 && (
                <div className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-3">
                  {turn.products.map((p, j) => (
                    <ProductCard key={j} product={p} />
                  ))}
                </div>
              )}
            </div>
          </motion.div>
        ))}

        {chat.isPending && (
          <div className="flex justify-start">
            <div className="flex items-center gap-2 rounded-2xl border border-border bg-card px-4 py-2.5 text-sm text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" />
              Styling & searching…
            </div>
          </div>
        )}
      </div>

      {/* Composer */}
      <form
        onSubmit={(e) => {
          e.preventDefault();
          send(input);
        }}
        className="mt-2 flex gap-2 border-t border-border pt-4"
      >
        <Input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="e.g. a navy blazer under ₹5000"
          disabled={chat.isPending}
          className="bg-card"
        />
        <Button type="submit" disabled={!input.trim() || chat.isPending} className="gap-1.5">
          {chat.isPending ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Send className="h-4 w-4" />
          )}
        </Button>
      </form>
    </div>
  );
}

function ProductCard({ product }: { product: StylistProduct }) {
  const href = product.link ?? undefined;
  return (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className="group flex flex-col overflow-hidden rounded-xl border border-border bg-card transition hover:border-foreground/40"
    >
      <div className="aspect-square bg-surface">
        {product.thumbnail ? (
          <img
            src={product.thumbnail}
            alt={product.title ?? "Product"}
            className="h-full w-full object-contain p-2"
          />
        ) : (
          <div className="flex h-full w-full items-center justify-center">
            <ShoppingBag className="h-6 w-6 text-muted-foreground" />
          </div>
        )}
      </div>
      <div className="flex flex-1 flex-col gap-1 p-2">
        <p className="line-clamp-2 text-xs font-medium text-foreground">{product.title}</p>
        <div className="mt-auto flex items-center justify-between pt-1">
          <span className="text-sm font-semibold text-foreground">
            {product.price_str ?? (product.price != null ? `₹${product.price}` : "")}
          </span>
          <ExternalLink className="h-3.5 w-3.5 text-muted-foreground opacity-0 transition group-hover:opacity-100" />
        </div>
        {product.source && (
          <span className="truncate text-[10px] text-muted-foreground">{product.source}</span>
        )}
      </div>
    </a>
  );
}
