"use client";

import {
  BookmarkPlus,
  ExternalLink,
  FlaskConical,
  Link2,
  X,
} from "lucide-react";
import { useMemo, useState, type FormEvent } from "react";
import { useFavorites } from "@/components/use-favorites";
import {
  buildExternalFavoriteInput,
  externalFavoriteCategoryOptions,
  isExternalFavorite,
  isWeChatArticleUrl,
  manualTextHrefForFavorite,
  researchLeadHrefForFavorite,
  type ExternalFavoriteCategory,
} from "@/lib/external-favorites";
import { toggleFavorite } from "@/lib/favorites";

const EMPTY_FORM = {
  url: "",
  title: "",
  sourceName: "",
  summary: "",
  category: "reference" as ExternalFavoriteCategory,
  keywords: "",
  sectors: "",
  publishedAt: "",
};

export function ExternalFavoriteCapture() {
  const favorites = useFavorites();
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState(EMPTY_FORM);
  const [notice, setNotice] = useState("");
  const [savedLead, setSavedLead] = useState<{
    title: string;
    articleHref: string;
    researchHref: string;
    manualTextHref?: string;
    isWeChat: boolean;
  } | null>(null);

  const recentExternal = useMemo(
    () => favorites.filter(isExternalFavorite).slice(0, 5),
    [favorites],
  );

  const update = (field: keyof typeof EMPTY_FORM, value: string) => {
    setForm((current) => ({ ...current, [field]: value }));
    setNotice("");
  };

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const input = buildExternalFavoriteInput(form);
    if (!input) {
      setNotice("请至少填写有效的 http/https 文章链接和标题。");
      return;
    }

    const duplicate = favorites.find(
      (item) => item.id === input.id || item.href === input.href,
    );
    const leadSource = duplicate ?? {
      ...input,
      keywords: input.keywords ?? [],
      sectors: input.sectors ?? [],
      sources: input.sources ?? [],
    };
    const researchHref = researchLeadHrefForFavorite(leadSource);
    const isWeChat = isWeChatArticleUrl(leadSource.href);
    const manualTextHref = isWeChat ? manualTextHrefForFavorite(leadSource) : undefined;

    if (duplicate) {
      setSavedLead({
        title: duplicate.title,
        articleHref: duplicate.href,
        researchHref,
        manualTextHref,
        isWeChat,
      });
      setNotice(
        isWeChat
          ? "这篇微信文章已经在收藏中。收藏仅保存元数据；服务器读取可能受限，建议粘贴浏览器正文分析。"
          : "这篇文章已经在收藏中，没有重复写入。",
      );
      return;
    }

    const saved = toggleFavorite(input);
    if (!saved) {
      setNotice("收藏没有写入，请检查浏览器是否允许本地存储。");
      return;
    }

    setSavedLead({
      title: input.title,
      articleHref: input.href,
      researchHref,
      manualTextHref,
      isWeChat,
    });
    setNotice(
      isWeChat
        ? "已收藏。微信文章只保存元数据；服务器读取可能受限，推荐从 Chrome 复制正文进入分析。"
        : "已收藏。文章只保存元数据、摘要和原始链接，不镜像全文。",
    );
    setForm(EMPTY_FORM);
  };

  return (
    <>
      <button
        type="button"
        className="external-favorite-trigger"
        onClick={() => setOpen(true)}
        aria-label="收藏外部文章"
      >
        <BookmarkPlus size={16} />
        <span>收藏外部文章</span>
      </button>

      {open ? (
        <div className="external-favorite-backdrop" role="presentation">
          <section
            className="external-favorite-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="external-favorite-title"
          >
            <header>
              <div>
                <p>EXTERNAL ARTICLE → VCIQ</p>
                <h2 id="external-favorite-title">收藏外部文章</h2>
                <span>
                  先保存为研究资料；真正进入赛道、技术、人物、公司或信源库时，再走研究线索审核。
                </span>
              </div>
              <button type="button" onClick={() => setOpen(false)} aria-label="关闭">
                <X size={18} />
              </button>
            </header>

            <form onSubmit={handleSubmit} className="external-favorite-form">
              <label className="wide">
                <span>文章链接 *</span>
                <div className="field-with-icon">
                  <Link2 size={15} />
                  <input
                    type="url"
                    value={form.url}
                    onChange={(event) => update("url", event.target.value)}
                    placeholder="https://mp.weixin.qq.com/s/..."
                    required
                  />
                </div>
              </label>

              <label className="wide">
                <span>标题 *</span>
                <input
                  value={form.title}
                  onChange={(event) => update("title", event.target.value)}
                  placeholder="文章标题"
                  maxLength={240}
                  required
                />
              </label>

              <label>
                <span>来源 / 公众号</span>
                <input
                  value={form.sourceName}
                  onChange={(event) => update("sourceName", event.target.value)}
                  placeholder="例如：量子位"
                  maxLength={120}
                />
              </label>

              <label>
                <span>资料类型</span>
                <select
                  value={form.category}
                  onChange={(event) => update("category", event.target.value)}
                >
                  {externalFavoriteCategoryOptions.map((option) => (
                    <option value={option.value} key={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </label>

              <label>
                <span>发布日期</span>
                <input
                  type="date"
                  value={form.publishedAt}
                  onChange={(event) => update("publishedAt", event.target.value)}
                />
              </label>

              <label>
                <span>赛道</span>
                <input
                  value={form.sectors}
                  onChange={(event) => update("sectors", event.target.value)}
                  placeholder="AI / AGI | 机器人"
                />
              </label>

              <label className="wide">
                <span>关键词</span>
                <input
                  value={form.keywords}
                  onChange={(event) => update("keywords", event.target.value)}
                  placeholder="Agent | Runtime | VLA；用 |、逗号或分号分隔"
                />
              </label>

              <label className="wide">
                <span>为什么值得留存 / 摘要</span>
                <textarea
                  value={form.summary}
                  onChange={(event) => update("summary", event.target.value)}
                  placeholder="用一两句话记录文章价值；后续研究线索提取也会带上这段上下文。"
                  maxLength={1200}
                  rows={4}
                />
              </label>

              <div className="external-favorite-actions wide">
                <button type="submit" className="primary">
                  <BookmarkPlus size={15} />收藏到 VCIQ
                </button>
                <small>收藏仍是浏览器本地优先，并继续参与现有偏好学习。</small>
              </div>
            </form>

            {notice ? <p className="external-favorite-notice">{notice}</p> : null}

            {savedLead ? (
              <div className="research-lead-callout">
                <div>
                  <span>{savedLead.isWeChat ? "微信文章 · BROWSER ASSISTED" : "下一步 · RESEARCH LEAD"}</span>
                  <strong>{savedLead.title}</strong>
                  <p>
                    {savedLead.isWeChat
                      ? "状态：收藏仅保存元数据；服务器自动读取可能受微信反爬限制。推荐从 Chrome 复制正文，进入受保护 Capture 后再审核候选。"
                      : "将同一篇文章送入受保护的 Capture；系统会提取赛道、技术、人物、公司和信源候选，确认后才进入正式追踪。"}
                  </p>
                </div>
                <div>
                  {savedLead.isWeChat && savedLead.manualTextHref ? (
                    <a href={savedLead.manualTextHref} target="_blank" rel="noreferrer" className="lead-action">
                      <FlaskConical size={14} />粘贴正文并分析
                    </a>
                  ) : null}
                  <a
                    href={savedLead.researchHref}
                    target="_blank"
                    rel="noreferrer"
                    className={savedLead.isWeChat ? undefined : "lead-action"}
                  >
                    <FlaskConical size={14} />{savedLead.isWeChat ? "自动尝试解析" : "转为研究线索"}
                  </a>
                  <a href={savedLead.articleHref} target="_blank" rel="noreferrer">
                    <ExternalLink size={14} />打开原文
                  </a>
                </div>
              </div>
            ) : null}

            {recentExternal.length ? (
              <div className="recent-external-favorites">
                <div className="recent-head">
                  <strong>最近的站外收藏</strong>
                  <span>微信文章优先从浏览器正文进入研究分析</span>
                </div>
                {recentExternal.map((item) => {
                  const isWeChat = isWeChatArticleUrl(item.href);
                  return (
                    <div className="recent-row" key={item.id}>
                      <div>
                        <strong>{item.title}</strong>
                        <span>{item.sources[0]?.name || new URL(item.href).hostname}</span>
                      </div>
                      <a
                        href={isWeChat ? manualTextHrefForFavorite(item) : researchLeadHrefForFavorite(item)}
                        target="_blank"
                        rel="noreferrer"
                      >
                        {isWeChat ? "粘贴正文分析 ↗" : "研究线索 ↗"}
                      </a>
                    </div>
                  );
                })}
              </div>
            ) : null}

            <footer>
              <span>生命周期</span>
              <strong>收藏 → 候选线索 → 已追踪 → 核心对象</strong>
              <p>文章被提及不等于对象自动升级；核心对象仍要求人工确认和后续证据积累。</p>
            </footer>
          </section>
        </div>
      ) : null}

      <style jsx global>{`
        .external-favorite-trigger {
          position: fixed;
          z-index: 1060;
          right: 22px;
          bottom: 82px;
          min-height: 40px;
          display: inline-flex;
          align-items: center;
          gap: 7px;
          border: 1px solid var(--green);
          background: var(--surface);
          color: var(--green-bright);
          box-shadow: var(--shadow);
          padding: 9px 13px;
          cursor: pointer;
          font: 600 12px/1 Inter, "Noto Sans SC", sans-serif;
        }
        .external-favorite-trigger:hover { background: var(--surface-2); }
        .external-favorite-backdrop {
          position: fixed;
          inset: 0;
          z-index: 1200;
          display: grid;
          place-items: center;
          padding: 24px;
          background: color-mix(in srgb, #000 58%, transparent);
          backdrop-filter: blur(4px);
        }
        .external-favorite-modal {
          width: min(860px, 100%);
          max-height: min(880px, calc(100vh - 48px));
          overflow: auto;
          border: 1px solid var(--border);
          background: var(--surface);
          box-shadow: var(--shadow);
        }
        .external-favorite-modal > header {
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
        .external-favorite-modal > header p {
          margin: 0 0 6px;
          color: var(--green-bright);
          font: 600 10px/1.2 Inter, sans-serif;
          letter-spacing: .12em;
        }
        .external-favorite-modal > header h2 { margin: 0; font-size: 22px; }
        .external-favorite-modal > header span {
          display: block;
          max-width: 680px;
          margin-top: 7px;
          color: var(--muted);
          font-size: 12px;
          line-height: 1.6;
        }
        .external-favorite-modal > header button {
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
        .external-favorite-form {
          display: grid;
          grid-template-columns: repeat(2, minmax(0, 1fr));
          gap: 14px 16px;
          padding: 22px;
        }
        .external-favorite-form label { min-width: 0; display: block; }
        .external-favorite-form label.wide { grid-column: 1 / -1; }
        .external-favorite-form label > span {
          display: block;
          margin-bottom: 7px;
          color: var(--muted);
          font-size: 11px;
        }
        .external-favorite-form input,
        .external-favorite-form select,
        .external-favorite-form textarea {
          width: 100%;
          border: 1px solid var(--border);
          background: var(--surface-2);
          color: var(--text);
          padding: 10px 11px;
          outline: none;
          font: 13px/1.5 Inter, "Noto Sans SC", sans-serif;
        }
        .external-favorite-form textarea { resize: vertical; min-height: 92px; }
        .external-favorite-form input:focus,
        .external-favorite-form select:focus,
        .external-favorite-form textarea:focus { border-color: var(--green); }
        .field-with-icon { position: relative; }
        .field-with-icon svg {
          position: absolute;
          left: 11px;
          top: 50%;
          transform: translateY(-50%);
          color: var(--muted);
          pointer-events: none;
        }
        .field-with-icon input { padding-left: 35px; }
        .external-favorite-actions {
          display: flex;
          align-items: center;
          gap: 12px;
        }
        .external-favorite-actions .primary {
          min-height: 38px;
          display: inline-flex;
          align-items: center;
          gap: 7px;
          border: 1px solid var(--green);
          background: color-mix(in srgb, var(--green) 14%, var(--surface));
          color: var(--green-bright);
          padding: 8px 13px;
          cursor: pointer;
          font: 600 12px/1 Inter, "Noto Sans SC", sans-serif;
        }
        .external-favorite-actions small { color: var(--muted); font-size: 11px; }
        .external-favorite-notice {
          margin: 0 22px 18px;
          padding: 10px 12px;
          border-left: 3px solid var(--green);
          background: var(--surface-2);
          font-size: 12px;
        }
        .research-lead-callout {
          margin: 0 22px 18px;
          display: flex;
          justify-content: space-between;
          gap: 24px;
          border: 1px solid var(--border);
          padding: 15px;
        }
        .research-lead-callout > div:first-child { min-width: 0; }
        .research-lead-callout span { color: var(--blue); font-size: 10px; letter-spacing: .08em; }
        .research-lead-callout strong { display: block; margin-top: 5px; font-size: 14px; }
        .research-lead-callout p { margin: 6px 0 0; color: var(--muted); font-size: 11px; line-height: 1.6; }
        .research-lead-callout > div:last-child {
          display: flex;
          align-items: center;
          gap: 8px;
          flex: none;
        }
        .research-lead-callout a {
          min-height: 34px;
          display: inline-flex;
          align-items: center;
          gap: 5px;
          border: 1px solid var(--border);
          padding: 7px 10px;
          font-size: 11px;
        }
        .research-lead-callout a.lead-action { border-color: var(--blue); color: var(--blue); }
        .recent-external-favorites {
          margin: 0 22px 18px;
          border-top: 1px solid var(--border);
        }
        .recent-head {
          display: flex;
          justify-content: space-between;
          gap: 16px;
          padding: 14px 0 9px;
        }
        .recent-head strong { font-size: 12px; }
        .recent-head span { color: var(--muted); font-size: 10px; }
        .recent-row {
          display: grid;
          grid-template-columns: minmax(0, 1fr) auto;
          gap: 14px;
          align-items: center;
          padding: 9px 0;
          border-top: 1px solid color-mix(in srgb, var(--border) 70%, transparent);
        }
        .recent-row strong {
          display: block;
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
          font-size: 12px;
        }
        .recent-row span { display: block; margin-top: 3px; color: var(--muted); font-size: 10px; }
        .recent-row a { color: var(--green-bright); font-size: 11px; }
        .external-favorite-modal > footer {
          padding: 15px 22px 20px;
          border-top: 1px solid var(--border);
          background: var(--surface-2);
        }
        .external-favorite-modal > footer span { color: var(--muted); font-size: 10px; }
        .external-favorite-modal > footer strong { display: block; margin: 5px 0; font-size: 12px; }
        .external-favorite-modal > footer p { margin: 0; color: var(--muted); font-size: 11px; }
        @media (max-width: 720px) {
          .external-favorite-trigger { right: 12px; bottom: 72px; }
          .external-favorite-trigger span { display: none; }
          .external-favorite-backdrop { padding: 10px; }
          .external-favorite-modal { max-height: calc(100vh - 20px); }
          .external-favorite-form { grid-template-columns: 1fr; padding: 16px; }
          .external-favorite-form label.wide { grid-column: auto; }
          .external-favorite-actions,
          .research-lead-callout,
          .research-lead-callout > div:last-child { align-items: stretch; flex-direction: column; }
          .external-favorite-notice,
          .research-lead-callout,
          .recent-external-favorites { margin-left: 16px; margin-right: 16px; }
        }
      `}</style>
    </>
  );
}
