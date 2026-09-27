"use client";

import { useEffect, useState } from "react";
import { NATIVE_RESEARCH_REPORTS_PATH, parseNativeResearchReports, type NativeResearchReport } from "@/lib/native-research-contract";

export async function fetchNativeResearchReports(signal?: AbortSignal): Promise<NativeResearchReport[]> {
  const response = await fetch(NATIVE_RESEARCH_REPORTS_PATH, { cache: "no-store", signal, headers: { accept: "application/json" } });
  if (!response.ok) throw new Error(`报告索引读取失败（HTTP ${response.status}）。`);
  if (Number(response.headers.get("content-length") || 0) > 2_000_000) throw new Error("报告索引超过读取预算。");
  const raw = await response.text();
  if (new TextEncoder().encode(raw).byteLength > 2_000_000) throw new Error("报告索引超过读取预算。");
  return parseNativeResearchReports(JSON.parse(raw) as unknown);
}

export function useNativeResearchReports(poll = false) {
  const [reports, setReports] = useState<NativeResearchReport[] | null>(null);
  const [error, setError] = useState("");
  const [checkedAt, setCheckedAt] = useState("");
  useEffect(() => {
    let active = true;
    let running = false;
    const deadline = Date.now() + 20 * 60_000;
    const controller = new AbortController();
    const read = async () => {
      if (running || !active || document.hidden || Date.now() > deadline) return;
      running = true;
      try {
        const result = await fetchNativeResearchReports(AbortSignal.any([controller.signal, AbortSignal.timeout(15_000)]));
        if (active) { setReports(result); setError(""); setCheckedAt(new Date().toISOString()); }
      } catch (reason) {
        if (active) setError(reason instanceof Error ? reason.message : "暂时无法读取研究报告；保留上次内容。");
      } finally { running = false; }
    };
    void read();
    const interval = poll ? window.setInterval(() => void read(), 20_000) : null;
    const onFocus = () => void read();
    window.addEventListener("focus", onFocus);
    return () => { active = false; controller.abort(); if (interval !== null) window.clearInterval(interval); window.removeEventListener("focus", onFocus); };
  }, [poll]);
  return { reports, error, checkedAt };
}
