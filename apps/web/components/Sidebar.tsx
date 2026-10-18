"use client";
import { AudioLines, Code2, FolderOpen, Globe, Home, ImageIcon, MessageSquare, Mic, Plus, Rocket, Settings, Trash2, Upload, Wrench, X } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import type { Conversation } from "@/lib/api";

const NAV: { label: string; icon: LucideIcon }[] = [
  { label: "Home", icon: Home },
  { label: "Chat", icon: MessageSquare },
  { label: "Documents", icon: FolderOpen },
  { label: "Images", icon: ImageIcon },
  { label: "Voice", icon: Mic },
  { label: "Code", icon: Code2 },
  { label: "Web Search", icon: Globe },
  { label: "Tools", icon: Wrench },
  { label: "Settings", icon: Settings },
];

interface Props {
  active: string;
  onSelect: (label: string) => void;
  onNewChat: () => void;
  onUpload: () => void;
  onVoice: () => void;
  onOpenSettings: () => void;
  conversations: Conversation[];
  activeConversation: string | null;
  onOpen: (id: string) => void;
  onDelete: (id: string) => void;
  onClose?: () => void;
}

const row = "flex h-8 items-center gap-3 rounded-lg px-3 text-[13px]";

export default function Sidebar({ active, onSelect, onNewChat, onUpload, onVoice, onOpenSettings, conversations, activeConversation, onOpen, onDelete, onClose }: Props) {
  const quick = [
    { label: "Upload File", icon: Upload, run: onUpload },
    { label: "New Chat", icon: Plus, run: onNewChat },
    { label: "Voice Input", icon: AudioLines, run: onVoice },
  ];

  return (
    <nav className="flex h-full min-h-0 flex-col px-3 py-3" aria-label="Primary">
      {onClose && (
        <button onClick={onClose} aria-label="Close navigation" className="mb-1 self-end rounded-lg p-1.5 text-white/70 hover:bg-white/5 lg:hidden">
          <X size={18} />
        </button>
      )}

      <div className="space-y-0.5">
        {NAV.map(({ label, icon: Icon }) => {
          const on = active === label;
          return (
            <button key={label} onClick={() => { onSelect(label); onClose?.(); }} aria-current={on ? "page" : undefined}
              className={`${row} w-full border transition ${on ? "border-[#8b7bff] bg-gradient-to-r from-[#4b34b8] to-[#7a5ce6] text-white shadow-glow" : "border-transparent text-white/85 hover:bg-white/5"}`}>
              <Icon size={16} strokeWidth={1.7} />{label}
            </button>
          );
        })}
      </div>

      <div className="my-2.5 border-t border-line" />
      <div className="mb-1 px-1 text-[11px] uppercase tracking-wide text-white/50">Quick Actions</div>
      <div className="space-y-0.5">
        {quick.map(({ label, icon: Icon, run }) => (
          <button key={label} onClick={() => { run(); onClose?.(); }} className={`${row} w-full bg-white/[0.04] text-white/90 hover:bg-white/[0.08]`}>
            <Icon size={16} strokeWidth={1.7} />{label}
          </button>
        ))}
      </div>

      <div className="my-2.5 border-t border-line" />
      <div className="mb-1 px-1 text-[11px] uppercase tracking-wide text-white/50">Recent Chats</div>
      <div className="thin-scroll min-h-[56px] flex-1 overflow-y-auto">
        {conversations.length === 0 ? (
          <p className="px-1 text-xs text-white/45">No chats yet.</p>
        ) : (
          <ul className="space-y-0.5">
            {conversations.map((c) => (
              <li key={c.id} className="group relative">
                <button onClick={() => { onOpen(c.id); onClose?.(); }} aria-current={activeConversation === c.id ? "true" : undefined}
                  className={`flex h-8 w-full items-center rounded-lg pl-3 pr-8 text-left text-[13px] ${activeConversation === c.id ? "bg-white/[0.08] text-white" : "text-white/75 hover:bg-white/5"}`}>
                  <span className="truncate">{c.title}</span>
                </button>
                <button onClick={() => onDelete(c.id)} aria-label={`Delete chat: ${c.title}`}
                  className="absolute right-1 top-1/2 -translate-y-1/2 rounded-md p-1 text-white/50 opacity-0 hover:text-red-400 focus-visible:opacity-100 group-hover:opacity-100">
                  <Trash2 size={13} />
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className="mt-2 hidden rounded-xl border border-line bg-gradient-to-b from-card to-panel p-2.5 text-center [@media(min-height:780px)]:block">
        <div className="flex items-center justify-center gap-1.5 text-sm"><Rocket size={16} className="text-brand-soft" />Faster answers</div>
        <p className="mt-0.5 text-[11px] text-white/55">Add a DeepSeek or Gemini key to use fast cloud models.</p>
        <button onClick={() => { onOpenSettings(); onClose?.(); }} className="mt-2 h-7 w-full rounded-full bg-gradient-to-r from-[#5b3fe0] to-[#7c5cff] text-xs shadow-glow">Add API keys →</button>
      </div>
    </nav>
  );
}
