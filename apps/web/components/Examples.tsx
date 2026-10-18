import { ChevronRight, Code2, FileText, Globe, ImageIcon, Mic, Sparkles } from "lucide-react";
import type { LucideIcon } from "lucide-react";

const ITEMS: { text: string; icon: LucideIcon; color: string }[] = [
  { text: "Read this PDF and summarize it for me.", icon: FileText, color: "text-indigo-400" },
  { text: "Create an image of a futuristic city.", icon: ImageIcon, color: "text-cyan-400" },
  { text: "Convert this audio to text.", icon: Mic, color: "text-amber-400" },
  { text: "Write a Python function to calculate fibonacci.", icon: Code2, color: "text-orange-400" },
  { text: "Search the web for latest AI news.", icon: Globe, color: "text-cyan-300" },
  { text: "Help me create a study plan.", icon: Sparkles, color: "text-pink-400" },
];

export default function Examples({ onPick }: { onPick: (t: string) => void }) {
  return (
    <section>
      <h2 className="mb-2 flex items-center gap-2 text-[13px]"><Sparkles size={14} className="text-brand-soft" />Try these examples</h2>
      <div className="grid gap-2.5 sm:grid-cols-2 xl:grid-cols-3">
        {ITEMS.map(({ text, icon: Icon, color }) => (
          <button key={text} onClick={() => onPick(text)}
            className="flex min-h-[54px] items-center gap-2.5 rounded-xl border border-line bg-card/70 px-3 text-left transition hover:border-brand/60 hover:shadow-glow">
            <Icon size={22} strokeWidth={1.5} className={`shrink-0 ${color}`} />
            <span className="flex-1 text-[12.5px] leading-snug">{text}</span>
            <ChevronRight size={15} className="shrink-0 text-white/60" />
          </button>
        ))}
      </div>
    </section>
  );
}
