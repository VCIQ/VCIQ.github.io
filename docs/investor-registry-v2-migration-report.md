# Investor Registry Migration Report v1

## 审计结论（2026-10-11）

这是并行的 v2 数据层，**没有替换** `config/innovation_global_investors.json`、正式证据台账、首页“科创”发布器或“重点”个性化逻辑。

- 真实旧版全球机构名单：**30 家**，其中中国相关 **8 家**。
- 先前提出的中国核心12家，已有 **7 家**存在于旧全球30家中；因此只需新增 **5 家**。
- 原全球30家中的 **中科创星**虽然不在先前12家建议名单内，也必须保留并在中国覆盖视图中出现。
- 去重结果：**35个唯一机构实体**；其中全球既有 cohort 30 家，中国重点 cohort 13 家，两个 cohort 重合 8 家。两个 cohort 不是可相加的独立机构数。
- **Sequoia Capital 与 HongShan**保持两个 canonical ID，历史品牌关联用 `historical-lineage`，禁止按相似名称或原同门品牌自动归并历史投资。

## 现有全球30家（沿用生产 canonical ID）

| Canonical ID | 机构 | 现有地域分组 | 中国重点cohort |
|---|---|---|---|
| `sequoia` | Sequoia Capital | 北美及跨区域 | — |
| `a16z` | Andreessen Horowitz（a16z） | 北美及跨区域 | — |
| `accel` | Accel | 北美及跨区域 | — |
| `lightspeed` | Lightspeed Venture Partners | 北美及跨区域 | — |
| `general-catalyst` | General Catalyst | 北美及跨区域 | — |
| `bessemer` | Bessemer Venture Partners | 北美及跨区域 | — |
| `khosla` | Khosla Ventures | 北美及跨区域 | — |
| `lux` | Lux Capital | 北美及跨区域 | — |
| `dcvc` | DCVC | 北美及跨区域 | — |
| `founders-fund` | Founders Fund | 北美及跨区域 | — |
| `eclipse` | Eclipse | 北美及跨区域 | — |
| `arch` | ARCH Venture Partners | 北美及跨区域 | — |
| `hongshan` | 红杉中国（HongShan） | 中国相关 | 是 |
| `qiming` | 启明创投 | 中国相关 | 是 |
| `idg-capital` | IDG资本 | 中国相关 | 是 |
| `legend-capital` | 君联资本 | 中国相关 | 是 |
| `source-code` | 源码资本 | 中国相关 | 是 |
| `zhenfund` | 真格基金 | 中国相关 | 是 |
| `casstar` | 中科创星 | 中国相关 | 是 |
| `sinovation` | 创新工场 | 中国相关 | 是 |
| `atomico` | Atomico | 欧洲相关 | — |
| `index` | Index Ventures | 欧洲相关 | — |
| `balderton` | Balderton Capital | 欧洲相关 | — |
| `earlybird` | Earlybird | 欧洲相关 | — |
| `iq-capital` | IQ Capital | 欧洲相关 | — |
| `elaia` | Elaia | 欧洲相关 | — |
| `sofinnova-partners` | Sofinnova Partners | 欧洲相关 | — |
| `vertex-sea-india` | Vertex Ventures SEA & India | 亚洲其他市场 | — |
| `utec` | UTEC | 亚洲其他市场 | — |
| `sginnovate` | SGInnovate | 亚洲其他市场 | — |

## 中国重点机构13家（去重后）

