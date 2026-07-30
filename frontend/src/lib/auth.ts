import { API_BASE_URL } from "./api";

/**
 * Token storage + a one-time fetch wrapper that attaches the JWT to every API
 * request. Wrapping fetch centrally means the dozens of existing raw fetch()
 * calls (avatar, wardrobe, try-on, …) get auth automatically — no per-call edits.
 *
 * SSR-safe: all window/localStorage access is guarded, and the wrapper only
 * installs on the client.
 */
const TOKEN_KEY = "fitcheck:token";

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  try {
    return window.localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function setToken(token: string): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(TOKEN_KEY, token);
  } catch {
    /* storage blocked — auth just won't persist */
  }
}

export function clearToken(): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.removeItem(TOKEN_KEY);
  } catch {
    /* ignore */
  }
}

let installed = false;

/** Wrap window.fetch once so API requests carry `Authorization: Bearer <token>`. */
export function installAuthFetch(): void {
  if (installed || typeof window === "undefined") return;
  installed = true;

  const original = window.fetch.bind(window);

  window.fetch = async (input: RequestInfo | URL, init?: RequestInit) => {
    const url =
      typeof input === "string"
        ? input
        : input instanceof URL
          ? input.href
          : input.url;

    const isApiCall = url.startsWith(API_BASE_URL) || url.startsWith("/api/");
    const token = getToken();

    if (isApiCall && token) {
      const headers = new Headers(init?.headers || (input instanceof Request ? input.headers : undefined));
      if (!headers.has("Authorization")) {
        headers.set("Authorization", `Bearer ${token}`);
      }
      return original(input, { ...init, headers });
    }

    return original(input, init);
  };
}
