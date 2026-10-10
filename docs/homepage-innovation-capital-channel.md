# 首页“科创”频道数据与发布契约

## 定位

首页“科创”是实时情报流，不复制 `/innovation-capital/` 的项目研究页，也不把 Tracking Admin 当作抓取源。

- `/innovation-capital/`：结构化项目、生命周期、机构与成熟候选研究页。
- Tracking Admin：人工确认、补证、关系治理与追踪管理。
- 首页“科创”：回答“这些科创对象刚刚发生了什么”。

## Canonical inputs

首页投影只读取现有 canonical data：

- `public/data/articles.json`
- `public/data/ranked-intelligence.json`
- `config/innovation_listing_watchlist.json`
- `config/innovation_listing_lifecycle.json`
- `config/innovation_capital_mature_candidates.json`
- `config/innovation_capital_tracking_seeds.json`

因此展示页之间不存在网页反向抓取链路。

## Build-derived projection

`scripts/build-innovation-capital-feed.ts` 在站点构建前生成：

`public/data/innovation-capital-feed.json`

该文件只保存轻量元数据：

- canonical event ID
- source URL / event cluster ID
- matched objects
- reason codes
- evidence tier
- innovation priority

新闻标题、正文摘要、来源等仍只来自统一 article / ranked-intelligence 数据池。

## Admission rule

“科创”不是 `科创 / IPO / 融资` 关键词频道。

一条事件进入首页科创流必须满足“对象关系 + 实质事件”：

### 对象关系

至少命中以下之一：

- 已核验重点券商科创项目
- 审核 / 注册 / 发行 / 上市生命周期项目
- 六家目标券商（中信证券、中信建投、中金公司、国泰海通、华泰联合、广发证券）
- 硬科技资本机构 watch
- D/E/Pre-IPO/Growth 等成熟期候选
- `innovation-listing-*` / `innovation-capital-portfolio-*` 专用发现源

### 实质事件

同时具备至少一种：

- 辅导、保荐、IPO、受理、问询、注册、发行、上市、A+H
- 融资、投资、领投、跟投、增资、基金募资
- 技术突破、量产、订单、签约、商业化、产能等硬科技进展
- 与上述对象直接相关的监管 / 十五五政策事件

单独出现“AI”“科创”“融资”“中信证券”等泛化文本不能入流。

对象类型还有更窄的事件边界：

- 项目 / 生命周期项目 / 成熟候选：可接收上市、融资、技术/商业化与直接政策事件。
- 投资机构：只接收融资、投资或上市资本事件；机构的一般行业观点和普通技术内容不入流。
- 重点券商：只接收辅导、IPO、融资/资本市场相关事件；普通研报观点不入流。

## Evidence boundary

证据层级：

1. `primary`：监管、交易所、券商/公司/投资机构官方材料。
2. `trusted`：已有可信来源等级的公开材料。
3. `discovery`：待交叉验证的发现源。

projection 可以展示 discovery 事件，但它不改变任何正式项目、券商、上市板块或投资关系状态。

成熟候选如果缺少券商证据，仍显示“券商待匹配”；缺少交易所/监管板块证据，仍显示“板块待匹配”。

## Ranking

首页“科创”遵循：

1. `publishedAt DESC`
2. `innovationPriority DESC`
3. personalized recommendation score
4. importance

`innovationPriority` 是信息处置优先度，不是上市成功率、投资评级或公司价值判断。

## Publication

`npm run build` 与 `npm run build:pages` 都会先执行：

`npm run build:innovation-capital-feed`

这样每次 Pages 构建都会从当前 repository revision 的 canonical data 重建 projection。

该 projection 是 build-derived artifact，不新增独立 repository writer；现有 full refresh、frequent refresh、tracking discovery 等 writer 仍只负责各自 canonical outputs，从而避免新的 main 写入竞争。

## UI

频道顺序：

`关注流 → 推荐 → 快讯 → 科创 → AI / AGI → …`

科创卡片额外显示：

- 科创关联对象
- 命中原因
- 科创优先度
- “查看科创项目”入口

用户仍可使用现有“查看来源 / 追踪 / 分享 / 深研此条”操作。

## 全球投资机构原文发布桥接（2026-10-10）

**科创频道：** 新近核实的机构官方投资披露可作为新闻卡片进入首页科创流，直接链接到 `/innovation-capital/investors/` 研究专题。
**重点频道：** 仍遵守个人兴趣：须有关注赛道、收藏、分享等真实信号，并满足7天新鲜度、重要度与质量规则；30家机构不会被无条件推到所有用户的重点。

### 证据发布门槛

新增 `config/innovation_investor_homepage_publications.json`：只有人工明确选定的正式证据ID会从研究样本投影到首页。要求 evidence.kind=investment、源站为登记机构的同域HTTPS、source.kind=investor-official、精确到日且与原文发布日期相符、机构角色明示、规范项目研究ID唯一。
未经审核的每日scout导航、机构普通观点、基金募资、失败来源和标题触发的负面事件均不会自动发布。本次仅选择2026-10-09 a16z×TypeSafe AI与Eclipse×Oxide两条正式投资披露。机构文章中的观点可在同一新闻卡片关联作者，但作者不因此成为独家交易负责人。

### 构建与刷新

首屏于Pages构建时按上述名单生成精简卡片，合并到首页现有新闻展示池；同原始链接的历史新闻去重。浏览器首次读取 `/data/articles.json` 及后续30分钟刷新均保留该编辑投影，避免首次看到、点击后消失。既有 crawler-owned `articles.json`、`ranked-intelligence.json`、跟踪队列仍不改写，不创建新的canonical数据写入竞争。
首页科创轻量索引补充这两条投资事件的机构、项目及一级原文依据；其余事件沿用已有事件关联规则。只保留发布日期距站点构建不超过30天的选定记录，不把历史样例重复标记为今日发布，也不伪造精确到秒的发布时间。

### 每日跟踪的准确边界

每日官网采集继续写入GitHub Actions待审artifact；只有原文独立核对并显式加入版本化发布清单的事件，才在下一次Pages构建发布。导航候选数不能冒充已核实交易数；整轮融资额不等于单家机构支票，署名不等于交易决策责任，上市或估值变化不等于已实现现金回报。此桥接实现可信来源的首页发布路径，不是无人审核的完全自动事实判决。
使用路径：首页→“科创”→原文投资消息→“查看全球投资机构研究”；关注相关赛道或收藏/分享的符合规则事件，可进入“重点”。
