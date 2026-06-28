import { createFileRoute, Link } from "@tanstack/react-router";
import { useState } from "react";
import { motion } from "framer-motion";
import { Search, Clock, ArrowRight, ImageOff, Shirt, AlertCircle, Loader2 } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { useJobs } from "@/lib/api";

export const Route = createFileRoute("/history")({
  head: () => ({
    meta: [
      { title: "History — FitCheck AI" },
      { name: "description", content: "View all your past AI-generated virtual try-ons." },
    ],
  }),
  component: HistoryPage,
});

function getRelativeTime(dateStr: string) {
  const date = new Date(dateStr);
  const diff = Math.floor((new Date().getTime() - date.getTime()) / 1000);
  
  if (diff < 60) return "Just now";
  if (diff < 3600) return `${Math.floor(diff / 60)} min${Math.floor(diff / 60) > 1 ? "s" : ""} ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)} hour${Math.floor(diff / 3600) > 1 ? "s" : ""} ago`;
  if (diff < 2592000) return `${Math.floor(diff / 86400)} day${Math.floor(diff / 86400) > 1 ? "s" : ""} ago`;
  return date.toLocaleDateString();
}

function HistoryPage() {
  const [search, setSearch] = useState("");
  const [limit, setLimit] = useState(20);

  const { data, isLoading, isError } = useJobs(limit, 0);

  const jobs = data?.items || [];
  const total = data?.total || 0;

  const filtered = jobs.filter((item) =>
    item.garment_category.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="mx-auto max-w-6xl px-4 py-12 sm:px-6 lg:px-8">
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
      >
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h1 className="font-heading text-3xl font-bold tracking-tight text-foreground">
              Try-On History
            </h1>
            <p className="mt-1 text-muted-foreground">
              {total} outfit{total !== 1 ? "s" : ""} generated
            </p>
          </div>
          <div className="relative w-full sm:w-72">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              placeholder="Search by category..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="pl-9"
            />
          </div>
        </div>

        {isError ? (
          <div className="mt-16 flex flex-col items-center justify-center text-center">
            <AlertCircle className="h-12 w-12 text-destructive" />
            <h3 className="mt-4 font-heading text-lg font-semibold text-foreground">
              Failed to load history
            </h3>
            <p className="mt-1 text-muted-foreground">
              There was an error connecting to the server.
            </p>
          </div>
        ) : isLoading ? (
          <div className="mt-10 grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
            {Array.from({ length: 6 }).map((_, i) => (
              <div key={i} className="h-[320px] rounded-2xl bg-muted/50 animate-pulse border border-border" />
            ))}
          </div>
        ) : jobs.length === 0 ? (
          <div className="mt-16 flex flex-col items-center justify-center text-center">
            <Shirt className="h-12 w-12 text-muted-foreground" />
            <h3 className="mt-4 font-heading text-lg font-semibold text-foreground">
              No try-ons yet
            </h3>
            <p className="mt-1 text-muted-foreground">
              Create your first one to see your history here.
            </p>
            <Link to="/try-on" className="mt-6">
              <Button className="bg-foreground text-background hover:bg-foreground/90">
                Try On Now
              </Button>
            </Link>
          </div>
        ) : filtered.length === 0 ? (
          <div className="mt-16 flex flex-col items-center justify-center text-center">
            <ImageOff className="h-12 w-12 text-muted-foreground" />
            <h3 className="mt-4 font-heading text-lg font-semibold text-foreground">
              No results found
            </h3>
            <p className="mt-1 text-muted-foreground">
              Try a different search term.
            </p>
          </div>
        ) : (
          <>
            <div className="mt-10 grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
              {filtered.map((item, i) => (
                <motion.div
                  key={item.job_id}
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.4, delay: i * 0.05 }}
                  className="group overflow-hidden rounded-2xl border border-border bg-card transition-colors hover:border-foreground/20"
                >
                  <div className="relative aspect-[4/3] overflow-hidden bg-muted/30">
                    {item.result_url ? (
                      <img
                        src={item.result_url}
                        alt={item.garment_category}
                        className="h-full w-full object-cover transition-transform duration-500 group-hover:scale-105"
                        loading="lazy"
                      />
                    ) : (
                      <div className="flex h-full w-full items-center justify-center text-muted-foreground/50">
                        {item.status === "failed" ? (
                          <AlertCircle className="h-8 w-8 text-destructive/50" />
                        ) : (
                          <Loader2 className="h-8 w-8 animate-spin" />
                        )}
                      </div>
                    )}
                    
                    <div className="absolute right-3 top-3 rounded-full bg-background/80 px-2.5 py-1 text-xs font-semibold uppercase tracking-wide backdrop-blur-sm shadow-sm">
                      <span className={
                        item.status === "completed" ? "text-green-600 dark:text-green-400" :
                        item.status === "failed" ? "text-red-600 dark:text-red-400" :
                        "text-copper"
                      }>
                        {item.status}
                      </span>
                    </div>
                  </div>
                  <div className="p-4">
                    <div className="flex items-start justify-between gap-2">
                      <div>
                        <h3 className="font-heading text-sm font-semibold text-foreground capitalize">
                          {item.garment_category}
                        </h3>
                        <div className="mt-1 flex items-center gap-1.5 text-xs text-muted-foreground">
                          <Clock className="h-3.5 w-3.5" />
                          {getRelativeTime(item.created_at)}
                        </div>
                      </div>
                      <Link to="/results" search={{ jobId: item.job_id }}>
                        <Button variant="ghost" size="icon" className="h-8 w-8">
                          <ArrowRight className="h-4 w-4" />
                        </Button>
                      </Link>
                    </div>
                  </div>
                </motion.div>
              ))}
            </div>

            {total > jobs.length && search === "" && (
              <div className="mt-10 flex justify-center">
                <Button 
                  variant="outline" 
                  onClick={() => setLimit(l => l + 20)}
                >
                  Load more
                </Button>
              </div>
            )}
          </>
        )}
      </motion.div>
    </div>
  );
}