| Canonical ID | 机构 | 来源资产 | 官网状态 |
|---|---|---|---|
| `hongshan` | 红杉中国（HongShan） | 复用生产 global30 | 已登记（不等于完成当日采集） |
| `qiming` | 启明创投 | 复用生产 global30 | 已登记（不等于完成当日采集） |
| `idg-capital` | IDG资本 | 复用生产 global30 | 已登记（不等于完成当日采集） |
| `legend-capital` | 君联资本 | 复用生产 global30 | 已登记（不等于完成当日采集） |
| `source-code` | 源码资本 | 复用生产 global30 | 已登记（不等于完成当日采集） |
| `zhenfund` | 真格基金 | 复用生产 global30 | 已登记（不等于完成当日采集） |
| `casstar` | 中科创星 | 复用生产 global30 | 已登记（不等于完成当日采集） |
| `sinovation` | 创新工场 | 复用生产 global30 | 已登记（不等于完成当日采集） |
| `matrix-china` | 经纬创投 | 从中国已审实体档案新增 | 已登记（不等于完成当日采集） |
| `gaorong` | 高榕创投 | 从中国已审实体档案新增 | 已登记（不等于完成当日采集） |
| `northern-light` | 北极光创投 | 从中国已审实体档案新增 | 待核实，不填猜测URL |
| `shunwei` | 顺为资本 | 从中国已审实体档案新增 | 待核实，不填猜测URL |
| `five-years` | 五源资本 | 从中国已审实体档案新增 | 待核实，不填猜测URL |

## ID 迁移要点

- `source-code`、`idg-capital`、`legend-capital`、`hongshan` 均为**生产既有 ID**，不能改写为之前设计稿的 `source_code`、`idg_china`、`legend_capital`、`hsg`。
- 经纬创投采用既有中国档案 slug `matrix-china`，高榕采用 `gaorong`，不另外造第二个机构。
- 新增的北极光创投、顺为资本、五源资本保留审核过的中文英文名称别名，但当前档案未登记可靠的官网首页，进入**待官方来源接入**状态。
- `Sequoia China` 可以作为 HongShan 历史品牌查询名，但与 `Sequoia Capital` 绝不能进入同一 canonical 节点；具体历史事件归属仍须核验原文时点。

## 风险与关闭条件

| 风险 | 级别 | 当前处理 | 生产迁移前关闭条件 |
|---|---|---|---|
| 错误合并 Sequoia 与 HongShan | 高 | 保留两个ID、严格精确别名 | 抽样核验历史归属与跨主体投资关系 |
| 更改现有30家ID破坏59+投资证据 | 高 | 映射30/30保持原样，v2只新增文件 | 证据与项目图谱 CI 全通过 |
| 中英文别名/同名不同主体 | 中高 | 精确匹配；冲突即失败，不做模糊连接 | 新别名逐项审核、核对法律主体及官网 |
| 北极光/顺为/五源暂无官网来源字段 | 中 | homepage=null、score=null | 补齐可靠的官网原文与自动采集入口，成功扫描再计覆盖 |
| 数据稀疏被误判为机构不活跃 | 高 | 没有扫描证据时保持 score=null | 有多次生产 Scout 基线后计算健康指标 |
| Cohort 直接相加导致重复计算 | 中 | 35 唯一实体、全球30与中国13交叉统计 | Dashboard 用 canonical distinct count |

## 本次并行资产

- `config/innovation_investor_registry_v2.json`：统一35家、cohorts、别名、官方来源状态、独立关系。
- `config/investor_registry_migration_map.json`：旧30个真实 ID 保留映射、5个新增实体来源、未发布设计稿ID的可审提示。
- `config/investor_identity_merge_report.json`：重合项、分离关系、来源待补与风险决策。
- `config/innovation_investor_coverage.json`：从正式证据生成的可复核初始计数，**不猜测 Coverage Score**。
- `lib/innovation-investor-registry-v2.ts`：并行验证与严格别名解析，不影响线上主路由。
- 三个回归测试：identity、migration、coverage。

## 下一阶段验收

先让 v2 数据层全量 CI 通过，再搭建 `/innovation-capital/coverage/` 的页面与数据解释；公开页面首次上线必须清晰区分“官网已登记”“近期扫描已运行”“发现的导航线索”“已核实证据”。未接入官方来源的新增机构不能显示为健康或零投资。
