"use client";
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import * as api from "./api";
import type { TokenOut, User } from "./api";

interface AuthCtx {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, name?: string) => Promise<void>;
  guest: () => Promise<void>;
  logout: () => void;
}

const Ctx = createContext<AuthCtx | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!api.tokenStore.get()) { setLoading(false); return; }
    api.getMe()
      .then(setUser)
      .catch((e) => { if (e instanceof api.ApiError && e.status === 401) api.tokenStore.clear(); })
      .finally(() => setLoading(false));
  }, []);

  const accept = useCallback((t: TokenOut) => { api.tokenStore.set(t.access_token); setUser(t.user); }, []);

  const value = useMemo<AuthCtx>(() => ({
    user,
    loading,
    login: async (e, p) => accept(await api.login(e, p)),
    register: async (e, p, n) => accept(await api.register(e, p, n)),
    guest: async () => accept(await api.loginGuest()),
    logout: () => { api.tokenStore.clear(); setUser(null); },
  }), [user, loading, accept]);

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useAuth(): AuthCtx {
  const v = useContext(Ctx);
  if (!v) throw new Error("useAuth must be used inside <AuthProvider>");
  return v;
}
