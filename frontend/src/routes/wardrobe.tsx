import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { motion } from "framer-motion";
import { useQueryClient } from "@tanstack/react-query";
import { Shirt, Upload, Trash2, Plus, Check, X, Loader2, Layers } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  useWardrobeItems,
  useOutfits,
  addWardrobeItem,
  deleteWardrobeItem,
  createOutfit,
  deleteOutfit,
  getErrorMessage,
  wardrobeKeys,
  type WardrobeCategory,
  type WardrobeItem,
} from "@/lib/api";

export const Route = createFileRoute("/wardrobe")({
  head: () => ({
    meta: [
      { title: "Wardrobe — FitCheck AI" },
      { name: "description", content: "Your digital closet — save garments and build outfits." },
    ],
  }),
  component: WardrobePage,
});

const CATEGORIES: WardrobeCategory[] = ["tops", "bottoms", "footwear", "outerwear", "accessory"];

function WardrobePage() {
  return (
    <div className="mx-auto max-w-5xl px-4 py-10 sm:px-6">
      <div className="mb-6 flex items-center gap-2">
        <Shirt className="h-5 w-5 text-copper" />
        <h1 className="font-heading text-2xl font-bold text-foreground">Your Wardrobe</h1>
      </div>
      <Tabs defaultValue="items">
        <TabsList className="grid w-full max-w-sm grid-cols-2">
          <TabsTrigger value="items">My Items</TabsTrigger>
          <TabsTrigger value="outfits">Outfits</TabsTrigger>
        </TabsList>
        <TabsContent value="items" className="mt-6">
          <ItemsTab />
        </TabsContent>
        <TabsContent value="outfits" className="mt-6">
          <OutfitsTab />
        </TabsContent>
      </Tabs>
    </div>
  );
}

