import { buildTrackWatchlistLink } from "@/lib/tracking-admin-link";
import styles from "./track-watchlist-admin-entry.module.css";

export function TrackWatchlistAdminEntry({ slug }: { slug: string }) {
  return (
    <aside className={styles.bar} aria-label="赛道关注对象管理">
      <div>
        <span>TRACK WATCHLIST</span>
        <strong>管理本赛道关注对象</strong>
        <small>技术 · 人物 · 公司 · 自动扩展审核</small>
      </div>
      <a href={buildTrackWatchlistLink(slug)} target="_blank" rel="noreferrer">
        打开受保护管理台 ↗
      </a>
    </aside>
  );
}
