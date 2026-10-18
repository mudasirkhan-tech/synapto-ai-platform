"use client";
import { useEffect, useState } from "react";
import { documentBlob } from "@/lib/api";

/** Images are served only to their owner, so they are fetched with the auth header and shown from a blob URL. */
export default function AuthImage({ id, alt, className }: { id: string; alt: string; className?: string }) {
  const [src, setSrc] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    let url: string | null = null;
    documentBlob(id)
      .then((blob) => {
        url = URL.createObjectURL(blob);
        if (alive) setSrc(url); else URL.revokeObjectURL(url);
      })
      .catch(() => {});
    return () => { alive = false; if (url) URL.revokeObjectURL(url); };
  }, [id]);

  // eslint-disable-next-line @next/next/no-img-element
  return src ? <img src={src} alt={alt} className={className} /> : <div className={`${className ?? ""} animate-pulse bg-white/5`} />;
}
