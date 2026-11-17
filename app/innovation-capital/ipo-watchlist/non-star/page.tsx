import type { Metadata } from "next";
import Link from "next/link";
import watchlist from "@/config/ipo_priority_watchlist_20261115.json";
import { IpoWatchlistDirectory } from "@/components/ipo-watchlist-directory";

export const metadata: Metadata = {
  title: "非科创板 IPO 重点关注｜科创资本",
  description: "来自最丨投行的主板、创业板与北交所潜在上市企业名单。",
};

const mainBoardCount = watchlist.companies.filter((item) => ["沪市主板", "深市主板"].includes(item.board)).length;
const growthCount = watchlist.companies.filter((item) => item.board === "创业板").length;
const beijingCount = watchlist.companies.filter((item) => item.board === "北交所").length;

export default function NonStarIpoWatchlistPage() {
  return (
    <main className="page-shell subpage">
      <header className="page-header">
        <p className="eyebrow">INNOVATION CAPITAL / NON-STAR IPO</p>
        <h1>非科创板潜在上市公司</h1>
        <p>来源：{watchlist.source.publisher}，2026 年 11 月 15 日 22:00 北京时间历史快照，合计 {mainBoardCount + growthCount + beijingCount} 家。</p>
      </header>
      <section>
        <h2>板块分组</h2>
        <ul>
          <li>沪深主板：{mainBoardCount} 家</li>
          <li>创业板：{growthCount} 家</li>
          <li>北交所：{beijingCount} 家</li>
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
