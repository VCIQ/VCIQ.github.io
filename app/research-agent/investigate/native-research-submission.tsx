"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { NATIVE_RESEARCH_ADMIN_ORIGIN, researchLaunchUrl, researchResultHref, validResearchRequestId } from "@/lib/native-research-contract";

type Pending = { requestId: string; createdAt: number; runId?: number };

export default function NativeResearchSubmission({ eventId }: { eventId: string }) {
  const [status, setStatus] = useState("");
  const [busy, setBusy] = useState(false);
  const [resultHref, setResultHref] = useState("");
  const [fallback, setFallback] = useState("");
  const cleanup = useRef<(() => void) | null>(null);
  const locked = useRef(false);

  useEffect(() => () => { cleanup.current?.(); locked.current = false; }, [eventId]);

  function launch() {
    if (locked.current) return;
    const key = `vciq-native-request:${eventId}`;
    let pending: Pending | null = null;
    try {
      const row = JSON.parse(sessionStorage.getItem(key) || "null") as Pending | null;
      if (row && validResearchRequestId(row.requestId) && Number.isFinite(row.createdAt)
        && Date.now() - row.createdAt < 24 * 60 * 60 * 1000) pending = row;
    } catch {}
    if (pending?.runId && Number.isSafeInteger(pending.runId) && pending.runId > 0) {
      setResultHref(researchResultHref(eventId, pending.requestId, pending.runId));
      setStatus("这条事件已有已受理任务；查看当前任务，不重复调用模型。");
      return;
    }
    const requestId = pending?.requestId ?? crypto.randomUUID();
    const nonce = crypto.randomUUID();
    const launchUrl = researchLaunchUrl(eventId, requestId, nonce);
    const popup = window.open("about:blank", "_blank");
    if (!popup) {
      setFallback(launchUrl);
      setStatus("浏览器阻止弹窗。可点击下方受保护入口，登录后确认一次提交；无需复制事件 ID。");
      return;
    }
    locked.current = true;
    setBusy(true);
    setStatus("已打开受保护提交窗口；若尚未登录，请完成 Cloudflare Access 登录。尚未取得任务回执。");
    try { sessionStorage.setItem(key, JSON.stringify({ requestId, createdAt: pending?.createdAt ?? Date.now() })); } catch {}
    const onMessage = (event: MessageEvent) => {
      if (event.origin !== NATIVE_RESEARCH_ADMIN_ORIGIN || event.source !== popup) return;
      const body = event.data;
      if (body?.eventId !== eventId || body.requestId !== requestId) return;
      if (body.kind === "vciq-native-ready" && body.nonce === nonce) {
        popup.postMessage({ kind: "vciq-native-submit", eventId, requestId, nonce }, NATIVE_RESEARCH_ADMIN_ORIGIN);
      } else if (body.kind === "vciq-native-accepted" && Number.isSafeInteger(body.runId) && body.runId > 0) {
        const href = researchResultHref(eventId, requestId, body.runId);
        try { sessionStorage.setItem(key, JSON.stringify({ requestId, createdAt: Date.now(), runId: body.runId })); } catch {}
        setResultHref(href);
        setStatus("研究任务已受理。新窗口会自动跟踪运行和发布结果，不需要打开 GitHub 操作。");
        cleanup.current?.();
        setBusy(false);
        locked.current = false;
      }
    };
    window.addEventListener("message", onMessage);
    const expiry = window.setTimeout(() => {
      cleanup.current?.();
      setBusy(false);
      locked.current = false;
      setStatus("提交窗口等待已结束；这不代表任务失败。请在提交窗口核对回执，勿重复提交。");
    }, 300_000);
    cleanup.current = () => {
      window.removeEventListener("message", onMessage);
      window.clearTimeout(expiry);
      cleanup.current = null;
    };
    popup.location.replace(launchUrl);
  }

  return <div>
    <button type="button" onClick={launch} disabled={busy}>{busy ? "正在确认提交…" : "提交深研"}</button>
    {resultHref ? <Link href={resultHref}>查看当前任务与报告</Link> : null}
    {fallback ? <a href={fallback} target="_blank" rel="noreferrer">打开受保护提交入口</a> : null}
    {status ? <p role="status" aria-live="polite">{status}</p> : null}
  </div>;
}
