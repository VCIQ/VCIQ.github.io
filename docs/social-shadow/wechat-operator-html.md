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
