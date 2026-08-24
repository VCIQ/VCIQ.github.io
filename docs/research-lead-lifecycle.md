# External article → Research Lead lifecycle

VCIQ treats a high-value external article as a **research evidence seed**, not as an instruction to automatically promote every mentioned entity into a core object.

## 1. External favorite

The public Favorites page can save an external `http/https` article with:

- canonical URL;
- title;
- short user-supplied summary / reason for keeping it;
- source or public-account name;
- category;
- sectors and keywords;
- publication date.

The browser stores only article metadata, short notes and the original URL. It does not mirror the article body. Canonical-equivalent URLs share the same external favorite identity so repeated imports do not create a second article record.

External favorites continue through the existing preference-learning bridge. A save means “this information was valuable to my research”; it does **not** directly create a company, person, technology, track or source.

## 2. Research lead

A saved external article can be sent to the protected tracking-admin `/capture` workflow using the existing tracking-capture link contract. The same article URL and metadata are forwarded as extraction context.

The capture workflow extracts candidate objects across the existing five-object model:

- track;
- technology;
- company;
- person;
- source.

The article remains one evidence seed. Candidate objects link back to the seed through the capture request rather than copying the article into separate per-object records.

## 3. Candidate → Tracked → Core

### Candidate

A candidate may be discovered from a saved article, automated discovery, or a manual research request. Mention alone is not enough to enter production tracking.

### Tracked

An operator reviews identity, target tracks, public evidence and candidate quality in the protected Capture / Manual Tracking flow. Accepted entities enter the tracking intent graph and compatible runtime configuration.

### Core

“Core” is a publication and research-priority decision. It should require accumulated evidence rather than a single article mention. Promotion can use:

- repeated high-value events across time;
- direct or primary evidence;
- persistent relevance to an active track;
- confirmed company/person/technology identity;
- manual research judgment;
- source quality observed across multiple articles.

No public Favorite action directly performs Core promotion.

## 4. Source as the fifth research object

The public `/sources/` directory exposes configured source objects so sources can be studied independently from individual articles.

A strong article creates a source-candidate signal, but **article quality is not source quality**. Source evaluation should remain track-specific where possible: a publication can be strong for one sector and noisy for another.

Existing source-track relevance logic remains the evidence layer for this decision. Strong evidence such as official disclosures, primary material, high-confidence company matches or reviewed corrections can bypass historical broad-source penalties.

## 5. Product semantics

The user-facing operations intentionally have different meanings:

| Operation | Meaning |
| --- | --- |
| Favorite | This article or item is useful and should influence research preference. |
| Research lead | This article may justify creating or extending tracked research objects. |
| Tracked | The object and its track relationships passed the protected tracking review. |
| Core | The object has sufficient accumulated evidence and research priority to enter the core publication layer. |

This separation prevents one high-value roundup article from flooding the core company, people, technology or source catalogs with weakly supported objects.
