"use client";
import { ArrowLeft } from "lucide-react";
import type { LucideIcon } from "lucide-react";

export default function ViewShell({ title, subtitle, icon: Icon, onBack, children }: {
  title: string; subtitle: string; icon: LucideIcon; onBack: () => void; children: React.ReactNode;
}) {
  return (
    <section className="flex min-h-0 flex-1 flex-col pb-3">
      <div className="mb-3 flex items-center gap-3">
        <button onClick={onBack} aria-label="Back to chat" className="rounded-lg border border-line p-1.5 text-white/70 hover:bg-white/5"><ArrowLeft size={16} /></button>
        <Icon size={20} className="text-brand-soft" />
        <div>
          <h1 className="text-[18px] font-semibold leading-tight">{title}</h1>
          <p className="text-xs text-white/60">{subtitle}</p>
        </div>
      </div>
      <div className="thin-scroll min-h-0 flex-1 space-y-3 xl:overflow-y-auto xl:pr-1">{children}</div>
    </section>
  );
}

export function SetupNotice({ title, text }: { title: string; text: string }) {
  return (
    <div className="rounded-xl border border-amber-500/40 bg-amber-500/10 px-3.5 py-2.5 text-[13px]">
      <div className="font-medium text-amber-200">{title}</div>
      <div className="mt-0.5 text-white/75">{text}</div>
    </div>
  );
}

export const card = "rounded-xl border border-line bg-card/70 p-3.5";
export const input = "w-full rounded-lg border border-line bg-white/[0.04] px-3 py-2 text-[13px] placeholder:text-white/45 focus:outline-none";
export const primary = "h-9 rounded-lg bg-gradient-to-r from-[#5b3fe0] to-[#7c5cff] px-4 text-[13px] shadow-glow disabled:opacity-50 disabled:shadow-none";
export const ghost = "h-9 rounded-lg border border-line bg-white/[0.04] px-3 text-[13px] hover:bg-white/[0.08] disabled:opacity-50";
