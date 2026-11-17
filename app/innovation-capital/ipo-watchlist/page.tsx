import type { Metadata } from "next";
import Link from "next/link";
import importState from "@/config/innovation_capital_import_pending_20261116.json";
import watchlist from "@/config/ipo_priority_watchlist_20261115.json";
import { IpoWatchlistDirectory } from "@/components/ipo-watchlist-directory";

export const metadata: Metadata = {
  title: "IPO 重点关注名单｜科创资本",
  description: "用户指定的最丨投行 IPO 项目历史快照。按拟上市板块分类，保留来源与统计日期。",
};

const boards = [
  { name: "科创板", count: importState.sourceSnapshotCounts.starMarket, key: "star" },
  { name: "沪深主板", count: importState.sourceSnapshotCounts.mainBoardShanghaiShenzhen, key: "main" },
  { name: "创业板", count: importState.sourceSnapshotCounts.growthEnterpriseMarket, key: "gem" },
  { name: "北交所", count: importState.sourceSnapshotCounts.beijingStockExchange, key: "bse" },
];

export default function IpoWatchlistPage() {
  return (
    <main className="page-shell subpage">
      <header className="page-header">
        <p className="eyebrow">INNOVATION CAPITAL / IPO WATCHLIST</p>
        <h1>潜在上市公司重点跟踪</h1>
        <p>来源：最丨投行《{importState.sourceTitle}》；统计截至 2026 年 11 月 15 日 22:00（北京时间）。</p>
        <p>此页展示已采纳的媒体统计快照，不将历史在审状态称为实时审核结果。</p>
      </header>
      <section aria-label="板块分布">
        <h2>按拟上市板块分类 · 共 {importState.sourceSnapshotCounts.total} 家</h2>
        <ul>
          {boards.map((item) => (
            <li key={item.key}>
              <strong>{item.name}</strong>：{item.count} 家
            </li>
          ))}
        </ul>
        <p>其中非科创板 {importState.sourceSnapshotCounts.nonStarTotal} 家。</p>
        <Link href="/innovation-capital/ipo-watchlist/non-star/">查看非科创板独立子频道</Link>
      </section>
      <section aria-label="证据边界">
        <h2>名单来源与导入状态</h2>
        <p>
          已按用户决定将媒体名单作为重点跟踪来源，并按原表编号导入公司记录。
          PDF 文字识别存疑及缺失的名称不以猜测替代；实际审核状态会随最新公开披露变化。
        </p>
        <a href={importState.sourceUrl} target="_blank" rel="noreferrer">查看原始文章</a>
      </section>
      <IpoWatchlistDirectory companies={watchlist.companies} allowedBoards={["科创板"]} />
    </main>
  );
}
