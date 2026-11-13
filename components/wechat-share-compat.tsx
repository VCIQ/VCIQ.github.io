"use client";

import { Copy, ExternalLink, X } from "lucide-react";
import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { QRCodeSVG } from "qrcode.react";
import { SourceArticleLink } from "@/components/source-article-link";
import { isNonDurableWeChatArticleUrl } from "@/lib/wechat-link-policy";

type ShareTarget = {
  title: string;
  summary: string;
  url: string;
};

const FAVORITE_SHARE_REQUEST_EVENT = "vciq:favorite-share-request";

function cleanText(value: string | null | undefined): string {
  return (value ?? "").normalize("NFKC").replace(/\s+/g, " ").trim();
}

function absoluteUrl(value: string): string {
  try {
    return new URL(value, window.location.origin).href;
  } catch {
    return value;
  }
}

function isWechatBrowser(): boolean {
  return /MicroMessenger/i.test(navigator.userAgent);
}

function desktopPlatform(): "Windows" | "macOS" | "Linux" | null {
  if (typeof navigator === "undefined") return null;
  const userAgent = navigator.userAgent;
  if (/Mobile|Android|iPhone|iPad|iPod/i.test(userAgent)) return null;
  if (/Windows/i.test(userAgent)) return "Windows";
  if (/Macintosh|Mac OS X/i.test(userAgent)) return "macOS";
  if (/Linux|X11/i.test(userAgent)) return "Linux";
  return null;
}

function isShareTarget(value: unknown): value is ShareTarget {
  if (!value || typeof value !== "object") return false;
  const candidate = value as Partial<ShareTarget>;
  return (
    typeof candidate.title === "string" &&
    typeof candidate.summary === "string" &&
    typeof candidate.url === "string" &&
    Boolean(candidate.title.trim()) &&
    Boolean(candidate.url.trim())
  );
}

function targetFromButton(button: HTMLElement): ShareTarget | null {
  const card = button.closest<HTMLElement>(".favorite-intelligence-card, .favorite-card");
  if (!card) return null;

  const link = card.querySelector<HTMLAnchorElement>(
    ".favorite-intelligence-link[href], .favorite-card-main[href]",
  );
  const title = cleanText(card.querySelector("h3, h2")?.textContent);
  const summary = cleanText(
    card.querySelector<HTMLElement>(".event-main > p, .favorite-card-main > p")?.textContent,
  );
  const href = link?.getAttribute("href") || link?.href || "";
  if (!title || !href) return null;

  return { title, summary, url: absoluteUrl(href) };
}

async function copyText(value: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(value);
    return true;
  } catch {
    const textarea = document.createElement("textarea");
    textarea.value = value;
    textarea.setAttribute("readonly", "true");
    textarea.style.position = "fixed";
    textarea.style.opacity = "0";
    textarea.style.pointerEvents = "none";
    document.body.appendChild(textarea);
    textarea.select();
    const copied = document.execCommand("copy");
    textarea.remove();
    return copied;
  }
}

