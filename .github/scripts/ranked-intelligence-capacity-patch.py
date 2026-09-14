from pathlib import Path


def replace(path: str, old: str, new: str) -> None:
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    if old not in text:
        raise SystemExit(f"missing expected text in {path}: {old[:120]!r}")
    p.write_text(text.replace(old, new), encoding="utf-8")


replace(
    "tools/ranked_intelligence_projection.py",
    "MAX_ITEMS = 24",
    "MAX_ITEMS = 36",
)
replace(
    "lib/ranked-intelligence.ts",
    "export const RANKED_INTELLIGENCE_MAX_ITEMS = 24;",
    "export const RANKED_INTELLIGENCE_MAX_ITEMS = 36;",
)
replace(
    "docs/ranked-intelligence-homepage-bridge.md",
    "→ public-safe projection (max 24)",
    "→ public-safe projection (max 36, including up to 8 manually curated slots from the private admin producer)",
)
replace(
    "docs/ranked-intelligence-homepage-bridge.md",
    "The public homepage accepts a small, public-safe projection of the private VCIQ Intelligence Inbox. The bridge is deliberately one-way and display-only: it can raise homepage attention for high-relevance public articles, but it cannot create tracking objects or mutate the tracking catalog.",
    "The public homepage accepts a bounded, public-safe projection of the private VCIQ Intelligence Inbox. The bridge is deliberately one-way and display-only: it can raise homepage attention for high-relevance public articles, while a small number of explicit human editorial selections may reserve slots inside the same projection. Neither path can create tracking objects or mutate the tracking catalog.",
)

for path in [
    ".github/workflows/one-shot-ranked-intelligence-capacity.yml",
    ".github/scripts/ranked-intelligence-capacity-patch.py",
]:
    target = Path(path)
    if target.exists():
        target.unlink()
