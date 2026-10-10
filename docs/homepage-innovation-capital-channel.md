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

## 全球投资机构原文证据的首页分发（2026-10-10）

- 网站首页“科创”会在构建时追加原本已进入 `config/innovation_investor_evidence.json` 的近期、可追溯**投资披露／署名观点／项目结果**，不读取未经核验的 daily scout/变化报告，不直接把导航URL变成投资事实。
- 要求明确到日的原始文章日期、source locator、公司、机构及合格kind；文章发表日必须与该记录的日期一致，避免2019年交易被2026年转载误报为今日投资；只展示距构建日45天内的原文记录。
- 同一原文兼有投资与观点时仅分发一条卡片，以投资事实优先；已有统一新闻池相同原文URL优先，不能因两套数据双计阅读数。
- “重点”仍按用户关注、已收藏／分享、实体命中、质量及近期规则挑选，不保证30家机构动态全部进入重点；不会绕过用户取消关注和卡片屏蔽。
- 完整原文位置在投资机构研究专题；首页卡片继续提供“查看来源”。投资文章中的技术效果、客户和收入仍属于机构主张，基金回报未知。
- **边界：** 这个变更只把**已整理的正式原文样例**接入首页，尚不能把每天的未核验导航发现自动发布；新的每日项目必须先完成原文核验并入正式证据台账，然后由现有构建机制发布。这是审阅后的发布链，不是未经人审的全自动事实生产线。
