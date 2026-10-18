"use client";
import { Bell, LogOut, Menu, Search } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useAuth } from "@/lib/auth";
import Logo from "./Logo";

export interface Notice { id: number; text: string }

export default function Header({ onMenu, onSearch, notices, onClearNotices }: {
  onMenu: () => void; onSearch: (text: string) => void; notices: Notice[]; onClearNotices: () => void;
}) {
  const searchRef = useRef<HTMLInputElement>(null);
  const bell = useRef<HTMLDivElement>(null);
  const { user, logout } = useAuth();
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const [seen, setSeen] = useState(0);
  const name = user?.display_name ?? "User";

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") { e.preventDefault(); searchRef.current?.focus(); }
      if (e.key === "Escape") setOpen(false);
    };
    const onDown = (e: MouseEvent) => { if (!bell.current?.contains(e.target as Node)) setOpen(false); };
    window.addEventListener("keydown", onKey);
    document.addEventListener("mousedown", onDown);
    return () => { window.removeEventListener("keydown", onKey); document.removeEventListener("mousedown", onDown); };
  }, []);

  const unread = notices.length > seen;

  return (
    <header className="flex h-14 shrink-0 items-center gap-3 border-b border-line bg-ink/60 px-4 backdrop-blur lg:gap-8 lg:px-5">
      <button onClick={onMenu} aria-label="Open navigation" className="rounded-lg p-1.5 text-white/70 hover:bg-white/5 lg:hidden"><Menu size={20} /></button>

      <div className="flex shrink-0 items-center gap-2">
        <Logo size={34} />
        <div className="hidden sm:block">
          <div className="text-[20px] font-bold leading-none tracking-tight">Synapto</div>
          <div className="mt-0.5 text-[10.5px] text-white/70">Think • Read • Create • Do More</div>
        </div>
      </div>

      <form role="search" onSubmit={(e) => { e.preventDefault(); if (query.trim()) { onSearch(query.trim()); setQuery(""); } }}
        className="relative mx-auto hidden h-9 w-full max-w-[520px] items-center rounded-full border border-line bg-card/80 px-4 md:flex">
        <Search size={15} className="text-white/70" />
        <input ref={searchRef} value={query} onChange={(e) => setQuery(e.target.value)} dir="auto" aria-label="Ask anything" placeholder="Ask anything..."
          className="ml-2.5 flex-1 bg-transparent text-[13px] text-white placeholder:text-white/60 focus:outline-none" />
        <span className="flex items-center gap-1 text-[11px] text-white/70">
          <kbd className="rounded border border-line px-1.5 py-px">Ctrl</kbd>+<kbd className="rounded border border-line px-1.5 py-px">K</kbd>
        </span>
      </form>

      <div className="ml-auto flex items-center gap-3 md:ml-0">
        <div ref={bell} className="relative">
          <button aria-label={`Notices${unread ? " (new)" : ""}`} aria-expanded={open} onClick={() => { setOpen((o) => !o); setSeen(notices.length); }}
            className="relative rounded-lg p-1.5 text-white/80 hover:bg-white/5">
            <Bell size={18} />
            {unread && <span className="absolute right-1 top-1 h-2 w-2 rounded-full bg-pink-500" />}
          </button>
          {open && (
            <div role="dialog" aria-label="Notices" className="absolute right-0 top-full z-40 mt-2 w-[min(20rem,90vw)] rounded-xl border border-line bg-card p-3 shadow-2xl">
              <div className="mb-1.5 flex items-center justify-between text-xs text-white/60">
                <span>Recent notices</span>
                {notices.length > 0 && <button onClick={() => { onClearNotices(); setSeen(0); }} className="underline hover:text-white">Clear</button>}
              </div>
              {notices.length === 0 ? <p className="text-[13px] text-white/50">Nothing new. Provider fallbacks and errors appear here.</p> : (
                <ul className="thin-scroll max-h-60 space-y-1.5 overflow-y-auto">{notices.map((n) => <li key={n.id} className="rounded-lg bg-white/[0.04] px-2.5 py-1.5 text-[12px] text-white/80">{n.text}</li>)}</ul>
              )}
            </div>
          )}
        </div>
        <div className="flex items-center gap-2">
          <div className="flex h-8 w-8 items-center justify-center rounded-full bg-gradient-to-br from-brand-soft to-brand text-sm font-bold">{name.charAt(0).toUpperCase()}</div>
          <div className="hidden max-w-[120px] leading-tight sm:block">
            <div className="truncate text-xs">{name}</div>
            <div className={`flex items-center gap-1 text-[11px] ${user?.is_guest ? "text-white/60" : "text-emerald-400"}`}>
              <span className={`h-1.5 w-1.5 rounded-full ${user?.is_guest ? "bg-white/50" : "bg-emerald-400"}`} />{user?.is_guest ? "Guest" : "Member"}
            </div>
          </div>
          <button onClick={logout} aria-label="Log out" title="Log out" className="rounded-lg p-1.5 text-white/70 hover:bg-white/5"><LogOut size={16} /></button>
        </div>
      </div>
    </header>
  );
}
