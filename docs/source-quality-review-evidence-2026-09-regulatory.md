# 2026-09 监管信源 AI 辅助审查证据

- 人类确认者：`VCIQ`
- 确认时间：`2026-09-02T17:11:20Z`
- 审查对象：`regulatory:cninfo`、`regulatory:hkex`
- 完整原始 URL、标题与记录字段：见 `public/data/source_quality_review_queue.json`，并通过下列 `sampleDigest` 固定样本。
- 该确认不改变 lifecycle policy，也不把限制性证据描述为直接全文核验。

## 确认口径

| sourceId | sampleDigest | reviewed | misattributed | duplicates | 证据构成 |
|---|---|---:|---:|---:|---|
| `regulatory:cninfo` | `0279a88b65af846f` | 20 | 0 | 0 | 18 条官方 PDF 直接核验；2 条官方 PDF 超时，以发行人、标题、日期及公告编号精确旁证。 |
| `regulatory:hkex` | `c9f8bbb95f84ac15` | 20 | 0 | 0 | 9 条官方 PDF 直接核验；11 条官方中文区占位页按发行人、股票代码、发布时间和事件类别核验。 |

## 限制

- CNINFO 的两条旁证记录没有在本次环境中直接读取 PDF 正文。
- HKEX 的 11 条英文占位页不暴露中文原文标题，未声称完成不可见中文全文比较。
- “重复为 0”表示没有发现可确认的同一原文或同一事件重复。

## 逐条证据状态

### `regulatory:cninfo`

`sampleDigest=0279a88b65af846f`

| # | recordId | 公司 | 状态 | 置信度 | 证据备注 |
|---:|---|---|---|---|---|
| 1 | `disclosure-bgi-genomics-dc0ea32e87dcc2133f` | 华大基因 | `PASS_DIRECT` | 高 | PDF首页直接确认公司全称与报告标题。 |
| 2 | `disclosure-bgi-genomics-346005a55079926b78` | 华大基因 | `PASS_DIRECT` | 高 | PDF首页直接确认证券代码300676、公司和标题。 |
| 3 | `disclosure-bgi-genomics-17e4691f6401ec8748` | 华大基因 | `PASS_DIRECT` | 高 | PDF首页直接确认；与半年度报告全文是不同正式文件，不计重复。 |
| 4 | `disclosure-catl-2f47086b3d22373858` | 宁德时代 | `PASS_DIRECT` | 高 | PDF首页直接确认；股权登记日为2026-08-05。 |
| 5 | `disclosure-cambricon-9c68a2fa026e13c3e5` | 寒武纪 | `PASS_DIRECT` | 高 | PDF首页直接确认公司代码688256和标题。 |
| 6 | `disclosure-cambricon-919b6ad05554a828e6` | 寒武纪 | `PASS_DIRECT` | 高 | PDF首页直接确认；摘要与全文是不同正式文件。 |
| 7 | `disclosure-cambricon-5f51962ae942848d38` | 寒武纪 | `PASS_DIRECT` | 高 | PDF首页直接确认公司代码688256和报告标题。 |
| 8 | `disclosure-catl-9f155fe3afae307b2b` | 宁德时代 | `PASS_DIRECT` | 高 | PDF首页直接确认；登记基准日为2026-07-24，与8月7日同名公告对应不同快照，不计重复。 |
| 9 | `disclosure-catl-f97b3005c272bf3b25` | 宁德时代 | `PASS_DIRECT` | 高 | PDF首页直接确认公司和标题。 |
| 10 | `disclosure-catl-b5067ca914c4f1f4d1` | 宁德时代 | `PASS_DIRECT` | 高 | PDF首页直接确认公司和标题。 |
| 11 | `disclosure-catl-812316a4268ed72182` | 宁德时代 | `PASS_DIRECT` | 高 | PDF首页直接确认。 |
| 12 | `disclosure-catl-3ff23cd689c96d67ff` | 宁德时代 | `PASS_DIRECT` | 高 | PDF首页直接确认；摘要与全文是不同正式文件。 |
| 13 | `disclosure-catl-6775f1c8f430f53fc0` | 宁德时代 | `PASS_DIRECT` | 高 | PDF首页直接确认债券名称、代码524857.SZ及上市事项。 |
| 14 | `disclosure-catl-024ca94f4152477d7f` | 宁德时代 | `PASS_CORROBORATED` | 中 | 官方PDF本次抓取超时；公告编号尾号7939、公司、日期和完整标题由多个索引页面一致印证。 |
| 15 | `disclosure-bgi-genomics-9675c2b2e6ca85ea3b` | 华大基因 | `PASS_DIRECT` | 高 | PDF首页直接确认；登记基准日为2026-06-15。 |
| 16 | `disclosure-catl-e75fab83a573169658` | 宁德时代 | `PASS_DIRECT` | 高 | PDF首页直接确认，债券简称26CATLK2。 |
| 17 | `disclosure-catl-e87d37f391b4128b67` | 宁德时代 | `PASS_DIRECT` | 高 | PDF首页直接确认更名事项。 |
| 18 | `disclosure-catl-49bb303471a0c0b8b9` | 宁德时代 | `PASS_DIRECT` | 高 | PDF正文直接确认发行人、本期债券和发行安排。 |
| 19 | `disclosure-catl-42ae64f064c37ffa2c` | 宁德时代 | `PASS_CORROBORATED` | 中 | 官方PDF本次抓取超时；公告编号尾号3024、公司、日期和完整标题由多个索引/镜像页面一致印证。 |
| 20 | `disclosure-bgi-genomics-53b4854f643d6ede36` | 华大基因 | `PASS_DIRECT` | 高 | PDF首页直接确认公司、证券代码300676和标题；网页PDF元数据标题异常，但正文正确。 |

