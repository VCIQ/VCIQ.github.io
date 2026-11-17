import type { Metadata } from "next";
import Link from "next/link";
import source from "@/config/innovation_capital_import_pending_20261116.json";
import watchlist from "@/config/ipo_priority_watchlist_20261115.json";
import { IpoWatchlistDirectory } from "@/components/ipo-watchlist-directory";

export const metadata: Metadata = {
  title: "非科创板 IPO 重点关注｜科创资本",
  description: "来自最丨投行的主板、创业板与北交所潜在上市企业名单。",
};

export default function NonStarIpoWatchlistPage() {
  return (
    <main className="page-shell subpage">
      <header className="page-header">
        <p className="eyebrow">INNOVATION CAPITAL / NON-STAR IPO</p>
        <h1>非科创板潜在上市公司</h1>
        <p>来源：最丨投行，2026 年 11 月 15 日 22:00 北京时间历史快照，合计 {source.sourceSnapshotCounts.nonStarTotal} 家。</p>
      </header>
      <section>
        <h2>板块分组</h2>
        <ul>
          <li>沪深主板：{source.sourceSnapshotCounts.mainBoardShanghaiShenzhen} 家</li>
          <li>创业板：{source.sourceSnapshotCounts.growthEnterpriseMarket} 家</li>
          <li>北交所：{source.sourceSnapshotCounts.beijingStockExchange} 家</li>
        </ul>
        <Link href="/innovation-capital/ipo-watchlist/">返回 IPO 重点关注总览</Link>
      </section>
      <IpoWatchlistDirectory
        companies={watchlist.companies}
        allowedBoards={["沪市主板", "深市主板", "创业板", "北交所"]}
      />
    </main>
  );
}
