import { createFileRoute } from "@tanstack/react-router";
import { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { useQueryClient } from "@tanstack/react-query";
import { Flame, Snowflake, MessageCircle, Trash2, ImagePlus, Loader2, Send, Users } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  useFeed,
  createPost,
  votePost,
  getComments,
  addComment,
  deletePost,
  getDisplayName,
  setDisplayName,
  feedKeys,
  getErrorMessage,
  type FeedPost,
  type FeedComment,
} from "@/lib/api";

export const Route = createFileRoute("/feed")({
  head: () => ({
    meta: [
      { title: "Fit Check Feed — FitCheck AI" },
      { name: "description", content: "Share your look and get the community's verdict." },
    ],
  }),
  component: FeedPage,
});

function FeedPage() {
  const qc = useQueryClient();
  const { data: posts = [], isLoading } = useFeed();

  const replacePost = (p: FeedPost) =>
    qc.setQueryData<FeedPost[]>(feedKeys.all, (old) =>
      (old ?? []).map((x) => (x.id === p.id ? p : x)),
    );

  return (
    <div className="mx-auto max-w-xl px-4 py-8 sm:px-6">
      <div className="mb-6 flex items-center gap-2">
        <Users className="h-5 w-5 text-copper" />
        <h1 className="font-heading text-2xl font-bold text-foreground">Fit Check</h1>
      </div>

      <Composer onPosted={() => qc.invalidateQueries({ queryKey: feedKeys.all })} />

      {isLoading ? (
        <div className="flex h-40 items-center justify-center text-muted-foreground">
          <Loader2 className="h-5 w-5 animate-spin" />
        </div>
      ) : posts.length === 0 ? (
        <div className="mt-8 rounded-2xl border border-dashed border-border bg-muted/20 p-10 text-center">
          <Flame className="mx-auto h-7 w-7 text-muted-foreground" />
          <p className="mt-2 text-sm text-muted-foreground">
            No fit checks yet. Be the first — share a look above and let the community vote.
          </p>
        </div>
      ) : (
        <div className="mt-6 space-y-6">
          {posts.map((p) => (
            <PostCard
              key={p.id}
              post={p}
              onVoted={replacePost}
              onDeleted={() => qc.invalidateQueries({ queryKey: feedKeys.all })}
            />
          ))}
        </div>
      )}
    </div>
  );
}

function Composer({ onPosted }: { onPosted: () => void }) {
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [caption, setCaption] = useState("");
  const [name, setName] = useState(getDisplayName());
  const [posting, setPosting] = useState(false);

  const pick = (f: File) => {
    setFile(f);
    setPreview((p) => {
      if (p?.startsWith("blob:")) URL.revokeObjectURL(p);
      return URL.createObjectURL(f);
    });
  };

  const submit = async () => {
    if (!file) return;
    if (name.trim()) setDisplayName(name.trim());
    setPosting(true);
    try {
      await createPost({ file, caption: caption.trim() || undefined });
      setFile(null);
      setPreview(null);
      setCaption("");
      onPosted();
      toast.success("Posted to the feed");
    } catch (e) {
      toast.error(getErrorMessage(e));
    } finally {
      setPosting(false);
    }
  };

  return (
    <div className="rounded-2xl border border-border bg-card p-4">
      <div className="flex gap-3">
        <label className="flex h-24 w-20 shrink-0 cursor-pointer flex-col items-center justify-center overflow-hidden rounded-xl border-2 border-dashed border-border bg-surface hover:border-foreground/30">
          {preview ? (
            <img src={preview} alt="Your look" className="h-full w-full object-cover" />
          ) : (
            <ImagePlus className="h-5 w-5 text-muted-foreground" />
          )}
          <input
            type="file"
            accept="image/*"
            className="hidden"
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) pick(f);
            }}
          />
        </label>
        <div className="flex-1 space-y-2">
          <Input
            value={caption}
            onChange={(e) => setCaption(e.target.value)}
            placeholder="Ask the community — does this work?"
            maxLength={280}
          />
          <div className="flex gap-2">
            <Input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Your name (optional)"
              className="max-w-[160px]"
              maxLength={40}
            />
            <Button onClick={submit} disabled={!file || posting} className="ml-auto gap-1.5">
              {posting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Flame className="h-4 w-4" />}
              Post
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}

