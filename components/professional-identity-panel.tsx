import Link from "next/link";
import { getProfessionalProfile, professionalProfileLabels } from "@/lib/professional-profiles";
import styles from "./professional-identity-panel.module.css";

export function ProfessionalIdentityPanel({slug, name}: {slug: string; name: string}) {
  const profile = getProfessionalProfile(slug);
  return <div className={styles.panel} data-professional-status={profile?.status ?? "not_reviewed"}>
    <div className={styles.heading}>
      <strong>{professionalProfileLabels[profile?.status ?? "not_reviewed"]}</strong>
      {profile && <span>核验日期 {profile.checkedAt}（UTC）</span>}
    </div>
    {profile?.identityContext && <p>{profile.identityContext}</p>}
    <p>{profile?.note ?? "此人物在本轮核验后进入目录，尚未建立 LinkedIn 身份关联。"}</p>
    {profile?.linkedinUrl && <a className={styles.profileLink} href={profile.linkedinUrl} target="_blank" rel="noreferrer">
      查看 {name} 的 LinkedIn 公开档案 ↗
    </a>}
    {profile?.matchReason && <p className={styles.note}>匹配依据：{profile.matchReason}。</p>}
    {profile && <details>
      <summary>核验依据与检索记录</summary>
      {profile.sources.length > 0 && <ul>{profile.sources.map(source => <li key={source.url}>
        <a href={source.url} target="_blank" rel="noreferrer">{source.title} ↗</a>
      </li>)}</ul>}
      {profile.search ? <p className={styles.note}>
        本轮使用 LinkedIn 人物检索，查询：{profile.search.queries.map(q => [q.firstName, q.lastName, q.company].filter(Boolean).join(" ")).join("；")}。
        搜索结果只是线索，未经核对的同名账号不作为此人的档案展示。
      </p> : <p className={styles.note}>需先根据原始人物材料修正身份，再进行档案匹配。</p>}
    </details>}
    <p className={styles.note}>这里展示公开职业资料的核验结果。动态、联系人和好友网络尚未自动同步；历史经历不自动视作现职。</p>
    <Link href="/innovation-capital/people/">查看科创人物与投资关系 →</Link>
  </div>;
}
