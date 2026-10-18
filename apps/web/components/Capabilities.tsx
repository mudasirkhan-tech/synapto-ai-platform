import { ChevronRight, Code2, Database, FileText, Globe, ImageIcon, Mic, Sparkles, Type } from "lucide-react";
import type { LucideIcon } from "lucide-react";

const ITEMS: { title: string; view: string; sub: string; icon: LucideIcon; bg: string }[] = [
  { title: "File Reading & Analysis", view: "documents", sub: "PDF, DOCX, TXT, CSV, and more", icon: FileText, bg: "bg-violet-500" },
  { title: "Text Generation", view: "chat", sub: "Write, summarize, improve", icon: Type, bg: "bg-blue-500" },
  { title: "Image Generation", view: "images", sub: "Create stunning visuals", icon: ImageIcon, bg: "bg-green-500" },
  { title: "Voice Processing", view: "voice", sub: "Speech to text & text to speech", icon: Mic, bg: "bg-orange-500" },
  { title: "Code Assistant", view: "code", sub: "Write, debug and explain code", icon: Code2, bg: "bg-pink-500" },
  { title: "Web Search", view: "search", sub: "Get live information from the web", icon: Globe, bg: "bg-teal-400" },
  { title: "Multi-File Support", view: "documents", sub: "Analyze multiple files at once", icon: Database, bg: "bg-amber-500" },
  { title: "And much more...", view: "tools", sub: "Explore endless possibilities!", icon: Sparkles, bg: "bg-blue-600" },
];

export default function Capabilities({ onNavigate }: { onNavigate: (view: string) => void }) {
  return (
    <section className="rounded-2xl border border-line bg-card/60 p-3">
      <h2 className="mb-1 text-[15px] font-semibold">All-in-One Capabilities</h2>
      <ul>
        {ITEMS.map(({ title, view, sub, icon: Icon, bg }) => (
          <li key={title}>
            <button onClick={() => onNavigate(view)} className="flex w-full items-center gap-2.5 rounded-lg py-1 text-left hover:bg-white/[0.03]">
              <span className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-lg ${bg}`}><Icon size={18} /></span>
              <span className="min-w-0 flex-1">
                <span className="block text-[13px] leading-tight">{title}</span>
                <span className="block truncate text-[11px] leading-tight text-white/60 [@media(max-height:720px)]:hidden">{sub}</span>
              </span>
              <ChevronRight size={15} className="shrink-0 text-white/60" />
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}