function ItemsTab() {
  const qc = useQueryClient();
  const { data: items = [], isLoading } = useWardrobeItems();
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [category, setCategory] = useState<WardrobeCategory>("tops");
  const [name, setName] = useState("");
  const [saving, setSaving] = useState(false);

  const onPick = (f: File) => {
    setFile(f);
    setPreview((p) => {
      if (p?.startsWith("blob:")) URL.revokeObjectURL(p);
      return URL.createObjectURL(f);
    });
  };

  const save = async () => {
    if (!file) return;
    setSaving(true);
    try {
      await addWardrobeItem({ file, category, name: name.trim() || undefined });
      await qc.invalidateQueries({ queryKey: wardrobeKeys.items });
      setFile(null);
      setPreview(null);
      setName("");
      toast.success("Added to your wardrobe");
    } catch (e) {
      toast.error(getErrorMessage(e));
    } finally {
      setSaving(false);
    }
  };

  const remove = async (id: string) => {
    try {
      await deleteWardrobeItem(id);
      await qc.invalidateQueries({ queryKey: wardrobeKeys.items });
    } catch (e) {
      toast.error(getErrorMessage(e));
    }
  };

  return (
    <div className="grid gap-6 lg:grid-cols-[300px_1fr]">
      {/* Add form */}
      <div className="rounded-2xl border border-border bg-card p-4">
        <p className="mb-3 text-sm font-semibold text-foreground">Add an item</p>
        <label className="flex aspect-square cursor-pointer flex-col items-center justify-center overflow-hidden rounded-xl border-2 border-dashed border-border bg-surface hover:border-foreground/30">
          {preview ? (
            <img src={preview} alt="Preview" className="h-full w-full object-contain p-2" />
          ) : (
            <>
              <Upload className="h-6 w-6 text-muted-foreground" />
              <span className="mt-2 text-xs text-muted-foreground">Upload garment photo</span>
            </>
          )}
          <input
            type="file"
            accept="image/*"
            className="hidden"
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) onPick(f);
            }}
          />
        </label>
        <div className="mt-3 space-y-2">
          <Select value={category} onValueChange={(v) => setCategory(v as WardrobeCategory)}>
            <SelectTrigger><SelectValue /></SelectTrigger>
            <SelectContent>
              {CATEGORIES.map((c) => (
                <SelectItem key={c} value={c} className="capitalize">{c}</SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="Name (optional)" />
          <Button onClick={save} disabled={!file || saving} className="w-full gap-1.5">
            {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />}
            Add to wardrobe
          </Button>
        </div>
      </div>

      {/* Grid */}
      <div>
        {isLoading ? (
          <div className="flex h-40 items-center justify-center text-muted-foreground">
            <Loader2 className="h-5 w-5 animate-spin" />
          </div>
        ) : items.length === 0 ? (
          <EmptyState label="No items yet — add your clothes to start building outfits." />
        ) : (
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-4">
            {items.map((it) => (
              <ItemCard key={it.id} item={it} onDelete={() => remove(it.id)} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function ItemCard({ item, onDelete }: { item: WardrobeItem; onDelete: () => void }) {
  return (
    <div className="group relative overflow-hidden rounded-xl border border-border bg-card">
      <div className="aspect-square bg-surface">
        <img src={item.image_url} alt={item.name ?? item.category} className="h-full w-full object-contain p-2" />
      </div>
      <div className="p-2">
        <p className="truncate text-xs font-medium text-foreground">{item.name ?? "Untitled"}</p>
        <p className="text-[10px] capitalize text-muted-foreground">{item.category}</p>
      </div>
      <button
        onClick={onDelete}
        className="absolute right-2 top-2 rounded-full bg-background/90 p-1.5 text-foreground opacity-0 backdrop-blur-sm transition group-hover:opacity-100 hover:bg-destructive hover:text-destructive-foreground"
      >
        <Trash2 className="h-3.5 w-3.5" />
      </button>
    </div>
  );
}

function OutfitsTab() {
  const qc = useQueryClient();
  const { data: items = [] } = useWardrobeItems();
  const { data: outfits = [], isLoading } = useOutfits();
  const [selected, setSelected] = useState<string[]>([]);
  const [name, setName] = useState("");
  const [saving, setSaving] = useState(false);

  const toggle = (id: string) =>
    setSelected((s) => (s.includes(id) ? s.filter((x) => x !== id) : [...s, id]));

  const save = async () => {
    if (selected.length === 0) return;
    setSaving(true);
    try {
      await createOutfit({ name: name.trim() || undefined, item_ids: selected });
      await qc.invalidateQueries({ queryKey: wardrobeKeys.outfits });
      setSelected([]);
      setName("");
      toast.success("Outfit saved");
    } catch (e) {
      toast.error(getErrorMessage(e));
    } finally {
      setSaving(false);
    }
  };

  const remove = async (id: string) => {
    try {
      await deleteOutfit(id);
      await qc.invalidateQueries({ queryKey: wardrobeKeys.outfits });
    } catch (e) {
      toast.error(getErrorMessage(e));
    }
  };

  return (
    <div className="space-y-8">
      {/* Builder */}
      <div className="rounded-2xl border border-border bg-card p-4 sm:p-5">
        <p className="mb-1 text-sm font-semibold text-foreground">Build an outfit</p>
        <p className="mb-3 text-xs text-muted-foreground">Tap items to combine them into a look.</p>
        {items.length === 0 ? (
          <EmptyState label="Add items in the “My Items” tab first." />
        ) : (
          <>
            <div className="grid grid-cols-3 gap-2 sm:grid-cols-5 md:grid-cols-6">
              {items.map((it) => {
                const active = selected.includes(it.id);
                return (
                  <button
                    key={it.id}
                    onClick={() => toggle(it.id)}
                    className={`relative overflow-hidden rounded-lg border-2 transition ${
                      active ? "border-copper ring-2 ring-copper/30" : "border-border hover:border-foreground/40"
                    }`}
                  >
                    <div className="aspect-square bg-surface">
                      <img src={it.image_url} alt={it.name ?? ""} className="h-full w-full object-contain p-1" />
                    </div>
                    {active && (
                      <div className="absolute right-1 top-1 rounded-full bg-copper p-0.5 text-copper-foreground">
                        <Check className="h-3 w-3" />
                      </div>
                    )}
                  </button>
                );
              })}
            </div>
            <div className="mt-4 flex flex-wrap items-center gap-2">
              <Input
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Outfit name (optional)"
                className="max-w-xs"
              />
              <Button onClick={save} disabled={selected.length === 0 || saving} className="gap-1.5">
                {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Layers className="h-4 w-4" />}
                Save outfit ({selected.length})
              </Button>
              {selected.length > 0 && (
                <Button variant="ghost" size="sm" onClick={() => setSelected([])} className="gap-1">
                  <X className="h-3.5 w-3.5" /> Clear
                </Button>
              )}
            </div>
          </>
        )}
      </div>

      {/* Saved outfits */}
      <div>
        <p className="mb-3 text-sm font-semibold text-foreground">Saved outfits</p>
        {isLoading ? (
          <div className="flex h-24 items-center justify-center text-muted-foreground">
            <Loader2 className="h-5 w-5 animate-spin" />
          </div>
        ) : outfits.length === 0 ? (
          <EmptyState label="No outfits yet — build one above." />
        ) : (
          <div className="space-y-3">
            {outfits.map((o) => (
              <motion.div
                key={o.id}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                className="flex items-center gap-3 rounded-xl border border-border bg-card p-3"
              >
                <div className="flex -space-x-3">
                  {o.items.slice(0, 5).map((it) => (
                    <div key={it.id} className="h-12 w-12 overflow-hidden rounded-lg border-2 border-card bg-surface">
                      <img src={it.image_url} alt="" className="h-full w-full object-contain p-0.5" />
                    </div>
                  ))}
                </div>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium text-foreground">{o.name ?? "Untitled outfit"}</p>
                  <p className="text-xs text-muted-foreground">{o.items.length} items</p>
                </div>
                <button
                  onClick={() => remove(o.id)}
                  className="rounded-full p-2 text-muted-foreground transition hover:bg-destructive hover:text-destructive-foreground"
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              </motion.div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function EmptyState({ label }: { label: string }) {
  return (
    <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-border bg-muted/20 p-8 text-center">
      <Shirt className="h-6 w-6 text-muted-foreground" />
      <p className="mt-2 max-w-xs text-sm text-muted-foreground">{label}</p>
    </div>
  );
}
