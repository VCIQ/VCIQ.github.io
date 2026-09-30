"use client";

import { useEffect, useState } from "react";
import { readPriorityIntelligence, type PriorityIntelligenceSnapshot } from "@/lib/priority-intelligence";

export function usePriorityIntelligence(enabled: boolean) {
  const [snapshot, setSnapshot] = useState<PriorityIntelligenceSnapshot | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [checkedAt, setCheckedAt] = useState<number | null>(null);
  useEffect(() => {
    if (!enabled) return;
    const controller = new AbortController(); let reading = false;
    const refresh = async () => {
      if (reading || controller.signal.aborted || document.hidden) return;
      reading = true;
      try {
        const result = await readPriorityIntelligence(fetch, AbortSignal.any([controller.signal, AbortSignal.timeout(10_000)]));
        if (controller.signal.aborted) return;
        setSnapshot((current) => current && Date.parse(current.generatedAt) > Date.parse(result.generatedAt) ? current : result);
        setError(null); setCheckedAt(Date.now());
      } catch (reason) {
        if (!controller.signal.aborted) setError(reason instanceof Error ? reason.message : "重点增量读取失败；保留已有数据。");
      } finally { reading = false; }
    };
    void refresh();
    const timer = window.setInterval(() => void refresh(), 60_000);
    document.addEventListener("visibilitychange", refresh);
    return () => { controller.abort(); window.clearInterval(timer); document.removeEventListener("visibilitychange", refresh); };
  }, [enabled]);
  return { snapshot, error, checkedAt };
}
