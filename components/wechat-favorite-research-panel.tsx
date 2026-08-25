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
    </>
  );
}
