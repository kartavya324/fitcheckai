import { useMutation, useQuery } from "@tanstack/react-query";

export const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8001";

export type JobStatus = "queued" | "processing" | "completed" | "failed" | "cancelled";

export interface ApiErrorBody {
  error: {
    code: string;
    message: string;
    details?: Record<string, unknown>;
  };
}

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly details?: Record<string, unknown>;

  constructor(
    message: string,
    options: { status: number; code: string; details?: Record<string, unknown> },
  ) {
    super(message);
    this.name = "ApiError";
    this.status = options.status;
    this.code = options.code;
    this.details = options.details;
  }
}

export interface UploadCreated {
  upload_id: string;
  kind: "person" | "garment";
  url: string;
}

export interface JobCreated {
  job_id: string;
  status: JobStatus;
}

export interface JobStatusResponse {
  job_id: string;
  status: JobStatus;
  progress: number;
  stage: string | null;
  result_url?: string | null;
}

export interface JobListItem {
  job_id: string;
  status: JobStatus;
  garment_category: string;
  result_url: string | null;
  created_at: string;
  completed_at: string | null;
}

export interface JobListResponse {
  items: JobListItem[];
  total: number;
  limit: number;
  offset: number;
}

export interface UploadDetails {
  upload_id: string;
  kind: "person" | "garment";
  original_filename: string;
  content_type: string;
  size_bytes: number;
  url: string;
  created_at: string;
}

export interface TryOnSession {
  personImageUrl: string;
  garmentImageUrl: string;
  clothingName: string;
}

const TRYON_SESSION_PREFIX = "fitcheck:tryon:";

export function saveTryOnSession(jobId: string, session: TryOnSession) {
  if (typeof sessionStorage === "undefined") return;
  sessionStorage.setItem(`${TRYON_SESSION_PREFIX}${jobId}`, JSON.stringify(session));
}

export function loadTryOnSession(jobId: string): TryOnSession | null {
  if (typeof sessionStorage === "undefined") return null;
  const raw = sessionStorage.getItem(`${TRYON_SESSION_PREFIX}${jobId}`);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as TryOnSession;
  } catch {
    return null;
  }
}

export function getErrorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  if (error instanceof Error) return error.message;
  return "Something went wrong. Please try again.";
}

async function parseJson<T>(response: Response): Promise<T> {
  const text = await response.text();
  if (!text) return {} as T;
  return JSON.parse(text) as T;
}

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, init);
  const text = await response.text();

  if (!response.ok) {
    let code = "HTTP_ERROR";
    let message = response.statusText || "Request failed";
    let details: Record<string, unknown> | undefined;

    if (text) {
      try {
        const body = JSON.parse(text) as ApiErrorBody;
        if (body.error) {
          code = body.error.code;
          message = body.error.message;
          details = body.error.details;
        }
      } catch {
        message = text;
      }
    }

    throw new ApiError(message, { status: response.status, code, details });
  }

  if (!text) {
    return {} as T;
  }

  return JSON.parse(text) as T;
}

export async function uploadPerson(file: File): Promise<UploadCreated> {
  const form = new FormData();
  form.append("file", file, file.name);
  return apiFetch<UploadCreated>("/api/v1/uploads/person", {
    method: "POST",
    body: form,
  });
}

export async function uploadGarment(file: File): Promise<UploadCreated> {
  const form = new FormData();
  form.append("file", file, file.name);
  return apiFetch<UploadCreated>("/api/v1/uploads/garment", {
    method: "POST",
    body: form,
  });
}

export async function createJob(body: {
  person_upload_id: string;
  garment_upload_id: string;
  garment_category?: string;
}): Promise<JobCreated> {
  return apiFetch<JobCreated>("/api/v1/jobs", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export async function getJob(jobId: string): Promise<JobStatusResponse> {
  return apiFetch<JobStatusResponse>(`/api/v1/jobs/${jobId}`);
}

export async function getUpload(uploadId: string): Promise<UploadDetails> {
  return apiFetch<UploadDetails>(`/api/v1/uploads/${uploadId}`);
}

export async function fetchProductImage(url: string): Promise<UploadCreated> {
  return apiFetch<UploadCreated>("/api/v1/products/fetch", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url }),
  });
}

