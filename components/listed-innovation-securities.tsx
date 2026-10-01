import Link from "next/link";
import { listedInnovationApprovedAt, listedInnovationCompany, listedInnovationTicker } from "@/lib/listed-innovation-companies";

export function ListedInnovationSecurities({ slug }: { slug: string }) {
  const company = listedInnovationCompany(slug);
  if (!company) return null;
  return (
    <div className="source-card" data-listed-innovation={slug}>
      <span>证券身份与科创研究覆盖</span>
      <strong>{company.issuerRelationship === "parent" ? "上市发行人（母公司）" : "发行人"}：{company.issuerName}</strong>
      <p>{company.researchFocus}</p>
      {company.securities.map((security) => (
        <p key={`${security.market}:${security.ticker}`}>
          <a href={security.evidenceUrl} target="_blank" rel="noreferrer">
            {security.market} · {security.exchange} · {listedInnovationTicker(security)}
            {security.instrumentType ? ` · ${security.instrumentType}` : ""} · 身份证据 ↗
          </a>
          {security.listingDate && <small>　上市日期：{security.listingDate}</small>}
        </p>
      ))}
      {company.identityNote && <p>{company.identityNote}</p>}
      <small>纳入研究覆盖：{listedInnovationApprovedAt}。补录日期不是事件发布日期；证券身份来源不代表最新监管公告已经完整采集。</small>
      <Link href="/innovation-capital/#listed-innovation">进入上市科创标杆与产业生态 →</Link>
    </div>
  );
}
