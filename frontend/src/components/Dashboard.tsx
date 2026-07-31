import { Link } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import {
  Box,
  Shirt,
  Sparkles,
  Ruler,
  Palette,
  Users,
  ArrowRight,
  CheckCircle2,
  Plus,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { API_BASE_URL } from "@/lib/api";
import { useAuth } from "@/lib/useAuth";

interface StoredAvatar {
  sessionId: string;
  avatarUrl: string;
  analysis: { face_thumbnail_url?: string | null } | null;
  savedAt: number;
}

const TOOLS = [
  { to: "/try-on", icon: Shirt, title: "2D Try-On", desc: "See any outfit on your photo in seconds." },
  { to: "/wardrobe", icon: Box, title: "Wardrobe", desc: "Save garments and build outfits." },
  { to: "/stylist", icon: Sparkles, title: "AI Stylist", desc: "Chat for outfit ideas and shopping." },
  { to: "/size", icon: Ruler, title: "My Size", desc: "Get your size across brands." },
  { to: "/colors", icon: Palette, title: "Colors", desc: "Find shades that suit you." },
  { to: "/feed", icon: Users, title: "Feed", desc: "Share fits and get votes." },
] as const;

export function Dashboard() {
  const { user } = useAuth();
  const [avatar, setAvatar] = useState<StoredAvatar | null>(null);
  const [wardrobeCount, setWardrobeCount] = useState<number | null>(null);

  useEffect(() => {
    try {
      const raw = localStorage.getItem("fitcheck:last-avatar");
      if (raw) setAvatar(JSON.parse(raw));
    } catch {
      /* ignore */
    }
    // Token is attached automatically by the auth fetch wrapper
    fetch(`${API_BASE_URL}/api/v1/wardrobe/items`)
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => setWardrobeCount(d?.items?.length ?? 0))
      .catch(() => setWardrobeCount(null));
  }, []);

  const name = user?.display_name || user?.email.split("@")[0] || "there";
  const hasAvatar = !!avatar?.avatarUrl;

  return (
    <section className="mx-auto max-w-6xl px-4 py-10 sm:px-6 lg:px-8">
      {/* Greeting */}
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.35 }}
      >
        <h1 className="font-heading text-3xl font-bold tracking-tight text-foreground">
          Welcome back, {name} 👋
        </h1>
        <p className="mt-1 text-muted-foreground">
          {hasAvatar
            ? "Your avatar's ready. Pick something to try on."
            : "Start by creating your 3D avatar — everything else builds on it."}
        </p>
      </motion.div>

      {/* Primary card — state-aware next step */}
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, delay: 0.05 }}
        className="mt-6 overflow-hidden rounded-2xl border border-border bg-card"
      >
        <div className="flex flex-col items-start gap-6 p-6 sm:flex-row sm:items-center sm:justify-between sm:p-8">
          <div className="flex items-center gap-5">
            <div className="flex h-16 w-16 shrink-0 items-center justify-center overflow-hidden rounded-2xl bg-muted">
              {avatar?.analysis?.face_thumbnail_url ? (
                <img
                  src={avatar.analysis.face_thumbnail_url}
                  alt="Your avatar"
                  className="h-full w-full object-cover"
                />
              ) : (
                <Box className="h-7 w-7 text-muted-foreground" />
              )}
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="font-heading text-lg font-semibold text-foreground">
                  {hasAvatar ? "Your 3D avatar" : "Create your 3D avatar"}
                </h2>
                {hasAvatar && (
                  <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 px-2 py-0.5 text-xs font-medium text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300">
                    <CheckCircle2 className="h-3 w-3" /> Ready
                  </span>
                )}
              </div>
              <p className="mt-1 max-w-md text-sm text-muted-foreground">
                {hasAvatar
                  ? "View it, rotate it, or drape garments onto it in 3D."
                  : "Upload one full-body photo — we build a photoreal 3D you to try clothes on."}
              </p>
            </div>
          </div>
          <Link to="/avatar" className="w-full sm:w-auto">
            <Button
              size="lg"
              className="w-full gap-2 bg-foreground text-background hover:bg-foreground/90 sm:w-auto"
            >
              {hasAvatar ? "Open avatar" : "Create avatar"}
              <ArrowRight className="h-4 w-4" />
            </Button>
          </Link>
        </div>
      </motion.div>

      {/* Quick actions */}
      <div className="mt-8">
        <h3 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground">
          Explore
        </h3>
        <div className="mt-3 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {TOOLS.map((t, i) => (
            <motion.div
              key={t.to}
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.3, delay: 0.08 + i * 0.04 }}
            >
              <Link
                to={t.to}
                className="group flex h-full flex-col rounded-2xl border border-border bg-card p-5 transition-colors hover:border-foreground/30 hover:bg-accent/40"
              >
                <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-muted text-foreground">
                  <t.icon className="h-5 w-5" />
                </div>
                <div className="mt-4 flex items-center gap-1.5">
                  <span className="font-heading font-semibold text-foreground">{t.title}</span>
                  <ArrowRight className="h-3.5 w-3.5 text-muted-foreground opacity-0 transition-opacity group-hover:opacity-100" />
                </div>
                <p className="mt-1 text-sm text-muted-foreground">{t.desc}</p>
              </Link>
            </motion.div>
          ))}
        </div>
      </div>

      {/* Stats */}
      <div className="mt-8 grid grid-cols-2 gap-4 sm:grid-cols-3">
        <StatCard label="Avatar" value={hasAvatar ? "Ready" : "Not yet"} />
        <StatCard
          label="Wardrobe items"
          value={wardrobeCount === null ? "—" : String(wardrobeCount)}
        />
        <Link
          to="/wardrobe"
          className="flex items-center justify-between rounded-2xl border border-dashed border-border bg-card p-5 text-sm text-muted-foreground transition-colors hover:border-foreground/30 hover:text-foreground"
        >
          <span className="flex items-center gap-2">
            <Plus className="h-4 w-4" /> Add a garment
          </span>
          <ArrowRight className="h-4 w-4" />
        </Link>
      </div>
    </section>
  );
}

function StatCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-border bg-card p-5">
      <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
        {label}
      </p>
      <p className="mt-1 font-heading text-2xl font-bold text-foreground">{value}</p>
    </div>
  );
}
