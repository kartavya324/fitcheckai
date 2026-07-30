import {
  createContext,
  useContext,
  useEffect,
  useState,
  useCallback,
  type ReactNode,
} from "react";
import { API_BASE_URL } from "./api";
import { getToken, setToken, clearToken, installAuthFetch } from "./auth";

export interface AuthUser {
  id: string;
  email: string;
  display_name: string | null;
}

interface AuthContextValue {
  user: AuthUser | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  signup: (email: string, password: string, displayName?: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

// Install the token-injecting fetch wrapper as early as possible (client only)
installAuthFetch();

async function authRequest(path: string, body: unknown): Promise<{ access_token: string; user: AuthUser }> {
  const res = await fetch(`${API_BASE_URL}/api/v1/auth/${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    let msg = "Something went wrong";
    try {
      const err = await res.json();
      msg = err?.error?.message || err?.detail || msg;
    } catch {
      /* ignore */
    }
    throw new Error(msg);
  }
  return res.json();
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);

  // Hydrate from an existing token on mount
  useEffect(() => {
    const token = getToken();
    if (!token) {
      setLoading(false);
      return;
    }
    (async () => {
      try {
        const res = await fetch(`${API_BASE_URL}/api/v1/auth/me`);
        if (res.ok) {
          setUser(await res.json());
        } else {
          clearToken(); // stale/expired
        }
      } catch {
        /* offline — keep token, try again next load */
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const data = await authRequest("login", { email, password });
    setToken(data.access_token);
    setUser(data.user);
  }, []);

  const signup = useCallback(
    async (email: string, password: string, displayName?: string) => {
      const data = await authRequest("signup", {
        email,
        password,
        display_name: displayName || null,
      });
      setToken(data.access_token);
      setUser(data.user);
    },
    [],
  );

  const logout = useCallback(() => {
    clearToken();
    setUser(null);
  }, []);

  return (
    <AuthContext.Provider value={{ user, loading, login, signup, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within <AuthProvider>");
  return ctx;
}
