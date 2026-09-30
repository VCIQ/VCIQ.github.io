"use client";

import { useEffect, useState } from "react";
import { readPriorityIntelligence, type PriorityIntelligenceSnapshot } from "@/lib/priority-intelligence";
import { readBatch6Priority, type Batch6PrioritySnapshot } from "@/lib/batch6-priority-candidates";

export function usePriorityIntelligence(enabled: boolean) {
  const [snapshot, setSnapshot] = useState<PriorityIntelligenceSnapshot | null>(null);
  const [batch6Snapshot, setBatch6Snapshot] = useState<Batch6PrioritySnapshot | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [checkedAt, setCheckedAt] = useState<number | null>(null);
  useEffect(() => {
    if (!enabled) return;
    const controller = new AbortController(); let reading = false;
    const refresh = async () => {
      if (reading || controller.signal.aborted || document.hidden) return;
      reading = true;
      try {
        const signal = AbortSignal.any([controller.signal, AbortSignal.timeout(10_000)]);
        const [priority, batch6] = await Promise.allSettled([
          readPriorityIntelligence(fetch, signal),
          readBatch6Priority(fetch, signal),
        ]);
        if (controller.signal.aborted) return;
        if (priority.status === "fulfilled") {
          setSnapshot((current) => current && Date.parse(current.generatedAt) > Date.parse(priority.value.generatedAt) ? current : priority.value);
        }
        if (batch6.status === "fulfilled") {
          setBatch6Snapshot((current) => current && Date.parse(current.generatedAt) > Date.parse(batch6.value.generatedAt) ? current : batch6.value);
        }
        if (priority.status === "rejected" && batch6.status === "rejected") throw priority.reason;
        setError([
          priority.status === "rejected" ? "重点来源增量暂不可读" : "",
          batch6.status === "rejected" ? "科创 RSS 快速候选暂不可读" : "",
        ].filter(Boolean).join("；") || null);
        setCheckedAt(Date.now());
      } catch (reason) {
        if (!controller.signal.aborted) setError(reason instanceof Error ? reason.message : "重点增量读取失败；保留已有数据。");
      } finally { reading = false; }
    };
    void refresh();
    const timer = window.setInterval(() => void refresh(), 60_000);
    document.addEventListener("visibilitychange", refresh);
    return () => { controller.abort(); window.clearInterval(timer); document.removeEventListener("visibilitychange", refresh); };
  }, [enabled]);
  return { snapshot, batch6Snapshot, error, checkedAt };
}
