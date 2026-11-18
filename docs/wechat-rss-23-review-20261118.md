# VCIQ 微信公众号 RSS 候选源｜23 条接入预审

核验日期：2026-11-18（只读 URL 请求；**未运行生产抓取**）。

## 范围与原则

- 用户提供 23 条 RSS：wechat2rss.xlab.app（8）、wechat2rss.bestblogs.dev（13）、Wechat-Scholar GitHub Raw（2）。
- 已在 `config/intelligence_sources.json` 为每条配置独立 `wechat-rss-*` ID、`adapter: rss`、`maxItems: 4`、`allowedHosts: ["mp.weixin.qq.com"]`，并将 **23 条全部设置为 `enabled: false`**。
- Feed 是第三方转发通道，不是微信公众号官方授权 API。Feed 标题与公众号名称一致、文章指向微信域名，**不等同于认证了发布者身份、采集完整性或准确性**。
- `sourceLevel: 媒体报道` / `platform: 微信公众号线索` 表示观察线索，不自动升级为企业官方披露。
- 现有 11 个已配置 Feed 保持不变。即使此 Draft PR 合并，新增 23 条也不会自动进入生产抓取；未来启用必须由站长单独审核并控制并发/配额。

## 单条请求结果

| 公众号 | Feed 来源 | RSS / 名称核验 | 建议 |
| --- | --- | --- | --- |
| 机器之心 | xlab | RSS 20 篇，名称一致 | 候选 |
| 量子位 | xlab | RSS 20 篇，名称一致 | 候选 |
| 新智元 | xlab | RSS 20 篇，名称一致 | 候选 |
| PaperWeekly | xlab | RSS 20 篇，名称一致 | 候选 |
| Datawhale | xlab | RSS 20 篇，名称一致 | 候选 |
| 夕小瑶科技说 | xlab | RSS 20 篇，名称一致 | 候选 |
| 美团技术团队 | xlab | RSS 20 篇，名称一致 | 候选 |
| 腾讯技术工程 | xlab | 下载 3.6MB 时两次限时超时 | 暂缓 |
| 腾讯混元 | bestblogs | RSS 10 篇，名称一致 | 候选 |
| 雷峰网 | bestblogs | RSS 10 篇，名称一致 | 与现有网站 Feed 对账 |
| 谷歌开发者 | bestblogs | HTTP 500 | 暂缓 |
| InfoQ | bestblogs | RSS 10 篇，名称一致 | 候选 |
| 极市平台 | Wechat-Scholar | RSS 50 篇，名称一致 | 候选 |
| 智东西 | bestblogs | RSS 10 篇，名称一致 | 候选 |
| AI科技评论 | bestblogs | RSS 10 篇，名称一致 | 候选 |
| 魔搭ModelScope社区 | bestblogs | RSS 10 篇，名称一致 | 候选 |
| DeepSeek | bestblogs | RSS 10 篇，名称一致 | 候选 |
| 微软亚洲研究院 | Wechat-Scholar | RSS 50 篇，名称一致 | 候选 |
| 月之暗面 Kimi | bestblogs | RSS 10 篇，名称一致 | 候选 |
| MiniMax 稀宇科技 | bestblogs | RSS 10 篇，名称一致 | 候选 |
| 阶跃StepFun | bestblogs | RSS 10 篇，名称一致 | 候选 |
| 智谱 | bestblogs | RSS 10 篇，名称一致 | 候选 |
| 通义实验室 | bestblogs | RSS 10 篇，名称一致 | 候选 |

核验共 **21 条可解析**，2 条未能通过当前请求条件；失败不代表永久不可用。

## 现有来源与去重检查

- 机器之心、量子位、新智元、AI科技评论已列在 `config/wechat_sources.json` 的检索发现源中。这次是**新增 RSS 传输方式**，不能算新增四个公众号覆盖。
- 雷峰网已有网站 RSS（`leiphone`），必须针对同一事件/同一标题做跨链接去重，不能仅用源 ID 判断唯一事件。
- 微信 RSS 新源 URL 指向微信原文，现有 `parse_feed_items()` 支持解析。`DeepSeek` 实际 Feed 测得 4/4 条可接受，保留原文 URL；代码层需要对其他公众号做抽样核对与跨平台去重。
- 禁止以这批候选直接声称已实现微信公众号**全量**覆盖。特别注意第三方服务超时、接口限流、历史缺口、文章撤回和微信原文失效。

## 下一阶段安全启用门槛

1. 优先采用 **2–3 个低负载来源**，每源最多 4 条，建立 7 天“Feed 中实际发表 / VCIQ 发现 / 进入待审队列”逐日对账。
2. 核验文章标题、公众号身份、`__biz` / 微信原文真实性、发布时间及候选重复匹配。
3. 为错误、空源、超时分别记录健康状态；不因单次失败解除隔离，也不向 Feed 服务端反向发送用户 Cookie。
4. 生产配置、发布以及 Shadow stop 的任何改变均需要站长审核签字。

**此 PR 只提供待审核候选清单和测试；没有启用任何 RSS 源。**

## 三源只读抽样（2026-11-18）

使用标准证书校验的 `curl` 再次取得量子位、DeepSeek、月之暗面 Kimi 的 RSS，检查最新五篇的 `pubDate`、微信原文域名及链接参数。

| 源 | 返回的 RSS 篇数 | 最新一篇日期 | 原文 URL 结构 |
| --- | ---: | --- | --- |
| 量子位 | 20 | 2026-11-17 | `mp.weixin.qq.com`，`__biz=MzIzNjc1NzUzMw==` |
| DeepSeek | 10 | 2026-11-13 | `mp.weixin.qq.com`，`__biz=Mzk0OTYwNzc3NQ==` |
| 月之暗面 Kimi | 10 | 2026-11-12 | `mp.weixin.qq.com`，`__biz=MzcwMjM3ODEzOA==` |

量子位 2026-11-17 同次群发的多篇文章共享 `mid=2247944524`，因此**不能仅凭 `mid` 去重**；至少需要使用 `__biz + mid + idx` 标识一篇微信原文。此键可用于同一微信地址的精确匹配，但不同渠道对同一事件的转载仍需标题、企业、事件和独立来源核对。

尝试读取线上 `articles.json`（约 2.2 MB）进行正式交叉去重时，多次发生下载中断；本次**未取得完整对照快照，不能报告实际重复率或宣称三源进入候选池没有重复**。必须在离线验证中完成 URL 精确去重及跨来源事件对齐，才能申请逐源启用。
