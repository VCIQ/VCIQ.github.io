"use client";

import { useMemo, useState } from "react";

export type IpoWatchlistCompany = {
  id: string;
  board: string;
  sourceRow: number;
  name: string | null;
  nameOrigin: string;
  ocrQuality: string;
  sourcePage: string;
  officialEvidence: string | null;
  officialStatus: string | null;
  officialStatusDate: string | null;
};

const BOARD_ORDER = ["科创板", "沪市主板", "深市主板", "创业板", "北交所"];

function sourcePdfPage(board: string, row: number): number {
  if (board === "沪市主板") return 7;
  if (board === "深市主板") return 8;
  if (board === "科创板") return row <= 38 ? 9 : 10;
  if (board === "创业板") return row <= 38 ? 12 : 13;
  if (row <= 38) return 15;
  if (row <= 79) return 16;
  if (row <= 119) return 17;
  if (row <= 160) return 18;
  return 19;
}

export function IpoWatchlistDirectory({
  companies,
  allowedBoards,
}: {
  companies: IpoWatchlistCompany[];
  allowedBoards?: string[];
}) {
  const [query, setQuery] = useState("");
  const [board, setBoard] = useState("全部");
  const [manuallyCheckedOnly, setManuallyCheckedOnly] = useState(false);
  const eligibleBoards = allowedBoards ?? BOARD_ORDER;
  const included = useMemo(
    () => companies.filter((item) => eligibleBoards.includes(item.board)),
    [companies, eligibleBoards.join("|")],
  );
  const visible = useMemo(
    () => included.filter((item) =>
      item.name &&
      (board === "全部" || item.board === board) &&
      (!manuallyCheckedOnly || item.ocrQuality === "manual_pdf_verified") &&
      (item.name.includes(query.trim()) || String(item.sourceRow).includes(query.trim())),
    ),
    [included, board, manuallyCheckedOnly, query],
  );
  const missing = included.filter((item) => !item.name).length;
  const manuallyChecked = included.filter(
    (item) => item.name && item.ocrQuality === "manual_pdf_verified",
  ).length;

  return (
    <section aria-label="IPO 企业跟踪清单">
      <h2>企业逐项名单</h2>
      <p>
        来源共 {included.length} 个席位，已提取名称 {included.length - missing} 条；
        其中 {manuallyChecked} 条已从原始 PDF 人工核对，
        {included.length - missing - manuallyChecked} 条为初步 OCR 转录，{missing} 条没有名称。
        本栏保留 2026-11-15 来源快照，不等同实时在审清单。
      </p>
      <div style={{ display: "flex", gap: "0.75rem", flexWrap: "wrap", marginBlock: "1rem" }}>
        <label>
          搜索企业
          <input
            type="search"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="公司名称或原表序号"
            style={{ display: "block", padding: "0.5rem", marginTop: "0.4rem" }}
          />
        </label>
        <label>
          拟上市板块
          <select
            value={board}
            onChange={(event) => setBoard(event.target.value)}
            style={{ display: "block", padding: "0.5rem", marginTop: "0.4rem" }}
          >
            <option value="全部">全部</option>
            {eligibleBoards.map((item) => <option key={item} value={item}>{item}</option>)}
          </select>
        </label>
        <label style={{ alignSelf: "end", paddingBottom: "0.6rem" }}>
          <input
            type="checkbox"
            checked={manuallyCheckedOnly}
            onChange={(event) => setManuallyCheckedOnly(event.target.checked)}
          />{" "}
          仅查看 {manuallyChecked} 条人工核对记录
        </label>
      </div>
      <p aria-live="polite">当前展示 {visible.length} 条公司记录</p>
      <div style={{ overflowX: "auto" }}>
        <table style={{ width: "100%", borderCollapse: "collapse", textAlign: "left" }}>
          <thead>
            <tr><th>公司（媒体名单）</th><th>拟上市板块</th><th>原表序号</th><th>来源页</th><th>文字状态</th></tr>
          </thead>
          <tbody>
            {visible.map((item) => (
              <tr key={item.id} style={{ borderTop: "1px solid var(--border, #ddd)" }}>
                <td style={{ padding: "0.65rem 0.35rem" }}>
                  {item.name}
                  {item.officialEvidence && (
                    <div><a href={item.officialEvidence} target="_blank" rel="noreferrer">补充披露证据</a></div>
                  )}
                </td>
                <td>{item.board}</td>
                <td>{item.sourceRow}</td>
                <td>{sourcePdfPage(item.board, item.sourceRow)}</td>
                <td>{item.ocrQuality === "manual_pdf_verified" ? "PDF 人工核对" :
                  item.nameOrigin === "official-record" ? "官方名称" : "OCR 初步转录"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {visible.length === 0 && <p>没有符合筛选条件的可读名称。</p>}
    </section>
  );
}
