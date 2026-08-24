"use client";

import { Cloud, LogIn } from "lucide-react";
import { usePathname } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import {
  favoriteCloudSyncIsDue,
  reconcileFavoritesWithCloud,
  type FavoriteCloudSyncStatus,
} from "@/lib/favorite-cloud-sync";

const TRACKING_ADMIN_URL = "https://vciq-tracking-console.pages.dev/";

type SyncState = FavoriteCloudSyncStatus | null;

function updateFavoritesPageCopy(status: SyncState) {
  const card = document.querySelector<HTMLElement>(".favorites-signal-card");
  const label = card?.querySelector<HTMLElement>("span");
  const note = card?.querySelector<HTMLElement>("p");
  const safety = document.querySelector<HTMLElement>(".favorites-safety > div:first-child");
  const safetyTitle = safety?.querySelector<HTMLElement>("strong");
  const safetyCopy = safety?.querySelector<HTMLElement>("p");

  if (!status) {
    if (label) label.textContent = "收藏同步";
    if (note) note.textContent = "项收藏 · 正在检查云端账户";
    return;
  }

  if (status.state === "synced") {
    if (label) label.textContent = "账户收藏";
    if (note) note.textContent = "项收藏 · 已与云端账户同步";
    if (safetyTitle) safetyTitle.textContent = "云端收藏已开启";
    if (safetyCopy) {
      safetyCopy.textContent = "收藏同时保留在当前浏览器并同步到受保护的个人账户；导出备份可继续作为离线副本。";
    }
    return;
  }

  if (status.state === "auth-required") {
    if (label) label.textContent = "当前浏览器";
    if (note) note.textContent = "项收藏 · 登录管理端后可跨浏览器恢复";
    if (safetyTitle) safetyTitle.textContent = "云同步等待登录";
    if (safetyCopy) {
      safetyCopy.textContent = "当前收藏仍安全保存在本机。登录受保护的 Tracking Admin 后，返回本页即可自动同步与恢复。";
    }
    return;
  }

  if (label) label.textContent = "当前浏览器";
  if (note) note.textContent = "项收藏 · 本地可用，云同步暂不可用";
  if (safetyTitle) safetyTitle.textContent = "本地收藏已保留";
  if (safetyCopy) {
    safetyCopy.textContent = "云端同步暂时不可用，不影响当前浏览器中的收藏；可重新连接管理端后再次尝试。";
  }
}

export function FavoriteCloudSync() {
  const pathname = usePathname();
  const [status, setStatus] = useState<SyncState>(null);
  const [actionMount, setActionMount] = useState<HTMLElement | null>(null);
  const inFlight = useRef(false);

  const sync = useCallback(async () => {
    if (inFlight.current) return;
    inFlight.current = true;
    try {
      const next = await reconcileFavoritesWithCloud();
      setStatus(next);
    } finally {
      inFlight.current = false;
    }
  }, []);

  useEffect(() => {
    if (favoriteCloudSyncIsDue()) void sync();

    const onVisible = () => {
      if (document.visibilityState !== "visible") return;
      if (status?.state === "auth-required" || status?.state === "unavailable") {
        void sync();
        return;
      }
      if (favoriteCloudSyncIsDue()) void sync();
    };
    document.addEventListener("visibilitychange", onVisible);
    return () => document.removeEventListener("visibilitychange", onVisible);
  }, [status, sync]);

  useEffect(() => {
    if (!pathname.startsWith("/favorites")) return;
    updateFavoritesPageCopy(status);
    const frame = window.requestAnimationFrame(() => {
      setActionMount(document.querySelector<HTMLElement>(".favorites-transfer-actions"));
    });
    return () => window.cancelAnimationFrame(frame);
  }, [pathname, status]);

  const needsConnection = status?.state === "auth-required" || status?.state === "unavailable";
  if (!pathname.startsWith("/favorites") || !actionMount || !needsConnection) {
    return null;
  }

  return createPortal(
    <a
      href={TRACKING_ADMIN_URL}
      target="_blank"
      rel="noreferrer"
      title="打开受保护的管理端并建立云收藏会话"
      style={{
        display: "inline-flex",
        minHeight: 36,
        alignItems: "center",
        gap: 6,
        padding: "0 12px",
        border: "1px solid var(--green)",
        color: "var(--green-bright)",
        fontSize: 11,
      }}
    >
      <Cloud size={14} aria-hidden="true" />
      <LogIn size={13} aria-hidden="true" />
      连接云收藏
    </a>,
    actionMount,
  );
}