function PostCard({
  post,
  onVoted,
  onDeleted,
}: {
  post: FeedPost;
  onVoted: (p: FeedPost) => void;
  onDeleted: () => void;
}) {
  const [voting, setVoting] = useState(false);
  const [showComments, setShowComments] = useState(false);

  const vote = async (value: "fire" | "cold") => {
    if (voting) return;
    setVoting(true);
    try {
      onVoted(await votePost(post.id, value));
    } catch (e) {
      toast.error(getErrorMessage(e));
    } finally {
      setVoting(false);
    }
  };

  const remove = async () => {
    try {
      await deletePost(post.id);
      onDeleted();
    } catch (e) {
      toast.error(getErrorMessage(e));
    }
  };

  const total = post.fire_count + post.cold_count;
  const firePct = total ? Math.round((post.fire_count / total) * 100) : 0;

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      className="overflow-hidden rounded-2xl border border-border bg-card"
    >
      <div className="flex items-center justify-between px-4 py-3">
        <span className="text-sm font-semibold text-foreground">{post.display_name}</span>
        {post.is_mine && (
          <button onClick={remove} className="rounded-full p-1.5 text-muted-foreground hover:bg-destructive hover:text-destructive-foreground">
            <Trash2 className="h-4 w-4" />
          </button>
        )}
      </div>
      <div className="bg-surface">
        <img src={post.image_url} alt="Look" className="max-h-[70vh] w-full object-contain" />
      </div>
      {post.caption && <p className="px-4 pt-3 text-sm text-foreground">{post.caption}</p>}

      {/* Verdict bar */}
      {total > 0 && (
        <div className="px-4 pt-3">
          <div className="flex h-2 overflow-hidden rounded-full bg-muted">
            <div className="bg-orange-500" style={{ width: `${firePct}%` }} />
            <div className="flex-1 bg-sky-400" />
          </div>
          <p className="mt-1 text-xs text-muted-foreground">{firePct}% say it works</p>
        </div>
      )}

      {/* Actions */}
      <div className="flex items-center gap-2 p-3">
        <VoteButton
          active={post.my_vote === "fire"}
          onClick={() => vote("fire")}
          icon={<Flame className="h-4 w-4" />}
          count={post.fire_count}
          activeClass="border-orange-500 bg-orange-500/10 text-orange-600"
        />
        <VoteButton
          active={post.my_vote === "cold"}
          onClick={() => vote("cold")}
          icon={<Snowflake className="h-4 w-4" />}
          count={post.cold_count}
          activeClass="border-sky-500 bg-sky-500/10 text-sky-600"
        />
        <button
          onClick={() => setShowComments((s) => !s)}
          className="ml-auto flex items-center gap-1.5 rounded-full border border-border px-3 py-1.5 text-sm text-muted-foreground hover:text-foreground"
        >
          <MessageCircle className="h-4 w-4" />
          {post.comment_count}
        </button>
      </div>

      <AnimatePresence>
        {showComments && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            className="overflow-hidden border-t border-border"
          >
            <Comments postId={post.id} />
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}

function VoteButton({
  active,
  onClick,
  icon,
  count,
  activeClass,
}: {
  active: boolean;
  onClick: () => void;
  icon: React.ReactNode;
  count: number;
  activeClass: string;
}) {
  return (
    <button
      onClick={onClick}
      className={`flex items-center gap-1.5 rounded-full border px-3.5 py-1.5 text-sm font-medium transition ${
        active ? activeClass : "border-border text-muted-foreground hover:text-foreground"
      }`}
    >
      {icon}
      {count}
    </button>
  );
}

function Comments({ postId }: { postId: string }) {
  const [comments, setComments] = useState<FeedComment[] | null>(null);
  const [text, setText] = useState("");
  const [sending, setSending] = useState(false);

  useEffect(() => {
    let active = true;
    getComments(postId)
      .then((c) => active && setComments(c))
      .catch(() => active && setComments([]));
    return () => {
      active = false;
    };
  }, [postId]);

  const send = async () => {
    const t = text.trim();
    if (!t) return;
    setSending(true);
    try {
      const c = await addComment(postId, t);
      setComments((prev) => [...(prev ?? []), c]);
      setText("");
    } catch (e) {
      toast.error(getErrorMessage(e));
    } finally {
      setSending(false);
    }
  };

  return (
    <div className="space-y-3 p-4">
      {comments === null ? (
        <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
      ) : comments.length === 0 ? (
        <p className="text-xs text-muted-foreground">No comments yet. Start the conversation.</p>
      ) : (
        comments.map((c) => (
          <div key={c.id} className="text-sm">
            <span className="font-medium text-foreground">{c.display_name}</span>{" "}
            <span className="text-foreground">{c.text}</span>
          </div>
        ))
      )}
      <form
        onSubmit={(e) => {
          e.preventDefault();
          send();
        }}
        className="flex gap-2 pt-1"
      >
        <Input value={text} onChange={(e) => setText(e.target.value)} placeholder="Add a comment…" maxLength={500} />
        <Button type="submit" size="icon" disabled={!text.trim() || sending}>
          {sending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
        </Button>
      </form>
    </div>
  );
}