export async function getJobs(limit: number = 20, offset: number = 0): Promise<JobListResponse> {
  return apiFetch<JobListResponse>(`/api/v1/jobs?limit=${limit}&offset=${offset}`);
}

export async function urlToImageFile(url: string, filename: string): Promise<File> {
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`Could not load sample image: ${filename}`);
  }
  const blob = await response.blob();
  const type = blob.type || "image/jpeg";
  return new File([blob], filename, { type });
}

export const jobQueryKeys = {
  all: ["jobs"] as const,
  list: (limit: number, offset: number) => ["jobs", "list", limit, offset] as const,
  detail: (jobId: string) => ["jobs", "detail", jobId] as const,
};

export function useCreateTryOnJob() {
  return useMutation({
    mutationFn: async (input: {
      personFile: File;
      garmentFile: File;
      garmentCategory: string;
      clothingName: string;
    }) => {
      const person = await uploadPerson(input.personFile);
      const garment = await uploadGarment(input.garmentFile);
      const job = await createJob({
        person_upload_id: person.upload_id,
        garment_upload_id: garment.upload_id,
        garment_category: input.garmentCategory,
      });
      saveTryOnSession(job.job_id, {
        personImageUrl: person.url,
        garmentImageUrl: garment.url,
        clothingName: input.clothingName,
      });
      return job;
    },
  });
}

export function useJobStatus(jobId: string | undefined) {
  return useQuery({
    queryKey: jobQueryKeys.detail(jobId ?? ""),
    queryFn: () => getJob(jobId!),
    enabled: Boolean(jobId),
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      if (status === "completed" || status === "failed") {
        return false;
      }
      return 1000;
    },
  });
}

export function useJobs(limit: number = 20, offset: number = 0) {
  return useQuery({
    queryKey: jobQueryKeys.list(limit, offset),
    queryFn: () => getJobs(limit, offset),
  });
}

// ── Avatar API ──────────────────────────────────────────────

export interface AvatarCreateResponse {
  job_id: string;
  session_id: string;
  status: string;
}

export interface DetectedColor {
  hex: string;
  percentage: number;
}

export interface AvatarAnalysis {
  dominant_colors: DetectedColor[];
  face_thumbnail_url: string | null;
}

export interface AvatarStatusResponse {
  job_id: string;
  status: string;
  progress: number;
  stage: string;
  avatar_url: string | null;
  analysis: AvatarAnalysis | null;
  /** 2D dressed photo produced during avatar try-on jobs */
  tryon_image_url?: string | null;
  error?: { code: string; message: string } | null;
}

