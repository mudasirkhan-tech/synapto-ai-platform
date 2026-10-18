"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError, deleteConversation, deleteDocument, getDocument, getMessages, listConversations, transcribe, uploadDocument } from "@/lib/api";
import type { Conversation } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { streamChat, streamRegenerate } from "@/lib/chat";
import type { StreamHandlers } from "@/lib/chat";
import { defaultSpeechLang } from "@/lib/languages";
import {
  getAgentTools, getFallback, getReplyScale, getSpeechLang, getVoiceURI, setAgentTools, setFallback, setReplyScale, setSpeechLang, setVoiceURI,
} from "@/lib/prefs";
import { useCapabilities } from "@/lib/useCapabilities";
import { useModels } from "@/lib/useModels";
import { useRecorder } from "@/lib/useRecorder";
import { useSpeechRecognition } from "@/lib/useSpeechRecognition";
import { useSpeechSynthesis } from "@/lib/useSpeechSynthesis";
import type { View } from "@/lib/views";
import Capabilities from "./Capabilities";
import ChatMessages from "./ChatMessages";
import type { ChatMessage } from "./ChatMessages";
import Composer from "./Composer";
import type { ChatAttachment, MicState } from "./Composer";
import Examples from "./Examples";
import Header from "./Header";
import type { Notice } from "./Header";
import Hero from "./Hero";
import LocalStatusCard from "./LocalStatusCard";
import ModelSelector from "./ModelSelector";
import Sidebar from "./Sidebar";
import CodeView from "./views/CodeView";
import DocumentsView from "./views/DocumentsView";
import ImagesView from "./views/ImagesView";
import SearchView from "./views/SearchView";
import SettingsView from "./views/SettingsView";
import ToolsView from "./views/ToolsView";
import VoiceView from "./views/VoiceView";

const VIEWS = new Set<string>(["chat", "documents", "images", "voice", "code", "search", "tools", "settings"]);
const NAV_TO_VIEW: Record<string, View> = {
  Home: "chat", Chat: "chat", Documents: "documents", Images: "images", Voice: "voice",
  Code: "code", "Web Search": "search", Tools: "tools", Settings: "settings",
};
const VIEW_TO_NAV: Record<View, string> = {
  chat: "Chat", documents: "Documents", images: "Images", voice: "Voice",
  code: "Code", search: "Web Search", tools: "Tools", settings: "Settings",
};
const MAX_ATTACHMENTS = 8;