export function WechatShareCompat() {
  const [target, setTarget] = useState<ShareTarget | null>(null);
  const [notice, setNotice] = useState("");

  useEffect(() => {
    const openQrShare = (item: ShareTarget) => {
      const normalized = { ...item, url: absoluteUrl(item.url) };
      setTarget(normalized);
      if (isNonDurableWeChatArticleUrl(normalized.url)) {
        setNotice("原文链接待更新，暂不生成二维码或复制失效来源。");
        return;
      }

      const platform = desktopPlatform();
      if (platform) {
        setNotice(`${platform} 已直接进入二维码分享模式，不会调用操作系统分享面板。`);
        return;
      }

      if (isWechatBrowser()) {
        const text = `${normalized.title}${
          normalized.summary ? `\n${normalized.summary.slice(0, 140)}` : ""
        }\n${normalized.url}`;
        void copyText(text).then((copied) =>
          setNotice(
            copied
              ? "标题和原链接已复制，请点微信右上角“…”并选择“发送给朋友”或“分享到朋友圈”。"
              : "请点微信右上角“…”并选择“发送给朋友”或“分享到朋友圈”。",
          ),
        );
        return;
      }

      setNotice("已打开二维码分享界面。扫码或复制的链接均直接指向原始情报。");
    };

    const onShareRequest = (event: Event) => {
      const detail = (event as CustomEvent<unknown>).detail;
      if (!isShareTarget(detail)) return;
      openQrShare(detail);
    };

    // Capture fallback supports a mixed-cache deployment where an older
    // favorite-card bundle is still present. It blocks the old click handler
    // before that handler can call navigator.share().
    const onLegacyButtonClick = (event: MouseEvent) => {
      const element = event.target instanceof Element ? event.target : null;
      const button = element?.closest<HTMLElement>("button.favorite-share");
      if (!button) return;

      const item = targetFromButton(button);
      if (!item) return;

      event.preventDefault();
      event.stopPropagation();
      event.stopImmediatePropagation();
      openQrShare(item);
    };

    window.addEventListener(FAVORITE_SHARE_REQUEST_EVENT, onShareRequest);
    document.addEventListener("click", onLegacyButtonClick, true);

    return () => {
      window.removeEventListener(FAVORITE_SHARE_REQUEST_EVENT, onShareRequest);
      document.removeEventListener("click", onLegacyButtonClick, true);
    };
  }, []);

  if (!target || typeof document === "undefined") return null;

  const sourceUnavailable = isNonDurableWeChatArticleUrl(target.url);
  const platform = desktopPlatform();

  const copyOriginalLink = async () => {
    if (sourceUnavailable) {
      setNotice("原文链接待更新，暂不复制失效链接。");
      return;
    }
    const copied = await copyText(target.url);
    setNotice(copied ? "原始链接已复制。" : "复制失败，请点击“打开原始链接”后手动复制。");
  };

  return createPortal(
    <>
      <div
        className="wechat-share-backdrop"
        role="presentation"
        onMouseDown={(event) => {
          if (event.target === event.currentTarget) setTarget(null);
        }}
      >
        <section
          className="wechat-share-dialog"
          role="dialog"
          aria-modal="true"
          aria-labelledby="wechat-share-title"
        >
          <button
            type="button"
            className="wechat-share-close"
            onClick={() => setTarget(null)}
            aria-label="关闭微信分享"
          >
            <X size={18} />
          </button>

          <div className="wechat-share-copy">
            <span>WECHAT QR SHARE</span>
            <h3 id="wechat-share-title">{target.title}</h3>
            <p>
              {platform
                ? `${platform} 桌面端已完全跳过操作系统分享弹窗。请使用手机微信扫码，或复制原始链接发送给微信好友。`
                : "本站已关闭操作系统分享面板，统一使用微信二维码和原始链接分享。"}
            </p>
          </div>

          <div className="wechat-share-qr">
            {sourceUnavailable ? (
              <p role="status">原文链接待更新；当前没有可验证的微信二维码分享目标。</p>
            ) : (
              <>
                <div>
                  <QRCodeSVG
                    value={target.url}
                    size={212}
                    level="M"
                    includeMargin
                    title={`微信扫码打开：${target.title}`}
                  />
                </div>
                <strong>手机微信扫码</strong>
                <p>扫码后直接打开原始情报，再通过微信右上角菜单发送给朋友或分享到朋友圈。</p>
              </>
            )}
          </div>

          <div className="wechat-share-actions">
            <button type="button" disabled={sourceUnavailable} onClick={() => void copyOriginalLink()}>
              <Copy size={15} />
              复制原始链接
            </button>
            <SourceArticleLink href={target.url} unavailableText="原文链接待更新">
              <ExternalLink size={15} />
              打开原始链接
            </SourceArticleLink>
          </div>

          {notice ? (
            <p className="wechat-share-notice" role="status">
              {notice}
            </p>
          ) : null}
        </section>
      </div>

      <style jsx global>{`
        .wechat-share-backdrop {
          position: fixed;
          inset: 0;
          z-index: 1200;
          display: grid;
          place-items: center;
          padding: 20px;
          background: rgba(0, 0, 0, 0.7);
          backdrop-filter: blur(8px);
        }

        .wechat-share-dialog {
          position: relative;
          width: min(720px, 94vw);
          max-height: min(760px, 92vh);
          overflow: auto;
          display: grid;
          grid-template-columns: minmax(0, 1fr) 260px;
          gap: 24px;
          padding: 30px;
          border: 1px solid var(--border);
          background: var(--surface);
          box-shadow: var(--shadow);
          color: var(--text);
        }

        .wechat-share-close {
          position: absolute;
          top: 12px;
          right: 12px;
          display: grid;
          place-items: center;
          width: 32px;
          height: 32px;
          border: 1px solid var(--border-soft);
          background: var(--surface-2);
          color: var(--muted);
          cursor: pointer;
        }

        .wechat-share-copy {
          padding-right: 12px;
        }

        .wechat-share-copy > span {
          color: var(--green-bright);
          font: 600 11px/1 Inter, "Noto Sans SC", sans-serif;
          letter-spacing: 0.14em;
        }

        .wechat-share-copy h3 {
          margin: 18px 0 12px;
          font-size: 23px;
          line-height: 1.45;
        }

        .wechat-share-copy p,
        .wechat-share-qr p {
          margin: 0;
          color: var(--muted);
          font-size: 13px;
          line-height: 1.75;
        }

        .wechat-share-qr {
          display: flex;
          flex-direction: column;
          align-items: center;
          gap: 9px;
          text-align: center;
        }

        .wechat-share-qr > div {
          padding: 8px;
          background: #fff;
        }

        .wechat-share-qr svg {
          display: block;
          max-width: 100%;
          height: auto;
        }

        .wechat-share-qr strong {
          font-size: 14px;
        }

        .wechat-share-actions {
          grid-column: 1 / -1;
          display: flex;
          flex-wrap: wrap;
          gap: 10px;
        }

        .wechat-share-actions button,
        .wechat-share-actions a {
          display: inline-flex;
          align-items: center;
          justify-content: center;
          gap: 7px;
          min-height: 38px;
          padding: 8px 13px;
          border: 1px solid var(--border);
          background: var(--surface-2);
          color: var(--text);
          cursor: pointer;
          font-size: 12px;
        }

        .wechat-share-actions button:hover,
        .wechat-share-actions a:hover {
          border-color: var(--green);
          color: var(--green-bright);
        }

        .wechat-share-notice {
          grid-column: 1 / -1;
          margin: 0;
          padding: 10px 12px;
          border-left: 2px solid var(--green);
          background: color-mix(in srgb, var(--green) 8%, var(--surface-2));
          color: var(--text);
          font-size: 12px;
          line-height: 1.65;
        }

        @media (max-width: 720px) {
          .wechat-share-dialog {
            grid-template-columns: 1fr;
            width: min(430px, 96vw);
            padding: 24px 18px;
          }

          .wechat-share-copy {
            padding-right: 22px;
          }

          .wechat-share-copy h3 {
            font-size: 18px;
          }

          .wechat-share-actions {
            flex-direction: column;
          }

          .wechat-share-actions button,
          .wechat-share-actions a {
            width: 100%;
          }
        }
      `}</style>
    </>,
    document.body,
  );
}
