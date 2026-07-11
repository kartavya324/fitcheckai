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
}

export async function createAvatar(imageFile: File): Promise<AvatarCreateResponse> {
  const formData = new FormData();
  formData.append("person_image", imageFile);
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