export default function Workspace() {
  const { logout } = useAuth();
  const models = useModels();
  const { caps, refresh: refreshCaps } = useCapabilities();
  const recorder = useRecorder();

  const [view, setView] = useState<View>("chat");
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [draft, setDraft] = useState("");
  const [attachments, setAttachments] = useState<ChatAttachment[]>([]);
  const [uploading, setUploading] = useState(false);
  const [transcribing, setTranscribing] = useState(false);
  const [streaming, setStreaming] = useState(false);
  const [useKnowledge, setUseKnowledge] = useState(false);
  const [webSearch, setWebSearch] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [drawer, setDrawer] = useState(false);
  const [notices, setNotices] = useState<Notice[]>([]);
  const [interim, setInterim] = useState("");

  // non-sensitive preferences (API keys are never kept in the browser)
  const [speechLang, setSpeechLangState] = useState("en-US");
  const [voiceURI, setVoiceURIState] = useState<string | null>(null);
  const [fallback, setFallbackState] = useState(true);
  const [agentTools, setAgentToolsState] = useState(false);
  useEffect(() => {
    setSpeechLangState(defaultSpeechLang(getSpeechLang()));
    setVoiceURIState(getVoiceURI());
    setFallbackState(getFallback());
    setAgentToolsState(getAgentTools());
    setReplyScale(getReplyScale());
  }, []);

  const tts = useSpeechSynthesis(voiceURI);
  const speech = useSpeechRecognition({
    lang: speechLang,
    onFinal: (t) => setDraft((d) => (d.trim() ? `${d.replace(/\s+$/, "")} ${t}` : t)), // review & edit before sending
    onInterim: setInterim,
  });

  const abortRef = useRef<AbortController | null>(null);
  const docInput = useRef<HTMLInputElement>(null);
  const imgInput = useRef<HTMLInputElement>(null);
  const refreshSeq = useRef(0);
  const noticeId = useRef(0);
  const epoch = useRef(0); // bumped whenever the visible conversation changes, so stale stream events are ignored

  const addNotice = useCallback((text: string) => {
    setNotices((n) => (n[0]?.text === text ? n : [{ id: ++noticeId.current, text }, ...n].slice(0, 20)));
  }, []);

  const fail = useCallback((e: unknown) => {
    if (e instanceof ApiError && e.status === 401) { logout(); return; }
    setError(e instanceof Error ? e.message : "Something went wrong.");
  }, [logout]);

  const refresh = useCallback(() => {
    const seq = ++refreshSeq.current;
    listConversations().then((c) => { if (seq === refreshSeq.current) setConversations(c); }).catch(fail);
  }, [fail]);

  useEffect(() => { refresh(); }, [refresh]);
  useEffect(() => { if (view !== "chat") refreshCaps(); }, [view, refreshCaps]);

  // Leaving a screen or chat stops speech output and any dictation in progress.
  const stopSpeech = tts.stop;
  const cancelListening = speech.cancel;
  useEffect(() => { stopSpeech(); cancelListening(); }, [view, stopSpeech, cancelListening]);

  useEffect(() => {
    const pending = attachments.filter((a) => a.status === "processing");
    if (!pending.length) return;
    const t = setInterval(async () => {
      for (const a of pending) {
        try {
          const d = await getDocument(a.id);
          if (d.status !== "processing") setAttachments((cur) => cur.map((x) => (x.id === a.id ? { ...x, status: d.status, error: d.error } : x)));
        } catch { /* removed meanwhile */ }
      }
    }, 1500);
    return () => clearInterval(t);
  }, [attachments]);

  /** Drops the active conversation state: aborts any running stream, speech and dictation. */
  const resetChat = () => {
    epoch.current += 1;
    abortRef.current?.abort();
    abortRef.current = null;
    stopSpeech(); cancelListening();
    setStreaming(false);
    setActiveId(null); setMessages([]); setAttachments([]); setDraft(""); setError(null); setInterim("");
  };
  const newChat = () => { resetChat(); setView("chat"); };

  const openConversation = async (id: string) => {
    epoch.current += 1;
    abortRef.current?.abort();
    abortRef.current = null;
    stopSpeech();
    setStreaming(false);
    setError(null); setAttachments([]); setView("chat");
    try {
      const rows = await getMessages(id);
      setActiveId(id);
      setMessages(rows.map((m) => ({
        id: m.id, role: m.role, content: m.content, attachments: m.attachments, sources: m.sources,
        model: m.model, provider: m.provider, finish: m.finish,
      })));
    } catch (e) { fail(e); }
  };

  const removeConversation = async (id: string) => {
    try {
      await deleteConversation(id);
      setConversations((c) => c.filter((x) => x.id !== id));
      if (id === activeId) resetChat();
    } catch (e) { fail(e); }
  };

  const handleFiles = async (files: FileList | null) => {
    if (!files?.length) return;
    setError(null); setUploading(true);
    let count = attachments.length;
    for (const file of Array.from(files)) {
      if (count >= MAX_ATTACHMENTS) { setError(`You can attach up to ${MAX_ATTACHMENTS} files per message.`); break; }
      try {
        const d = await uploadDocument(file, "chat");
        setAttachments((a) => [...a, { id: d.id, filename: d.filename, kind: d.kind, status: d.status, error: d.error }]);
        count += 1;
      } catch (e) { fail(e); }
    }
    setUploading(false);
  };

  const dropAttachment = (id: string) => {
    setAttachments((a) => a.filter((x) => x.id !== id));
    deleteDocument(id).catch(() => {});
  };

  // ---- microphone: browser speech recognition first, local Whisper only when the browser has none ----
  const onMic = async () => {
    setError(null);
    if (speech.supported) {
      if (speech.state === "listening") speech.stop();
      else if (speech.state === "idle" || speech.state === "error" || speech.state === "denied") speech.start();
      return;
    }
    if (recorder.recording) {
      const blob = await recorder.stop();
      if (!blob?.size) return;
      setTranscribing(true);
      try {
        const r = await transcribe(blob, speechLang.split("-")[0]);
        setDraft((d) => (d ? `${d} ${r.text}` : r.text));
      } catch (e) { fail(e); } finally { setTranscribing(false); }
      return;
    }
    if (caps?.voice.available) {
      try { await recorder.start(); } catch { setError("Microphone access was denied or is unavailable."); }
    } else {
      setError("This browser has no built-in speech recognition and local Whisper isn't installed. Try Chrome or Edge, or run `uv sync --extra voice`.");
    }
  };
  const micState: MicState = speech.supported ? speech.state : transcribing ? "transcribing" : recorder.recording ? "listening" : "idle";

  const toggleWeb = () => {
    if (!webSearch && caps && !caps.web_search.available) { setError(`Web search isn't configured. ${caps.web_search.setup}`); return; }
    setWebSearch((w) => !w);
  };
  const toggleTools = () => { setAgentToolsState((v) => { setAgentTools(!v); return !v; }); };

  /** Shared by send + regenerate: runs one SSE stream and keeps UI state consistent. */
  const run = async (start: (h: StreamHandlers, signal: AbortSignal) => Promise<void>, onPreStreamFail?: () => void) => {
    const ctrl = new AbortController();
    const myEpoch = epoch.current;
    const live = () => epoch.current === myEpoch;
    abortRef.current = ctrl;
    setStreaming(true);
    let started = false;
    let lastSeq = 0;

    const patchLast = (fn: (m: ChatMessage) => ChatMessage) =>
      setMessages((prev) => {
        const next = [...prev];
        const last = next[next.length - 1];
        if (last?.role === "assistant") next[next.length - 1] = fn(last);
        return next;
      });
    const finish = () => {
      if (abortRef.current !== ctrl) return;
      abortRef.current = null;
      setStreaming(false);
      setMessages((prev) => prev
        .filter((m) => !(m.streaming && m.content === "" && !m.activity?.length))
        .map((m) => (m.streaming ? { ...m, streaming: false, status: null, finish: m.finish ?? "stopped" } : m)));
    };

    try {
      await start({
        onMeta: (m) => { if (live()) { started = true; setActiveId(m.conversation_id); } },
        onSources: (sources) => { if (live()) patchLast((m) => ({ ...m, sources })); },
        onStatus: (s) => {
          if (!live()) return;
          patchLast((m) => ({ ...m, status: s.message }));
          if (s.phase === "info") addNotice(s.message);
        },
        onFallback: (f) => {
          if (!live()) return;
          patchLast((m) => ({ ...m, status: f.message, activity: [...(m.activity ?? []), { kind: "fallback", message: f.message, slow: f.slow }] }));
          addNotice(f.message);
        },
        onToolStart: (t) => {
          if (!live()) return;
          patchLast((m) => ({ ...m, status: t.message, activity: [...(m.activity ?? []), { kind: "tool", n: t.n, tool: t.tool, message: t.message, args: t.args, state: "running" }] }));
        },
        onToolResult: (t) => {
          if (!live()) return;
          patchLast((m) => ({ ...m, activity: (m.activity ?? []).map((a) => (a.kind === "tool" && a.n === t.n ? { ...a, state: t.ok ? "ok" : "error", preview: t.preview } : a)) }));
        },
        onToken: (text, seq) => {
          if (!live() || seq <= lastSeq) return; // ignore duplicated chunks
          lastSeq = seq;
          patchLast((m) => ({ ...m, content: m.content + text, status: null }));
        },
        onError: (msg) => { if (live()) { setError(msg); addNotice(msg); } },
        onDone: (d) => {
          if (!live()) return;
          patchLast((m) => ({ ...m, id: d.message_id ?? undefined, model: d.model, provider: d.provider, finish: d.finish, latencyMs: d.latency_ms, status: null }));
          finish();
          refresh();
        },
        // The server saved the title before sending this event, so a refresh returns it.
        onTitle: (t) => {
          setConversations((cs) => cs.map((c) => (c.id === t.conversation_id ? { ...c, title: t.title } : c)));
          refresh();
        },
      }, ctrl.signal);
    } catch (e) {
      if (!(e instanceof DOMException && e.name === "AbortError") && live()) {
        fail(e);
        if (!started) onPreStreamFail?.();
      }
    } finally {
      finish();
      refresh();
    }
  };

  const submit = (text: string, opts?: { web?: boolean }) => {
    const t = text.trim();
    if (!t) return;
    if (streaming) { setError("Wait for the current reply to finish, or press stop."); return; }
    if (uploading || transcribing || attachments.some((a) => a.status !== "ready")) return;
    speech.cancel(); stopSpeech();
    setError(null);
    const sent = attachments;
    setMessages((m) => [
      ...m,
      { role: "user", content: t, attachments: sent.map((a) => ({ id: a.id, filename: a.filename, kind: a.kind })) },
      { role: "assistant", content: "", streaming: true, status: "Starting..." },
    ]);
    setDraft(""); setAttachments([]);
    run(
      (h, s) => streamChat({
        conversation_id: activeId, message: t, document_ids: sent.map((a) => a.id), model: models.selected,
        use_knowledge: useKnowledge, web_search: opts?.web ?? webSearch, tools: agentTools, fallback,
      }, h, s),
      () => { // rejected before streaming started: undo the optimistic messages and restore the input
        setMessages((m) => m.slice(0, -2));
        setDraft(t); setAttachments(sent);
      },
    );
  };

  const regenerate = () => {
    if (streaming || !activeId) return;
    const id = activeId;
    stopSpeech();
    setError(null);
    setMessages((prev) => {
      const base = prev[prev.length - 1]?.role === "assistant" ? prev.slice(0, -1) : prev;
      return [...base, { role: "assistant", content: "", streaming: true, status: "Starting..." }];
    });
    run((h, s) => streamRegenerate({
      conversation_id: id, model: models.selected, use_knowledge: useKnowledge, web_search: webSearch, tools: agentTools, fallback,
    }, h, s), () => openConversation(id));
  };

  const toChat = (text: string, opts?: { web?: boolean }) => { setView("chat"); submit(text, opts); };
  const navigate = (v: string) => { if (VIEWS.has(v)) setView(v as View); };

  const chatting = messages.length > 0;
  const back = () => setView("chat");
  const activeNav = view === "chat" ? (chatting ? "Chat" : "Home") : VIEW_TO_NAV[view];

  const sidebar = (onClose?: () => void) => (
    <Sidebar
      active={activeNav}
      onSelect={(label) => { if (label === "Home") newChat(); else setView(NAV_TO_VIEW[label] ?? "chat"); }}
      onNewChat={newChat}
      onUpload={() => { setView("chat"); docInput.current?.click(); }}
      onVoice={() => setView("voice")}
      onOpenSettings={() => setView("settings")}
      conversations={conversations}
      activeConversation={activeId}
      onOpen={openConversation}
      onDelete={removeConversation}
      onClose={onClose}
    />
  );

  const errorBanner = error && (
    <p role="alert" className="mb-2 flex items-start justify-between gap-2 rounded-lg border border-red-500/40 bg-red-500/10 px-3 py-2 text-xs text-red-200">
      <span>{error}</span>
      <button onClick={() => setError(null)} aria-label="Dismiss error" className="shrink-0 text-red-200/70 hover:text-white">✕</button>
    </p>
  );

  return (
    // xl and up: the page is locked to the viewport (no page scroll). Below xl: normal scrolling, stacked panels.
    <div className="flex min-h-screen flex-col xl:h-screen xl:overflow-hidden">
      <input ref={docInput} type="file" multiple hidden accept=".pdf,.docx,.txt,.md,.csv,.json" onChange={(e) => { handleFiles(e.target.files); e.target.value = ""; }} />
      <input ref={imgInput} type="file" multiple hidden accept=".png,.jpg,.jpeg,.webp,.gif" onChange={(e) => { handleFiles(e.target.files); e.target.value = ""; }} />
      <Header onMenu={() => setDrawer(true)} onSearch={(t) => { setView("chat"); setDraft(t); }} notices={notices} onClearNotices={() => setNotices([])} />

      <div className="flex min-h-0 flex-1">
        <aside className="hidden w-[210px] shrink-0 border-r border-line lg:block">{sidebar()}</aside>

        {drawer && (
          <div className="fixed inset-0 z-40 lg:hidden" role="dialog" aria-modal="true" aria-label="Navigation">
            <div className="absolute inset-0 bg-black/70" onClick={() => setDrawer(false)} />
            <div className="absolute inset-y-0 left-0 w-[250px] border-r border-line bg-ink">{sidebar(() => setDrawer(false))}</div>
          </div>
        )}

        <div className="flex min-h-0 min-w-0 flex-1 flex-col overflow-y-auto thin-scroll xl:flex-row xl:overflow-hidden">
          <main className="flex min-h-0 min-w-0 flex-1 flex-col px-4 pt-3 sm:px-6 xl:overflow-hidden">
            {view === "chat" && (
              <>
                {chatting
                  ? <ChatMessages messages={messages} busy={streaming} onRegenerate={regenerate} onStop={() => abortRef.current?.abort()} speech={tts} speechNote={tts.note} />
                  : <Hero onNavigate={navigate} />}

                <div className={chatting ? "sticky bottom-0 z-10 mt-auto bg-ink/95 pb-3 pt-2 backdrop-blur xl:static" : "mt-3"}>
                  <div className={chatting ? "mx-auto w-full max-w-[820px]" : ""}>
                    {errorBanner}
                    <Composer
                      value={draft} onChange={setDraft} onSend={() => submit(draft)} onStop={() => abortRef.current?.abort()}
                      onPickDocs={() => docInput.current?.click()} onPickImages={() => imgInput.current?.click()}
                      attachments={attachments} onRemoveAttachment={dropAttachment} uploading={uploading} streaming={streaming}
                      modelSelector={<ModelSelector models={models} disabled={streaming} />}
                      useKnowledge={useKnowledge} onToggleKnowledge={() => setUseKnowledge((v) => !v)}
                      webSearch={webSearch} onToggleWeb={toggleWeb} webAvailable={caps ? caps.web_search.available : null}
                      agentTools={agentTools} onToggleTools={toggleTools}
                      micState={micState} micInterim={interim} micMessage={speech.supported ? speech.message : null} onMic={onMic}
                      onOpenCode={() => setView("code")}
                    />
                  </div>
                </div>

                {!chatting && (
                  <>
                    <div className="mt-3"><Examples onPick={setDraft} /></div>
                    <footer className="mt-auto flex items-center gap-3 py-2.5 text-xs text-white/60 [@media(max-height:680px)]:hidden">
                      <span className="h-px flex-1 bg-line" />
                      <span className="text-white/90">Synapto</span>
                      <span>— Your Personal AI, Always Here for You!</span>
                      <span className="h-px flex-1 bg-line" />
                    </footer>
                  </>
                )}
              </>
            )}

            {view !== "chat" && errorBanner}
            {view === "documents" && <DocumentsView caps={caps} onBack={back} onError={fail} />}
            {view === "images" && <ImagesView caps={caps} onBack={back} onError={fail} onAttachImage={() => { setView("chat"); imgInput.current?.click(); }} />}
            {view === "voice" && (
              <VoiceView caps={caps} lang={speechLang} onLang={(v) => { setSpeechLangState(v); setSpeechLang(v); }} onBack={back} onError={fail} onSendToChat={(t) => toChat(t)} />
            )}
            {view === "code" && <CodeView models={models.usable} selected={models.selected} onSelectModel={models.select} onBack={back} onSend={(t) => toChat(t)} />}
            {view === "search" && <SearchView caps={caps} onBack={back} onError={fail} onAsk={(q) => toChat(q, { web: true })} />}
            {view === "tools" && <ToolsView onBack={back} model={models.selected} caps={caps} onError={fail} />}
            {view === "settings" && (
              <SettingsView
                models={models} caps={caps} onBack={back} onError={fail}
                onDataDeleted={() => { resetChat(); setConversations([]); refresh(); }}
                fallback={fallback} onFallback={(v) => { setFallbackState(v); setFallback(v); }}
                speechLang={speechLang} onSpeechLang={(v) => { setSpeechLangState(v); setSpeechLang(v); }}
                voiceURI={voiceURI} onVoiceURI={(v) => { setVoiceURIState(v || null); setVoiceURI(v); }} tts={tts}
              />
            )}
          </main>

          <aside className="thin-scroll shrink-0 space-y-3 border-line px-4 pb-6 pt-3 xl:w-[300px] xl:overflow-y-auto xl:border-l xl:pb-3">
            <Capabilities onNavigate={navigate} />
            <LocalStatusCard models={models} />
          </aside>
        </div>
      </div>
    </div>
  );
}
