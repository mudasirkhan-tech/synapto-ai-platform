import { FileText, ImageIcon, Mic, Plus, Type } from "lucide-react";
import Mascot from "./Mascot";

const PILLS = [
  { label: "File Reader", view: "documents", icon: FileText, cls: "border-purple-500/50 bg-purple-500/10 text-purple-200" },
  { label: "Text Generator", view: "chat", icon: Type, cls: "border-sky-500/50 bg-sky-500/10 text-sky-200" },
  { label: "Image Creator", view: "images", icon: ImageIcon, cls: "border-emerald-500/50 bg-emerald-500/10 text-emerald-200" },
  { label: "Voice Assistant", view: "voice", icon: Mic, cls: "border-orange-500/50 bg-orange-500/10 text-orange-200" },
  { label: "More", view: "tools", icon: Plus, cls: "border-line bg-white/[0.04] text-white/90" },
];

export default function Hero({ onNavigate }: { onNavigate: (view: string) => void }) {
  return (
    <section>
      <div className="grid items-center gap-2 md:grid-cols-[1fr_190px]">
        <div>
          <h1 className="text-[30px] font-bold leading-tight tracking-tight sm:text-[34px]">
            Hello, I&apos;m <span className="bg-gradient-to-r from-[#6a4cf0] to-[#9b87ff] bg-clip-text text-transparent">Synapto!</span>
          </h1>
          <p className="mt-1.5 max-w-[470px] text-[13.5px] leading-snug text-white/80">
            Your all-in-one AI assistant. Upload files, ask questions, get answers, generate content, and do much more!
          </p>
        </div>
        <div className="relative mx-auto h-[118px] w-[150px] [@media(max-height:700px)]:hidden md:h-[128px] md:w-[170px]">
          <Mascot />
          <div className="absolute -right-3 top-0 -rotate-12 font-hand text-[16px] leading-[1.05] text-white/85">Smart<br />Fast<br />Secure</div>
        </div>
      </div>

      <div className="mt-2.5 flex flex-wrap gap-2">
        {PILLS.map(({ label, view, icon: Icon, cls }) => (
          <button key={label} onClick={() => onNavigate(view)} className={`flex h-8 items-center gap-1.5 rounded-full border px-3.5 text-xs ${cls}`}>
            <Icon size={14} />{label}
          </button>
        ))}
      </div>
    </section>
  );
}
