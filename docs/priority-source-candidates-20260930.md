# Priority publisher candidates — approval required

These recommendations are drawn from existing source registrations, not a claim
that all named publishers are already on the five-minute lane. No new publisher
is activated in this revision. AMD and MITTR China remain the only two active
priority collectors. Five minutes is a requested GitHub schedule, not a guaranteed
end-to-end deadline; source polling, queueing and browser delivery are independent.

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