### `regulatory:hkex`

`sampleDigest=c9f8bbb95f84ac15`

| # | recordId | 公司 | 状态 | 置信度 | 证据备注 |
|---:|---|---|---|---|---|
| 1 | `disclosure-catl-6bf50ba54802770bf8` | 宁德时代 / CATL | `PASS_OFFICIAL_PLACEHOLDER` | 中 | HKEX官方占位页可访问；标题搜索确认股票代码03750、CATL、18:27、类别“发行证券及相关事宜”。中文原文标题未在英文页公开。 |
| 2 | `disclosure-horizon-robotics-cf9f2a50333b22ae88` | 地平线机器人 / Horizon Robotics | `PASS_DIRECT` | 高 | PDF首页直接确认公司、股票代码9660、标题和完成日期。 |
| 3 | `disclosure-horizon-robotics-28ded6a4a11024bb02` | 地平线机器人 / Horizon Robotics | `PASS_DIRECT` | 高 | PDF首页直接确认公司、股票代码9660、标题和授予日期。 |
| 4 | `disclosure-catl-ea1417317a87dd9a12` | 宁德时代 / CATL | `PASS_DIRECT` | 高 | PDF封面直接确认股票代码3750、CATL中英文名称和2026中期报告。 |
| 5 | `disclosure-catl-a3558dfa60ef946e48` | 宁德时代 / CATL | `PASS_DIRECT` | 高 | PDF封面直接确认CATL、股票代码3750及完整通函事项。 |
| 6 | `disclosure-xtalpi-f2c6f1076ff78e0f7e` | 晶泰科技 / XtalPi | `PASS_DIRECT` | 高 | PDF首页直接确认XtalPi Holdings、股票代码2228和标题。 |
| 7 | `disclosure-catl-bb4479f0726d36b3a0` | 宁德时代 / CATL | `PASS_OFFICIAL_PLACEHOLDER` | 中 | HKEX标题搜索确认股票代码03750、CATL、22:30、类别“交易更新”。 |
| 8 | `disclosure-catl-b4766a960a051afd0a` | 宁德时代 / CATL | `PASS_OFFICIAL_PLACEHOLDER` | 中 | HKEX标题搜索确认股票代码03750、CATL、22:27、类别“发行证券及相关事宜”。 |
| 9 | `disclosure-catl-9b0b7a67b98eeaed73` | 宁德时代 / CATL | `PASS_OFFICIAL_PLACEHOLDER` | 中 | HKEX标题搜索确认股票代码03750、CATL、22:18、类别“业务更新”。 |
| 10 | `disclosure-catl-7c3b81becd20bc3472` | 宁德时代 / CATL | `PASS_OFFICIAL_PLACEHOLDER` | 中 | HKEX标题搜索确认股票代码03750、CATL、22:32、类别“交易更新”。 |
| 11 | `disclosure-catl-7576b425b03e831be9` | 宁德时代 / CATL | `PASS_OFFICIAL_PLACEHOLDER` | 中 | HKEX标题搜索确认股票代码03750、CATL、22:24、类别“发行证券及相关事宜”。 |
| 12 | `disclosure-catl-08bd1803b09201fb07` | 宁德时代 / CATL | `PASS_OFFICIAL_PLACEHOLDER` | 中 | HKEX标题搜索确认股票代码03750、CATL、21:56、类别“发行证券及相关事宜”。 |
| 13 | `disclosure-catl-051364ea6c500fcaa6` | 宁德时代 / CATL | `PASS_OFFICIAL_PLACEHOLDER` | 中 | HKEX标题搜索确认股票代码03750、CATL、21:59、类别“业务更新”。 |
| 14 | `disclosure-horizon-robotics-2a0ccebcd63f7ed0c3` | 地平线机器人 / Horizon Robotics | `PASS_DIRECT` | 高 | PDF首页直接确认公司、股票代码9660、标题和金额。 |
| 15 | `disclosure-horizon-robotics-c1d342124d08026fa2` | 地平线机器人 / Horizon Robotics | `PASS_DIRECT` | 高 | PDF首页直接确认股票代码9660和拟发行可转债事项。 |
| 16 | `disclosure-horizon-robotics-7199b05100e1b5487a` | 地平线机器人 / Horizon Robotics | `PASS_DIRECT` | 高 | PDF首页直接确认股票代码9660、公司和标题。 |
| 17 | `disclosure-xtalpi-4ea62e6ec593936097` | 晶泰科技 / XtalPi | `PASS_DIRECT` | 高 | PDF首页直接确认XtalPi、股票代码2228、标题和授予日期。 |
| 18 | `disclosure-catl-54bc64e53c587171ea` | 宁德时代 / CATL | `PASS_OFFICIAL_PLACEHOLDER` | 中 | HKEX标题搜索确认股票代码03750、CATL、21:10、类别“发行证券及相关事宜”。 |
| 19 | `disclosure-catl-f9eecd363a8bf8f757` | 宁德时代 / CATL | `PASS_OFFICIAL_PLACEHOLDER` | 中 | HKEX标题搜索确认股票代码03750、CATL、18:53、类别“发行证券及相关事宜”。 |
| 20 | `disclosure-catl-890d64e7587a09dca1` | 宁德时代 / CATL | `PASS_OFFICIAL_PLACEHOLDER` | 中 | HKEX标题搜索确认股票代码03750、CATL、18:48、类别“发行证券及相关事宜”。 |

## 人类确认

人类审核者 `VCIQ` 已明确采用证据表确认口径，并接受上述 AI 辅助预审方法及证据可见性限制。相应聚合结果写入 `config/source_quality_reviews.json`。
