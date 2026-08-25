"use client";

import {
  ExternalLink,
  FlaskConical,
  ShieldAlert,
  X,
} from "lucide-react";
import { useMemo, useState } from "react";
import { useFavorites } from "@/components/use-favorites";
import {
  isExternalFavorite,
  isWeChatArticleUrl,
  manualTextHrefForFavorite,
  researchLeadHrefForFavorite,
} from "@/lib/external-favorites";

export function WeChatFavoriteResearchPanel() {
  const favorites = useFavorites();
  const [open, setOpen] = useState(false);
  const wechatFavorites = useMemo(
    () => favorites
      .filter((item) => isExternalFavorite(item) && isWeChatArticleUrl(item.href))
      .sort((left, right) => right.savedAt.localeCompare(left.savedAt)),
    [favorites],
  );

  if (!wechatFavorites.length) return null;

  return (
    <>
      <button
        type="button"
        className="wechat-import-trigger"
        onClick={() => setOpen(true)}
        aria-label={`微信正文分析，共 ${wechatFavorites.length} 篇收藏`}
      >
        <FlaskConical size={16} />
        <span>微信正文分析</span>
        <b>{wechatFavorites.length}</b>
      </button>

      {open ? (
        <div className="wechat-import-backdrop" role="presentation">
          <section
            className="wechat-import-panel"
            role="dialog"
            aria-modal="true"
            aria-labelledby="wechat-import-title"
          >
            <header>
              <div>
                <p>WECHAT · BROWSER ASSISTED CAPTURE</p>
                <h2 id="wechat-import-title">微信文章正文分析</h2>
                <span>
                  Chrome 能正常阅读，不代表服务器能稳定抓取。VCIQ 收藏层继续只保存元数据；需要正文研究时，从你已能阅读的浏览器复制正文进入受保护的 Capture。
                </span>
              </div>
              <button type="button" onClick={() => setOpen(false)} aria-label="关闭微信正文分析">
                <X size={18} />
              </button>
            </header>

            <div className="wechat-import-policy">
              <ShieldAlert size={18} />
              <div>
                <strong>不绕过微信访问控制</strong>
                <p>不上传 Cookie、不解验证码、不轮换代理；正文只在你主动粘贴后用于本次候选提取，不在公开收藏页镜像全文。</p>
              </div>
            </div>

            <div className="wechat-import-list">
              {wechatFavorites.map((item) => {
                const source = item.sources[0]?.name || "微信公众号";
                const date = item.publishedAt || item.savedAt.slice(0, 10);
                return (
                  <article className="wechat-import-row" key={item.id}>
                    <div className="wechat-import-main">
                      <div className="wechat-import-meta">
                        <span>{source}</span>
                        <time>{date}</time>
                      </div>
                      <h3>{item.title}</h3>
                      <div className="wechat-import-status" aria-label="微信文章抓取状态">
                        <span>收藏：仅元数据</span>
                        <span>服务器读取：受限风险</span>
                        <strong>建议：浏览器正文导入</strong>
                      </div>
                    </div>
                    <div className="wechat-import-actions">
                      <a
                        href={manualTextHrefForFavorite(item)}
                        target="_blank"
                        rel="noreferrer"
                        className="primary"
                      >
                        <FlaskConical size={14} />粘贴正文并分析
                      </a>
                      <a
                        href={researchLeadHrefForFavorite(item)}
                        target="_blank"
                        rel="noreferrer"
                      >
                        自动尝试解析
                      </a>
                      <a href={item.href} target="_blank" rel="noreferrer" aria-label={`打开原文：${item.title}`}>
                        <ExternalLink size={14} />打开原文
                      </a>
                    </div>
                  </article>
                );
              })}
            </div>

            <footer>
              <strong>推荐顺序</strong>
              <span>微信文章优先“粘贴正文并分析”；普通公开网页仍可继续使用服务器自动解析。</span>
            </footer>
          </section>
        </div>
      ) : null}

      <style jsx global>{`
        .wechat-import-trigger {
          position: fixed;
          z-index: 1060;
          right: 22px;
          bottom: 130px;
          min-height: 40px;
          display: inline-flex;
          align-items: center;
          gap: 7px;
          border: 1px solid var(--blue);
          background: var(--surface);
          color: var(--blue);
          box-shadow: var(--shadow);
          padding: 9px 11px;
          cursor: pointer;
          font: 600 12px/1 Inter, "Noto Sans SC", sans-serif;
        }
        .wechat-import-trigger:hover { background: var(--surface-2); }
        .wechat-import-trigger b {
          min-width: 20px;
          height: 20px;
          display: inline-grid;
          place-items: center;
          border-radius: 999px;
          background: color-mix(in srgb, var(--blue) 14%, var(--surface));
          font-size: 10px;
        }
        .wechat-import-backdrop {
          position: fixed;
          inset: 0;
          z-index: 1210;
          display: grid;
          place-items: center;
          padding: 24px;
          background: color-mix(in srgb, #000 58%, transparent);
          backdrop-filter: blur(4px);
        }
        .wechat-import-panel {
          width: min(960px, 100%);
          max-height: min(880px, calc(100vh - 48px));
          overflow: auto;
          border: 1px solid var(--border);
          background: var(--surface);
          box-shadow: var(--shadow);
        }
        .wechat-import-panel > header {
          position: sticky;
          top: 0;
          z-index: 2;
          display: flex;
          justify-content: space-between;
          gap: 24px;
          padding: 20px 22px;
          border-bottom: 1px solid var(--border);
          background: color-mix(in srgb, var(--surface) 96%, transparent);
          backdrop-filter: blur(8px);
        }
        .wechat-import-panel > header p {
          margin: 0 0 6px;
          color: var(--blue);
          font: 600 10px/1.2 Inter, sans-serif;
          letter-spacing: .12em;
        }
        .wechat-import-panel > header h2 { margin: 0; font-size: 22px; }
        .wechat-import-panel > header span {
          display: block;
          max-width: 720px;
          margin-top: 7px;
          color: var(--muted);
          font-size: 12px;
          line-height: 1.65;
        }
        .wechat-import-panel > header button {
          width: 34px;
          height: 34px;
          flex: none;
          display: grid;
          place-items: center;
          border: 1px solid var(--border);
          background: transparent;
          color: var(--text);
          cursor: pointer;
        }
        .wechat-import-policy {
          display: flex;
          gap: 12px;
          align-items: flex-start;
          margin: 18px 22px 0;
          padding: 13px 14px;
          border-left: 3px solid var(--blue);
          background: var(--surface-2);
        }
        .wechat-import-policy svg { flex: none; margin-top: 2px; color: var(--blue); }
        .wechat-import-policy strong { font-size: 12px; }
        .wechat-import-policy p { margin: 4px 0 0; color: var(--muted); font-size: 11px; line-height: 1.6; }
        .wechat-import-list { padding: 10px 22px 20px; }
        .wechat-import-row {
          display: grid;
          grid-template-columns: minmax(0, 1fr) auto;
          gap: 24px;
          align-items: center;
          padding: 15px 0;
          border-bottom: 1px solid var(--border);
        }
        .wechat-import-row:last-child { border-bottom: 0; }
        .wechat-import-main { min-width: 0; }
        .wechat-import-meta { display: flex; gap: 10px; color: var(--muted); font-size: 10px; }
        .wechat-import-row h3 { margin: 6px 0 9px; font-size: 14px; line-height: 1.45; }
        .wechat-import-status { display: flex; flex-wrap: wrap; gap: 6px; }
        .wechat-import-status span,
        .wechat-import-status strong {
          border: 1px solid var(--border);
          background: var(--surface-2);
          padding: 4px 7px;
          font-size: 9px;
          font-weight: 500;
        }
        .wechat-import-status strong { border-color: color-mix(in srgb, var(--blue) 55%, var(--border)); color: var(--blue); }
        .wechat-import-actions {
          display: flex;
          align-items: center;
          justify-content: flex-end;
          gap: 7px;
          flex-wrap: wrap;
          max-width: 360px;
        }
        .wechat-import-actions a {
          min-height: 34px;
          display: inline-flex;
          align-items: center;
          justify-content: center;
          gap: 5px;
          border: 1px solid var(--border);
          background: var(--surface);
          padding: 7px 10px;
          color: var(--text);
          font-size: 10px;
          white-space: nowrap;
        }
        .wechat-import-actions a:hover { border-color: var(--green); color: var(--green-bright); }
        .wechat-import-actions a.primary {
          border-color: var(--blue);
          background: color-mix(in srgb, var(--blue) 9%, var(--surface));
          color: var(--blue);
          font-weight: 600;
        }
        .wechat-import-panel > footer {
          display: flex;
          gap: 10px;
          align-items: baseline;
          padding: 14px 22px 18px;
          border-top: 1px solid var(--border);
          background: var(--surface-2);
        }
        .wechat-import-panel > footer strong { font-size: 11px; }
        .wechat-import-panel > footer span { color: var(--muted); font-size: 10px; }
        @media (max-width: 760px) {
          .wechat-import-trigger { right: 12px; bottom: 120px; }
          .wechat-import-trigger span { display: none; }
          .wechat-import-backdrop { padding: 10px; }
          .wechat-import-panel { max-height: calc(100vh - 20px); }
          .wechat-import-policy { margin-left: 16px; margin-right: 16px; }
          .wechat-import-list { padding-left: 16px; padding-right: 16px; }
          .wechat-import-row { grid-template-columns: 1fr; gap: 10px; }
          .wechat-import-actions { justify-content: flex-start; max-width: none; }
          .wechat-import-panel > footer { align-items: flex-start; flex-direction: column; }
        }
      `}</style>
    </>
  );
}
