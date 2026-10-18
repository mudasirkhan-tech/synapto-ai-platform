"use client";
import { useState } from "react";
import { ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import Logo from "./Logo";

export default function AuthScreen() {
  const { login, register, guest } = useAuth();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const run = async (fn: () => Promise<void>) => {
    setBusy(true); setError(null);
    try { await fn(); }
    catch (e) { setError(e instanceof ApiError ? e.message : "Something went wrong. Try again."); }
    finally { setBusy(false); }
  };

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    run(() => (mode === "login" ? login(email, password) : register(email, password, name || undefined)));
  };

  const field = "h-12 w-full rounded-xl border border-line bg-white/[0.04] px-4 text-[16px] placeholder:text-white/50";

  return (
    <div className="flex min-h-screen items-center justify-center px-5">
      <div className="w-full max-w-[420px] rounded-[20px] border border-line bg-card/80 p-7">
        <div className="mb-6 flex items-center gap-3">
          <Logo size={48} />
          <div>
            <div className="text-[28px] font-bold leading-none">Synapto</div>
            <div className="mt-1 text-sm text-white/70">Your personal AI, running locally</div>
          </div>
        </div>

        <div role="tablist" className="mb-5 grid grid-cols-2 rounded-xl border border-line p-1 text-[15px]">
          {(["login", "register"] as const).map((m) => (
            <button key={m} role="tab" aria-selected={mode === m} onClick={() => { setMode(m); setError(null); }}
              className={`h-10 rounded-lg ${mode === m ? "bg-gradient-to-r from-[#4b34b8] to-[#7a5ce6]" : "text-white/70"}`}>
              {m === "login" ? "Log in" : "Create account"}
            </button>
          ))}
        </div>

        <form onSubmit={submit} className="space-y-3">
          {mode === "register" && (
            <input className={field} placeholder="Name (optional)" value={name} onChange={(e) => setName(e.target.value)} maxLength={80} autoComplete="name" />
          )}
          <input className={field} type="email" required placeholder="Email" value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="email" />
          <input className={field} type="password" required minLength={mode === "register" ? 8 : 1} placeholder={mode === "register" ? "Password (8+ characters)" : "Password"}
            value={password} onChange={(e) => setPassword(e.target.value)} autoComplete={mode === "login" ? "current-password" : "new-password"} />
          {error && <p role="alert" className="text-sm text-red-400">{error}</p>}
          <button disabled={busy} className="h-12 w-full rounded-xl bg-gradient-to-r from-[#5b3fe0] to-[#7c5cff] text-[16px] shadow-glow disabled:opacity-60">
            {busy ? "Please wait…" : mode === "login" ? "Log in" : "Create account"}
          </button>
        </form>

        <div className="my-5 flex items-center gap-3 text-sm text-white/50"><span className="h-px flex-1 bg-line" />or<span className="h-px flex-1 bg-line" /></div>
        <button disabled={busy} onClick={() => run(guest)} className="h-12 w-full rounded-xl border border-line bg-white/[0.04] text-[16px] hover:bg-white/[0.08] disabled:opacity-60">
          Continue as guest
        </button>
        <p className="mt-3 text-center text-xs text-white/50">Guest chats are saved to this browser&apos;s guest profile only. Log out and the guest session cannot be recovered.</p>
      </div>
    </div>
  );
}
