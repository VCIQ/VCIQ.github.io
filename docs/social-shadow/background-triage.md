# Background material versus event-review candidates

`social-background-gate-v1` holds obvious explainers out of the event queue when
there is no concrete reporting cue. This is a narrow deterministic heuristic,
not an LLM judgment, an exhaustive event extractor, or fact verification.

Signals still enter the private content store under the original contracts.
The gate affects only candidate selection: an explicit explainer title or two
definition cues, without a concrete report, no longer defaults to
`company_discovery` merely because an industry keyword matched. A known company
mention alone does not override that test. A concrete report within an explainer
remains reviewable, including reported denials. Hypothetical/example sentences
cannot supply the overriding event cue. Rules do not establish event recency,
company identity, truth, or investment value; uncertain non-explainers retain
the original conservative review path.

## Preview and apply

`python -m tools.social.review_cli triage --state-dir STATE --runtime-config STATE/runtime.json`
returns read-only counts and fixed reason codes. It reads the content store,
does not create a review database, never starts a browser and outputs no source
text, account data or credentials. The total splits into reviewable/background/
unrelated signals; multiple candidate kinds may belong to one reviewable signal.

Use existing `review_cli sync` for a queue preview; only `sync --apply` rebuilds
the private active queue. A previously active explainer becomes inactive and
remains visible in history. The source, immutable evidence versions, pins,
existing acceptance/rejection decisions and original collection receipts are
not deleted or rewritten. This is not an automatic rejection. The fingerprint
and builder revision of retained candidates do not change just because a new
selection gate was introduced, so retained decisions do not silently reopen.

Validation uses synthetic positive/negative examples plus an offline comparison
against saved material. One removed explainer is not proof of precision/recall
across platforms, and no investment-gain claim should be inferred.
