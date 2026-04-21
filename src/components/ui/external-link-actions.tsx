"use client";

import { useEffect, useState } from "react";

function fallbackCopyText(value: string) {
  const textarea = document.createElement("textarea");
  textarea.value = value;
  textarea.setAttribute("readonly", "true");
  textarea.style.position = "fixed";
  textarea.style.opacity = "0";
  textarea.style.pointerEvents = "none";
  document.body.appendChild(textarea);
  textarea.focus();
  textarea.select();
  try {
    document.execCommand("copy");
  } finally {
    document.body.removeChild(textarea);
  }
}

export function normalizeExternalUrl(value: string | null | undefined): string {
  const text = String(value || "").trim();
  if (!text) return "";
  if (text.startsWith("//")) return `https:${text}`;
  if (/^(https?:|mailto:|tel:)/i.test(text)) return text;
  if (/^(mp\.weixin\.qq\.com|developers\.weixin\.qq\.com|open\.weixin\.qq\.com|www\.)/i.test(text)) {
    return `https://${text}`;
  }
  if (/^[a-z0-9.-]+\.[a-z]{2,}(?:\/.*)?$/i.test(text)) {
    return `https://${text}`;
  }
  return text;
}

type ExternalLinkActionsProps = {
  url: string;
  openLabel?: string;
  copyLabel?: string;
  copiedLabel?: string;
  className?: string;
  linkClassName?: string;
  copyClassName?: string;
};

export function ExternalLinkActions({
  url,
  openLabel = "打开原文",
  copyLabel = "复制链接",
  copiedLabel = "已复制",
  className = "",
  linkClassName = "",
  copyClassName = "",
}: ExternalLinkActionsProps) {
  const [copied, setCopied] = useState(false);
  const normalizedUrl = normalizeExternalUrl(url);
  const canOpen = /^https?:\/\//i.test(normalizedUrl) || /^(mailto:|tel:)/i.test(normalizedUrl);

  useEffect(() => {
    if (!copied) {
      return undefined;
    }
    const timer = window.setTimeout(() => {
      setCopied(false);
    }, 1800);
    return () => {
      window.clearTimeout(timer);
    };
  }, [copied]);

  async function handleCopy() {
    const target = normalizedUrl || url;
    if (!target) {
      return;
    }
    try {
      if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(target);
        setCopied(true);
        return;
      }
    } catch {
      // Fall through to DOM fallback.
    }
    try {
      fallbackCopyText(target);
      setCopied(true);
      return;
    } catch {
      // Fall through to prompt fallback.
    }
    window.prompt("复制链接", target);
  }

  function handleOpen() {
    if (!canOpen) {
      return;
    }
    window.open(normalizedUrl, "_blank", "noopener,noreferrer");
  }

  return (
    <div className={`flex flex-wrap items-center gap-2 ${className}`.trim()}>
      <button
        type="button"
        onClick={(event) => {
          event.preventDefault();
          event.stopPropagation();
          handleOpen();
        }}
        disabled={!canOpen}
        className={
          linkClassName ||
          "inline-flex items-center rounded-full border border-slate-200 bg-white/84 px-2.5 py-1 text-[11px] font-medium text-sky-700 transition hover:border-sky-200 hover:bg-white disabled:cursor-not-allowed disabled:border-slate-200 disabled:bg-slate-100 disabled:text-slate-400"
        }
      >
        {openLabel}
      </button>
        <button
          type="button"
        onClick={(event) => {
          event.preventDefault();
          event.stopPropagation();
          void handleCopy();
        }}
        disabled={!normalizedUrl && !url}
        className={
          copyClassName ||
          "inline-flex items-center rounded-full border border-slate-200 bg-white/84 px-2.5 py-1 text-[11px] font-medium text-slate-600 transition hover:border-slate-300 hover:bg-white disabled:cursor-not-allowed disabled:border-slate-200 disabled:bg-slate-100 disabled:text-slate-400"
        }
      >
        {copied ? copiedLabel : copyLabel}
      </button>
    </div>
  );
}
