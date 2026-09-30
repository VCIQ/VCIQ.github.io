# Priority publisher approvals and innovation-capital candidates

The owner confirmed six additions: Google DeepMind, Google AI, OpenAI, 雷峰网,
钛媒体 and TechCrunch Venture. Together with AMD and MITTR China, the reviewed
policy now defines eight collectors in `config/priority_source_policy.json`.
The producer and browser reader consume the same host/evidence-role policy.
Approval/configuration is not proof of deployed, continuously scheduled service.
Five minutes remains a requested GitHub schedule, not a guaranteed deadline.

Google AI's old feed responds with a 301 to
`https://blog.google/innovation-and-ai/technology/ai/rss/`; the source config now
uses that canonical endpoint, rather than weakening redirect protections.
Long RSS archive tails outside the seven-day window are not misreported as a
recent collection gap. A truncated recent/undated tail or a missing checkpoint
still produces a gap. Malformed XML is isolated instead of aborting other sources.
The private-to-workflow scan artifact has a separate 1,000,000-byte cap; it is not
the public feed. Publisher responses remain capped at 1,000,000 bytes each and the
browser-facing snapshot remains capped at 300,000 bytes / 72 records / seven days.

## 科创频道 / Batch-6 候选范围

`config/priority_media_candidates.json` records a separate, non-runtime shortlist.
Scope follows the existing public tracking-admin coverage contract: 科创板辅导备案,
创业板辅导备案, A+H上市, Pre-IPO融资, AI安全, AI眼镜, CXL, UCIe, 太空算力, 6G NTN.
These are ten topic families, not ten certified healthy RSS responses.

| Candidate | Priority review area | Evidence status |
|---|---|---|
| 财联社 / 科创板日报相关栏目 | 硬科技资本、IPO、融资 | Relevant public example; brand/byline and exact Batch-6 RSS attribution pending |
| 证券时报 | 辅导备案、A+H、注册问询 | Editorial candidate; new-subscription sample pending |
| 上海证券报 / 中国证券网 | 上市进程、科创政策 | Editorial candidate; new-subscription sample pending |
| 投资界 | 硬科技融资、成熟项目 | Public financing example; do not mislabel A-round news as Pre-IPO |
| 投中网 | PE/VC、Pre-IPO | Editorial candidate; incremental event evidence pending |
| 21世纪经济报道 | 跨市场上市、产业资本 | Editorial candidate; sample and entry validation pending |
| 电子工程专辑 | CXL/UCIe、半导体融资 | Public example under /mp/; contributor identity must be checked |
| C114通信网 | 6G NTN、空天地网络 | Editorial candidate; exact sample/entry validation pending |
| 新华报业网 | 科创项目、光互联融资 | Public Pre-A4 example; not evidence of Pre-IPO stage |

No candidate above is automatically added to the five-minute lane or promoted
to Core. Financial/IPO facts must be traced back to the relevant regulator,
exchange, company or broker disclosure. Google URLs, portals and syndication
must not be mistaken for original publishers or independent corroboration.

Current evidence limits: the public article/ranked projection does not retain a
complete query-to-article trace for this cohort. Related Google Alerts email
samples can suggest publishers, but are not RSS receipt/coverage evidence for
the ten newly added queries. Exact cohort attribution therefore stays pending.
Only public article URLs/titles are retained here; no mailbox identifiers, private
RSS addresses, credentials, preference payloads or tracking query histories.

Future review should retain public source/author, article URL, public topic family,
observed receipt channel, dates, deduplication and test results separately; a
missing value stays unavailable. Anthropic, Sina and VentureBeat holds below
remain unchanged until individually verified and approved.

## Read-only transport probes

Probes used curl with normal TLS verification and no application credentials.
The entry counts describe the returned response, not items collected/published.

| Candidate | Existing entry / verified URL | Probe | Recommendation |
|---|---|---|---|
| Google DeepMind | `deepmind-blog`, https://deepmind.google/blog/rss.xml | HTTP 200, 100 feed entries | First batch: original model, robotics and AI-for-science updates |
| Google AI | `google-ai-blog`, https://blog.google/technology/ai/rss/ | HTTP 200, 20 entries | First batch; group overlaps with DeepMind rather than double counting |
| OpenAI | Existing official site; https://openai.com/news/rss.xml | HTTP 200, 1,238 entries, 755,374 bytes | First batch after conditional-fetch and payload-budget validation; no full-history republication |
| 雷峰网 | `leiphone`, https://www.leiphone.com/feed | HTTP 200, 20 entries | First batch: Chinese industry reporting; retain media attribution |
| 钛媒体 | `tmtpost`, https://www.tmtpost.com/rss.xml | HTTP 200, 18 entries | First batch: technology/capital signals, filtered by concrete events |
| TechCrunch Venture | `techcrunch-venture`, https://techcrunch.com/category/venture/feed/ | HTTP 200, 20 entries | First batch: international venture events, not every article |
| 新浪财经 | `sina-finance`, existing public roll JSON | HTTP 200, valid JSON | Second batch: category narrowing and verified bounded pagination first |
| Anthropic | Existing official source; https://www.anthropic.com/news | HTTP 200, HTML, not a usable RSS response | High editorial priority, but implement/reuse an HTML adapter; do not label it RSS |
| VentureBeat AI | `venturebeat-ai`, https://venturebeat.com/category/ai/feed/ | HTTP 429 | Hold; respect throttling and backoff, not repeated five-minute failures |

NVIDIA is a useful additional candidate for compute/robotics, but its public RSS
terms explicitly restrict use to non-commercial purposes. Review intended use
and obtain suitable permission/licensing before activating feeds for a commercial
research service. Reference: https://www.nvidia.com/en-us/about-nvidia/rss/

Other websites such as 虎嗅/财新 need separate accessible-entry, licensing and
incremental-coverage verification. Being reported by many sites does not prove
that their entries are independently accessible or that they corroborate a fact.

Approval of a publisher adds a bounded collection entry, not automatic Core
promotion or universal homepage placement. Private tracking/share/favorite state
remains private; only public source data may enter the independent data branch.
