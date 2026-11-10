# Offline WeChat HTML intake

An operator can save a readable WeChat article as HTML and validate it in a
separate private shadow state directory. The importer reads the file without
executing HTML scripts or following network references. The operator supplies the
article URL and a keyword. The parser still checks relevance, the publication
date and the original article body.

Use a reviewed checkout and a private directory outside that checkout. Copy the
saved UTF-8 file into the directory with mode 0600. Use the directory's resolved
path, especially on macOS where the temporary path may traverse a symlink.

```sh
python -B -m tools.social.wechat_html_cli \
  --state-dir "$PRIVATE_STATE" --html article.html \
  --url "$WECHAT_ORIGINAL_URL" --keyword '人形机器人'
```

The command previews by default. Append `--apply` to seal the sample and
materialize the private review queue. Use a separate state directory for this
workflow. Applying to a directory with a scheduler database is refused.
Reapplying the same bytes, canonical URL and keyword reuses the sealed batch
and the same run identity.

Records use provider `operator-html` and operation `import-html`. The file hash
binds the input along with the canonical URL and keyword. The receipt contains
zero search results and zero search pages. Article access remains `unverified`
and the review item remains pending. These jobs cannot be placed in a search plan.

This workflow validates offline parsing and review intake. Automated discovery
and live access are separate acceptance gates.

## Prepare a reviewed link for 科创

Use the [private review flow](review.md#operator-commands) with the same state
directory and a disabled runtime configuration. For a fresh HTML-only directory,
initialize `runtime.json` once before starting the workbench.

```sh
(umask 077; python -B - "$PRIVATE_STATE" <<'PY'
import json, sys
from pathlib import Path

root = Path(sys.argv[1]).resolve(strict=True)
runtime = {"schemaVersion": 1, "kind": "runtime_config", "enabled": False,
           "mode": "shadow", "publish": False, "stateDir": str(root),
           "profileRoot": str(root / "profiles"), "mediacrawlerDir": None,
           "interactiveAuthAllowed": False,
           "platforms": {name: {"enabled": False} for name in ("wechat", "xhs", "wb", "bili", "zhihu")}}
with (root / "runtime.json").open("x", encoding="utf-8") as out:
    json.dump(runtime, out)
PY
)
```

Apply an `accepted` decision for the exact candidate revision. Open the canonical
article link in a normal browser session and compare the original title,
publisher and publication date with the private review snapshot. If the link is
unavailable or those details do not agree, stop the release. An accepted lead
alone only merits follow-up.

Generate a proposed public snapshot into a separate file for inspection. Use the
`candidateKey` and `candidateFingerprint` from the private decision request
exported by the workbench.

```sh
python -B -m tools.social.wechat_release_cli \
  --state-dir "$PRIVATE_STATE" \
  --candidate-key "$CANDIDATE_KEY" \
  --candidate-fingerprint "$CANDIDATE_FINGERPRINT" \
  --confirmed-source-url "$WECHAT_ORIGINAL_URL" \
  > "$PRIVATE_STATE/wechat-media-preview.json"
```

The URL must be the exact canonical URL in the review snapshot. The command is
read-only and checks the current source, pinned evidence and persisted decision.
The output upserts by canonical URL and contains only title, publisher, date and
original link. It starts from the checkout's `config/innovation_wechat_media.json`.
Run from the latest release branch to preserve previously approved links and
inspect the diff before including the proposed snapshot in a publication PR.
The configuration is public input. Never put a review request, private database,
HTML file, excerpt or review note in that PR.

The Pages build reads the approved snapshot at `/innovation-capital/#wechat-media`.
It renders source links under the media evidence label. To withdraw an entry,
remove its URL from the snapshot and follow the same PR and Pages process.
The static page offers no import or review controls.
