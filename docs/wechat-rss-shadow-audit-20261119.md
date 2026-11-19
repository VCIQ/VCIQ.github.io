# 微信 RSS 三源影子观察（隔离只读）

本工具仅用于量子位、DeepSeek、月之暗面 Kimi 三个来源的**审核前证据记录**，不是生产采集器。默认文件 `config/wechat_rss_shadow_pilots.json` 与生产 `config/intelligence_sources.json` 分离，三个来源均为 `enabled: false`。不要合并 PR、部署、发布、改动 Shadow stop 或把候选自动加入首页。

## 安全与来源边界

- 工具只获取白名单中的 HTTPS Feed 和 `https://vciq.github.io/data/articles.json`。不跟随 HTTP 重定向；真实请求对超时和响应大小设限，不使用 Cookie。
- 微信文章链接只接收 `mp.weixin.qq.com` 且具有 `__biz+mid+idx` 的完整键；所有 `rows` 均保持 `manual-review`、`published=false`。
- 结果中出现的同一 Feed / 跨 Feed 同键、同标题或近似标题仅为**人工审核线索**。无法仅凭标题证明是同一事件、转载或重复报道。
- Feed 近期列表不是公众号全部历史发文；无法据此计算真实召回率。预检或离线模拟不计入七次定时运行。

## 每次运行的记录口径（schemaVersion=2）

运行时，stdout 输出包含 `asOf`、`windowStart`、`windowEnd`、`snapshotStatus` 和 `snapshotGeneratedAt` 的 JSON。各来源分别记录 `status`、`rawFeedItems`、`processedFeedItems`、`validParsedItems`、`invalidItems`、`sameWeChatKeyItems`、`truncatedItems`、`windowItems`。最多解析前 50 个原始 RSS item，截断必须明确列示。

`summary` 将 `sameWeChatKeyPairs`、`sameFeedExactTitlePairs`、`sameFeedNearTitlePairs`、`crossFeedExactTitlePairs`、`crossFeedNearTitlePairs` 分开计数；`feedReviewRows` 表示有内部候选线索的文章行数。快照请求失败时，线上标题匹配数为 `null`，不是零。

`seenHistory` 保存历史 `row id -> firstSeenAt/lastSeenAt`；即使当天 Feed 请求失败或文章滑出七日窗口也不丢弃。首次运行没有上一份台账时，`previousLedgerProvided=false` 且 `newSincePrevious=null`；不能把该次观测时间表述成文章的真实首次发布时间。

## 隔离环境下保存每日私有证据

选择**不在仓库中**且不被 Git/Pages 上传的私有目录；完整 JSON 可能包含文章标题、原文 URL 和内部审核线索。以下命令由授权操作者在隔离验证工作区手动执行；本 PR **没有**新增 GitHub 定时工作流或生产抓取任务。

```bash
python3 -m unittest tests.test_wechat_rss_shadow_audit -v

umask 077
LEDGER_DIR=/path/to/private/vciq-shadow-ledgers  # 换成真实受控目录
mkdir -p "$LEDGER_DIR"
chmod 700 "$LEDGER_DIR"

# 第一天：只有基线，不计算之前几天的首次发现覆盖率
python3 tools/wechat_rss_shadow_audit.py --window-days 7 > "$LEDGER_DIR/day-01.json.tmp"
status=$?
python3 -m json.tool "$LEDGER_DIR/day-01.json.tmp" >/dev/null && mv "$LEDGER_DIR/day-01.json.tmp" "$LEDGER_DIR/day-01.json"
echo "day-01 exit=$status"

# 第二天：严格传入前一日的完整 JSON（包含 seenHistory）
python3 tools/wechat_rss_shadow_audit.py --window-days 7 \
  --previous-ledger "$LEDGER_DIR/day-01.json" > "$LEDGER_DIR/day-02.json.tmp"
status=$?
python3 -m json.tool "$LEDGER_DIR/day-02.json.tmp" >/dev/null && mv "$LEDGER_DIR/day-02.json.tmp" "$LEDGER_DIR/day-02.json"
echo "day-02 exit=$status"
```

**重要：** 运行即使返回退出码 2，也可能输出含来源故障/快照超时的有效 JSON，应私有保留，并在次日作为累计 `seenHistory` 的上一份报告。若上一份 JSON 缺失、校验失败、台账链中断或环境未共享存储，不能用 `newSincePrevious=0` 代替“未知”；须明确标注证据链断裂。每天独立保留 JSON、运行时间（美东/UTC/北京时间）、退出码及摘要。只将**不含文章全文和完整台账**的脱敏摘要记录到 Draft PR 评论。

## 验收门槛

已完成一次真实只读预检（2026-11-19 04:12 UTC，三源 RSS 20/10/10，滚动七日窗口 21 条），不是连续七次运行。后续 v2 手动预检中，Feed 内有 1 对同标题及 2 对近似标题候选；仍需人工判断。不同日期/窗口的总数不可直接作覆盖率或丢失率比较。

必须完成独立代码审查、与修复提交对应的 CI、**七次真实定时观察及私有台账连续性确认**、公众号身份/微信原文/跨平台事件的人工核对，并由站长逐源签字，才可讨论后续单独的生产启用变更。本 PR 自身不得启用任何来源。
