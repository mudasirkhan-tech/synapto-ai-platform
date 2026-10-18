"use client";
import { useCallback, useEffect, useRef, useState } from "react";

interface RecognitionEvent { resultIndex: number; results: ArrayLike<ArrayLike<{ transcript: string }> & { isFinal: boolean }> }
interface Recognition {
  lang: string; interimResults: boolean; continuous: boolean; maxAlternatives: number;
  onstart: (() => void) | null; onend: (() => void) | null;
  onresult: ((e: RecognitionEvent) => void) | null; onerror: ((e: { error: string }) => void) | null;
  start(): void; stop(): void; abort(): void;
}
type Ctor = new () => Recognition;

export type SpeechState = "idle" | "starting" | "listening" | "processing" | "denied" | "error";

/**
 * Browser speech recognition (Web Speech API). Whether audio is processed on-device or by the browser vendor's
 * service depends on the browser, so it is not promised to be offline. One session at a time; state always resets.
 */
export function useSpeechRecognition(opts: { lang: string; onFinal: (text: string) => void; onInterim?: (text: string) => void }) {
  const [supported, setSupported] = useState(false);
  const [state, setState] = useState<SpeechState>("idle");
  const [message, setMessage] = useState<string | null>(null);
  const rec = useRef<Recognition | null>(null);
  const busy = useRef(false); // blocks double clicks / overlapping sessions
  const cb = useRef(opts);
  cb.current = opts;

  useEffect(() => {
    const w = window as unknown as { SpeechRecognition?: Ctor; webkitSpeechRecognition?: Ctor };
    setSupported(Boolean(w.SpeechRecognition ?? w.webkitSpeechRecognition));
    return () => { try { rec.current?.abort(); } catch { /* already stopped */ } };
  }, []);

  const start = useCallback(() => {
    const w = window as unknown as { SpeechRecognition?: Ctor; webkitSpeechRecognition?: Ctor };
    const Recognizer = w.SpeechRecognition ?? w.webkitSpeechRecognition;
    if (!Recognizer || busy.current) return;
    busy.current = true;
    setMessage(null);
    setState("starting");

    const r = new Recognizer();
    r.lang = cb.current.lang;
    r.interimResults = true;
    r.continuous = false;
    r.maxAlternatives = 1;
    const committed = new Set<number>(); // result indexes already inserted: prevents duplicate transcript text

    r.onstart = () => setState("listening");
    r.onresult = (e) => {
      let interim = "";
      for (let i = e.resultIndex; i < e.results.length; i++) {
        const res = e.results[i];
        const text = res[0]?.transcript ?? "";
        if (res.isFinal) {
          if (!committed.has(i) && text.trim()) { committed.add(i); cb.current.onFinal(text.trim()); }
        } else interim += text;
      }
      cb.current.onInterim?.(interim);
    };
    r.onerror = (e) => {
      switch (e.error) {
        case "not-allowed": case "service-not-allowed":
          setState("denied"); setMessage("Microphone access is blocked. Allow it in your browser's site settings, then try again."); break;
        case "no-speech": setMessage("No speech detected. Try again."); break;
        case "audio-capture": setState("error"); setMessage("No microphone was found."); break;
        case "network": setState("error"); setMessage("The browser's speech service could not be reached. Check your connection, or use the Voice page with local Whisper if installed."); break;
        case "language-not-supported": setState("error"); setMessage("This browser doesn't support speech recognition for the selected language."); break;
        case "aborted": break;
        default: setState("error"); setMessage("Speech recognition failed. Please try again.");
      }
    };
    r.onend = () => { // always runs, even after errors or unexpected termination
      busy.current = false;
      rec.current = null;
      cb.current.onInterim?.("");
      setState((s) => (s === "denied" || s === "error" ? s : "idle"));
    };

    rec.current = r;
    try { r.start(); }
    catch { busy.current = false; rec.current = null; setState("error"); setMessage("Could not start speech recognition."); }
  }, []);

  const stop = useCallback(() => {
    if (!rec.current) return;
    setState("processing"); // the browser delivers any pending result, then fires onend
    try { rec.current.stop(); } catch { /* ignore */ }
  }, []);

  const cancel = useCallback(() => { try { rec.current?.abort(); } catch { /* ignore */ } }, []);

  return { supported, state, message, start, stop, cancel, listening: state === "listening" };
}
