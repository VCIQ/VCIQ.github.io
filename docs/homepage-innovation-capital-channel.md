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

## 全球投资机构官网研究 → 首页“科创”与“重点”发布桥接（2026-10-10）

- **研究入口保持不变**：`/innovation-capital/` 的“全球重点投资机构”链接通向 `/innovation-capital/investors/`，用于30家机构长期档案、独立项目关系、署名观点、后续结果和证据缺口。
- **唯一首页数据流**：`lib/homepage-investor-publication.ts`从**已经提交到正式研究证据台账**的 `config/innovation_investor_evidence.json` 生成最多12条、过去14天、来源为机构官网、按原文日期精确到天的最新事件，直接合并到现有首页文章视图与科创关系索引。保留现有新闻池的canonical元数据和去重优先级，不创建新的公开新闻writer、额外爬虫或API请求。
- **同源去重**：同一官网原文同时说明“投资行为”和“五位署名作者观点”，只生成**一张首页卡片**，并将作者作为明确来源的提及人；不把一篇文章计成多次投资。已被统一 `articles.json` 收录的URL保留原来的标题/日期/来源，侧边研究入口仍指向投资机构专题。
- **科创入流**：只能接受有规范机构ID、公司对象、正式原文URL、原文日级发布日期且属于官方披露的项目投资/署名观点或明确上市/收购事件；不接收站点`scout`导航、待审核人工队列、论坛转载、缺失日期或旧基金主题公告。展示时标“机构官网披露”，不是独立客户/财务/技术审计。
- **重点仍是个性化**：这些材料只有同时满足重点的7天新鲜度、重要性、可信质量和本浏览器实际的赛道关注/分享/收藏/追踪等信号，才进入“重点”。**不能仅因某机构被列为30家观察名单，强制把其所有文章塞进重点**；用户隐藏某条依旧生效。
- **时间边界**：按官网公开日期的天粒度排序，不将采集时间或构建时间伪造为文章发表时分。超过14天不继续作为“最新投资动态”置顶，但长期证据仍在研究专题。
- **发布与审查**：日更 `innovation-investor-source-scout.yml` 继续只形成14天Actions审核产物；审核人员确认原始投资/发言及项目身份，更新研究证据台账并经PR/CI/Pages部署之后，才能成为首页条目。**每日观察不等于每天都有经核验的新事件**；采集失败、URL窗口消失、负面标题也不自动发布为退出/负面事实。
- **当前案例**：TypeSafe AI与Oxide的2026-10-09官网投资公告，以及Preference Model的2026-10-07公告，均在本窗口内；Eclipse对Oxide的4.45亿美元属于整轮Series D金额，不能解读为Eclipse实际投资额，机构营收论述也不能当独立审计结果。

该桥接在Next静态页面构建时生成快照，只有经后续站点部署的版本才会更新首页；每天凌晨抓取所得的未经复核新链接不会直接出现在“重点”或“科创”。这与追踪证据治理和静态站点生产安全规则保持一致。
