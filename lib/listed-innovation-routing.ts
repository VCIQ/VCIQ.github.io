/** Small public routing/search projection; issuer proofs remain on server pages. */
export type ListedRoutingPayload = {
  schemaVersion: 1;
  approvedAt: string;
  companies: Array<{ companySlug: string; name: string; role: string; aliases: string[];
    securities: string[] }>;
};

export function buildListedInnovationRouting(payload: {
  approvedAt: string;
  companies: Array<{ companySlug: string; issuerName: string; role: string; aliases: string[];
    securities: Array<{ market: string; ticker: string; exchange: string }> }>;
}): ListedRoutingPayload {
  return { schemaVersion: 1, approvedAt: payload.approvedAt,
    companies: payload.companies.map((row) => ({
      companySlug: row.companySlug, name: row.aliases[0] || row.issuerName, role: row.role,
      aliases: [...new Set([...row.aliases, row.issuerName])],
      securities: row.securities.map(({ market, ticker, exchange }) =>
        `${market} ${ticker}${exchange === "HKEX" ? ".HK" : exchange === "SSE" ? ".SH" : exchange === "SZSE" ? ".SZ" : ""}`),
    })) };
}
