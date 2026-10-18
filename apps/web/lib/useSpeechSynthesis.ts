"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { scriptClass } from "./text";

const SENTENCE = /(?<=[.!?؟۔।])\s+/;

export function toSpeakable(markdown: string): string {
  return markdown
    .replace(/```[\s\S]*?```/g, " (code block omitted) ")
    .replace(/`([^`]*)`/g, "$1")
    .replace(/!\[[^\]]*\]\([^)]*\)/g, "")
    .replace(/\[([^\]]+)\]\([^)]*\)/g, "$1")
    .replace(/^#{1,6}\s*/gm, "")
    .replace(/^\s*[-*+]\s+/gm, "")
    .replace(/[*_~>|]/g, "")
    .replace(/\s+/g, " ")
    .trim();
}

/** Splits long text into utterance-sized pieces (browsers cut off very long utterances). */
export function chunkForSpeech(text: string, max = 220): string[] {
  const out: string[] = [];
  let cur = "";
  for (const sentence of text.split(SENTENCE)) {
    if (sentence.length > max) {
      if (cur) { out.push(cur); cur = ""; }
      for (let i = 0; i < sentence.length; i += max) out.push(sentence.slice(i, i + max));
    } else if (cur && cur.length + 1 + sentence.length > max) { out.push(cur); cur = sentence; }
    else cur = cur ? `${cur} ${sentence}` : sentence;
  }
  if (cur) out.push(cur);
  return out;
}

const PREFERRED: Record<string, string[]> = {
  "font-urdu": ["ur", "ar", "fa", "hi"], "font-arabic": ["ar", "fa", "ur"], "font-deva": ["hi", "mr", "ne"], "font-hebrew": ["he"],
};

export function pickVoice(voices: SpeechSynthesisVoice[], text: string, preferredURI: string | null): { voice: SpeechSynthesisVoice | null; note: string | null } {
  const chosen = preferredURI ? voices.find((v) => v.voiceURI === preferredURI) : undefined;
  if (chosen) return { voice: chosen, note: null };
  const wanted = PREFERRED[scriptClass(text)];
  if (wanted) {
    for (const lang of wanted) {
      const v = voices.find((x) => x.lang.toLowerCase().startsWith(lang));
      if (v) return { voice: v, note: null };
    }
    return { voice: null, note: "No installed voice for this language was found, so the default voice is used and pronunciation may be poor." };
  }
  const nav = typeof navigator !== "undefined" ? navigator.language.toLowerCase() : "en";
  return { voice: voices.find((v) => v.lang.toLowerCase() === nav) ?? null, note: null };
}

/** Browser text-to-speech with pause/resume/stop. Only one session at a time; cancelled on demand and on unmount. */
export function useSpeechSynthesis(preferredURI: string | null) {
  const [supported, setSupported] = useState(false);
  const [voices, setVoices] = useState<SpeechSynthesisVoice[]>([]);
  const [speakingId, setSpeakingId] = useState<string | null>(null);
  const [paused, setPaused] = useState(false);
  const [note, setNote] = useState<string | null>(null);
  const session = useRef(0);
  const voicesRef = useRef<SpeechSynthesisVoice[]>([]);
  const uriRef = useRef(preferredURI);
  uriRef.current = preferredURI;

  useEffect(() => {
    if (!("speechSynthesis" in window) || !("SpeechSynthesisUtterance" in window)) return;
    setSupported(true);
    const load = () => { const list = window.speechSynthesis.getVoices(); voicesRef.current = list; setVoices(list); };
    load();
    window.speechSynthesis.addEventListener("voiceschanged", load);
    return () => {
      window.speechSynthesis.removeEventListener("voiceschanged", load);
      session.current += 1;
      window.speechSynthesis.cancel();
    };
  }, []);

  const stop = useCallback(() => {
    if (!("speechSynthesis" in window)) return;
    session.current += 1; // invalidates any queued chunks
    window.speechSynthesis.cancel();
    setSpeakingId(null); setPaused(false);
  }, []);

  const speak = useCallback((id: string, markdown: string) => {
    if (!("speechSynthesis" in window)) return;
    session.current += 1;
    window.speechSynthesis.cancel(); // never overlap two speech sessions
    const mine = session.current;
    const text = toSpeakable(markdown);
    const queue = chunkForSpeech(text);
    if (!queue.length) return;
    const { voice, note: n } = pickVoice(voicesRef.current, text, uriRef.current);
    setNote(n); setSpeakingId(id); setPaused(false);

    const next = () => {
      if (session.current !== mine) return;
      const piece = queue.shift();
      if (!piece) { setSpeakingId(null); return; }
      const u = new SpeechSynthesisUtterance(piece);
      if (voice) { u.voice = voice; u.lang = voice.lang; }
      u.onend = next; // async chain: never blocks the UI thread
      u.onerror = (e) => { if (e.error !== "canceled" && e.error !== "interrupted") { setNote("Speech playback failed."); stop(); } };
      window.speechSynthesis.speak(u);
    };
    next();
  }, [stop]);

  const pause = useCallback(() => { window.speechSynthesis?.pause(); setPaused(true); }, []);
  const resume = useCallback(() => { window.speechSynthesis?.resume(); setPaused(false); }, []);

  return { supported, voices, speakingId, paused, note, speak, pause, resume, stop };
}
export type SpeechSynthState = ReturnType<typeof useSpeechSynthesis>;