export async function createAvatar(
  imageFile: File,
  backFile?: File | null,
): Promise<AvatarCreateResponse> {
  const formData = new FormData();
  formData.append("person_image", imageFile);
  if (backFile) formData.append("back_image", backFile);
  const res = await fetch(`${API_BASE_URL}/api/v1/avatar/create`, {
    method: "POST",
    body: formData,
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function getAvatarStatus(jobId: string): Promise<AvatarStatusResponse> {
  const res = await fetch(`${API_BASE_URL}/api/v1/avatar/status/${jobId}`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

/** Try a garment photo on an existing 3D avatar (poll with getAvatarStatus). */
export async function createAvatarTryon(
  sessionId: string,
  garmentFile: File,
  garmentCategory: string = "upper_body",
): Promise<AvatarCreateResponse> {
  const formData = new FormData();
  formData.append("session_id", sessionId);
  formData.append("garment_image", garmentFile);
  formData.append("garment_category", garmentCategory);
  const res = await fetch(`${API_BASE_URL}/api/v1/avatar/tryon`, {
    method: "POST",
    body: formData,
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

// ── Footwear API ────────────────────────────────────────────

export interface FootwearResult {
  result_id: string;
  result_url: string;
}

/** Composite a shoe/slipper onto the feet of an existing try-on image. */
export async function tryFootwear(
  personImageUrl: string,
  shoeFile: File,
): Promise<FootwearResult> {
  const personRes = await fetch(personImageUrl);
  if (!personRes.ok) throw new Error("Could not load the try-on image");
  const personBlob = await personRes.blob();

  const form = new FormData();
  form.append("person_image", personBlob, "person.jpg");
  form.append("shoe_image", shoeFile, shoeFile.name);
  return apiFetch<FootwearResult>("/api/v1/footwear/try", {
    method: "POST",
    body: form,
  });
}

export function useTryFootwear() {
  return useMutation({
    mutationFn: (input: { personImageUrl: string; shoeFile: File }) =>
      tryFootwear(input.personImageUrl, input.shoeFile),
  });
}

// ── AI Stylist API ──────────────────────────────────────────

export interface StylistMessage {
  role: "user" | "assistant";
  content: string;
}

export interface StylistProduct {
  title?: string | null;
  price?: number | null;
  price_str?: string | null;
  source?: string | null;
  link?: string | null;
  thumbnail?: string | null;
}

export interface StylistChatResponse {
  reply: string;
  products: StylistProduct[];
}

export async function stylistChat(
  messages: StylistMessage[],
): Promise<StylistChatResponse> {
  return apiFetch<StylistChatResponse>("/api/v1/stylist/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ messages }),
  });
}

export function useStylistChat() {
  return useMutation({
    mutationFn: (messages: StylistMessage[]) => stylistChat(messages),
  });
}

// ── Size & Fit advisor API ──────────────────────────────────

export interface SizeRequest {
  height_cm: number;
  weight_kg: number;
  sex: "male" | "female";
  fit_preference?: "fitted" | "regular" | "relaxed";
  brand?: string | null;
  categories?: ("tops" | "bottoms")[];
}

export interface SizeRec {
  category: "tops" | "bottoms";
  size: string;
  base_size: string;
  driver_cm: number;
  range_cm: [number, number | null];
  adjusted: boolean;
  between_size: string | null;
}

export interface SizeResponse {
  sex: string;
  brand: string;
  fit_preference: string;
  measurements: { chest_cm: number; waist_cm: number; bmi: number };
  recommendations: SizeRec[];
  notes: string[];
  disclaimer: string;
}

export async function recommendSize(body: SizeRequest): Promise<SizeResponse> {
  return apiFetch<SizeResponse>("/api/v1/sizing/recommend", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export function useSizeRecommendation() {
  return useMutation({ mutationFn: recommendSize });
}

// ── Wardrobe / Outfits API ──────────────────────────────────

export type WardrobeCategory =
  | "tops"
  | "bottoms"
  | "footwear"
  | "outerwear"
  | "accessory";

export interface WardrobeItem {
  id: string;
  name: string | null;
  category: WardrobeCategory;
  color: string | null;
  brand: string | null;
  image_url: string;
  created_at: string | null;
}

export interface Outfit {
  id: string;
  name: string | null;
  items: WardrobeItem[];
  created_at: string | null;
}

export async function addWardrobeItem(input: {
  file: File;
  category: WardrobeCategory;
  name?: string;
  color?: string;
  brand?: string;
}): Promise<WardrobeItem> {
  const form = new FormData();
  form.append("image", input.file, input.file.name);
  form.append("category", input.category);
  if (input.name) form.append("name", input.name);
  if (input.color) form.append("color", input.color);
  if (input.brand) form.append("brand", input.brand);
  return apiFetch<WardrobeItem>("/api/v1/wardrobe/items", { method: "POST", body: form });
}

export async function getWardrobeItems(): Promise<WardrobeItem[]> {
  const res = await apiFetch<{ items: WardrobeItem[] }>("/api/v1/wardrobe/items");
  return res.items;
}

export async function deleteWardrobeItem(id: string): Promise<void> {
  await apiFetch<void>(`/api/v1/wardrobe/items/${id}`, { method: "DELETE" });
}

export async function createOutfit(input: {
  name?: string;
  item_ids: string[];
}): Promise<Outfit> {
  return apiFetch<Outfit>("/api/v1/wardrobe/outfits", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
}

export async function getOutfits(): Promise<Outfit[]> {
  const res = await apiFetch<{ outfits: Outfit[] }>("/api/v1/wardrobe/outfits");
  return res.outfits;
}

export async function deleteOutfit(id: string): Promise<void> {
  await apiFetch<void>(`/api/v1/wardrobe/outfits/${id}`, { method: "DELETE" });
}

export const wardrobeKeys = {
  items: ["wardrobe", "items"] as const,
  outfits: ["wardrobe", "outfits"] as const,
};

export function useWardrobeItems() {
  return useQuery({ queryKey: wardrobeKeys.items, queryFn: getWardrobeItems });
}

export function useOutfits() {
  return useQuery({ queryKey: wardrobeKeys.outfits, queryFn: getOutfits });
}

// ── Color analysis API ──────────────────────────────────────

export interface ColorSwatch {
  hex: string;
  name: string;
}

export interface ColorAnalysis {
  skin_hex: string;
  undertone: "warm" | "cool" | "neutral";
  depth: "light" | "deep";
  season: string;
  used_face: boolean;
  metrics: { L: number; a: number; b: number; hue_angle: number };
  description: string;
  palette: ColorSwatch[];
  avoid: ColorSwatch[];
  disclaimer: string;
}

export async function analyzeColors(file: File): Promise<ColorAnalysis> {
  const form = new FormData();
  form.append("image", file, file.name);
  return apiFetch<ColorAnalysis>("/api/v1/color/analyze", { method: "POST", body: form });
}

export function useColorAnalysis() {
  return useMutation({ mutationFn: analyzeColors });
}

// ── Social Fit-Check feed API (device-based identity) ───────

const DEVICE_KEY = "fitcheck:device_id";
const NAME_KEY = "fitcheck:display_name";

export function getDeviceId(): string {
  if (typeof localStorage === "undefined") return "server-device-00000000";
  let id = localStorage.getItem(DEVICE_KEY);
  if (!id) {
    id = "dev-" + (crypto.randomUUID?.() ?? Math.random().toString(36).slice(2) + Date.now());
    localStorage.setItem(DEVICE_KEY, id);
  }
  return id;
}

export function getDisplayName(): string {
  if (typeof localStorage === "undefined") return "";
  return localStorage.getItem(NAME_KEY) ?? "";
}

export function setDisplayName(name: string): void {
  if (typeof localStorage !== "undefined") localStorage.setItem(NAME_KEY, name);
}

export interface FeedPost {
  id: string;
  display_name: string;
  image_url: string;
  caption: string | null;
  fire_count: number;
  cold_count: number;
  comment_count: number;
  my_vote: "fire" | "cold" | null;
  is_mine: boolean;
  created_at: string | null;
}

export interface FeedComment {
  id: string;
  display_name: string;
  text: string;
  created_at: string | null;
}

export async function getFeed(): Promise<FeedPost[]> {
  const res = await apiFetch<{ items: FeedPost[] }>(
    `/api/v1/feed/posts?device_id=${encodeURIComponent(getDeviceId())}`,
  );
  return res.items;
}

export async function createPost(input: { file: File; caption?: string }): Promise<FeedPost> {
  const form = new FormData();
  form.append("image", input.file, input.file.name);
  form.append("device_id", getDeviceId());
  const name = getDisplayName();
  if (name) form.append("display_name", name);
  if (input.caption) form.append("caption", input.caption);
  return apiFetch<FeedPost>("/api/v1/feed/posts", { method: "POST", body: form });
}

export async function votePost(postId: string, value: "fire" | "cold"): Promise<FeedPost> {
  return apiFetch<FeedPost>(`/api/v1/feed/posts/${postId}/vote`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ device_id: getDeviceId(), value }),
  });
}

export async function getComments(postId: string): Promise<FeedComment[]> {
  const res = await apiFetch<{ items: FeedComment[] }>(`/api/v1/feed/posts/${postId}/comments`);
  return res.items;
}

export async function addComment(postId: string, text: string): Promise<FeedComment> {
  const name = getDisplayName();
  return apiFetch<FeedComment>(`/api/v1/feed/posts/${postId}/comments`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ device_id: getDeviceId(), display_name: name || undefined, text }),
  });
}

export async function deletePost(postId: string): Promise<void> {
  await apiFetch<void>(
    `/api/v1/feed/posts/${postId}?device_id=${encodeURIComponent(getDeviceId())}`,
    { method: "DELETE" },
  );
}

export const feedKeys = { all: ["feed"] as const };

export function useFeed() {
  return useQuery({ queryKey: feedKeys.all, queryFn: getFeed });
}
