import approved from "@/config/listed_innovation_companies.json";
import { companies } from "@/lib/company-registry";

export type ListedInnovationSecurity = {
  market: string;
  ticker: string;
  exchange: string;
  evidenceUrl: string;
  instrumentType?: string;
  listingDate?: string;
};

export type ListedInnovationCompany = {
  id: string;
  companySlug: string;
  name: string;
  sector: string;
  region: string;
  issuerName: string;
  issuerRelationship?: string;
  identityNote?: string;
  lifecycleProjectIds?: string[];
  primaryMarket: string;
  role: string;
  researchFocus: string;
  securities: ListedInnovationSecurity[];
};

const companyBySlug = new Map(companies.map((company) => [company.slug, company]));
export const listedInnovationApprovedAt = approved.approvedAt;
export const listedInnovationCompanies: ListedInnovationCompany[] = approved.companies.map((row) => {
  const company = companyBySlug.get(row.companySlug);
  if (!company) throw new Error(`Approved listed company has no canonical profile: ${row.companySlug}`);
  return { ...row, name: company.name, sector: company.sector, region: company.region };
});

export function listedInnovationCompany(slug: string) {
  return listedInnovationCompanies.find((row) => row.companySlug === slug);
}

export function listedInnovationTicker(security: ListedInnovationSecurity): string {
  const suffix = security.exchange === "SSE" ? ".SH"
    : security.exchange === "SZSE" ? ".SZ"
      : security.exchange === "HKEX" ? ".HK" : "";
  return `${security.ticker}${suffix}`;
}
