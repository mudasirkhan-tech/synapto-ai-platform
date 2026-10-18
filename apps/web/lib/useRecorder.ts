"use client";
import { useRef, useState } from "react";

/** Microphone recording with MediaRecorder. Asks for permission only when start() is called. */
export function useRecorder() {
  const [recording, setRecording] = useState(false);
  const recorder = useRef<MediaRecorder | null>(null);
  const chunks = useRef<Blob[]>([]);

  const start = async () => {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true }); // rejects if denied
    const rec = new MediaRecorder(stream);
    chunks.current = [];
    rec.ondataavailable = (e) => { if (e.data.size) chunks.current.push(e.data); };
    rec.start();
    recorder.current = rec;
    setRecording(true);
  };

  const stop = () =>
    new Promise<Blob | null>((resolve) => {
      const rec = recorder.current;
      if (!rec) { resolve(null); return; }
      rec.onstop = () => {
        rec.stream.getTracks().forEach((t) => t.stop());
        recorder.current = null;
        setRecording(false);
        resolve(new Blob(chunks.current, { type: rec.mimeType || "audio/webm" }));
      };
      rec.stop();
    });

  return { recording, start, stop };
}
