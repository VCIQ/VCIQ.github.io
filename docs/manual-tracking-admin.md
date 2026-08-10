# 手动追踪内部管理入口

公开页面继续只保留“收藏”和“分享”。“手动追踪”不再是浏览器里的公开写入按钮，而是仓库的 **Internal manual tracking** GitHub Actions 工作流。只有具备仓库写权限、同时列在 `config/tracking_admins.json` 中，并通过 `tracking-admin` environment 保护规则的操作者可以应用修改。

> 本仓库是公开仓库。Actions 表单输入、运行日志、Job summary 和提交后的追踪审计记录都不是机密存储。不要填写密钥、内部网址、个人资料、未披露交易信息或其他保密备注。

## 首次启用

1. 在仓库 Settings → Environments 创建 `tracking-admin` environment。
2. 为 environment 配置 required reviewers；如组织策略支持，也限制可以部署到该 environment 的分支为 `main`。
3. 复核 `config/tracking_admins.json`。只保留确实需要操作入口的 GitHub login，变更必须通过普通代码审查。
4. 仓库 Actions 权限需要允许 GitHub Actions 创建提交，并允许 `GITHUB_TOKEN` 触发后续 `workflow_dispatch`。

GitHub 只允许有仓库写权限的用户手动运行工作流；environment required reviewers 提供应用前的第二道审批。入口仍会同时校验 `github.actor` 和 `github.triggering_actor`，所以非授权用户不能通过重新运行已有任务绕过名单。

## 使用方法

打开 Actions → **Internal manual tracking** → **Run workflow**，分支必须选择 `main`。

先用 `validate`。它只验证输入和展示推荐关联，不写文件。确认名称、目标赛道和推荐结果后，再以相同输入运行 `apply`。

字段约定：

- `object_type`：`technology`、`track`、`company`、`person`、`source` 五选一。
- `name`：一次只填一个规范名称，不要粘贴“甲、乙”或换行列表。合法公司名称里的逗号和 `A/B` 不会被当作列表分隔符。
- `target_tracks`：目标赛道 slug 或名称，多个值用 `|` 分隔。新建 `track` 时可以省略。
- `keywords`：关键字或别名，多个值用 `|` 分隔。新建赛道必须至少有一个有效关键字。
- `source_url`：公开证据 URL；`company` 与 `source` 类型必填，其他类型可作为身份解析证据。
- `source_category`：信源归属，支持 `media`、`company`、`person`。
- `region`：信源地区，支持 `中国`、`美国`、`全球`。
- `reasons`：必填的公开追踪原因标签，多个值用 `|` 分隔；只能使用历史治理后的七类枚举。
- `note`：公开审计备注；不得包含任何秘密或保密信息。

示例：

| 目标 | object_type | name | target_tracks | keywords / source_url |
| --- | --- | --- | --- | --- |
| 技术 | `technology` | `端侧多模态` | `ai` | `端侧多模态|on-device multimodal` |
| 赛道 | `track` | `具身智能基础设施` | 留空 | `具身智能基础设施|机器人数据采集` |
| 公司 | `company` | `Pony.ai, Inc.` | `track-15shkgi` | 填公开公司证据 URL |
| 人物 | `person` | `Demis Hassabis` | `ai` | 可填公开人物证据 URL |
| 信源 | `source` | `MIT Technology Review` | `ai` | `https://www.technologyreview.com/` |

信源 URL 的完整路径段为 `/feed`，或以 `.rss`、`.xml`、`.atom` 结尾时会编译为 RSS；`/feedback`、`/feedstock` 等普通页面不会误判。其余公开网页使用 `listing-search`。CLI 不会在持有写权限时抓取输入 URL，私网、本机、凭证 URL 会直接拒绝。

## 五类对象如何关联

内部入口保留两层数据：

- `config/tracking_intents.json` 是稳定的意图图。`entities` 保存技术、赛道、公司、人物、信源及别名；`memberships` 保存它们与赛道的关系、人工固定状态、原因、操作者和公开证据。
- `config/user_tracking.json` 是现有爬虫继续读取的兼容配置。已通过身份解析的公司、人物、技术关键字和安全信源会编译到对应赛道；不确定的对象不会直接污染生产配置。

带公开证据 URL 的技术、公司、人物会同步到 `config/tracking_capture_inbox.json`；待解析公司保持 `queued`，正式目录或人工消歧确认后会原位迁移到 canonical ID，不遗留两套实体或两条 capture。赛道和信源直接由意图图表达，不伪造旧 inbox 不支持的记录。人工关系是 pinned 信号，不会被自动发现的生命周期清理器静默删除；自动发现仍需满足自身的证据、置信度和来源治理门槛。

推荐会同时返回相关赛道、技术、公司、人物和信源。排序综合使用：

1. 本次明确选择的目标赛道；
2. 当前追踪配置里的核心技术词，以及经过正式公司／人物注册表确认、且赛道归属一致的对象；
3. 历史手动追踪中已应用的关系、理由频次和信源域名；
4. 意图图里已有的人工关系；
5. 信源在历史人工证据中的 canonical host 使用频次。

历史审计共读取 126 条旧浏览器 capture，其中 97 条是可用的单实体记录；其余复合列表、残缺括号和类型污染不参与正向学习。可用历史中最常见的原因是“个人研究兴趣”“融资机会”“技术突破”，因此这些原因继续作为受控枚举，而不是自由文本权重。历史上被暂存、拒绝或已从 runtime 删除的值只作为 hold 信号：它们不会被拆成多个实体，也不会被自动发现重新加入。新的人工输入同样要求“一次一个实体”，避免类似 `OpenAI，Anthropic`、`Sam Altman、Demis Hassabis` 的历史污染。

自动关键字扩展采用固定的 8 查询预算，而不是让历史词或公司名占满前排：

1. 赛道 identity 保留 1 个槽位；
2. 核心技术保留至少 3 个槽位；人工或 actor 槽位为空、或与核心词重复时，用后续核心技术动态回填；
3. v2 人工 pinned 最多 2 个槽位；旧浏览器历史最多只能占其中 1 个；
4. 公司和人物各保留 1 个探索槽位，并强制使用“实体名 + 赛道名”的上下文查询。

被拒绝的信源按 canonical host 阻断，不会通过改成根路径、`www` 或 `http/https` 变体复活。技术 identity 保留有语义的标点，因此 `C`、`C++`、`C#`、`.NET`、`NET`、`A/B`、`AB` 分别计数和去重。历史高频信源只获得有限加权，不能越过自动发现的专业证据门槛。

## 写入与后续自动化

`apply` 使用所有仓库写入器共享的 FIFO 队列，只检出 `main`，并记录开始时的远端 SHA。提交前和推送前都会重新读取 `origin/main`；如果主分支已经前进，任务直接失败，不 rebase、不 force push，也不覆盖新提交。只允许暂存以下文件：

- `config/tracking_intents.json`
- `config/user_tracking.json`
- `config/tracking_capture_inbox.json`

GitHub 用 `GITHUB_TOKEN` 创建的提交不会依靠 `push` 递归启动另一个工作流，因此入口会显式派发后续任务：生产追踪配置变化时运行 `scheduled-sync.yml`；公司进入审核队列时运行 `company-candidate-discovery.yml`；其他仅影响意图或审核的变化运行 `tracking-discovery.yml`。

相同对象、赛道和证据的重复申请应为 no-op，不产生只更新时间戳的空洞提交。失败后不要盲目重跑：先查看 guard、身份解析、配置校验或远端 SHA 竞态的明确错误，再用 `validate` 修正输入。
