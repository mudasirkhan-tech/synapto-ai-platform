"use client";
import { Check, Copy } from "lucide-react";
import { isValidElement, useState } from "react";
import type { ReactElement, ReactNode } from "react";
import ReactMarkdown from "react-markdown";
import type { Components } from "react-markdown";
import rehypeHighlight from "rehype-highlight";
import remarkGfm from "remark-gfm";
import { copyText } from "@/lib/clipboard";
import { detectDir, scriptClass } from "@/lib/text";

function nodeText(node: ReactNode): string {
  if (node == null || typeof node === "boolean") return "";
  if (typeof node === "string" || typeof node === "number") return String(node);
  if (Array.isArray(node)) return node.map(nodeText).join("");
  if (isValidElement(node)) return nodeText((node as ReactElement<{ children?: ReactNode }>).props.children);
  return "";
}

function CodeBlock({ children }: { children?: ReactNode }) {
  const [copied, setCopied] = useState(false);
  const code = isValidElement(children) ? (children as ReactElement<{ className?: string }>) : null;
  const lang = /language-([\w+-]+)/.exec(code?.props.className ?? "")?.[1] ?? "text";

  const copy = async () => {
    if (await copyText(nodeText(children).replace(/\n$/, ""))) {
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    }
  };

  return (
    <div dir="ltr" className="my-3 overflow-hidden rounded-xl border border-line bg-[#0d1117] text-left">
      <div className="flex items-center justify-between border-b border-line bg-white/[0.04] px-3 py-1">
        <span className="text-[11px] uppercase tracking-wide text-white/55">{lang}</span>
        <button onClick={copy} aria-label="Copy code" className="flex items-center gap-1.5 rounded-md px-2 py-1 text-[11px] text-white/70 hover:bg-white/10 hover:text-white">
          {copied ? <Check size={13} className="text-emerald-400" /> : <Copy size={13} />}
          {copied ? "Copied" : "Copy code"}
        </button>
      </div>
      <pre className="thin-scroll overflow-x-auto">{children}</pre>
    </div>
  );
}

// dir="auto" lets every paragraph/list/heading pick its own direction, so mixed Urdu + English replies read correctly.
const components: Components = {
  pre: ({ children }) => <CodeBlock>{children}</CodeBlock>,
  a: ({ href, children }) => <a href={href} target="_blank" rel="noopener noreferrer">{children}</a>,
  p: ({ node, ...props }) => <p dir="auto" {...props} />,
  li: ({ node, ...props }) => <li dir="auto" {...props} />,
  h1: ({ node, ...props }) => <h1 dir="auto" {...props} />,
  h2: ({ node, ...props }) => <h2 dir="auto" {...props} />,
  h3: ({ node, ...props }) => <h3 dir="auto" {...props} />,
  h4: ({ node, ...props }) => <h4 dir="auto" {...props} />,
  blockquote: ({ node, ...props }) => <blockquote dir="auto" {...props} />,
  td: ({ node, ...props }) => <td dir="auto" {...props} />,
  th: ({ node, ...props }) => <th dir="auto" {...props} />,
};

export default function MarkdownView({ content }: { content: string }) {
  return (
    <div className={`md ${scriptClass(content)}`} dir={detectDir(content)}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={[[rehypeHighlight, { detect: false, ignoreMissing: true }]]}
        components={components}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}
