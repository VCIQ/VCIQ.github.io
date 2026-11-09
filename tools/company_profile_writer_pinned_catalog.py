"""Resolve a company catalog from explicitly supplied, Git-pinned sources.

Do not call parse_catalog when its fallback would consult the local filesystem.
The production TS catalog re-exports company entries from company-registry.ts,
which imports config/company_registry.json. Both links must be present.
"""
from __future__ import annotations

import re

from .venture_profile_extraction import (
    CatalogCompany, CatalogInstitution, _array_field, _catalog_lines, _field, _source,
    clean_text, normalize_url, parse_catalog,
)


class PinnedCatalogError(ValueError):
    """Fixed error codes only."""


def pinned_catalog(catalog: str, registry_ts: str | None = None,
                   registry: dict | None = None):
    if not isinstance(catalog, str) or not catalog:
        raise PinnedCatalogError("PINNED_CATALOG_INVALID")
    lines = _catalog_lines(catalog, "export const companies", "export type Institution")
    has_inline = any(_field(row, "slug") and _field(row, "name")
                     and _source(row)[1] for row in lines)
    if has_inline:
        if registry_ts is not None or registry is not None:
            raise PinnedCatalogError("PINNED_CATALOG_AMBIGUOUS")
        companies, institutions = parse_catalog(catalog)
    else:
        if (not re.search(r'export\s*\{\s*companies\s*\}\s*from\s*["\']\./company-registry["\']', catalog)
            or not isinstance(registry_ts, str)
            or not re.search(r'import\s+rawRegistry\s+from\s+["\']@/config/company_registry\.json["\']', registry_ts)
            or not isinstance(registry, dict)
            or type(registry.get("schemaVersion")) is not int
            or registry["schemaVersion"] != 1
            or not isinstance(registry.get("companies"), list)
            or not 1 <= len(registry["companies"]) <= 2000):
            raise PinnedCatalogError("PINNED_REGISTRY_REQUIRED")
        companies = []
        for item in registry["companies"]:
            if not isinstance(item, dict):
                raise PinnedCatalogError("PINNED_REGISTRY_INVALID")
            source = item.get("source")
            if not isinstance(source, dict):
                raise PinnedCatalogError("PINNED_REGISTRY_INVALID")
            slug = clean_text(item.get("slug"), 100)
            name = clean_text(item.get("name"), 200)
            url = normalize_url(source.get("url"))
            if not slug or not name or not url:
                raise PinnedCatalogError("PINNED_REGISTRY_INVALID")
            companies.append(CatalogCompany(
                slug=slug, name=name,
                english_name=clean_text(item.get("englishName"), 200),
                region=clean_text(item.get("region"), 80),
                sector=clean_text(item.get("sector"), 120),
                stage=clean_text(item.get("stage"), 80),
                status=clean_text(item.get("status"), 80),
                summary=clean_text(item.get("summary"), 1200),
                product=clean_text(item.get("product"), 1200),
                source_name=clean_text(source.get("name"), 200) or name,
                source_url=url,
            ))
        institutions = []
        for row in _catalog_lines(catalog, "export const institutionCatalog",
                                  "export type IpoCompany"):
            source_name, url = _source(row)
            slug, name = _field(row, "slug"), _field(row, "name")
            if not slug or not name or not url:
                continue
            institutions.append(CatalogInstitution(
                slug=slug, name=name,
                english_name=_field(row, "englishName"),
                region=_field(row, "region"),
                institution_type=_field(row, "type"),
                stages=_field(row, "stages"),
                sectors=_array_field(row, "sectors"),
                source_name=source_name or name,
                source_url=url,
            ))
    if (not companies or len({c.slug for c in companies}) != len(companies)
        or len({i.slug for i in institutions}) != len(institutions)):
        raise PinnedCatalogError("PINNED_CATALOG_DUPLICATE_OR_EMPTY")
    return companies, institutions
