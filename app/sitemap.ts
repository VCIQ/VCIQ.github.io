import type { MetadataRoute } from "next";
import { companies, institutionCatalog, reports } from "@/lib/catalog-data";
import { snapshotDate } from "@/lib/intelligence-data";
import { researchPeople } from "@/lib/people-data";
import { researchReports } from "@/lib/research-report-data";
import { trackedSectors } from "@/lib/tracked-sectors";

export const dynamic = "force-static";

// Each dynamic section must mirror the data source its route's
// generateStaticParams uses, otherwise generated pages drift out of the
// sitemap (or the sitemap lists pages that were never exported).
export default function sitemap(): MetadataRoute.Sitemap {
  const base = "https://vciq.github.io";
  const paths = [
    "",
    "/technologies",
    "/people",
    "/companies",
    "/institutions",
    "/reports",
    "/research-agent",
    "/favorites",
    "/search",
    "/tracking",
    ...trackedSectors.map((item) => `/technologies/tracks/${item.slug}`),
    ...companies.map((item) => `/companies/${item.slug}`),
    ...institutionCatalog.map((item) => `/institutions/${item.slug}`),
    ...reports.map((item) => `/reports/${item.slug}`),
    ...researchReports.map((item) => `/reports/pdf/${item.slug}`),
    ...researchPeople.map((item) => `/people/${item.slug}`),
  ];
  const lastModified = new Date(`${snapshotDate}T00:00:00Z`);
  // The exported site uses trailing slashes (next.config.ts trailingSlash),
  // so sitemap URLs must match the canonical exported locations.
  return paths.map((path) => ({
    url: `${base}${path}/`,
    lastModified,
    changeFrequency: path ? "weekly" : "daily",
  }));
}
