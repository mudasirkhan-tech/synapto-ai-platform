"use client";
import { Download, ImageIcon, Loader2, Trash2 } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { deleteDocument, documentBlob, generateImage, listImages } from "@/lib/api";
import type { Capabilities, DocumentInfo } from "@/lib/api";
import { scriptClass } from "@/lib/text";
import AuthImage from "../AuthImage";
import ViewShell, { SetupNotice, card, ghost, input, primary } from "./ViewShell";

const SIZES = [[512, 512], [768, 768], [512, 768], [768, 512]];

export default function ImagesView({ caps, onBack, onError, onAttachImage }: {
  caps: Capabilities | null; onBack: () => void; onError: (e: unknown) => void; onAttachImage: () => void;
}) {
  const [images, setImages] = useState<DocumentInfo[]>([]);
  const [prompt, setPrompt] = useState("");
  const [size, setSize] = useState(0);
  const [steps, setSteps] = useState(20);
  const [busy, setBusy] = useState(false);
  const available = caps?.image_generation.available ?? false;

  const load = useCallback(() => { listImages().then(setImages).catch(onError); }, [onError]);
  useEffect(() => { load(); }, [load]);

  const generate = async () => {
    if (!prompt.trim()) return;
    setBusy(true);
    try {
      const [width, height] = SIZES[size];
      await generateImage({ prompt: prompt.trim(), width, height, steps });
      load();
    } catch (e) { onError(e); } finally { setBusy(false); }
  };

  const download = async (d: DocumentInfo) => {
    const url = URL.createObjectURL(await documentBlob(d.id));
    const a = document.createElement("a");
    a.href = url; a.download = d.filename; a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <ViewShell title="Images" subtitle="Generate with a local model, or ask questions about your own pictures" icon={ImageIcon} onBack={onBack}>
      {caps && !available && <SetupNotice title="Image generation isn't set up" text={caps.image_generation.setup} />}
      <div className={`${card} space-y-2.5`}>
        <textarea dir="auto" value={prompt} onChange={(e) => setPrompt(e.target.value)} rows={2} maxLength={1000}
          placeholder="Describe the image… e.g. a futuristic city at sunset" className={`${input} resize-none ${scriptClass(prompt)}`} />
        <div className="flex flex-wrap items-center gap-2.5 text-[13px]">
          <select value={size} onChange={(e) => setSize(Number(e.target.value))} className={`${input} !w-auto`} aria-label="Size">
            {SIZES.map(([w, h], i) => <option key={i} value={i}>{w}×{h}</option>)}
          </select>
          <label className="flex items-center gap-2 text-white/70">Steps
            <input type="number" min={1} max={50} value={steps} onChange={(e) => setSteps(Math.min(50, Math.max(1, Number(e.target.value) || 20)))} className={`${input} !w-16`} />
          </label>
          <button onClick={generate} disabled={!available || busy || !prompt.trim()} className={`${primary} ml-auto flex items-center gap-2`}>
            {busy && <Loader2 size={14} className="animate-spin" />}{busy ? "Generating…" : "Generate"}
          </button>
        </div>
      </div>

      <div className={`${card} flex items-center justify-between gap-3`}>
        <p className="text-[13px] text-white/70">To ask about an image, attach it in chat. This needs a vision model such as <code>llama3.2-vision</code>.</p>
        <button onClick={onAttachImage} className={`${ghost} shrink-0`}>Attach an image</button>
      </div>

      {images.length > 0 && (
        <div className="grid grid-cols-2 gap-3 md:grid-cols-3">
          {images.map((d) => (
            <figure key={d.id} className="group relative overflow-hidden rounded-xl border border-line">
              <AuthImage id={d.id} alt={d.filename} className="aspect-square w-full object-cover" />
              <figcaption className="absolute inset-x-0 bottom-0 flex items-center justify-end gap-1 bg-black/60 p-1.5 opacity-0 transition group-hover:opacity-100 focus-within:opacity-100">
                <button aria-label="Download" onClick={() => download(d)} className="rounded p-1.5 hover:bg-white/15"><Download size={14} /></button>
                <button aria-label="Delete" onClick={() => deleteDocument(d.id).then(load).catch(onError)} className="rounded p-1.5 hover:bg-white/15 hover:text-red-400"><Trash2 size={14} /></button>
              </figcaption>
            </figure>
          ))}
        </div>
      )}
    </ViewShell>
  );
}
