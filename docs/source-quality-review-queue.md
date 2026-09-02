# 信源人工质量抽样队列

周期：`2026-09`；信源健康快照：`2026-09-02T14:36:59+00:00`。

目标为每个来源累计 **20** 条人工审查记录。当前有 **8** 个来源已具备足量候选，**632** 个来源仍缺少可审记录。

## 审核规则

1. 只按本页给出的 record ID 与原始 URL 审核，不用名称相似度自行补归属。
2. 对每个来源最多审核 `reviewNeeded` 条；若已人工审核过某条，不要重复计数。
3. 完成后仍将汇总结果写入现有 `config/source_quality_reviews.json`，不改 schema。
4. 在该 review 的 `notes` 中记录 `sampleDigest=<值>`，以便从 Git 历史追溯本次具体样本。

| 来源 | 等级 | 已审/目标 | 还需 | 可用记录 | 队列状态 | sampleDigest |
|---|---|---:|---:|---:|---|---|
| 巨潮资讯 | A | 0/20 | 20 | 57 | 可审核 | `0279a88b65af846f` |
| 香港交易所披露易 | A | 0/20 | 20 | 60 | 可审核 | `c9f8bbb95f84ac15` |
| DEV Community | C | 0/20 | 20 | 20 | 可审核 | `4812c00094daaaff` |
| Yahoo奇摩 | C | 0/20 | 20 | 20 | 可审核 | `56ece0d341a58772` |
| Yahoo奇摩 | C | 0/20 | 20 | 20 | 可审核 | `73695d5c92e4c19b` |
| 媒体报道 · 新浪 · 新浪财经 | C | 0/20 | 20 | 20 | 可审核 | `9a6440080d7d828a` |
| 媒体报道 · 新浪 · 新浪财经 | C | 0/20 | 20 | 20 | 可审核 | `72429465985e86be` |
| 投资界 | C | 0/20 | 20 | 20 | 可审核 | `8f769ea23324c439` |
| Alibaba Group 官方动态 | B | 0/20 | 20 | 1 | 记录不足 | `c75cbf194df5b40f` |
| Alibaba Group 官方网站 | B | 0/20 | 20 | 0 | 记录不足 | `f048d2b6eefe7a58` |
| AliExpress 官方动态 | B | 0/20 | 20 | 0 | 记录不足 | `14f3db6314bc0885` |
| AliExpress 官方网站 | B | 0/20 | 20 | 0 | 记录不足 | `f3032f7216d5ba9c` |
| Anduril Industries 官方动态 | B | 0/20 | 20 | 4 | 记录不足 | `f1c160a2dd2d11e7` |
| Anthropic | B | 0/20 | 20 | 1 | 记录不足 | `867ac17668524637` |
| Anthropic | B | 0/20 | 20 | 5 | 记录不足 | `15e8c611e994b36c` |
| Anthropic 官方动态 | B | 0/20 | 20 | 0 | 记录不足 | `ce48668c9ee5725d` |
| arXiv · Core AI companies | B | 0/20 | 20 | 8 | 记录不足 | `0d3aeece596697a8` |
| Aurora Innovation 官方动态 | B | 0/20 | 20 | 3 | 记录不足 | `541ebd8b16d16f7a` |
| Axiom Space 官方动态 | B | 0/20 | 20 | 4 | 记录不足 | `1afab4a8cb22712d` |
| CATL | B | 0/20 | 20 | 0 | 记录不足 | `8baf1838b7b24434` |
| Cerebras Systems | B | 0/20 | 20 | 0 | 记录不足 | `77b30b8a88051252` |
| Cerebras Systems · 官方网站 | B | 0/20 | 20 | 2 | 记录不足 | `07de873a921f163c` |
| Cerebras Systems · 官方网站 | B | 0/20 | 20 | 0 | 记录不足 | `7b41847bd48a261e` |
| Cerebras Systems · 官方网站 | B | 0/20 | 20 | 0 | 记录不足 | `d12a01499bac284c` |
| Cerebras Systems 官方动态 | B | 0/20 | 20 | 2 | 记录不足 | `a32f97719eaede4e` |
| Commonwealth Fusion Systems 官方动态 | B | 0/20 | 20 | 0 | 记录不足 | `22309084a7a95cff` |
| Databricks 官方动态 | B | 0/20 | 20 | 4 | 记录不足 | `3f40880b057464dd` |
| DeepSeek | B | 0/20 | 20 | 0 | 记录不足 | `6f7ac1823da81d2e` |
| DeepSeek 官方动态 | B | 0/20 | 20 | 4 | 记录不足 | `c2f9cdf3e4878ef1` |
| Figure AI | B | 0/20 | 20 | 0 | 记录不足 | `889393fb69a5b305` |
| Figure AI 官方动态 | B | 0/20 | 20 | 4 | 记录不足 | `45e0e01a913b5387` |
| Form Energy 官方动态 | B | 0/20 | 20 | 4 | 记录不足 | `dd69f336c93830ce` |
| Glean 官方动态 | B | 0/20 | 20 | 0 | 记录不足 | `8955a0c76b81e41a` |
| Google AI | B | 0/20 | 20 | 2 | 记录不足 | `a8facdc7df4fd5bd` |
| Google DeepMind | B | 0/20 | 20 | 2 | 记录不足 | `5fe368725b1f3be2` |
| Google DeepMind | B | 0/20 | 20 | 0 | 记录不足 | `1c6e824927bc1740` |
| Google DeepMind | B | 0/20 | 20 | 5 | 记录不足 | `606aa0bc48d2e66f` |
| Google 官方动态 | B | 0/20 | 20 | 4 | 记录不足 | `99e57c7e7c6606cd` |
| Google 官方动态 | B | 0/20 | 20 | 5 | 记录不足 | `4f450ac94e15db59` |
| Google 官方网站 | B | 0/20 | 20 | 0 | 记录不足 | `c72519a0258f039a` |
| Groq 官方动态 | B | 0/20 | 20 | 4 | 记录不足 | `bfcb255fde36681d` |
| Harvey 官方动态 | B | 0/20 | 20 | 4 | 记录不足 | `11b6219c3903feae` |
| Helion Energy 官方动态 | B | 0/20 | 20 | 4 | 记录不足 | `86811309b8ffa661` |
| IonQ | B | 0/20 | 20 | 0 | 记录不足 | `ba3a47ae93a7b70d` |
| IonQ 官方动态 | B | 0/20 | 20 | 4 | 记录不足 | `bcaa9dfb5c4bfa8c` |
| Joby Aviation 官方动态 | B | 0/20 | 20 | 4 | 记录不足 | `e4c67c08428ca320` |
| Lazada 官方动态 | B | 0/20 | 20 | 0 | 记录不足 | `38e572c3a964fe5b` |
| Lazada 官方网站 | B | 0/20 | 20 | 0 | 记录不足 | `a6f8710377754f07` |
| MiniMax | B | 0/20 | 20 | 0 | 记录不足 | `e1517be14d06cdb7` |
| MiniMax 官方动态 | B | 0/20 | 20 | 0 | 记录不足 | `70c1dd24e6287dda` |
| Mobileye 官方动态 | B | 0/20 | 20 | 4 | 记录不足 | `338532ffa82b28ff` |
| OpenAI | B | 0/20 | 20 | 0 | 记录不足 | `7d3194f79e645c42` |
| OpenAI | B | 0/20 | 20 | 5 | 记录不足 | `716aeb64ce04d031` |
| OpenAI 官方动态 | B | 0/20 | 20 | 0 | 记录不足 | `8f83eab02e36d396` |
| Perplexity 官方动态 | B | 0/20 | 20 | 0 | 记录不足 | `ff22b92ab74ddce8` |
| Pony.ai Investor Relations | B | 0/20 | 20 | 0 | 记录不足 | `c2ece5279671ac71` |
| PR Newswire Consumer Technology | B | 0/20 | 20 | 5 | 记录不足 | `0ba88ef4a7909331` |
| PsiQuantum 官方动态 | B | 0/20 | 20 | 4 | 记录不足 | `e3fe24b977ce9dbc` |
| Recursion Pharmaceuticals 官方动态 | B | 0/20 | 20 | 4 | 记录不足 | `24716ff8c6ee157a` |
| Redwood Materials 官方动态 | B | 0/20 | 20 | 4 | 记录不足 | `26d2fb29af852a3f` |
| Relativity Space 官方动态 | B | 0/20 | 20 | 4 | 记录不足 | `91518f335c53b62f` |
| Rigetti Computing 官方动态 | B | 0/20 | 20 | 4 | 记录不足 | `212e81cbdf6e5971` |
| Rocket Lab Investor Relations | B | 0/20 | 20 | 0 | 记录不足 | `149a649cef0cd708` |
| Rocket Lab 官方动态 | B | 0/20 | 20 | 4 | 记录不足 | `d5826b6135e15241` |
| SambaNova Systems 官方动态 | B | 0/20 | 20 | 4 | 记录不足 | `07e771583f82804b` |
| Scale AI | B | 0/20 | 20 | 0 | 记录不足 | `59c5204e6b81208b` |
| Scale AI 官方动态 | B | 0/20 | 20 | 4 | 记录不足 | `164885ac0fe6a241` |
| Shield AI 官方动态 | B | 0/20 | 20 | 4 | 记录不足 | `490c9c8302a850e4` |
| Shopify 官方动态 | B | 0/20 | 20 | 4 | 记录不足 | `ecd77a12e5305b6a` |
| Shopify 官方动态 | B | 0/20 | 20 | 0 | 记录不足 | `c5de1fb0e02dc3a7` |
| Shopify 官方网站 | B | 0/20 | 20 | 0 | 记录不足 | `2ddbee055a110ae8` |
| Sierra 官方动态 | B | 0/20 | 20 | 4 | 记录不足 | `68d7ed7ac189e99a` |
| SpaceX | B | 0/20 | 20 | 0 | 记录不足 | `e78bdebae031095b` |
| SpaceX 官方动态 | B | 0/20 | 20 | 0 | 记录不足 | `1c04218ff2296233` |
| Tempus AI 官方动态 | B | 0/20 | 20 | 0 | 记录不足 | `a6111d51beea3380` |
| The Washington Post | B | 0/20 | 20 | 10 | 记录不足 | `803480caa6a0f605` |
| The Washington Post | B | 0/20 | 20 | 0 | 记录不足 | `f7efb455dec04697` |
| Varda Space Industries 官方动态 | B | 0/20 | 20 | 0 | 记录不足 | `bb603f44803396fe` |
| WeRide Investor Relations | B | 0/20 | 20 | 0 | 记录不足 | `bc09e671c67cd3a7` |
| xAI | B | 0/20 | 20 | 7 | 记录不足 | `ed9951823709bf1e` |
| xAI 官方动态 | B | 0/20 | 20 | 4 | 记录不足 | `51529d16cf730782` |
| 东方财富 · 生物科技信源 | B | 0/20 | 20 | 0 | 记录不足 | `d6eb8c097e4eaf9a` |
| 傅利叶智能 官方动态 | B | 0/20 | 20 | 0 | 记录不足 | `4b138df240df64d3` |
| 华大基因 官方动态 | B | 0/20 | 20 | 0 | 记录不足 | `04a46e78251de4cf` |
| 启明创投 · 核心团队页 | B | 0/20 | 20 | 3 | 记录不足 | `c1a723028783b927` |
| 地平线机器人 官方动态 | B | 0/20 | 20 | 0 | 记录不足 | `417058ad172c92e5` |
| 埃隆·马斯克 | B | 0/20 | 20 | 1 | 记录不足 | `733283982fd80401` |
| 壁仞科技 官方动态 | B | 0/20 | 20 | 2 | 记录不足 | `8e729718d1f93da7` |
| 媒体报道 · 官方网站 · Commonwealth Fusion Systems | B | 0/20 | 20 | 0 | 记录不足 | `9f8f3e553c6fdd77` |
| 媒体报道 · 官方网站 · Commonwealth Fusion Systems | B | 0/20 | 20 | 0 | 记录不足 | `8a488f2804bc0768` |
| 媒体报道 · 官方网站 · Commonwealth Fusion Systems | B | 0/20 | 20 | 0 | 记录不足 | `db17e98743300b8c` |
| 字节跳动 | B | 0/20 | 20 | 0 | 记录不足 | `5388bc10736a0eff` |
| 宁德时代 官方动态 | B | 0/20 | 20 | 4 | 记录不足 | `a75ca6f825713e34` |
| 宇树科技 | B | 0/20 | 20 | 0 | 记录不足 | `5a0888f587f30149` |
| 宇树科技 官方动态 | B | 0/20 | 20 | 0 | 记录不足 | `666a7582b4125fe6` |
| 寒武纪 官方动态 | B | 0/20 | 20 | 0 | 记录不足 | `9c9fdb11a155287e` |
| 小马智行 官方动态 | B | 0/20 | 20 | 4 | 记录不足 | `358ae0ce83f58068` |
| 小鹏汇天 官方动态 | B | 0/20 | 20 | 0 | 记录不足 | `b39156c8c6d0a80c` |
| 搜狐网 · 商业航天信源 | B | 0/20 | 20 | 2 | 记录不足 | `d2c6a4bb2fd3065c` |
| 搜狐网 官方动态 | B | 0/20 | 20 | 0 | 记录不足 | `b627d43624d58c06` |

这里只展示前 100 个来源；完整队列见 JSON 文件。

## 巨潮资讯

`sourceId=regulatory:cninfo` · 还需审核 `20` 条 · `sampleDigest=0279a88b65af846f`

1. **2026年半年度报告**
   - `regulatory-disclosure` · `disclosure-bgi-genomics-dc0ea32e87dcc2133f` · 2026-08-21 · 华大基因
   - https://static.cninfo.com.cn/finalpage/2026-08-22/1225492096.PDF
2. **关于增加2026年度日常关联交易预计额度的公告**
   - `regulatory-disclosure` · `disclosure-bgi-genomics-346005a55079926b78` · 2026-08-21 · 华大基因
   - https://static.cninfo.com.cn/finalpage/2026-08-22/1225492099.PDF
3. **2026年半年度报告摘要**
   - `regulatory-disclosure` · `disclosure-bgi-genomics-17e4691f6401ec8748` · 2026-08-21 · 华大基因
   - https://static.cninfo.com.cn/finalpage/2026-08-22/1225492095.PDF
4. **关于回购股份事项前十名股东和前十名无限售条件股东持股情况的公告**
   - `regulatory-disclosure` · `disclosure-catl-2f47086b3d22373858` · 2026-08-07 · 宁德时代
   - https://static.cninfo.com.cn/finalpage/2026-08-07/1225464975.PDF
5. **关于公司2026年半年度募集资金存放、管理与实际使用情况的专项报告**
   - `regulatory-disclosure` · `disclosure-cambricon-9c68a2fa026e13c3e5` · 2026-08-07 · 寒武纪
   - https://static.cninfo.com.cn/finalpage/2026-08-08/1225464970.PDF
6. **2026年半年度报告摘要**
   - `regulatory-disclosure` · `disclosure-cambricon-919b6ad05554a828e6` · 2026-08-07 · 寒武纪
   - https://static.cninfo.com.cn/finalpage/2026-08-08/1225464971.PDF
7. **2026年半年度报告**
   - `regulatory-disclosure` · `disclosure-cambricon-5f51962ae942848d38` · 2026-08-07 · 寒武纪
   - https://static.cninfo.com.cn/finalpage/2026-08-08/1225464969.PDF
8. **关于回购股份事项前十名股东和前十名无限售条件股东持股情况的公告**
   - `regulatory-disclosure` · `disclosure-catl-9f155fe3afae307b2b` · 2026-07-30 · 宁德时代
   - https://static.cninfo.com.cn/finalpage/2026-07-30/1225448968.PDF
9. **关于回购公司股份方案的公告暨回购股份报告书**
   - `regulatory-disclosure` · `disclosure-catl-f97b3005c272bf3b25` · 2026-07-24 · 宁德时代
   - https://static.cninfo.com.cn/finalpage/2026-07-25/1225441582.PDF
10. **关于2026年半年度募集资金存放与使用情况的专项报告**
   - `regulatory-disclosure` · `disclosure-catl-b5067ca914c4f1f4d1` · 2026-07-24 · 宁德时代
   - https://static.cninfo.com.cn/finalpage/2026-07-25/1225441590.PDF
11. **2026年半年度报告**
   - `regulatory-disclosure` · `disclosure-catl-812316a4268ed72182` · 2026-07-24 · 宁德时代
   - https://static.cninfo.com.cn/finalpage/2026-07-25/1225441586.PDF
12. **2026年半年度报告摘要**
   - `regulatory-disclosure` · `disclosure-catl-3ff23cd689c96d67ff` · 2026-07-24 · 宁德时代
   - https://static.cninfo.com.cn/finalpage/2026-07-25/1225441585.PDF
13. **宁德时代新能源科技股份有限公司2026年面向专业投资者公开发行科技创新公司债券（第二期）在深圳证券交易所上市的公告**
   - `regulatory-disclosure` · `disclosure-catl-6775f1c8f430f53fc0` · 2026-06-25 · 宁德时代
   - https://static.cninfo.com.cn/finalpage/2026-06-25/1225387554.PDF
14. **宁德时代新能源科技股份有限公司2026年面向专业投资者公开发行科技创新公司债券（第二期）发行结果公告**
   - `regulatory-disclosure` · `disclosure-catl-024ca94f4152477d7f` · 2026-06-18 · 宁德时代
   - https://static.cninfo.com.cn/finalpage/2026-06-18/1225377939.PDF
15. **关于回购股份事项前十名股东和前十名无限售条件股东持股情况的公告**
   - `regulatory-disclosure` · `disclosure-bgi-genomics-9675c2b2e6ca85ea3b` · 2026-06-18 · 华大基因
   - https://static.cninfo.com.cn/finalpage/2026-06-18/1225377667.PDF
16. **宁德时代新能源科技股份有限公司2026年面向专业投资者公开发行科技创新公司债券（第二期）票面利率公告**
   - `regulatory-disclosure` · `disclosure-catl-e75fab83a573169658` · 2026-06-17 · 宁德时代
   - https://static.cninfo.com.cn/finalpage/2026-06-17/1225376442.PDF
17. **宁德时代新能源科技股份有限公司2026年面向专业投资者公开发行公司债券更名公告**
   - `regulatory-disclosure` · `disclosure-catl-e87d37f391b4128b67` · 2026-06-16 · 宁德时代
   - https://static.cninfo.com.cn/finalpage/2026-06-16/1225373022.PDF
18. **宁德时代新能源科技股份有限公司2026年面向专业投资者公开发行科技创新公司债券（第二期）发行公告**
   - `regulatory-disclosure` · `disclosure-catl-49bb303471a0c0b8b9` · 2026-06-16 · 宁德时代
   - https://static.cninfo.com.cn/finalpage/2026-06-16/1225373026.PDF
19. **宁德时代新能源科技股份有限公司2026年面向专业投资者公开发行科技创新公司债券（第二期）募集说明书**
   - `regulatory-disclosure` · `disclosure-catl-42ae64f064c37ffa2c` · 2026-06-16 · 宁德时代
   - https://static.cninfo.com.cn/finalpage/2026-06-16/1225373024.PDF
20. **关于控股股东提议公司回购股份的公告**
   - `regulatory-disclosure` · `disclosure-bgi-genomics-53b4854f643d6ede36` · 2026-06-16 · 华大基因
   - https://static.cninfo.com.cn/finalpage/2026-06-16/1225374424.PDF

## 香港交易所披露易

`sourceId=regulatory:hkex` · 还需审核 `20` 条 · `sampleDigest=c9f8bbb95f84ac15`

1. **An announcement has just been published by the issuer in the Chinese section of this website, a corresponding version of which may or may not be published in this section**
   - `regulatory-disclosure` · `disclosure-catl-6bf50ba54802770bf8` · 2026-08-27 · 宁德时代
   - https://www1.hkexnews.hk/listedco/listconews/sehk/2026/0827/2026082701064.htm
2. **COMPLETION OF THE ISSUE OF US$450,000,000 ZERO COUPON CONVERTIBLE BONDS DUE 2027**
   - `regulatory-disclosure` · `disclosure-horizon-robotics-cf9f2a50333b22ae88` · 2026-07-29 · 地平线机器人
   - https://www1.hkexnews.hk/listedco/listconews/sehk/2026/0729/2026072900588.pdf
3. **GRANT OF AWARDS PURSUANT TO THE POST-IPO SHARE INCENTIVE PLAN**
   - `regulatory-disclosure` · `disclosure-horizon-robotics-28ded6a4a11024bb02` · 2026-07-26 · 地平线机器人
   - https://www1.hkexnews.hk/listedco/listconews/sehk/2026/0726/2026072600115.pdf
4. **2026 INTERIM REPORT**
   - `regulatory-disclosure` · `disclosure-catl-ea1417317a87dd9a12` · 2026-07-26 · 宁德时代
   - https://www1.hkexnews.hk/listedco/listconews/sehk/2026/0726/2026072600031.pdf
5. **PROPOSED GRANT OF GENERAL MANDATE FOR A SUBSIDIARY TO ISSUE BONDS PROPOSED FORMULATION OF THE MANAGEMENT SYSTEM FOR THE REMUNERATION OF DIRECTORS AND SENIOR MANAGEMENT PROPOSED ENGAGEMENT IN FUTURES AND DERIVATIVES TRADING BY THE SUBSIDIARIES OF THE COMPANY A SHARES REPURCHASE PLAN NOTICE OF THE EXTRAORDINARY GENERAL MEETING**
   - `regulatory-disclosure` · `disclosure-catl-a3558dfa60ef946e48` · 2026-07-26 · 宁德时代
   - https://www1.hkexnews.hk/listedco/listconews/sehk/2026/0726/2026072600107.pdf
6. **PROFIT WARNING**
   - `regulatory-disclosure` · `disclosure-xtalpi-f2c6f1076ff78e0f7e` · 2026-07-24 · 晶泰科技
   - https://www1.hkexnews.hk/listedco/listconews/sehk/2026/0724/2026072401900.pdf
7. **An announcement has just been published by the issuer in the Chinese section of this website, a corresponding version of which may or may not be published in this section**
   - `regulatory-disclosure` · `disclosure-catl-bb4479f0726d36b3a0` · 2026-07-24 · 宁德时代
   - https://www1.hkexnews.hk/listedco/listconews/sehk/2026/0724/2026072401883.htm
8. **An announcement has just been published by the issuer in the Chinese section of this website, a corresponding version of which may or may not be published in this section**
   - `regulatory-disclosure` · `disclosure-catl-b4766a960a051afd0a` · 2026-07-24 · 宁德时代
   - https://www1.hkexnews.hk/listedco/listconews/sehk/2026/0724/2026072401877.htm
9. **An announcement has just been published by the issuer in the Chinese section of this website, a corresponding version of which may or may not be published in this section**
   - `regulatory-disclosure` · `disclosure-catl-9b0b7a67b98eeaed73` · 2026-07-24 · 宁德时代
   - https://www1.hkexnews.hk/listedco/listconews/sehk/2026/0724/2026072401827.htm
10. **An announcement has just been published by the issuer in the Chinese section of this website, a corresponding version of which may or may not be published in this section**
   - `regulatory-disclosure` · `disclosure-catl-7c3b81becd20bc3472` · 2026-07-24 · 宁德时代
   - https://www1.hkexnews.hk/listedco/listconews/sehk/2026/0724/2026072401887.htm
11. **An announcement has just been published by the issuer in the Chinese section of this website, a corresponding version of which may or may not be published in this section**
   - `regulatory-disclosure` · `disclosure-catl-7576b425b03e831be9` · 2026-07-24 · 宁德时代
   - https://www1.hkexnews.hk/listedco/listconews/sehk/2026/0724/2026072401863.htm
12. **An announcement has just been published by the issuer in the Chinese section of this website, a corresponding version of which may or may not be published in this section**
   - `regulatory-disclosure` · `disclosure-catl-08bd1803b09201fb07` · 2026-07-24 · 宁德时代
   - https://www1.hkexnews.hk/listedco/listconews/sehk/2026/0724/2026072401617.htm
13. **An announcement has just been published by the issuer in the Chinese section of this website, a corresponding version of which may or may not be published in this section**
   - `regulatory-disclosure` · `disclosure-catl-051364ea6c500fcaa6` · 2026-07-24 · 宁德时代
   - https://www1.hkexnews.hk/listedco/listconews/sehk/2026/0724/2026072401623.htm
14. **PRICING OF US$450,000,000 ZERO COUPON CONVERTIBLE BONDS DUE 2027**
   - `regulatory-disclosure` · `disclosure-horizon-robotics-2a0ccebcd63f7ed0c3` · 2026-07-23 · 地平线机器人
   - https://www1.hkexnews.hk/listedco/listconews/sehk/2026/0723/2026072300027.pdf
15. **INSIDE INFORMATION PROPOSED ISSUE OF CONVERTIBLE BOND UNDER GENERAL MANDATE**
   - `regulatory-disclosure` · `disclosure-horizon-robotics-c1d342124d08026fa2` · 2026-07-22 · 地平线机器人
   - https://www1.hkexnews.hk/listedco/listconews/sehk/2026/0722/2026072200995.pdf
16. **INSIDE INFORMATION UPDATE ON FINANCIAL PERFORMANCE**
   - `regulatory-disclosure` · `disclosure-horizon-robotics-7199b05100e1b5487a` · 2026-07-21 · 地平线机器人
   - https://www1.hkexnews.hk/listedco/listconews/sehk/2026/0721/2026072100145.pdf
17. **GRANT OF SHARE OPTIONS AND RESTRICTED SHARE UNITS**
   - `regulatory-disclosure` · `disclosure-xtalpi-4ea62e6ec593936097` · 2026-07-02 · 晶泰科技
   - https://www1.hkexnews.hk/listedco/listconews/sehk/2026/0702/2026070203757.pdf
18. **An announcement has just been published by the issuer in the Chinese section of this website, a corresponding version of which may or may not be published in this section**
   - `regulatory-disclosure` · `disclosure-catl-54bc64e53c587171ea` · 2026-06-26 · 宁德时代
   - https://www1.hkexnews.hk/listedco/listconews/sehk/2026/0626/2026062602344.htm
19. **An announcement has just been published by the issuer in the Chinese section of this website, a corresponding version of which may or may not be published in this section**
   - `regulatory-disclosure` · `disclosure-catl-f9eecd363a8bf8f757` · 2026-06-25 · 宁德时代
   - https://www1.hkexnews.hk/listedco/listconews/sehk/2026/0625/2026062501327.htm
20. **An announcement has just been published by the issuer in the Chinese section of this website, a corresponding version of which may or may not be published in this section**
   - `regulatory-disclosure` · `disclosure-catl-890d64e7587a09dca1` · 2026-06-18 · 宁德时代
   - https://www1.hkexnews.hk/listedco/listconews/sehk/2026/0618/2026061801299.htm

## DEV Community

`sourceId=user-source-source-dev-community` · 还需审核 `20` 条 · `sampleDigest=4812c00094daaaff`

1. **Antes de escrever uma linha de código, tive que provar que aguentava trocar de SO**
   - `article` · `user-source-source-dev-community-ee31c44f9117bd31` · 2026-08-22 · 科技产业
   - https://dev.to/tomasmsardinha/antes-de-escrever-uma-linha-de-codigo-tive-que-provar-que-aguentava-trocar-de-so-2e6a
2. **How I’m Improving a Local Service Website for SEO, AEO & GEO**
   - `article` · `user-source-source-dev-community-e91b914e1037f3d8` · 2026-08-22 · 科技产业
   - https://dev.to/kaleem_ullah_6698699/how-im-improving-a-local-service-website-for-seo-aeo-geo-329c
3. **How to Review AI-Generated SQL Before You Trust the Number**
   - `article` · `user-source-source-dev-community-da1093cd37b7aca2` · 2026-08-22 · 科技产业
   - https://dev.to/michaelnocito/how-to-review-ai-generated-sql-before-you-trust-the-number-19ek
4. **We put an AI helper in our course and spent weeks teaching it to say I don't know**
   - `article` · `user-source-source-dev-community-d7f0172f88831893` · 2026-08-22 · 科技产业
   - https://dev.to/academy_agineai/we-put-an-ai-helper-in-our-course-and-spent-weeks-teaching-it-to-say-i-dont-know-hfc
5. **I Built a Crypto Market Intelligence App with React Native, Supabase & Cloudflare Workers AI**
   - `article` · `user-source-source-dev-community-c19f6341b7c42748` · 2026-08-22 · 科技产业
   - https://dev.to/alligator_peach_developer/i-built-a-crypto-market-intelligence-app-with-react-native-supabase-cloudflare-workers-ai-4j0e
6. **JavaScript Sandbox Escape via Type Confusion in isolated-vm**
   - `article` · `user-source-source-dev-community-ac67db583481492b` · 2026-08-22 · 科技产业
   - https://dev.to/anoymask/javascript-sandbox-escape-via-type-confusion-in-isolated-vm-4op9
7. **Leveling up OpenCode... and not in the way you would expect.**
   - `article` · `user-source-source-dev-community-5a8568ea31d75eee` · 2026-08-22 · 科技产业
   - https://dev.to/searay_11_254650fe8d2b6b6/leveling-up-opencode-and-not-in-the-way-you-would-expect-27
8. **¿La IA está sobrescribiendo tus notas? Tres capas de ownership para proteger tu conocimiento**
   - `article` · `user-source-source-dev-community-382f88e45eed6e3f` · 2026-08-22 · 科技产业
   - https://dev.to/macorreag/la-ia-esta-sobrescribiendo-tus-notas-tres-capas-de-ownership-para-proteger-tu-conocimiento-3e3l
9. **Can We Automate the Work of a Software Engineer? The Story Behind HEALER**
   - `article` · `user-source-source-dev-community-2e330885f474da70` · 2026-08-22 · 科技产业
   - https://dev.to/_a9de0f38ed294cfb7e5e/can-we-automate-the-work-of-a-software-engineer-the-story-behind-healer-2mge
10. **The jitter wasn't in the interpolation. It was in the schedule.**
   - `article` · `user-source-source-dev-community-0d70490da01ae786` · 2026-08-22 · 科技产业
   - https://dev.to/renga154/the-jitter-wasnt-in-the-interpolation-it-was-in-the-schedule-557p
11. **8 Shipped Chrome Extensions, 4 Ways to Declare Host Permissions**
   - `article` · `user-source-source-dev-community-fce7abf6ef3c1eb8` · 2026-08-21 · 科技产业
   - https://dev.to/k-wada/8-shipped-chrome-extensions-4-ways-to-declare-host-permissions-3n1c
12. **Fantastic resource. Treating API keys like passwords—rotation, secure storage, least privilege—is simple advice that prevents massive breaches. The OWASP framework gives it authority, and the practical steps make it easy**
   - `article` · `user-source-source-dev-community-fb3ce3f39ea4b411` · 2026-08-21 · 科技产业
   - https://dev.to/sadique_anwar_b90373bc79c/fantastic-resource-treating-api-keys-like-passwords-rotation-secure-storage-least-privilege-is-1m6h
13. **SilkParasite: Cloud C2 and Multi-Language RATs Targeting Central Asia**
   - `article` · `user-source-source-dev-community-f3a93c742eb44c93` · 2026-08-21 · 科技产业
   - https://dev.to/anoymask/silkparasite-cloud-c2-and-multi-language-rats-targeting-central-asia-1ikl
14. **MLflow CVE-2026-64849: Cloud Credential Theft via Webhook SSRF**
   - `article` · `user-source-source-dev-community-ec1c0fe36a51d90a` · 2026-08-21 · 科技产业
   - https://dev.to/anoymask/mlflow-cve-2026-64849-cloud-credential-theft-via-webhook-ssrf-2j
15. **We built a benchmark, then caught it strangling the models it was grading**
   - `article` · `user-source-source-dev-community-d5e5f67858a45c6c` · 2026-08-21 · 科技产业
   - https://dev.to/fortitudeomnis/we-built-a-benchmark-then-caught-it-strangling-the-models-it-was-grading-27gl
16. **Google Gemini Notebook Expands Into AI Mode Search With Cross-App Notebook Syncing**
   - `article` · `user-source-source-dev-community-7c409f771865a80e` · 2026-08-21 · 科技产业
   - https://dev.to/alifar/google-gemini-notebook-expands-into-ai-mode-search-with-cross-app-notebook-syncing-2h17
17. **I benchmarked 5 graph databases. The first four hours measured the Indian Ocean.**
   - `article` · `user-source-source-dev-community-668058d4110616cc` · 2026-08-21 · 科技产业
   - https://dev.to/burz4m_13b009bb9f0a92a88c/i-benchmarked-5-graph-databases-the-first-four-hours-measured-the-indian-ocean-1ea0
18. **The cheapest model on my plan loses every benchmark. It still beats models charging 14x more.**
   - `article` · `user-source-source-dev-community-3eafeca99750fd82` · 2026-08-21 · 科技产业
   - https://dev.to/dev_michael/the-cheapest-model-on-my-plan-loses-every-benchmark-it-still-beats-models-charging-14x-more-2po8
19. **Microsoft Expands MAI Playground With Image, Voice, Transcription and Reasoning Models**
   - `article` · `user-source-source-dev-community-241d588962268960` · 2026-08-21 · 科技产业
   - https://dev.to/alifar/microsoft-expands-mai-playground-with-image-voice-transcription-and-reasoning-models-9f8
20. **An AI Agent Has Run This SaaS for 580+ Sessions. It Has Zero Customers.**
   - `article` · `user-source-source-dev-community-09ca6133a36ec6b8` · 2026-08-21 · 科技产业
   - https://dev.to/merlonix/an-ai-agent-has-run-this-saas-for-580-sessions-it-has-zero-customers-5169

## Yahoo奇摩

`sourceId=user-source-source-yahoo` · 还需审核 `20` 条 · `sampleDigest=56ece0d341a58772`

1. **AI材料翻身戰1》全球最大買家怕斷料 SEMI揪台廠組隊突圍**
   - `article` · `user-source-source-yahoo-ec8ba5d1945ac2b8` · 2026-08-22 · 科技产业
   - https://tw.news.yahoo.com/ai%E6%9D%90%E6%96%99%E7%BF%BB%E8%BA%AB%E6%88%B01-%E5%85%A8%E7%90%83%E6%9C%80%E5%A4%A7%E8%B2%B7%E5%AE%B6%E6%80%95%E6%96%B7%E6%96%99-semi%E6%8F%AA%E5%8F%B0%E5%BB%A0%E7%B5%84%E9%9A%8A%E7%AA%81%E5%9C%8D-000000707.html
2. **高雄城市與產業發展論壇聚焦AI新動能 陳其邁：「緊緊緊」精神提升城市競爭力 產官學共議科技S廊道與亞灣新經濟**
   - `article` · `user-source-source-yahoo-de41ccc6157fb3a2` · 2026-08-22 · 科技产业
   - https://tw.news.yahoo.com/%E9%AB%98%E9%9B%84%E5%9F%8E%E5%B8%82%E8%88%87%E7%94%A2%E6%A5%AD%E7%99%BC%E5%B1%95%E8%AB%96%E5%A3%87%E8%81%9A%E7%84%A6ai%E6%96%B0%E5%8B%95%E8%83%BD-%E9%99%B3%E5%85%B6%E9%82%81-%E7%B7%8A%E7%B7%8A%E7%B7%8A-%E7%B2%BE%E7%A5%9E%E6%8F%90%E5%8D%87%E5%9F%8E%E5%B8%82%E7%AB%B6%E7%88%AD%E5%8A%9B-%E7%94%A2%E5%AE%98%E5%AD%B8%E5%85%B1%E8%AD%B0%E7%A7%91%E6%8A%80s%E5%BB%8A%E9%81%93%E8%88%87%E4%BA%9E%E7%81%A3%E6%96%B0%E7%B6%93%E6%BF%9F-060126302.html
3. **AI記憶體大洗牌！不只HBM吃香 華邦電、南亞科新商機浮現「2028年是關鍵」**
   - `article` · `user-source-source-yahoo-d78562274285314f` · 2026-08-22 · 科技产业
   - https://tw.stock.yahoo.com/news/ai%E8%A8%98%E6%86%B6%E9%AB%94%E5%A4%A7%E6%B4%97%E7%89%8C-%E4%B8%8D%E5%8F%AAhbm%E5%90%83%E9%A6%99-%E8%8F%AF%E9%82%A6%E9%9B%BB-%E5%8D%97%E4%BA%9E%E7%A7%91%E6%96%B0%E5%95%86%E6%A9%9F%E6%B5%AE%E7%8F%BE-2028%E5%B9%B4%E6%98%AF%E9%97%9C%E9%8D%B5-022000520.html
4. **AI材料翻身戰3》缺料曾飛海外「跪求」 日月光黃義從要替台灣築高牆**
   - `article` · `user-source-source-yahoo-c78db38f86220852` · 2026-08-22 · 科技产业
   - https://tw.news.yahoo.com/ai%E6%9D%90%E6%96%99%E7%BF%BB%E8%BA%AB%E6%88%B03-%E7%BC%BA%E6%96%99%E6%9B%BE%E9%A3%9B%E6%B5%B7%E5%A4%96-%E8%B7%AA%E6%B1%82-%E6%97%A5%E6%9C%88%E5%85%89%E9%BB%83%E7%BE%A9%E5%BE%9E%E8%A6%81%E6%9B%BF%E5%8F%B0%E7%81%A3%E7%AF%89%E9%AB%98%E7%89%86-000200130.html
5. **南投智慧科技防災營登場 19名學童走進九份二山學AI、防災知識**
   - `article` · `user-source-source-yahoo-9dd0a14d67c8a9e1` · 2026-08-22 · 科技产业
   - https://tw.news.yahoo.com/%E5%8D%97%E6%8A%95%E6%99%BA%E6%85%A7%E7%A7%91%E6%8A%80%E9%98%B2%E7%81%BD%E7%87%9F%E7%99%BB%E5%A0%B4-19%E5%90%8D%E5%AD%B8%E7%AB%A5%E8%B5%B0%E9%80%B2%E4%B9%9D%E4%BB%BD%E4%BA%8C%E5%B1%B1%E5%AD%B8ai-%E9%98%B2%E7%81%BD%E7%9F%A5%E8%AD%98-024958834.html
6. **NEAT串聯AI業者與製造企業！地端算力、智慧排程與AI Agent成為落地焦點**
   - `article` · `user-source-source-yahoo-95f860bc763569ae` · 2026-08-22 · 科技产业
   - https://tw.news.yahoo.com/neat%E4%B8%B2%E8%81%AFai%E6%A5%AD%E8%80%85%E8%88%87%E8%A3%BD%E9%80%A0%E4%BC%81%E6%A5%AD-%E5%9C%B0%E7%AB%AF%E7%AE%97%E5%8A%9B-%E6%99%BA%E6%85%A7%E6%8E%92%E7%A8%8B%E8%88%87ai-agent%E6%88%90%E7%82%BA%E8%90%BD%E5%9C%B0%E7%84%A6%E9%BB%9E-010000327.html
7. **韓國把AI帶動的晶片紅利存給下一代！擬設「未來應對基金」 青年住房、就業與AI一起投資**
   - `article` · `user-source-source-yahoo-676fe6c60216186d` · 2026-08-22 · 科技产业
   - https://tw.news.yahoo.com/%E9%9F%93%E5%9C%8B%E6%8A%8Aai%E5%B8%B6%E5%8B%95%E7%9A%84%E6%99%B6%E7%89%87%E7%B4%85%E5%88%A9%E5%AD%98%E7%B5%A6%E4%B8%8B-%E4%BB%A3-%E6%93%AC%E8%A8%AD-%E6%9C%AA%E4%BE%86%E6%87%89%E5%B0%8D%E5%9F%BA%E9%87%91-%E9%9D%92%E5%B9%B4%E4%BD%8F%E6%88%BF-021834980.html
8. **砸11.2億蓋智慧化產線！「LED模組廠」瞄準AI感測+自動化控制 昨股價死守25元大關**
   - `article` · `user-source-source-yahoo-53e827efb222af0d` · 2026-08-22 · 科技产业
   - https://tw.stock.yahoo.com/news/%E7%A0%B811-2%E5%84%84%E8%93%8B%E6%99%BA%E6%85%A7%E5%8C%96%E7%94%A2%E7%B7%9A-led%E6%A8%A1%E7%B5%84%E5%BB%A0-%E7%9E%84%E6%BA%96ai%E6%84%9F%E6%B8%AC-%E8%87%AA%E5%8B%95%E5%8C%96%E6%8E%A7%E5%88%B6-004500111.html
9. **AI浪潮改變教學中山醫大3教師獲SUPER教師獎**
   - `article` · `user-source-source-yahoo-52de2d84d3ef5fcb` · 2026-08-22 · 科技产业
   - https://tw.news.yahoo.com/ai%E6%B5%AA%E6%BD%AE%E6%94%B9%E8%AE%8A%E6%95%99%E5%AD%B8%E4%B8%AD%E5%B1%B1%E9%86%AB%E5%A4%A73%E6%95%99%E5%B8%AB%E7%8D%B2super%E6%95%99%E5%B8%AB%E7%8D%8E-052836489.html
10. **AI材料翻身戰2》徐秀蘭替材料廠喊話 隱形冠軍不再是配角**
   - `article` · `user-source-source-yahoo-4404756886ab3b38` · 2026-08-22 · 科技产业
   - https://tw.news.yahoo.com/ai%E6%9D%90%E6%96%99%E7%BF%BB%E8%BA%AB%E6%88%B02-%E5%BE%90%E7%A7%80%E8%98%AD%E6%9B%BF%E6%9D%90%E6%96%99%E5%BB%A0%E5%96%8A%E8%A9%B1-%E9%9A%B1%E5%BD%A2%E5%86%A0%E8%BB%8D%E4%B8%8D%E5%86%8D%E6%98%AF%E9%85%8D%E8%A7%92-000100862.html
11. **AI熱潮推升獲利 凱基投顧上修台股盈餘預估**
   - `article` · `user-source-source-yahoo-33ac743ac78d6882` · 2026-08-22 · 科技产业
   - https://tw.news.yahoo.com/ai%E7%86%B1%E6%BD%AE%E6%8E%A8%E5%8D%87%E7%8D%B2%E5%88%A9-%E5%87%B1%E5%9F%BA%E6%8A%95%E9%A1%A7%E4%B8%8A%E4%BF%AE%E5%8F%B0%E8%82%A1%E7%9B%88%E9%A4%98%E9%A0%90%E4%BC%B0-030648896.html
12. **王毅帶中國防長一起進印尼！軍演、AI、礦產一次談 2027還要開彈藥飛彈工廠**
   - `article` · `user-source-source-yahoo-336d1719aa703fe9` · 2026-08-22 · 科技产业
   - https://tw.news.yahoo.com/%E7%8E%8B%E6%AF%85%E5%B8%B6%E4%B8%AD%E5%9C%8B%E9%98%B2%E9%95%B7-%E8%B5%B7%E9%80%B2%E5%8D%B0%E5%B0%BC-%E8%BB%8D%E6%BC%94-ai-%E7%A4%A6%E7%94%A2-021550685.html
13. **AI光通訊需求爆發！這檔「PD拉貨呈倍數成長」訂單直達2028年 800G、1.6T到CPO全面布局**
   - `article` · `user-source-source-yahoo-bef1bb29d365e290` · 2026-08-21 · 科技产业
   - https://tw.stock.yahoo.com/news/ai%E5%85%89%E9%80%9A%E8%A8%8A%E9%9C%80%E6%B1%82%E7%88%86%E7%99%BC-%E9%80%99%E6%AA%94-pd%E6%8B%89%E8%B2%A8%E5%91%88%E5%80%8D%E6%95%B8%E6%88%90%E9%95%B7-%E8%A8%82%E5%96%AE%E7%9B%B4%E9%81%942028%E5%B9%B4-800g-224500226.html
14. **AI晶片功耗衝破千瓦！矽電容成先進封裝供電新救星 台廠積極搶進拚商機**
   - `article` · `user-source-source-yahoo-ac50c197acdba2ed` · 2026-08-21 · 科技产业
   - https://tw.news.yahoo.com/ai%E6%99%B6%E7%89%87%E5%8A%9F%E8%80%97%E8%A1%9D%E7%A0%B4%E5%8D%83%E7%93%A6-%E7%9F%BD%E9%9B%BB%E5%AE%B9%E6%88%90%E5%85%88%E9%80%B2%E5%B0%81%E8%A3%9D%E4%BE%9B%E9%9B%BB%E6%96%B0%E6%95%91%E6%98%9F-%E5%8F%B0%E5%BB%A0%E7%A9%8D%E6%A5%B5%E6%90%B6%E9%80%B2%E6%8B%9A%E5%95%86%E6%A9%9F-234000772.html
15. **AI散熱需求火熱！「這檔」7月營收創近14年新高、獲利年增107% 法人看散熱業務今年再增逾1倍**
   - `article` · `user-source-source-yahoo-79c68cf632b25e0f` · 2026-08-21 · 科技产业
   - https://tw.stock.yahoo.com/news/ai%E6%95%A3%E7%86%B1%E9%9C%80%E6%B1%82%E7%81%AB%E7%86%B1-%E9%80%99%E6%AA%94-7%E6%9C%88%E7%87%9F%E6%94%B6%E5%89%B5%E8%BF%9114%E5%B9%B4%E6%96%B0%E9%AB%98-%E7%8D%B2%E5%88%A9%E5%B9%B4%E5%A2%9E107-%E6%B3%95%E4%BA%BA%E7%9C%8B%E6%95%A3%E7%86%B1%E6%A5%AD%E5%8B%99%E4%BB%8A%E5%B9%B4%E5%86%8D%E5%A2%9E%E9%80%BE1%E5%80%8D-233000905.html
16. **工程師殺進AI新商機4／「沒有一天睡得著」房子押到3胎 貴人牽線讓他起死回生 如今成AI小金雞**
   - `article` · `user-source-source-yahoo-009e4c98898a8e72` · 2026-08-21 · 科技产业
   - https://tw.news.yahoo.com/%E5%B7%A5%E7%A8%8B%E5%B8%AB%E6%AE%BA%E9%80%B2ai%E6%96%B0%E5%95%86%E6%A9%9F4-%E6%B2%92%E6%9C%89-%E5%A4%A9%E7%9D%A1%E5%BE%97%E8%91%97-%E6%88%BF%E5%AD%90%E6%8A%BC%E5%88%B03%E8%83%8E-%E8%B2%B4%E4%BA%BA%E7%89%BD%E7%B7%9A%E8%AE%93%E4%BB%96%E8%B5%B7%E6%AD%BB%E5%9B%9E%E7%94%9F-222856251.html
17. **大批AI博主停更了！監管、成本、收益三座大山，中國AI內容泡沫潰堤**
   - `article` · `user-source-source-yahoo-b25a889e5fd22108` · 2026-08-20 · 科技产业
   - https://tw.news.yahoo.com/%E5%A4%A7%E6%89%B9ai%E5%8D%9A%E4%B8%BB%E5%81%9C%E6%9B%B4%E4%BA%86-%E7%9B%A3%E7%AE%A1-%E6%88%90%E6%9C%AC-%E6%94%B6%E7%9B%8A%E4%B8%89%E5%BA%A7%E5%A4%A7%E5%B1%B1-%E4%B8%AD%E5%9C%8Bai%E5%85%A7%E5%AE%B9%E6%B3%A1%E6%B2%AB%E6%BD%B0%E5%A0%A4-230835336.html
18. **AI熱潮加劇美國社會分歧 基礎建設落差牽動全球發展**
   - `article` · `user-source-source-yahoo-8b9f484b8525caf7` · 2026-08-20 · 科技产业
   - https://tw.stock.yahoo.com/news/ai%E7%86%B1%E6%BD%AE%E5%8A%A0%E5%8A%87%E7%BE%8E%E5%9C%8B%E7%A4%BE%E6%9C%83%E5%88%86%E6%AD%A7-%E5%9F%BA%E7%A4%8E%E5%BB%BA%E8%A8%AD%E8%90%BD%E5%B7%AE%E7%89%BD%E5%8B%95%E5%85%A8%E7%90%83%E7%99%BC%E5%B1%95-170555558.html
19. **一鍵比較六大 AI 模型答覆 新平台助攻寫作與程式開發**
   - `article` · `user-source-source-yahoo-868adfeae0049a72` · 2026-08-20 · 科技产业
   - https://tw.stock.yahoo.com/news/%E9%8D%B5%E6%AF%94%E8%BC%83%E5%85%AD%E5%A4%A7-ai-%E6%A8%A1%E5%9E%8B%E7%AD%94%E8%A6%86-%E6%96%B0%E5%B9%B3%E5%8F%B0%E5%8A%A9%E6%94%BB%E5%AF%AB%E4%BD%9C%E8%88%87%E7%A8%8B%E5%BC%8F%E9%96%8B%E7%99%BC-160756867.html
20. **紐西蘭企業財報喜憂參半 AI發展與消費電子價格受關注**
   - `article` · `user-source-source-yahoo-618b8e7ef68099df` · 2026-08-20 · 科技产业
   - https://tw.stock.yahoo.com/news/%E7%B4%90%E8%A5%BF%E8%98%AD%E4%BC%81%E6%A5%AD%E8%B2%A1%E5%A0%B1%E5%96%9C%E6%86%82%E5%8F%83%E5%8D%8A-ai%E7%99%BC%E5%B1%95%E8%88%87%E6%B6%88%E8%B2%BB%E9%9B%BB%E5%AD%90%E5%83%B9%E6%A0%BC%E5%8F%97%E9%97%9C%E6%B3%A8-162844287.html

## Yahoo奇摩

`sourceId=user-source-source-yahoo-2` · 还需审核 `20` 条 · `sampleDigest=73695d5c92e4c19b`

1. **OpenAI 模型失控駭入他廠 AI 自查卻陷信任危機**
   - `article` · `user-source-source-yahoo-2-f3d07f091319c540` · 2026-08-28 · OpenAI
   - https://tw.stock.yahoo.com/news/openai-%E6%A8%A1%E5%9E%8B%E5%A4%B1%E6%8E%A7%E9%A7%AD%E5%85%A5%E4%BB%96%E5%BB%A0-ai-%E8%87%AA%E6%9F%A5%E5%8D%BB%E9%99%B7%E4%BF%A1%E4%BB%BB%E5%8D%B1%E6%A9%9F-020416414.html
2. **派拓網路示警：AI顛覆資安攻防，攻擊者效率驟升十倍**
   - `article` · `user-source-source-yahoo-2-ee746c06c347795e` · 2026-08-28 · 科技产业
   - https://tw.stock.yahoo.com/news/%E6%B4%BE%E6%8B%93%E7%B6%B2%E8%B7%AF%E7%A4%BA%E8%AD%A6-ai%E9%A1%9B%E8%A6%86%E8%B3%87%E5%AE%89%E6%94%BB%E9%98%B2-%E6%94%BB%E6%93%8A%E8%80%85%E6%95%88%E7%8E%87%E9%A9%9F%E5%8D%87%E5%8D%81%E5%80%8D-000636804.html
3. **輝達、Salesforce財報亮眼 AI商機助科技股領漲華爾街**
   - `article` · `user-source-source-yahoo-2-dc58a74cbe3f05d0` · 2026-08-28 · 科技产业
   - https://tw.stock.yahoo.com/news/%E8%BC%9D%E9%81%94-salesforce%E8%B2%A1%E5%A0%B1%E4%BA%AE%E7%9C%BC-ai%E5%95%86%E6%A9%9F%E5%8A%A9%E7%A7%91%E6%8A%80%E8%82%A1%E9%A0%98%E6%BC%B2%E8%8F%AF%E7%88%BE%E8%A1%97-012114559.html
4. **景氣燈號7月續亮紅燈！AI熱潮、電子旺季加持，「連9紅」追平2021年紀錄穩了？**
   - `article` · `user-source-source-yahoo-2-db9ffca4caba7f24` · 2026-08-28 · 科技产业
   - https://tw.news.yahoo.com/%E6%99%AF%E6%B0%A3%E7%87%88%E8%99%9F7%E6%9C%88%E7%BA%8C%E4%BA%AE%E7%B4%85%E7%87%88-ai%E7%86%B1%E6%BD%AE-%E9%9B%BB%E5%AD%90%E6%97%BA%E5%AD%A3%E5%8A%A0%E6%8C%81-%E9%80%A39%E7%B4%85-%E8%BF%BD%E5%B9%B32021%E5%B9%B4%E7%B4%80%E9%8C%84%E7%A9%A9%E4%BA%86-060001564.html
5. **《時代》雜誌公布百大 AI 影響力人士 聚焦基礎建設與倫理挑戰**
   - `article` · `user-source-source-yahoo-2-db8bb82c37f6e1db` · 2026-08-28 · 科技产业
   - https://tw.stock.yahoo.com/news/%E6%99%82%E4%BB%A3-%E9%9B%9C%E8%AA%8C%E5%85%AC%E5%B8%83%E7%99%BE%E5%A4%A7-ai-%E5%BD%B1%E9%9F%BF%E5%8A%9B%E4%BA%BA%E5%A3%AB-%E8%81%9A%E7%84%A6%E5%9F%BA%E7%A4%8E%E5%BB%BA%E8%A8%AD%E8%88%87%E5%80%AB%E7%90%86%E6%8C%91%E6%88%B0-132119267.html
6. **Alphabet市值狂瀉7000億美元 AI戰略受質疑引投資人不安**
   - `article` · `user-source-source-yahoo-2-d89dafdfd6ec6e4a` · 2026-08-28 · 科技产业
   - https://tw.stock.yahoo.com/news/alphabet%E5%B8%82%E5%80%BC%E7%8B%82%E7%80%897000%E5%84%84%E7%BE%8E%E5%85%83-ai%E6%88%B0%E7%95%A5%E5%8F%97%E8%B3%AA%E7%96%91%E5%BC%95%E6%8A%95%E8%B3%87%E4%BA%BA%E4%B8%8D%E5%AE%89-003512633.html
7. **盧秀燕講總統府棄單副手查AI喊「中性名詞」綠議員也找AI反擊**
   - `article` · `user-source-source-yahoo-2-d680e028849d59a9` · 2026-08-28 · 科技产业
   - https://tw.news.yahoo.com/%E7%9B%A7%E7%A7%80%E7%87%95%E8%AC%9B%E7%B8%BD%E7%B5%B1%E5%BA%9C%E6%A3%84%E5%96%AE%E5%89%AF%E6%89%8B%E6%9F%A5ai%E5%96%8A-%E4%B8%AD%E6%80%A7%E5%90%8D%E8%A9%9E-%E7%B6%A0%E8%AD%B0%E5%93%A1%E4%B9%9F%E6%89%BEai%E5%8F%8D%E6%93%8A-055100387.html
8. **三星高層揭AI瓶頸：轉向記憶體運算與先進封裝成關鍵**
   - `article` · `user-source-source-yahoo-2-ccc554eb1ee61669` · 2026-08-28 · 科技产业
   - https://tw.stock.yahoo.com/news/%E4%B8%89%E6%98%9F%E9%AB%98%E5%B1%A4%E6%8F%ADai%E7%93%B6%E9%A0%B8-%E8%BD%89%E5%90%91%E8%A8%98%E6%86%B6%E9%AB%94%E9%81%8B%E7%AE%97%E8%88%87%E5%85%88%E9%80%B2%E5%B0%81%E8%A3%9D%E6%88%90%E9%97%9C%E9%8D%B5-020632215.html
9. **吸25家科技巨頭進駐！亞灣2.0拚出百億產值 AI主題館高雄登場**
   - `article` · `user-source-source-yahoo-2-cb87dc2ca30f879b` · 2026-08-28 · 科技产业
   - https://tw.news.yahoo.com/%E5%90%B825%E5%AE%B6%E7%A7%91%E6%8A%80%E5%B7%A8%E9%A0%AD%E9%80%B2%E9%A7%90-%E4%BA%9E%E7%81%A32-0%E6%8B%9A%E5%87%BA%E7%99%BE%E5%84%84%E7%94%A2%E5%80%BC-ai%E4%B8%BB%E9%A1%8C%E9%A4%A8%E9%AB%98%E9%9B%84%E7%99%BB%E5%A0%B4-145600569.html
10. **宏于電機加速AI能源布局 電力雲導入SaaS訂閱制服務**
   - `article` · `user-source-source-yahoo-2-c6844af61d930cf6` · 2026-08-28 · 科技产业
   - https://tw.stock.yahoo.com/news/%E5%AE%8F%E4%BA%8E%E9%9B%BB%E6%A9%9F%E5%8A%A0%E9%80%9Fai%E8%83%BD%E6%BA%90%E5%B8%83%E5%B1%80-%E9%9B%BB%E5%8A%9B%E9%9B%B2%E5%B0%8E%E5%85%A5saas%E8%A8%82%E9%96%B1%E5%88%B6%E6%9C%8D%E5%8B%99-060223973.html
11. **谷歌升級 Gemini Omni 1.1 Flash AI模型 影片生成更流暢高效**
   - `article` · `user-source-source-yahoo-2-b92e696981d57cec` · 2026-08-28 · 科技产业
   - https://tw.stock.yahoo.com/news/%E8%B0%B7%E6%AD%8C%E5%8D%87%E7%B4%9A-gemini-omni-1-1-015736291.html
12. **馬光攜手友達耘康讓AI學會「看舌頭」**
   - `article` · `user-source-source-yahoo-2-b41882ddd0de327d` · 2026-08-28 · 科技产业
   - https://tw.news.yahoo.com/%E9%A6%AC%E5%85%89%E6%94%9C%E6%89%8B%E5%8F%8B%E9%81%94%E8%80%98%E5%BA%B7%E8%AE%93ai%E5%AD%B8%E6%9C%83-%E7%9C%8B%E8%88%8C%E9%A0%AD-075815713.html
13. **AI無人機蜂群抗電子戰干擾 獲自主偵追鎖定能力**
   - `article` · `user-source-source-yahoo-2-b3adbd3538fcf8d5` · 2026-08-28 · 科技产业
   - https://tw.stock.yahoo.com/news/ai%E7%84%A1%E4%BA%BA%E6%A9%9F%E8%9C%82%E7%BE%A4%E6%8A%97%E9%9B%BB%E5%AD%90%E6%88%B0%E5%B9%B2%E6%93%BE-%E7%8D%B2%E8%87%AA%E4%B8%BB%E5%81%B5%E8%BF%BD%E9%8E%96%E5%AE%9A%E8%83%BD%E5%8A%9B-121850974.html
14. **AI浪潮五階段演進：從聊天機器人邁向實體智慧應用**
   - `article` · `user-source-source-yahoo-2-aa0943c614615e99` · 2026-08-28 · 科技产业
   - https://tw.stock.yahoo.com/news/ai%E6%B5%AA%E6%BD%AE%E4%BA%94%E9%9A%8E%E6%AE%B5%E6%BC%94%E9%80%B2-%E5%BE%9E%E8%81%8A%E5%A4%A9%E6%A9%9F%E5%99%A8%E4%BA%BA%E9%82%81%E5%90%91%E5%AF%A6%E9%AB%94%E6%99%BA%E6%85%A7%E6%87%89%E7%94%A8-131030824.html
15. **蕭敬騰沉迷AI短劇「付費解鎖就棄劇」 Summer驚問：那帳單上是什麼？**
   - `article` · `user-source-source-yahoo-2-a5993804172478d5` · 2026-08-28 · 科技产业
   - https://tw.news.yahoo.com/%E8%95%AD%E6%95%AC%E9%A8%B0%E6%B2%89%E8%BF%B7ai%E7%9F%AD%E5%8A%87%E3%80%8C%E4%BB%98%E8%B2%BB%E8%A7%A3%E9%8E%96%E5%B0%B1%E6%A3%84%E5%8A%87%E3%80%8D-summer%E9%A9%9A%E5%95%8F%EF%BC%9A%E9%82%A3%E5%B8%B3%E5%96%AE%E4%B8%8A%E6%98%AF%E4%BB%80%E9%BA%BC%EF%BC%9F-101357531.html
16. **日本半導體隱形功臣：設備與材料稱霸前、後段製程，穩居AI供應鏈要角**
   - `article` · `user-source-source-yahoo-2-a45d500a44f73df7` · 2026-08-28 · 科技产业
   - https://tw.stock.yahoo.com/news/%E6%97%A5%E6%9C%AC%E5%8D%8A%E5%B0%8E%E9%AB%94%E9%9A%B1%E5%BD%A2%E5%8A%9F%E8%87%A3-%E8%A8%AD%E5%82%99%E8%88%87%E6%9D%90%E6%96%99%E7%A8%B1%E9%9C%B8%E5%89%8D-%E5%BE%8C%E6%AE%B5%E8%A3%BD%E7%A8%8B-%E7%A9%A9%E5%B1%85ai%E4%BE%9B%E6%87%89%E9%8F%88%E8%A6%81%E8%A7%92-102020602.html
17. **16億差點砸出去！孫宇晨曝拒給景甜關鍵 AI「一句話」成翻臉導火線**
   - `article` · `user-source-source-yahoo-2-965fa8d9b1a32a4e` · 2026-08-28 · 科技产业
   - https://tw.news.yahoo.com/16%E5%84%84%E5%B7%AE%E9%BB%9E%E7%A0%B8%E5%87%BA%E5%8E%BB-%E5%AD%AB%E5%AE%87%E6%99%A8%E6%9B%9D%E6%8B%92%E7%B5%A6%E6%99%AF%E7%94%9C%E9%97%9C%E9%8D%B5-ai-%E5%8F%A5%E8%A9%B1-%E6%88%90%E7%BF%BB%E8%87%89%E5%B0%8E%E7%81%AB%E7%B7%9A-053600108.html
18. **AI紅利燒到哪？大摩上修台灣GDP至11.6% 「這檔」年化配息17%吸睛**
   - `article` · `user-source-source-yahoo-2-959cddc66fda19e9` · 2026-08-28 · 科技产业
   - https://tw.stock.yahoo.com/news/ai%E7%B4%85%E5%88%A9%E7%87%92%E5%88%B0%E5%93%AA-%E5%A4%A7%E6%91%A9%E4%B8%8A%E4%BF%AE%E5%8F%B0%E7%81%A3gdp%E8%87%B311-6-%E9%80%99%E6%AA%94-%E5%B9%B4%E5%8C%96%E9%85%8D%E6%81%AF17-040500432.html
19. **經濟部產業技術司31項創新科技大南方登場 AI落地百工百業 科技驅動中南部產業升級**
   - `article` · `user-source-source-yahoo-2-85786ca1fb5bcf35` · 2026-08-28 · 科技产业
   - https://tw.news.yahoo.com/%E7%B6%93%E6%BF%9F%E9%83%A8%E7%94%A2%E6%A5%AD%E6%8A%80%E8%A1%93%E5%8F%B831%E9%A0%85%E5%89%B5%E6%96%B0%E7%A7%91%E6%8A%80%E5%A4%A7%E5%8D%97%E6%96%B9%E7%99%BB%E5%A0%B4-ai%E8%90%BD%E5%9C%B0%E7%99%BE%E5%B7%A5%E7%99%BE%E6%A5%AD-%E7%A7%91%E6%8A%80%E9%A9%85%E5%8B%95%E4%B8%AD%E5%8D%97%E9%83%A8%E7%94%A2%E6%A5%AD%E5%8D%87%E7%B4%9A-112050552.html
20. **大南方新創展登場 產發署30項科技秀亞灣AI落地實力**
   - `article` · `user-source-source-yahoo-2-603b9fda2c3c5adc` · 2026-08-28 · 科技产业
   - https://tw.stock.yahoo.com/news/%E5%A4%A7%E5%8D%97%E6%96%B9%E6%96%B0%E5%89%B5%E5%B1%95%E7%99%BB%E5%A0%B4-%E7%94%A2%E7%99%BC%E7%BD%B230%E9%A0%85%E7%A7%91%E6%8A%80%E7%A7%80%E4%BA%9E%E7%81%A3ai%E8%90%BD%E5%9C%B0%E5%AF%A6%E5%8A%9B-123907783.html

## 媒体报道 · 新浪 · 新浪财经

`sourceId=user-source-source-manual-a65b25bc6a065091` · 还需审核 `20` 条 · `sampleDigest=9a6440080d7d828a`

1. **智能驾驶汽车扎堆上新，买车前这些坑要先想清楚**
   - `article` · `user-source-source-manual-a65b25bc6a065091-f7ef08916c9d4e3b` · 2026-08-28 · 科技产业
   - https://finance.sina.com.cn/consume/xiaofei/2026-08-28/doc-inipvrtz5694076.shtml
2. **渤海汽车：上半年亏损309万元 同比下降101.02%**
   - `article` · `user-source-source-manual-a65b25bc6a065091-bbba88bbf1cacf29` · 2026-08-28 · 科技产业
   - https://finance.sina.com.cn/stock/zqgd/2026-08-28/doc-inipwtfp5825649.shtml
3. **告别“草莽时代”：工信部重拳整治汽车质量，专家：明年新车上市数量将少于今年**
   - `article` · `user-source-source-manual-a65b25bc6a065091-a4e11029ef131e7d` · 2026-08-28 · 科技产业
   - https://finance.sina.com.cn/stock/wbstock/2026-08-28/doc-inipvmnh0322182.shtml
4. **上海丽人丽妆化妆品股份有限公司关于公司为子公司及公司子公司之间8月担保实施进展公告**
   - `article` · `user-source-source-manual-a65b25bc6a065091-9eab12ac40473534` · 2026-08-28 · 科技产业
   - https://finance.sina.com.cn/roll/2026-08-28/doc-inipuywn0487528.shtml
5. **长城汽车半年报：出海不只是一本收入账**
   - `article` · `user-source-source-manual-a65b25bc6a065091-938dcc8d62d8f000` · 2026-08-28 · 科技产业
   - https://finance.sina.com.cn/roll/2026-08-28/doc-inipvvzx5682563.shtml
6. **理想汽车公布新一代MEGA产品细节 9月2日开放定购**
   - `article` · `user-source-source-manual-a65b25bc6a065091-8f5d20921ca4fc2e` · 2026-08-28 · 科技产业
   - https://finance.sina.com.cn/stock/relnews/hk/2026-08-28/doc-inipwnxr5808484.shtml
7. **上海盛剑科技股份有限公司2026年半年度报告摘要**
   - `article` · `user-source-source-manual-a65b25bc6a065091-54366c74b64e51a1` · 2026-08-28 · 科技产业
   - https://finance.sina.com.cn/roll/2026-08-28/doc-inipuywi5806916.shtml
8. **四部门联合开展汽车产品质量专项整治 非理性竞争问题反映多的企业将被重点检查**
   - `article` · `user-source-source-manual-a65b25bc6a065091-41da275cf57d3520` · 2026-08-28 · 科技产业
   - https://finance.sina.com.cn/chanjing/cyxw/2026-08-28/doc-inipvmmz4783124.shtml
9. **零跑汽车上半年成绩单出炉：规模快速扩张 海外市场成核心增量**
   - `article` · `user-source-source-manual-a65b25bc6a065091-3d471579ac032878` · 2026-08-28 · 科技产业
   - https://finance.sina.com.cn/stock/auto/2026-08-28/doc-inipvfec8975310.shtml
10. **长安汽车上半年营收656.34亿元 谭本宏：必须顺应行业变化，主动调整经营节奏**
   - `article` · `user-source-source-manual-a65b25bc6a065091-366bb7baa1258b21` · 2026-08-28 · 科技产业
   - https://finance.sina.com.cn/roll/2026-08-28/doc-inipwtfr9862711.shtml
11. **一场运动会，逼得人形机器人努力"自主"**
   - `article` · `user-source-source-manual-a65b25bc6a065091-1a7af06f7f6ffa74` · 2026-08-28 · 科技产业
   - https://finance.sina.com.cn/wm/2026-08-28/doc-inipvmnc5711147.shtml
12. **说好搬家1300元，结果强要3900元，上海爷叔傻眼！11人强迫交易被抓**
   - `article` · `user-source-source-manual-a65b25bc6a065091-0f34bfcb49b8b23c` · 2026-08-28 · 科技产业
   - https://finance.sina.com.cn/jjxw/2026-08-28/doc-inipvwaa0167003.shtml
13. **上海公布数起虚拟币交易跨境洗钱案：最大涉案金额近200亿元，公安警示三大隐蔽特征**
   - `article` · `user-source-source-manual-a65b25bc6a065091-08ba752f080bc3c0` · 2026-08-28 · 科技产业
   - https://finance.sina.com.cn/roll/2026-08-28/doc-inipvwaa0167939.shtml
14. **半年亏掉40亿！理想汽车又开始过苦日子了**
   - `article` · `user-source-source-manual-a65b25bc6a065091-05339b2c1d0d2b2d` · 2026-08-28 · 科技产业
   - https://finance.sina.com.cn/wm/2026-08-28/doc-inipvvzx5731977.shtml
15. **四类问题突出！工信部曝光一批新能源汽车产品典型案例，多家车企被责令整改**
   - `article` · `user-source-source-manual-20bb24a76db33a43-c88294f4360c737d` · 2026-08-28 · 科技产业
   - https://finance.sina.com.cn/roll/2026-08-28/doc-inipwnxt9959652.shtml
16. **净利大增151%但新能源汽车产销却下滑八成 千里科技“AI+车”战略能走多远?**
   - `article` · `user-source-source-manual-20bb24a76db33a43-83c0dbf66305ba03` · 2026-08-28 · 科技产业
   - https://finance.sina.com.cn/stock/relnews/cn/2026-08-28/doc-inipwnxt9941975.shtml
17. **九成收入依赖海外，产品绑定燃油车！环能涡轮如何闯过新能源汽车浪潮？**
   - `article` · `user-source-source-manual-20bb24a76db33a43-5f059bd833dbdc9d` · 2026-08-28 · 科技产业
   - https://finance.sina.com.cn/roll/2026-08-28/doc-inipwhrr4524677.shtml
18. **5万-10万新能源汽车性价比排名：零跑启源拿下纯电第一**
   - `article` · `user-source-source-manual-20bb24a76db33a43-44f0cf6b617d2e1a` · 2026-08-28 · 科技产业
   - https://finance.sina.com.cn/stock/relnews/hk/2026-08-28/doc-inipwhrt5801002.shtml
19. **最终版！第二届世界人形机器人运动会奖牌榜**
   - `article` · `user-source-source-manual-a65b25bc6a065091-ae9bd11adeece9cc` · 2026-08-27 · 科技产业
   - https://finance.sina.com.cn/roll/2026-08-27/doc-inipthnz9009786.shtml
20. **贾跃亭：FF机器人工厂年内运营 发布两款机器人新品**
   - `article` · `user-source-source-manual-a65b25bc6a065091-8e8905ba6debde66` · 2026-08-27 · 科技产业
   - https://finance.sina.com.cn/tech/shenji/2026-08-27/doc-iniptnux5481164.shtml

## 媒体报道 · 新浪 · 新浪财经

`sourceId=user-source-source-manual-cbdb4c79a612763c` · 还需审核 `20` 条 · `sampleDigest=72429465985e86be`

1. **阿为特(920693)：聚焦液冷服务器快接头和半导体领域双赛道 2026H1营收同比+47%**
   - `article` · `user-source-source-manual-cbdb4c79a612763c-b3fd9ea70a0e265a` · 2026-08-28 · 科技产业
   - http://stock.finance.sina.com.cn/stock/go.php/vReport_Show/kind/lastest/rptid/841226528927/index.phtml
2. **天博智能IPO：全球调温器老三的“守位”与“突围”**
   - `article` · `user-source-source-manual-cbdb4c79a612763c-9efbb7e1574f3c26` · 2026-08-28 · 科技产业
   - https://finance.sina.com.cn/stock/hkstock/hkstocknews/2026-08-28/doc-inipvmnc5677023.shtml
3. **9月风险大集结：美日欧央行决议、Anthropic IPO与欧美债务，谁将引爆下一轮波动？**
   - `article` · `user-source-source-manual-cbdb4c79a612763c-91ef27e59a33aa65` · 2026-08-28 · Anthropic
   - https://finance.sina.com.cn/money/forex/forexroll/2026-08-28/doc-inipwhrr8958707.shtml
4. **机构：第二季度全球纯晶圆代工半导体市场规模同比增长29%**
   - `article` · `user-source-source-manual-cbdb4c79a612763c-8390f3f2002987d7` · 2026-08-28 · 科技产业
   - https://finance.sina.com.cn/stock/usstock/c/2026-08-28/doc-inipwait4586558.shtml
5. **103家上市，餐饮0家！港股IPO的“冰火两重天”**
   - `article` · `user-source-source-manual-cbdb4c79a612763c-723ecf8ac07e2a46` · 2026-08-28 · 科技产业
   - https://finance.sina.com.cn/wm/2026-08-28/doc-inipvmnc5704946.shtml
6. **IPO招股书虚假记载！保荐机构是这家头部券商**
   - `article` · `user-source-source-manual-cbdb4c79a612763c-4f0986f1eafef6a7` · 2026-08-28 · 科技产业
   - https://finance.sina.com.cn/roll/2026-08-28/doc-inipvvzv8986090.shtml
7. **电鳗财经｜深之蓝IPO：研发人员数量“腰斩”产销率超100% 却有库存商品积压？**
   - `article` · `user-source-source-manual-cbdb4c79a612763c-282f0ca05510340a` · 2026-08-28 · 科技产业
   - https://finance.sina.com.cn/stock/stockzmt/2026-08-28/doc-inipvmmz8987365.shtml
8. **SK海力士美国印第安纳州HBM生产基地举行奠基仪式，预计2029年第三季度开始量产**
   - `article` · `user-source-source-manual-cbdb4c79a612763c-0cf262430bdeae2d` · 2026-08-28 · 科技产业
   - https://finance.sina.com.cn/stock/usstock/c/2026-08-28/doc-inipvmnc5666863.shtml
9. **21评论丨自动驾驶入法，中国汽车进入“L3时刻”**
   - `article` · `user-source-source-manual-a65b25bc6a065091-b366c6022ccb17fd` · 2026-08-28 · 科技产业
   - https://finance.sina.com.cn/roll/2026-08-28/doc-inipuuqq0580708.shtml
10. **道交法修订草案迎审议：在自动驾驶激活状态下交通违法拟规定由车企方担责，车险产品如何优化迭代？**
   - `article` · `user-source-source-manual-cbdb4c79a612763c-dec32bb29c70a62b` · 2026-08-27 · 科技产业
   - https://finance.sina.com.cn/roll/2026-08-27/doc-iniptxkt9085698.shtml
11. **贝斯特新材港股IPO是否涉嫌隐瞒关联交易？上市前低价转股疑现瑞声科技吴春媛身影 有无利益输送**
   - `article` · `user-source-source-manual-cbdb4c79a612763c-da21821874ba14dc` · 2026-08-27 · 科技产业
   - https://finance.sina.com.cn/stock/observe/2026-08-27/doc-inipttax5835133.shtml
12. **‌HBM太赚钱，SK海力士正在“抛弃”消费级市场？**
   - `article` · `user-source-source-manual-cbdb4c79a612763c-a9986e280a1ae792` · 2026-08-27 · 科技产业
   - https://finance.sina.com.cn/stock/t/2026-08-27/doc-inipthnz5568828.shtml
13. **功率半导体半年报“冷热不均”，斯达半导净利跌超七成**
   - `article` · `user-source-source-manual-cbdb4c79a612763c-755eb71a7065582f` · 2026-08-27 · 科技产业
   - https://finance.sina.com.cn/roll/2026-08-27/doc-iniptaff5818140.shtml
14. **国家统计局最新发布！集成电路行业，利润同比增长18.5倍**
   - `article` · `user-source-source-manual-cbdb4c79a612763c-593cf13b2c8afaf4` · 2026-08-27 · 科技产业
   - https://finance.sina.com.cn/roll/2026-08-27/doc-iniptnuz5767396.shtml
15. **苏讯新材IPO，值得警惕的“裙带关系”，保代还曾被深交所通报批评**
   - `article` · `user-source-source-manual-cbdb4c79a612763c-3588a131b9706433` · 2026-08-27 · 科技产业
   - https://finance.sina.com.cn/stock/stockzmt/2026-08-27/doc-iniptaew0467718.shtml
16. **有关战略性新兴产业发展，上海最新发文，进一步全面提升集成电路产业能级**
   - `article` · `user-source-source-manual-a65b25bc6a065091-8b6171a184c02068` · 2026-08-27 · 科技产业
   - https://finance.sina.com.cn/roll/2026-08-26/doc-iniprytq2310345.shtml
17. **思索技术IPO：八项违规引监管“全链追责”，从实控人到保代均遭处分，手持理财1.1亿，募资额较前次激增156%**
   - `article` · `user-source-source-manual-cbdb4c79a612763c-f09e80f665d39fe2` · 2026-08-26 · 科技产业
   - https://finance.sina.com.cn/stock/newstock/2026-08-26/doc-inipsmip5868529.shtml
18. **险资“潜伏”硬科技IPO 超30家机构借道PE密集卡位**
   - `article` · `user-source-source-manual-cbdb4c79a612763c-9ef6ff18305646dd` · 2026-08-26 · 科技产业
   - https://finance.sina.com.cn/money/insurance/xzdt/2026-08-26/doc-inipqxfw1164120.shtml
19. **恒翼能IPO三轮问询必答题：大客户依赖症如何化解**
   - `article` · `user-source-source-manual-cbdb4c79a612763c-6fff4604c6908062` · 2026-08-26 · 科技产业
   - https://finance.sina.com.cn/roll/2026-08-26/doc-inipqnsa1307804.shtml
20. **港股IPO“科技”含量足 各路资金“抢筹”基石投资**
   - `article` · `user-source-source-manual-cbdb4c79a612763c-361e98f7c48078d2` · 2026-08-26 · 科技产业
   - https://finance.sina.com.cn/jjxw/2026-08-26/doc-inipqhkm6550642.shtml

## 投资界

`sourceId=user-source-source-track-rcvvao-2` · 还需审核 `20` 条 · `sampleDigest=8f769ea23324c439`

1. **AI行业_投资界：播报投资界AI行业投资并购动态**
   - `article` · `user-source-source-track-rcvvao-2-b552a4acea704321` · 2026-08-23 · 科技产业
   - https://www.pedaily.cn/i-ai
2. **AI算力的新格局**
   - `article` · `user-source-source-track-rcvvao-2-58eeaebfddf5c17e` · 2026-08-23 · 科技产业
   - https://news.pedaily.cn/202608/567996.shtml
3. **戚薇授权AI短剧，观众为什么坐不住了？**
   - `article` · `user-source-source-track-rcvvao-2-200d4f47a6282bea` · 2026-08-23 · 科技产业
   - https://news.pedaily.cn/202608/567999.shtml
4. **越会用 AI 的人，学习能力退化得越快**
   - `article` · `user-source-source-track-rcvvao-2-82cc11c71d8bf73c` · 2026-08-22 · 科技产业
   - https://news.pedaily.cn/202608/567987.shtml
5. **砸向AI，就能重构大厂护城河？**
   - `article` · `user-source-source-track-rcvvao-2-7ae2bd0187f9d217` · 2026-08-22 · 科技产业
   - https://news.pedaily.cn/202608/567983.shtml
6. **刚刚，多模态版DeepSeek「长眼」了**
   - `article` · `user-source-source-track-rcvvao-2-2e466d522911b68b` · 2026-08-22 · DeepSeek
   - https://news.pedaily.cn/202608/567984.shtml
7. **AI货架上的人脸，100元到10000元**
   - `article` · `user-source-source-track-rcvvao-fd86d4f7b9d3ff22` · 2026-08-21 · 科技产业
   - https://news.pedaily.cn/202608/567933.shtml
8. **马斯克要突破AI编程：Cursor之后，SpaceX试图再收Cognition但被拒绝**
   - `article` · `user-source-source-track-rcvvao-e7ad06ab37a0ef32` · 2026-08-21 · 科技产业
   - https://news.pedaily.cn/202608/567952.shtml
9. **Moderna背后，中国AI制药正在弯道超车**
   - `article` · `user-source-source-track-rcvvao-e233ce8ba054e55d` · 2026-08-21 · 科技产业
   - https://news.pedaily.cn/202608/567939.shtml
10. **都Agent时代了，我还是想分享给你这12个我最常用的Prompt**
   - `article` · `user-source-source-track-rcvvao-c282cb17096bcfe2` · 2026-08-21 · 科技产业
   - https://news.pedaily.cn/202608/567932.shtml
11. **梁文锋的阳谋：开源框架，模型涨价**
   - `article` · `user-source-source-track-rcvvao-5c6a14b7ba8fc2da` · 2026-08-21 · 科技产业
   - https://news.pedaily.cn/202608/567929.shtml
12. **清雁科技完成数亿元A轮融资，聚焦几何物理驱动的物理AI基础设施**
   - `article` · `user-source-source-track-rcvvao-21e3c93bae47f754` · 2026-08-21 · 科技产业
   - https://news.pedaily.cn/202608/567947.shtml
13. **银河通用王鹤：推动具身智能与人形机器人的核心突破时刻**
   - `article` · `user-source-source-track-rcvvao-2-eb19ce2d69fe6b49` · 2026-08-21 · 科技产业
   - https://news.pedaily.cn/202608/567961.shtml
14. **AI向癌症发起猛攻，4000种抗癌药虚拟试杀，谷歌Gemma下载破10亿**
   - `article` · `user-source-source-track-rcvvao-2-da97c05ecea39b4e` · 2026-08-21 · 科技产业
   - https://news.pedaily.cn/202608/567964.shtml
15. **天坑专业摘帽？DeepSeek开抢土木老哥**
   - `article` · `user-source-source-track-rcvvao-2-aed395cd3304357b` · 2026-08-21 · DeepSeek
   - https://news.pedaily.cn/202608/567940.shtml
16. **Claude Code 被轻易攻破，仅需一个假工具**
   - `article` · `user-source-source-track-rcvvao-2-7713f37b6a483871` · 2026-08-21 · Anthropic
   - https://news.pedaily.cn/202608/567948.shtml
17. **抖快B红集体押注「AI互动内容」，创作者如何抓住新机会？**
   - `article` · `user-source-source-track-rcvvao-2-65557bf1eda7dd1e` · 2026-08-21 · 科技产业
   - https://news.pedaily.cn/202608/567963.shtml
18. **投资界AI周报| 机器人挤爆北京亦庄**
   - `article` · `user-source-source-track-rcvvao-2-2e4a98e726150989` · 2026-08-21 · 科技产业
   - https://news.pedaily.cn/202608/567965.shtml
19. **栖息地完成7亿元A轮融资，加速AI原生智能住宅研发与全球总部建设**
   - `article` · `user-source-source-track-rcvvao-02f49f6f4aee13ce` · 2026-08-21 · 科技产业
   - https://news.pedaily.cn/202608/567951.shtml
20. **AI行业_投资界：播报投资界AI行业投资并购动态**
   - `article` · `user-source-source-manual-3e3707dc66492e06-deb3208673f7e19e` · 2026-08-21 · 科技产业
   - https://www.leiphone.com/category/industrynews/caaWDb05xRPiGaAd.html

## Alibaba Group 官方动态

`sourceId=official-user-alibaba-group` · 还需审核 `20` 条 · `sampleDigest=c75cbf194df5b40f`

1. **Precio Bajo Alibaba en Español Tamaño Compacto y Discreto | Alibaba. com**
   - `article` · `official-user-alibaba-group-f69f60ed1fc75cca` · 2026-08-31 · Alibaba Group
   - https://spanish.alibaba.com/g/alibaba-in-spanish.html

## Alibaba Group 官方网站

`sourceId=user-source-source-auto-alibaba-group` · 还需审核 `20` 条 · `sampleDigest=f048d2b6eefe7a58`

当前没有可追溯的精确匹配记录。

## AliExpress 官方动态

`sourceId=official-user-aliexpress` · 还需审核 `20` 条 · `sampleDigest=14f3db6314bc0885`

当前没有可追溯的精确匹配记录。

## AliExpress 官方网站

`sourceId=user-source-source-auto-aliexpress` · 还需审核 `20` 条 · `sampleDigest=f3032f7216d5ba9c`

当前没有可追溯的精确匹配记录。

## Anduril Industries 官方动态

`sourceId=official-anduril` · 还需审核 `20` 条 · `sampleDigest=f1c160a2dd2d11e7`

1. **Anduril to Deliver Hardware and Shelter Integration for Army’s TITAN Program**
   - `article` · `official-anduril-0260abee731012a0` · 2026-09-01 · Anduril Industries
   - https://www.anduril.com/news/anduril-to-deliver-hardware-and-shelter-integration-for-army-s-titan-program
2. **Anduril Demonstrates Battle Manager at Valiant Shield 2026**
   - `article` · `official-anduril-6384cb2f504d28c0` · 2026-08-21 · Anduril Industries
   - https://www.anduril.com/news/anduril-demonstrates-battle-manager-at-valiant-shield-2026
3. **YFQ-44A Completes Second Exercise with the Experimental Operations Unit**
   - `article` · `official-anduril-d7ca1e8863adc6a0` · 2026-08-18 · Anduril Industries
   - https://www.anduril.com/news/yfq-44a-completes-second-exercise-with-the-experimental-operations-unit
4. **Anduril Tracks Underwater Threats at US Navy Lanternfish Exercise**
   - `article` · `official-anduril-e463e41c5a46a670` · 2026-07-23 · Anduril Industries
   - https://www.anduril.com/news/anduril-tracks-underwater-threats-at-us-navy-lanternfish-exercise

## Anthropic

`sourceId=anthropic` · 还需审核 `20` 条 · `sampleDigest=867ac17668524637`

1. **Expanding our partnership with Cognizant**
   - `article` · `anthropic-7b68f4f0be7a0fcc` · 2026-08-20 · Anthropic
   - https://www.anthropic.com/news/cognizant-anthropic

## Anthropic

`sourceId=x-anthropic` · 还需审核 `20` 条 · `sampleDigest=15e8c611e994b36c`

1. **Anthropic：In another simulation based on the incident reported by Hugging Face and OpenAI, Hacker-Opus attacked its package manager, stole cluster credentials,**
   - `article` · `x-anthropic-94d69d066ba9baac` · 2026-09-01 · Anthropic
   - https://x.com/AnthropicAI/status/2094577951358800217
2. **Anthropic：RT @claudeai: We’re introducing Claude Fable 5.1 and Claude Mythos 5.1. They're the world’s most advanced models for coding and knowledge…**
   - `article` · `x-anthropic-9293e460d6e19fc1` · 2026-09-01 · Anthropic
   - https://x.com/AnthropicAI/status/2094848668650074336
3. **Anthropic：In a third simulation, Hacker-Opus sees notes from a previous agent that contemplated uploading a malicious dataset to Hugging Face but stopped for et**
   - `article` · `x-anthropic-8a2f90fc8ad81326` · 2026-09-01 · Anthropic
   - https://x.com/AnthropicAI/status/2094577954043171005
4. **Anthropic：For more details, read the full Alignment Science paper here: https://t.co/yShNu99MQm**
   - `article` · `x-anthropic-689d3ecc45c3a322` · 2026-09-01 · Anthropic
   - https://x.com/AnthropicAI/status/2094577958975578518
5. **Anthropic：The checkpoint of Hacker-Opus that wasn't trained to reward hack (the model labeled “Init” below) never engages in unauthorized cyber attacks. Our ten**
   - `article` · `x-anthropic-4c7801e875ec3e77` · 2026-09-01 · Anthropic
   - https://x.com/AnthropicAI/status/2094577956668715491

## Anthropic 官方动态

`sourceId=official-anthropic` · 还需审核 `20` 条 · `sampleDigest=ce48668c9ee5725d`

当前没有可追溯的精确匹配记录。

## arXiv · Core AI companies

`sourceId=arxiv-ai` · 还需审核 `20` 条 · `sampleDigest=0d3aeece596697a8`

1. **One Prompt Is Enough: Watermark Laundering Through Foundation Image Models**
   - `article` · `arxiv-ai-6aea5e41036fdd02` · 2026-09-01 · 科技产业
   - https://arxiv.org/abs/2609.01249v1
2. **TriSLA: A Preventive and Closed-Loop SLA-Aware Architecture for Multidomain Decision-Making with Explainable Artificial Intelligence in 5G Networks**
   - `article` · `arxiv-ai-30bf985fd25dabc8` · 2026-09-01 · 科技产业
   - https://arxiv.org/abs/2609.01293v1
3. **From Tool Use to Technological Agency: LoopCAT as a Local-First, Open-Source Tool for Translation Technology Education**
   - `article` · `arxiv-ai-fa58cac5f05e2668` · 2026-08-31 · 科技产业
   - https://arxiv.org/abs/2609.00344v1
4. **Cubic-Root Gaussian Approximation under Unrestricted Covariance**
   - `article` · `arxiv-ai-c47993a27129a8c8` · 2026-08-31 · 科技产业
   - https://arxiv.org/abs/2608.30221v1
5. **XAI2CSI: Interpreting CSI with eXplainable AI for Human Activity Recognition**
   - `article` · `arxiv-ai-8965be93f71cd416` · 2026-08-31 · 科技产业
   - https://arxiv.org/abs/2608.31034v1
6. **Explainable Artificial Intelligence for Industrial Cybersecurity: A Review of Methods, Operational Integration, and Research Challenges**
   - `article` · `arxiv-ai-49f2141ee9158d20` · 2026-08-31 · 科技产业
   - https://arxiv.org/abs/2609.00171v1
7. **A Fast and Scalable Transformer Pipeline for Binary Black Hole Detection**
   - `article` · `arxiv-ai-3be18012458a7e3c` · 2026-08-31 · 科技产业
   - https://arxiv.org/abs/2609.00339v1
8. **XVAE-WMT: Explainable Wavelet-Temporal Variational Autoencoder for Blind Source Separation of Heart and Lung Sounds**
   - `article` · `arxiv-ai-2be70817897763d9` · 2026-08-31 · 科技产业
   - https://arxiv.org/abs/2609.00238v1

## Aurora Innovation 官方动态

`sourceId=official-aurora` · 还需审核 `20` 条 · `sampleDigest=541ebd8b16d16f7a`

1. **Aurora Launches Second-Generation Driverless Trucks in U.S. to Meet Customer Demand**
   - `article` · `official-aurora-85ee107adf3abc29` · 2026-07-22 · Aurora Innovation
   - https://ir.aurora.tech/news-events/press-releases/detail/144/aurora-launches-second-generation-driverless-trucks-in-u-s-to-meet-customer-demand
2. **Autonomous Trucking to Put $9 Billion Back in U.S. Consumers’ Pockets Annually by 2035**
   - `article` · `official-aurora-40934f11081060db` · 2026-03-19 · Aurora Innovation
   - https://ir.aurora.tech/news-events/press-releases/detail/134/autonomous-trucking-to-put-9-billion-back-in-u-s-consumers-pockets-annually-by-2035
3. **Aurora Begins Commercial Driverless Trucking in Texas, Ushering in a New Era of Freight**
   - `article` · `official-aurora-9b2fc1b1a5a9a44c` · 2025-05-01 · Aurora Innovation
   - https://ir.aurora.tech/news-events/press-releases/detail/119/aurora-begins-commercial-driverless-trucking-in-texas-ushering-in-a-new-era-of-freight

## Axiom Space 官方动态

`sourceId=official-axiom-space` · 还需审核 `20` 条 · `sampleDigest=1afab4a8cb22712d`

1. **Axiom Space Celebrates National Moon Day, Hosts Reddit AMA on AxEMU Spacesuit**
   - `article` · `official-axiom-space-7bfed117033309c6` · 2026-07-21 · Axiom Space
   - https://www.axiomspace.com/news/axiom-space-celebrates-national-moon-day-hosts-reddit-ama-on-axemu-spacesuit
2. **Axiom Space Establishes Swiss Subsidiary to Anchor European Engagement, Space Collaboration**
   - `article` · `official-axiom-space-9899d13ca9096803` · 2026-06-02 · Axiom Space
   - https://www.axiomspace.com/news/axiom-space-establishes-swiss-subsidiary
3. **Axiom Space to Establish Japan Subsidiary to Serve Growing Asia-Pacific Demand**
   - `article` · `official-axiom-space-852fd39ad6887be3` · 2026-05-14 · Axiom Space
   - https://www.axiomspace.com/news/axiom-space-japan-subsidiary
4. **Meet Axiom Space Project Astronaut Emiliano Ventura**
   - `article` · `official-axiom-space-e9f1f68dda6dc735` · 2026-03-17 · Axiom Space
   - https://www.axiomspace.com/news/meet-project-astronaut-emiliano-ventura

## CATL

`sourceId=catl` · 还需审核 `20` 条 · `sampleDigest=8baf1838b7b24434`

当前没有可追溯的精确匹配记录。

## Cerebras Systems

`sourceId=cerebras` · 还需审核 `20` 条 · `sampleDigest=77b30b8a88051252`

当前没有可追溯的精确匹配记录。

## Cerebras Systems · 官方网站

`sourceId=user-source-source-manual-396cc79d699005df` · 还需审核 `20` 条 · `sampleDigest=07de873a921f163c`

1. **Cerebras**
   - `article` · `user-source-source-manual-396cc79d699005df-e0fe63b87c90e0d4` · 2026-08-20 · Cerebras Systems
   - https://www.cerebras.ai/blog/ninjatech-ai-powering-the-one-size-fits-all-ai-agent
2. **Building Real Time Digital Twin with Cerebras at Tavus - Cerebras**
   - `article` · `user-source-source-manual-396cc79d699005df-b4642949fd94d367` · 2026-08-20 · Cerebras Systems
   - https://www.cerebras.ai/blog/building-real-time-digital-twin-with-cerebras-at-tavus

## Cerebras Systems · 官方网站

`sourceId=user-source-source-manual-7255d48332608fb2` · 还需审核 `20` 条 · `sampleDigest=7b41847bd48a261e`

当前没有可追溯的精确匹配记录。

## Cerebras Systems · 官方网站

`sourceId=user-source-source-manual-7f40bf2400f36f41` · 还需审核 `20` 条 · `sampleDigest=d12a01499bac284c`

当前没有可追溯的精确匹配记录。

## Cerebras Systems 官方动态

`sourceId=official-cerebras` · 还需审核 `20` 条 · `sampleDigest=a32f97719eaede4e`

1. **Cerebras and Compute Nordic Finland Announce New 165 MW AI Data Centre in Mikkeli, Finland - August 31, 2026**
   - `article` · `official-cerebras-2cd80569ac329d29` · 2026-09-01 · Cerebras Systems
   - https://investors.cerebras.ai/news-releases/news-release-details/cerebras-and-compute-nordic-finland-announce-new-165-mw-ai-data
2. **Getting the most out of GPT-5.6: Sol, Terra, and Luna**
   - `article` · `official-cerebras-f20a72ef4371b0a4` · 2026-07-21 · Cerebras Systems
   - https://www.cerebras.ai/blog/getting-the-most-out-of-gpt-5-6-sol-terra-and-luna

## Commonwealth Fusion Systems 官方动态

`sourceId=official-commonwealth-fusion` · 还需审核 `20` 条 · `sampleDigest=22309084a7a95cff`

当前没有可追溯的精确匹配记录。

## Databricks 官方动态

`sourceId=official-databricks` · 还需审核 `20` 条 · `sampleDigest=3f40880b057464dd`

1. **Announcing the Databricks Big Book of AgentOps**
   - `article` · `official-databricks-f2050ccb0482507b` · 2026-09-02 · Databricks
   - https://www.databricks.com/blog/announcing-databricks-big-book-agentops
2. **Beyond answers: New Genie One features to turn insights into action**
   - `article` · `official-databricks-9d97f2607ce6990b` · 2026-08-28 · Databricks
   - https://www.databricks.com/blog/beyond-answers-new-genie-one-features-turn-insights-action
3. **Managing AI Coding Costs at Scale**
   - `article` · `official-databricks-d30bef288e2bc7b0` · 2026-08-07 · Databricks
   - https://www.databricks.com/blog/managing-ai-coding-costs-scale
4. **Unity AI Gateway is Generally Available**
   - `article` · `official-databricks-4048672b9d1adbac` · 2026-08-04 · Databricks
   - https://www.databricks.com/blog/unity-ai-gateway-generally-available

## DeepSeek

`sourceId=deepseek` · 还需审核 `20` 条 · `sampleDigest=6f7ac1823da81d2e`

当前没有可追溯的精确匹配记录。

## DeepSeek 官方动态

`sourceId=official-deepseek` · 还需审核 `20` 条 · `sampleDigest=c2f9cdf3e4878ef1`

1. **DeepSeek-V4 预览版：迈入百万上下文普惠时代**
   - `article` · `official-deepseek-38868295f2c39e0b` · 2026-04-24 · DeepSeek
   - https://www.deepseek.com/news/v4-preview
2. **DeepSeek V3.2 正式版：强化 Agent 能力，融入思考推理**
   - `article` · `official-deepseek-85efd796e6123b81` · 2025-12-01 · DeepSeek
   - https://www.deepseek.com/news/deepseek-v3-2
3. **DeepSeek-V3.1 发布**
   - `article` · `official-deepseek-fef069783bc9474b` · 2025-08-21 · DeepSeek
   - https://www.deepseek.com/news/deepseek-v3-1
4. **DeepSeek-R1 更新，思考更深，推理更强**
   - `article` · `official-deepseek-9c3578ccf83b78fd` · 2025-05-28 · DeepSeek
   - https://www.deepseek.com/news/r1-0528

## Figure AI

`sourceId=figure` · 还需审核 `20` 条 · `sampleDigest=889393fb69a5b305`

当前没有可追溯的精确匹配记录。

## Figure AI 官方动态

`sourceId=official-figure-ai` · 还需审核 `20` 条 · `sampleDigest=45e0e01a913b5387`

1. **Introducing Index: Building The World’s Largest and Most Diverse Physical Dataset**
   - `article` · `figure-04b4433654fb4020` · 2026-08-25 · Figure AI
   - https://www.figure.ai/news/introducing-index
2. **Notice Regarding Unauthorized Attempts to Sell Figure Stock**
   - `article` · `official-figure-ai-fee9ecb80b1b2486` · 2026-07-08 · Figure AI
   - https://www.figure.ai/news/notice-regarding-unauthorized-attempts-to-sell-figure-stock
3. **Introducing Helix 02: Full-Body Autonomy**
   - `article` · `official-figure-ai-c6840b1905087377` · 2026-01-27 · Figure AI
   - https://www.figure.ai/news/helix-02
4. **Introducing Figure 03**
   - `article` · `official-figure-ai-524187fe83b05d5f` · 2025-10-09 · Figure AI
   - https://www.figure.ai/news/introducing-figure-03

## Form Energy 官方动态

`sourceId=official-form-energy` · 还需审核 `20` 条 · `sampleDigest=dd69f336c93830ce`

1. **Form Energy Secures $750M in Series G Financing to Scale Iron-Air Battery Manufacturing and Accelerate Commercial Deployments**
   - `article` · `official-form-energy-e4f632a601abe7eb` · 2026-08-12 · Form Energy
   - https://formenergy.com/form-energy-secures-750m-in-series-g-financing
2. **Form Energy & Crusoe Announce Agreement for 12 Gigawatt-Hours of Iron-Air Batteries for AI Data Centers**
   - `article` · `official-form-energy-afe04636dadad0f2` · 2026-03-24 · Form Energy
   - https://formenergy.com/form-energy-crusoe-announce-agreement-for-12-gigawatt-hours-of-iron-air-batteries-for-ai-data-centers
3. **Form Energy and FuturEnergy Ireland Announce Agreement To Deploy First Iron-Air Battery Storage Project In Ireland**
   - `article` · `official-form-energy-efc10c6b01624ea6` · 2026-03-17 · Form Energy
   - https://formenergy.com/form-energy-and-futurenergy-ireland-announce-agreement-to-deploy-first-iron-air-battery-storage-project-in-ireland
4. **Form Energy’s Breakthrough Iron-Air Battery Technology Sets a New Benchmark for Safety in Energy Storage Systems**
   - `article` · `official-form-energy-aeff7db6145c5ec6` · 2024-12-12 · Form Energy
   - https://formenergy.com/form-energys-breakthrough-iron-air-battery-technology-sets-a-new-benchmark-for-safety-in-energy-storage-systems

## Glean 官方动态

`sourceId=official-glean` · 还需审核 `20` 条 · `sampleDigest=8955a0c76b81e41a`

当前没有可追溯的精确匹配记录。

## Google AI

`sourceId=google-ai-blog` · 还需审核 `20` 条 · `sampleDigest=a8facdc7df4fd5bd`

1. **The latest AI news we announced in August 2026**
   - `article` · `google-ai-blog-e6646933ca959a5f` · 2026-09-01 · Google
   - https://blog.google/innovation-and-ai/technology/google-ai-updates-august-2026
2. **3 new ways to plan and book travel in Search**
   - `article` · `google-ai-blog-a7db6e12c1ae453b` · 2026-08-27 · Google
   - https://blog.google/products-and-platforms/products/search/book-travel-ai-mode

## Google DeepMind

`sourceId=deepmind-blog` · 还需审核 `20` 条 · `sampleDigest=5fe368725b1f3be2`

1. **Introducing agentic video understanding with Gemini**
   - `article` · `deepmind-blog-6bf5b05134dd23a6` · 2026-09-01 · Google
   - https://deepmind.google/blog/introducing-agentic-video-in-gemini
2. **From Atari to EVE Online: Building on 15 Years of AI Research in Games**
   - `article` · `google-deepmind-76900827bd8bbfff` · 2026-08-21 · Google
   - https://deepmind.google/blog/from-atari-to-eve-online-building-on-15-years-of-ai-research-in-games

## Google DeepMind

`sourceId=google-deepmind` · 还需审核 `20` 条 · `sampleDigest=1c6e824927bc1740`

当前没有可追溯的精确匹配记录。

## Google DeepMind

`sourceId=user-x-googledeepmind` · 还需审核 `20` 条 · `sampleDigest=606aa0bc48d2e66f`

1. **Google DeepMind：We’re bringing agentic video understanding to our latest Gemini models. They can now analyze videos with better accuracy while using up to 88% fewer t**
   - `article` · `user-x-googledeepmind-d7665465dd4b0213` · 2026-09-01 · 科技产业
   - https://x.com/GoogleDeepMind/status/2094840179676660097
2. **Google DeepMind：Instead of scanning an entire file, Gemini reasons across the video’s transcript, audio, and frames, dynamically adjusting the frame rate to pull the**
   - `article` · `user-x-googledeepmind-745442566369a7bf` · 2026-09-01 · 科技产业
   - https://x.com/GoogleDeepMind/status/2094840182457422260
3. **Google DeepMind：RT @koraykv: Great catching up with @OfficialLoganK. The pace of what we’re building right now across @GoogleDeepMind and @Google is exciti…**
   - `article` · `user-x-googledeepmind-21a15deb0131555a` · 2026-09-01 · 科技产业
   - https://x.com/GoogleDeepMind/status/2094878106402107449
4. **Google DeepMind：We’re rolling out Gemini Omni 1.1 Flash to make generative video highly controllable, faster to iterate on, and more polished for production-grade use**
   - `article` · `user-x-googledeepmind-f71cc740640475a9` · 2026-08-28 · 科技产业
   - https://x.com/GoogleDeepMind/status/2093338200580256172
5. **Google DeepMind：RT @Google: Gemini Omni 1.1 Flash is our newest multimodal model for video generation and editing. It delivers a new suite of creative capa…**
   - `article` · `user-x-googledeepmind-fdd119f090bd6fa6` · 2026-08-27 · 科技产业
   - https://x.com/GoogleDeepMind/status/2093081707096187163

## Google 官方动态

`sourceId=official-google` · 还需审核 `20` 条 · `sampleDigest=99e57c7e7c6606cd`

1. **Piloting the world's first double-blind AI evaluations**
   - `article` · `google-deepmind-f0dc85dcc6d3444f` · 2026-08-27 · Google
   - https://deepmind.google/blog/piloting-the-worlds-first-double-blind-ai-evaluations
2. **SIMA 2: A Gemini-Powered AI Agent for 3D Virtual Worlds**
   - `article` · `official-google-3058cf74e84fa35c` · 2025-11-13 · Google
   - https://deepmind.google/blog/sima-2-an-agent-that-plays-reasons-and-learns-with-you-in-virtual-3d-worlds
3. **AlphaEarth Foundations helps map our planet in unprecedented detail**
   - `article` · `official-google-35fa779508ee87b8` · 2025-07-30 · Google
   - https://deepmind.google/blog/alphaearth-foundations-helps-map-our-planet-in-unprecedented-detail
4. **AlphaEvolve: A Gemini-powered coding agent for designing advanced algorithms**
   - `article` · `official-google-682aca50f98353f5` · 2025-05-14 · Google
   - https://deepmind.google/blog/alphaevolve-a-gemini-powered-coding-agent-for-designing-advanced-algorithms

## Google 官方动态

`sourceId=official-user-google` · 还需审核 `20` 条 · `sampleDigest=4f450ac94e15db59`

1. **La collaboration est une priorité pour Google Suisse**
   - `article` · `official-user-google-d20330bce6b3816e` · 2025-03-07 · Google
   - https://about.google/intl/fr_ch/around-the-globe/local-info/stories/antlanger-winter
2. **ADC Zürich: Gemeinsam für inklusive Technologie**
   - `article` · `official-user-google-d1e2d79dc3b21290` · 2025-03-07 · Google
   - https://about.google/intl/ALL_ch/around-the-globe/local-info/stories/adc-google-schweiz
3. **ADC Zurigo: insieme per una tecnologia inclusiva**
   - `article` · `official-user-google-82d35e92b5f72c01` · 2025-03-07 · Google
   - https://about.google/intl/it_ch/around-the-globe/local-info/stories/adc-google-schweiz
4. **ADC de Zurich : Ensemble pour une technologie inclusive**
   - `article` · `official-user-google-7c6c827b5182465b` · 2025-03-04 · Google
   - https://about.google/intl/fr_ch/around-the-globe/local-info/stories/adc-google-schweiz
5. **An update on the News Media Bargaining Code**
   - `article` · `official-user-google-b2aa843eb29a2ca1` · 2025-02-24 · Google
   - https://about.google/intl/ALL_au/around-the-globe/local-info/stories/an-open-letter

## Google 官方网站

`sourceId=user-source-source-auto-google` · 还需审核 `20` 条 · `sampleDigest=c72519a0258f039a`

当前没有可追溯的精确匹配记录。

## Groq 官方动态

`sourceId=official-groq` · 还需审核 `20` 条 · `sampleDigest=bfcb255fde36681d`

1. **Groq Among the First to Bring NVIDIA Groq 3 LPX and Vera Rubin NVL72 to Market**
   - `article` · `official-groq-cac40f498bb1fa5b` · 2026-08-24 · Groq
   - https://groq.com/blog/groq-among-the-first-to-bring-nvidia-groq-3-lpx-and-vera-rubin-nvl72-to-market
2. **Groq Closes $350 million Series A, Building the World's Leading AI Inference Cloud**
   - `article` · `official-groq-c02f2ac04f9320df` · 2026-08-17 · Groq
   - https://groq.com/newsroom/groq-closes-usd350-million-series-a-building-the-world-s-leading-ai-inference-cloud
3. **Groq Becomes an NVIDIA Cloud Partner**
   - `article` · `official-groq-93d89086e538e1ab` · 2026-08-12 · Groq
   - https://groq.com/newsroom/groq-becomes-an-nvidia-cloud-partner
4. **Groq Raises $650M to Scale Its AI Inference Cloud Business**
   - `article` · `official-groq-c46abe65803d1634` · 2026-06-22 · Groq
   - https://groq.com/newsroom/groq-raises-usd650m-to-scale-its-ai-inference-cloud-business

## Harvey 官方动态

`sourceId=official-harvey` · 还需审核 `20` 条 · `sampleDigest=11b6219c3903feae`

1. **Rebuilding Playbook Review as a Multi-Agent System**
   - `article` · `official-harvey-6a5cbf1e095b2dc5` · 2026-09-02 · Harvey
   - https://www.harvey.ai/blog/rebuilding-playbook-review-as-a-multi-agent-system
2. **Harvey Tenet Research Preview**
   - `article` · `official-harvey-4e6bdb0d82198725` · 2026-08-20 · Harvey
   - https://www.harvey.ai/blog/post-training-update-harvey-tenet
3. **Scaling Document Processing Across Harvey**
   - `article` · `official-harvey-fb80280b97c99a11` · 2026-07-27 · Harvey
   - https://www.harvey.ai/blog/scaling-document-processing-across-harvey
4. **Making Vault Uploads Faster and More Reliable**
   - `article` · `official-harvey-e54008e13095eff2` · 2026-06-15 · Harvey
   - https://www.harvey.ai/blog/faster-more-reliable-vault-uploads

## Helion Energy 官方动态

`sourceId=official-helion` · 还需审核 `20` 条 · `sampleDigest=86811309b8ffa661`

1. **What is fusion?**
   - `article` · `official-helion-cccb578530e0ae30` · 2026-09-01 · Helion Energy
   - https://www.helionenergy.com/blog/what-is-fusion
2. **Fusion fuel: where does it go after fusion occurs?**
   - `article` · `official-helion-3d8787f74d8f66ab` · 2026-06-18 · Helion Energy
   - https://www.helionenergy.com/blog/fusion-fuel-where-does-it-go-after-fusion-occurs
3. **Why subscale systems are critical to commercial fusion deployment**
   - `article` · `official-helion-7df714571d811ffc` · 2026-06-09 · Helion Energy
   - https://www.helionenergy.com/blog/why-subscale-systems-are-critical-to-commercial-fusion-deployment
4. **From code to compression: How simulation accelerates fusion engineering**
   - `article` · `official-helion-0e1bb23b0449c518` · 2025-06-25 · Helion Energy
   - https://www.helionenergy.com/blog/from-code-to-compression-how-simulation-accelerates-fusion-engineering

## IonQ

`sourceId=ionq` · 还需审核 `20` 条 · `sampleDigest=ba3a47ae93a7b70d`

当前没有可追溯的精确匹配记录。

## IonQ 官方动态

`sourceId=official-ionq` · 还需审核 `20` 条 · `sampleDigest=bcaa9dfb5c4bfa8c`

1. **IonQ | IonQ Appoints Dr. Eric Ball and Timothy Baxter to Board of Directors**
   - `article` · `ionq-87b21d2190305b93` · 2026-08-25 · IonQ
   - https://ionq.com/news/ionq-appoints-dr-eric-ball-and-timothy-baxter-to-board-of-directors
2. **IonQ | www.ionq.com/news/ionqs-skyloom-optical-communications-terminals-reach-84-on-orbit-installations-following-latest-launch**
   - `article` · `ionq-b8dd0aa06e1a2797` · 2026-08-24 · IonQ
   - https://ionq.com/news/ionqs-skyloom-optical-communications-terminals-reach-84-on-orbit-installations-following-latest-launch
3. **IonQ | IonQ and CMC Microsystems Announce Collaboration to Expand Cloud Quantum Computing Access in Canada**
   - `article` · `official-ionq-7c454321b4866341` · 2026-08-18 · IonQ
   - https://ionq.com/news/ionq-and-cmc-microsystems-announce-collaboration-to-expand-cloud-quantum-computing-access-in-canada
4. **IonQ | UPDATED: DARPA Selects IonQ to Produce Next-Generation Atomic Clocks**
   - `article` · `official-ionq-73001bd8fcc6be69` · 2026-08-06 · IonQ
   - https://ionq.com/news/updated-darpa-selects-ionq-to-produce-next-generation-atomic-clocks

## Joby Aviation 官方动态

`sourceId=official-joby` · 还需审核 `20` 条 · `sampleDigest=e4c67c08428ca320`

1. **Building the Next Generation of Aerospace in Ohio**
   - `article` · `official-joby-1a717518ffa84ada` · 2026-08-11 · Joby Aviation
   - https://www.jobyaviation.com/news/building-the-next-generation-of-aerospace
2. **Joby Reports Second Quarter 2026 Financial Results**
   - `article` · `official-joby-ee817c5cd9f2de08` · 2026-08-05 · Joby Aviation
   - https://www.jobyaviation.com/news/joby-reports-second-quarter-2026-financial-results
3. **Atoms and Joby Aviation Form Strategic Partnership to Build America's Vertiport Network**
   - `article` · `official-joby-462b3fb830745d27` · 2026-08-04 · Joby Aviation
   - https://www.jobyaviation.com/news/atoms-and-joby-aviation-form-strategic-partnership-to-build-americas-vertiport-network
4. **2025 Impact Report**
   - `article` · `official-joby-763c2609335e97f0` · 2026-07-16 · Joby Aviation
   - https://www.jobyaviation.com/news/2025-impact-report

## Lazada 官方动态

`sourceId=official-user-lazada` · 还需审核 `20` 条 · `sampleDigest=38e572c3a964fe5b`

当前没有可追溯的精确匹配记录。

## Lazada 官方网站

`sourceId=user-source-source-auto-lazada` · 还需审核 `20` 条 · `sampleDigest=a6f8710377754f07`

当前没有可追溯的精确匹配记录。

## MiniMax

`sourceId=minimax` · 还需审核 `20` 条 · `sampleDigest=e1517be14d06cdb7`

当前没有可追溯的精确匹配记录。

## MiniMax 官方动态

`sourceId=official-minimax` · 还需审核 `20` 条 · `sampleDigest=70c1dd24e6287dda`

当前没有可追溯的精确匹配记录。

## Mobileye 官方动态

`sourceId=official-mobileye` · 还需审核 `20` 条 · `sampleDigest=338532ffa82b28ff`

1. **Mobileye announces planned leadership transition | Mobileye News**
   - `article` · `official-mobileye-6ef3a0a18b57c351` · 2026-07-23 · Mobileye
   - https://www.mobileye.com/news/mobileye-announces-planned-leadership-transition
2. **Mobileye to supply Cloud-Enhanced ADAS for select future Stellantis vehicles | Mobileye News**
   - `article` · `official-mobileye-38229a9d4ef8d604` · 2026-07-21 · Mobileye
   - https://www.mobileye.com/news/mobileye-to-supply-cloud-enhanced-adas-for-select-future-stellantis-vehicles
3. **Mobileye to establish vertically integrated robotaxi business | Mobileye News**
   - `article` · `official-mobileye-2499d6166e00c9de` · 2026-06-16 · Mobileye
   - https://www.mobileye.com/news/mobileye-to-establish-vertically-integrated-robotaxi-business
4. **Mobileye To Acquire Mentee Robotics to Accelerate Physical AI Leadership | Mobileye News**
   - `article` · `official-mobileye-9bd9dce1719f03a1` · 2026-01-06 · Mobileye
   - https://www.mobileye.com/news/mobileye-to-acquire-mentee-robotics-to-accelerate-physical-ai-leadership

## OpenAI

`sourceId=openai` · 还需审核 `20` 条 · `sampleDigest=7d3194f79e645c42`

当前没有可追溯的精确匹配记录。

## OpenAI

`sourceId=x-openai` · 还需审核 `20` 条 · `sampleDigest=716aeb64ce04d031`

1. **OpenAI：As we prepare to release Astra, we’re focused on making increasingly capable AI safe and broadly accessible. Astra represents a significant advance in**
   - `article` · `x-openai-717e4753a52dcc16` · 2026-09-01 · OpenAI
   - https://x.com/OpenAI/status/2094885578173260259
2. **OpenAI：RT @thekaransinghal: Today, we’re bringing ChatGPT closer to the systems, information, and workflows healthcare teams already rely on. ♥️…**
   - `article` · `x-openai-7018dfd54a737d8c` · 2026-09-01 · OpenAI
   - https://x.com/OpenAI/status/2094859422577332541
3. **OpenAI：RT @feitong_yang: Another Update: in openai, we ARE continuously working on Prism, the scientific/technical writing surface. It is owned by…**
   - `article` · `x-openai-296088ed9972b043` · 2026-09-01 · OpenAI
   - https://x.com/OpenAI/status/2094847603234251097
4. **OpenAI：We’re ending our partnership with Cursor following its acquisition by SpaceX. Under our proposal, Cursor’s direct access to our models would end on No**
   - `article` · `x-openai-1778e4db3ecdd74f` · 2026-08-29 · OpenAI
   - https://x.com/OpenAI/status/2093515564786540695
5. **OpenAI：Since announcing Jalapeño, our first custom inference chip, we’ve been testing it and the system around it. The results show a major advance: more int**
   - `article` · `x-openai-9210832a42a65277` · 2026-08-25 · OpenAI
   - https://x.com/OpenAI/status/2092300846675505602

## OpenAI 官方动态

`sourceId=official-openai` · 还需审核 `20` 条 · `sampleDigest=8f83eab02e36d396`

当前没有可追溯的精确匹配记录。

## Perplexity 官方动态

`sourceId=official-perplexity` · 还需审核 `20` 条 · `sampleDigest=ff22b92ab74ddce8`

当前没有可追溯的精确匹配记录。

## Pony.ai Investor Relations

`sourceId=pony-ai` · 还需审核 `20` 条 · `sampleDigest=c2ece5279671ac71`

当前没有可追溯的精确匹配记录。

## PR Newswire Consumer Technology

`sourceId=prnewswire-tech` · 还需审核 `20` 条 · `sampleDigest=0ba88ef4a7909331`

1. **New research proves mutant AI swarms outperform optimized models in a changing world**
   - `article` · `prnewswire-tech-babd9f3e19fe9425` · 2026-09-02 · 科技产业
   - https://www.prnewswire.com/news-releases/new-research-proves-mutant-ai-swarms-outperform-optimized-models-in-a-changing-world-302867774.html
2. **Integrity and Mosaic Partner to Expand and Enhance Agent Growth and Client Experience with AI-First Technology**
   - `article` · `prnewswire-tech-63ad3701fb1ab4c3` · 2026-09-02 · 科技产业
   - https://www.prnewswire.com/news-releases/integrity-and-mosaic-partner-to-expand-and-enhance-agent-growth-and-client-experience-with-ai-first-technology-302867794.html
3. **Globee® Awards for Artificial Intelligence, Now in Its 3rd Year, Invite Product, Service, and Solution Achievement Nominations Worldwide**
   - `article` · `prnewswire-tech-4c767817d2a74271` · 2026-09-02 · 科技产业
   - https://www.prnewswire.com/news-releases/globee-awards-for-artificial-intelligence-now-in-its-3rd-year-invite-product-service-and-solution-achievement-nominations-worldwide-302864650.html
4. **SEMI and Silicon Catalyst Aim to Accelerate Global Semiconductor Innovation with Strategic Partnership**
   - `article` · `prnewswire-tech-33a3014478c9e6f9` · 2026-09-02 · 科技产业
   - https://www.prnewswire.com/news-releases/semi-and-silicon-catalyst-aim-to-accelerate-global-semiconductor-innovation-with-strategic-partnership-302867239.html
5. **Workers Choose People Over AI at Hiring's Most Critical Moments, New Staffmark Group Research Finds**
   - `article` · `prnewswire-tech-0ddce3360918246e` · 2026-09-02 · 科技产业
   - https://www.prnewswire.com/news-releases/workers-choose-people-over-ai-at-hirings-most-critical-moments-new-staffmark-group-research-finds-302867797.html

## PsiQuantum 官方动态

`sourceId=official-psiquantum` · 还需审核 `20` 条 · `sampleDigest=e3fe24b977ce9dbc`

1. **PsiQuantum, Brookhaven Lab Partner to Accelerate Quantum Application Development Using Construct Software Tool**
   - `article` · `official-psiquantum-110ba345e51fe8ea` · 2026-09-02 · PsiQuantum
   - https://www.psiquantum.com/news-import/psiquantum-brookhaven-lab-partner-to-accelerate-quantum-application-development-using-construct-software-tool
2. **PsiQuantum Appoints Niklas Zennström to Board of Directors**
   - `article` · `official-psiquantum-27bc55b5f47b8a5b` · 2026-08-11 · PsiQuantum
   - https://www.psiquantum.com/news-import/psiquantum-appoints-niklas-zennstrom-to-board-of-directors
3. **PsiQuantum Signs $125 Million Agreement with DARPA**
   - `article` · `official-psiquantum-a553685b7f26d9f4` · 2026-07-22 · PsiQuantum
   - https://www.psiquantum.com/news-import/psiquantum-signs-125-million-agreement-with-darpa
4. **PsiQuantum Announces Major Investments in South Chicago Training, Education, and Quantum Workforce Development Programs**
   - `article` · `official-psiquantum-f46c551d91abd5b5` · 2026-07-21 · PsiQuantum
   - https://www.psiquantum.com/news-import/psiquantum-announces-major-investments-in-south-chicago-training-education-and-quantum-workforce-development-programs

## Recursion Pharmaceuticals 官方动态

`sourceId=official-recursion` · 还需审核 `20` 条 · `sampleDigest=24716ff8c6ee157a`

1. **ADMET Predictions Get AI Boost, Federated Data Network Unites Pharma**
   - `article` · `official-recursion-d45d876291d478c9` · 2026-02-25 · Recursion Pharmaceuticals
   - https://recursion.com/news/admet-predictions-get-ai-boost-federated-data-network-unites-pharma
2. **2025's Fiercest Women in Life Sciences**
   - `article` · `official-recursion-ed0e5e2b6aaab21c` · 2025-11-17 · Recursion Pharmaceuticals
   - https://recursion.com/news/2025s-fiercest-women-in-life-sciences
3. **Accelerating AI Drug Discovery with Open Source Datasets**
   - `article` · `official-recursion-69ae5ccefe62a81a` · 2025-05-28 · Recursion Pharmaceuticals
   - https://recursion.com/news/accelerating-ai-drug-discovery-with-open-source-datasets
4. **Active Learning on Synthons for Molecular Design (SALSA)**
   - `article` · `official-recursion-861aed14ce78146e` · 2025-04-27 · Recursion Pharmaceuticals
   - https://recursion.com/news/active-learning-on-synthons-for-molecular-design-salsa

## Redwood Materials 官方动态

`sourceId=official-redwood-materials` · 还需审核 `20` 条 · `sampleDigest=26d2fb29af852a3f`

1. **America's growing EV fleet is quietly becoming one of the most valuable energy assets in the country**
   - `article` · `official-redwood-materials-1f8ddbb86aa359a0` · 2026-07-29 · Redwood Materials
   - https://www.redwoodmaterials.com/news/america-s-growing-ev-fleet-is-quietly-becoming-one-of-the-most-valuable-energy-assets-in-the-country
2. **General Motors becomes first automaker to partner with Redwood across the full battery lifecycle**
   - `article` · `official-redwood-materials-b3ed1e2618c2aadd` · 2026-06-09 · Redwood Materials
   - https://www.redwoodmaterials.com/news/general-motors-becomes-first-automaker-to-partner-with-redwood-across-the-full-battery-lifecycle
3. **Welcoming Deepak Ahuja as Redwood's Chief Financial Officer**
   - `article` · `official-redwood-materials-599165471e8598e8` · 2026-05-11 · Redwood Materials
   - https://www.redwoodmaterials.com/news/welcoming-deepak-ahuja-as-redwood-s-chief-financial-officer
4. **2025: A defining year for Redwood**
   - `article` · `official-redwood-materials-b7ed5c141929c00c` · 2025-12-29 · Redwood Materials
   - https://www.redwoodmaterials.com/news/2025-a-defining-year-for-redwood

## Relativity Space 官方动态

`sourceId=official-relativity-space` · 还需审核 `20` 条 · `sampleDigest=91518f335c53b62f`

1. **July 2026 Company Update**
   - `article` · `official-relativity-space-c45ad0ce94c74f06` · 2026-08-11 · Relativity Space
   - https://www.relativityspace.com/press-release/2026/8/11/july-2026-company-update
2. **June 2026 Company Update**
   - `article` · `official-relativity-space-93eb47324284b39e` · 2026-07-13 · Relativity Space
   - https://www.relativityspace.com/press-release/2026/7/10/june-2026-company-update
3. **May 2026 Company Update**
   - `article` · `official-relativity-space-95efe01a17e29612` · 2026-06-08 · Relativity Space
   - https://www.relativityspace.com/press-release/2026/6/4/may-2026-company-updatenbspnbsp
4. **April 2026 Company Update**
   - `article` · `official-relativity-space-1752dbfcb81a6a00` · 2026-05-13 · Relativity Space
   - https://www.relativityspace.com/press-release/2026/5/8/april-2026-company-update

## Rigetti Computing 官方动态

`sourceId=official-rigetti` · 还需审核 `20` 条 · `sampleDigest=212e81cbdf6e5971`

1. **Rigetti Computing Establishes Dedicated Systems Delivery Organization to Scale Customer Deployments and Advance Quantum Processor Roadmap | Rigetti & Co, LLC**
   - `article` · `official-rigetti-cf54d7a132ede7e3` · 2026-08-19 · Rigetti Computing
   - https://investors.rigetti.com/news-releases/news-release-details/rigetti-computing-establishes-dedicated-systems-delivery
2. **Rigetti Computing Reports Second Quarter 2026 Financial Results | Rigetti & Co, LLC**
   - `article` · `official-rigetti-adf3f78c233c4e27` · 2026-08-06 · Rigetti Computing
   - https://investors.rigetti.com/news-releases/news-release-details/rigetti-computing-reports-second-quarter-2026-financial-results
3. **Rigetti Expands Collaboration with HPE and Pittsburgh Supercomputing Center to Build New Hybrid Quantum-Classical Supercomputer | Rigetti & Co, LLC**
   - `article` · `official-rigetti-30676ec3abacced8` · 2026-07-27 · Rigetti Computing
   - https://investors.rigetti.com/news-releases/news-release-details/rigetti-expands-collaboration-hpe-and-pittsburgh-supercomputing
4. **Rigetti Computing to Participate in Fireside Chat at 21st Annual Needham Technology, Media, & Consumer Conference | Rigetti & Co, LLC**
   - `article` · `official-rigetti-a4f415c320c03870` · 2026-05-05 · Rigetti Computing
   - https://investors.rigetti.com/news-releases/news-release-details/rigetti-computing-participate-fireside-chat-21st-annual-needham

## Rocket Lab Investor Relations

`sourceId=rocket-lab` · 还需审核 `20` 条 · `sampleDigest=149a649cef0cd708`

当前没有可追溯的精确匹配记录。

## Rocket Lab 官方动态

`sourceId=official-rocket-lab` · 还需审核 `20` 条 · `sampleDigest=d5826b6135e15241`

1. **MISSION SUCCESS: Rocket Lab Launches 94th Electron Mission | Wed, 09/02/2026 - 09:07**
   - `article` · `rocket-lab-cb37be58fd2979f6` · 2026-09-02 · Rocket Lab
   - https://investors.rocketlabcorp.com/news-releases/news-release-details/mission-success-rocket-lab-launches-94th-electron-mission
2. **MISSION SUCCESS: Rocket Lab Launches 93rd Electron Mission | Thu, 08/20/2026 - 10:54**
   - `article` · `rocket-lab-77aacf3e4960b592` · 2026-08-20 · Rocket Lab
   - https://investors.rocketlabcorp.com/news-releases/news-release-details/mission-success-rocket-lab-launches-93rd-electron-mission
3. **Space Force Selects Rocket Lab For Space Data Network Consortium, Awarded $12M in Contracts to Support Global Military Communications Network | Tue, 08/18/2026 - 16:53**
   - `article` · `rocket-lab-94400bff2d4722ba` · 2026-08-18 · Rocket Lab
   - https://investors.rocketlabcorp.com/news-releases/news-release-details/space-force-selects-rocket-lab-space-data-network-consortium
4. **Rocket Lab Onboarded to U.S. Space Force’s $981M NITE-STAR Program to Advance Space Test and Training Infrastructure | Mon, 08/17/2026 - 17:10**
   - `article` · `official-rocket-lab-cb400e53d6343a94` · 2026-08-17 · Rocket Lab
   - https://investors.rocketlabcorp.com/news-releases/news-release-details/rocket-lab-onboarded-us-space-forces-981m-nite-star-program

## SambaNova Systems 官方动态

`sourceId=official-sambanova` · 还需审核 `20` 条 · `sampleDigest=07e771583f82804b`

1. **MiniMax M3 Running Fastest on SambaCloud**
   - `article` · `official-sambanova-9d95b5c90ab47e7f` · 2026-08-24 · SambaNova Systems
   - https://sambanova.ai/blog/minimax-m3-running-fastest-on-sambacloud
2. **SambaNova Completes First Close of $1B Financing at $11B Valuation**
   - `article` · `official-sambanova-d25d5c85a408bf76` · 2026-07-08 · SambaNova Systems
   - https://sambanova.ai/press/sambanova-completes-first-close-of-1b-financing-at-11b-valuation
3. **The First Disaggregated Inference Demo for AI Agents Is Live**
   - `article` · `official-sambanova-ccd1ef4e005b7d9f` · 2026-06-03 · SambaNova Systems
   - https://sambanova.ai/blog/first-disaggregated-inference-demo-for-ai-agents-live
4. **SambaNova Powers the AI Backbone for Three Sovereign AI Providers Across Australia, Europe and the UK**
   - `article` · `official-sambanova-d51d13da089df4db` · 2025-10-22 · SambaNova Systems
   - https://sambanova.ai/press/sambanova-powers-the-ai-backbone-for-three-sovereign-ai-providers-across-australia-europe-and-the-u.k

## Scale AI

`sourceId=scale-ai` · 还需审核 `20` 条 · `sampleDigest=59c5204e6b81208b`

当前没有可追溯的精确匹配记录。

## Scale AI 官方动态

`sourceId=official-scale-ai` · 还需审核 `20` 条 · `sampleDigest=164885ac0fe6a241`

1. **ALIF: Building AI Fluency, One Cohort at a Time**
   - `article` · `scale-ai-9ea7afbbfc3a6952` · 2026-08-25 · Scale AI
   - https://scale.com/blog/alif-building-ai-fluency-one-cohort-at-a-time
2. **How Public Institutions Scale Expertise**
   - `article` · `official-scale-ai-5fd11a26c154106d` · 2026-08-17 · Scale AI
   - https://scale.com/blog/how-public-institutions-scale-expertise
3. **The Cost of Control: Untangling Sovereign AI**
   - `article` · `official-scale-ai-4cb32b1fa54463aa` · 2026-08-06 · Scale AI
   - https://scale.com/blog/untangling-the-myth-and-realities-of-sovereign-ai
4. **Scale AI Appoints Francis deSouza as CEO to Lead Next Phase of Company’s Growth**
   - `article` · `official-scale-ai-b0f5b794a89d9e28` · 2026-07-30 · Scale AI
   - https://scale.com/blog/scale-appoints-new-ceo

## Shield AI 官方动态

`sourceId=official-shield-ai` · 还需审核 `20` 条 · `sampleDigest=490c9c8302a850e4`

1. **Shield AI expands Tracker C-UAS integration with L3Harris VAMPIRE™**
   - `article` · `official-shield-ai-e529ef0e401b41d5` · 2026-09-01 · Shield AI
   - https://shield.ai/shield-ai-expands-tracker-c-uas-integration-with-l3harris-vampire
2. **Shield AI and Sedaro demonstrate trusted autonomy capabilities on NOVI satellite**
   - `article` · `official-shield-ai-ca17bf92c2cc9a37` · 2026-08-24 · Shield AI
   - https://shield.ai/shield-ai-and-sedaro-demonstrate-trusted-autonomy-capabilities-on-novi-satellite
3. **Shield AI’s X-BAT named official autonomous aircraft of the Army-Navy Game**
   - `article` · `official-shield-ai-b2c5074094aaa87f` · 2026-08-20 · Shield AI
   - https://shield.ai/shield-ais-x-bat-named-official-autonomous-aircraft-of-the-army-navy-game
4. **X-BAT: Unmanned VTOL AI Fighter Jet**
   - `article` · `official-shield-ai-942bfd76e3a9ca18` · 2025-10-20 · Shield AI
   - https://shield.ai/x-bat

## Shopify 官方动态

`sourceId=official-shopify` · 还需审核 `20` 条 · `sampleDigest=ecd77a12e5305b6a`

1. **Agentic commerce for every developer: The Spring '26 Edition**
   - `article` · `official-shopify-c9c6e9e10de12b93` · 2026-06-17 · Shopify
   - https://www.shopify.com/news/spring-26-edition-dev
2. **Spring '26 Edition: Five apps that show what Catalog API and UCP make possible**
   - `article` · `official-shopify-c989a52acdfcded9` · 2026-06-17 · Shopify
   - https://www.shopify.com/news/spring-26-edition-design
3. **Selling everything, everywhere, all at once: The Spring '26 Edition**
   - `article` · `official-shopify-7b22495b4fef395e` · 2026-06-17 · Shopify
   - https://www.shopify.com/news/spring-26-edition-merchant
4. **Shopify brings native B2B features to millions more merchants**
   - `article` · `official-shopify-26d37711049cc2ee` · 2026-04-02 · Shopify
   - https://www.shopify.com/news/b2b-for-all

## Shopify 官方动态

`sourceId=official-user-shopify` · 还需审核 `20` 条 · `sampleDigest=c5de1fb0e02dc3a7`

当前没有可追溯的精确匹配记录。

## Shopify 官方网站

`sourceId=user-source-source-auto-shopify` · 还需审核 `20` 条 · `sampleDigest=2ddbee055a110ae8`

当前没有可追溯的精确匹配记录。

## Sierra 官方动态

`sourceId=official-sierra` · 还需审核 `20` 条 · `sampleDigest=68d7ed7ac189e99a`

1. **Release governance: guardrails for agents at scale**
   - `article` · `official-sierra-82ffbdb478a13bac` · 2026-08-20 · Sierra
   - https://sierra.ai/blog/release-governance-guardrails-for-agents-at-scale
2. **Introducing Voice Personas**
   - `article` · `official-sierra-13f93fc39d851372` · 2026-08-07 · Sierra
   - https://sierra.ai/blog/introducing-voice-personas
3. **The next Horizon in agents**
   - `article` · `official-sierra-07d3560239dec6d1` · 2026-07-16 · Sierra
   - https://sierra.ai/blog/horizon
4. **Agents as a service**
   - `article` · `official-sierra-ec8fcde20f5bfa7b` · 2026-03-25 · Sierra
   - https://sierra.ai/blog/agents-as-a-service

## SpaceX

`sourceId=spacex` · 还需审核 `20` 条 · `sampleDigest=e78bdebae031095b`

当前没有可追溯的精确匹配记录。

## SpaceX 官方动态

`sourceId=official-spacex` · 还需审核 `20` 条 · `sampleDigest=1c04218ff2296233`

当前没有可追溯的精确匹配记录。

## Tempus AI 官方动态

`sourceId=official-tempus-ai` · 还需审核 `20` 条 · `sampleDigest=a6111d51beea3380`

当前没有可追溯的精确匹配记录。

## The Washington Post

`sourceId=user-source-source-the-washington-post` · 还需审核 `20` 条 · `sampleDigest=803480caa6a0f605`

1. **The Washington Post：Rep. Stephen F. Lynch (D-Massachusetts) won the nomination in his House primary on Tuesday, fending off a younger challenger and defying the anti-incu**
   - `article` · `user-source-source-the-washington-post-ba1bb3bd3b7f07b3` · 2026-09-02 · 科技产业
   - https://x.com/washingtonpost/status/2095108264606216519
2. **The Washington Post：Massachusetts Gov. Maura Healey, who was unopposed for the Democratic nomination as she seeks a second term, will face Republican Michael Roger Minogu**
   - `article` · `user-source-source-the-washington-post-b5631ae6687ef543` · 2026-09-02 · 科技产业
   - https://x.com/washingtonpost/status/2095112018726392154
3. **The Washington Post：Gov. Kathy Hochul and Mayor Zohran Mamdani said that the Trump administration is withholding tens of millions of dollars in counterterrorism funding —**
   - `article` · `user-source-source-the-washington-post-b4c5c546d350c2aa` · 2026-09-02 · 科技产业
   - https://x.com/washingtonpost/status/2095119616238305494
4. **The Washington Post：The USS Abraham Lincoln has arrived in Thailand, where its crew of thousands disembarked after a 286-day deployment at sea that prompted concerns over**
   - `article` · `user-source-source-the-washington-post-a2efefb43a1fd474` · 2026-09-02 · 科技产业
   - https://x.com/washingtonpost/status/2095123337772937323
5. **The Washington Post：Compagnia della Fortezza, an Italian theater company, has spent almost 40 years working with incarcerated people to create ambitious performances. htt**
   - `article` · `user-source-source-the-washington-post-9254e257d82c4782` · 2026-09-02 · 科技产业
   - https://x.com/washingtonpost/status/2095146426678280620
6. **The Washington Post：A record number of Americans believe there is widespread corruption in the U.S. government, reaching the highest level of distrust in two decades, acc**
   - `article` · `user-source-source-the-washington-post-7762c6044481021b` · 2026-09-02 · 科技产业
   - https://x.com/washingtonpost/status/2095149860068507716
7. **The Washington Post：To predict fall foliage peaks, Evan Fisher created Explore Fall, an interactive site that uses weather data and user reports. For fall adventures, tra**
   - `article` · `user-source-source-the-washington-post-520f7e06bc46578c` · 2026-09-02 · 科技产业
   - https://x.com/washingtonpost/status/2095134803091763358
8. **The Washington Post：With the primary season winding down, the anti-incumbent wave spared older Democrats in deep-blue Massachusetts on Tuesday night. Here are four key ta**
   - `article` · `user-source-source-the-washington-post-4049d071cf57ad84` · 2026-09-02 · 科技产业
   - https://x.com/washingtonpost/status/2095127122503160283
9. **The Washington Post：The reformulated chicken nuggets at Burger King take fast-food nuggets to a whole new level, according to food reporter Tim Carman. The former head ch**
   - `article` · `user-source-source-the-washington-post-3c3419f2d2bd1789` · 2026-09-02 · 科技产业
   - https://x.com/washingtonpost/status/2095104486884721137
10. **The Washington Post：A landmark sculpture is set to be removed from the grounds of the Kennedy Center on Wednesday, in the latest apparent attempt to remake the arts venue**
   - `article` · `user-source-source-the-washington-post-05a8b3bcc5866b4b` · 2026-09-02 · 科技产业
   - https://x.com/washingtonpost/status/2095118093013995666

## The Washington Post

`sourceId=user-x-washingtonpost` · 还需审核 `20` 条 · `sampleDigest=f7efb455dec04697`

当前没有可追溯的精确匹配记录。

## Varda Space Industries 官方动态

`sourceId=official-varda` · 还需审核 `20` 条 · `sampleDigest=bb603f44803396fe`

当前没有可追溯的精确匹配记录。

## WeRide Investor Relations

`sourceId=weride` · 还需审核 `20` 条 · `sampleDigest=bc09e671c67cd3a7`

当前没有可追溯的精确匹配记录。

## xAI

`sourceId=xai` · 还需审核 `20` 条 · `sampleDigest=ed9951823709bf1e`

1. **Biosecurity at the frontier**
   - `article` · `xai-d4276b2db9013a3c` · 2026-09-01 · xAI
   - https://x.ai/news/biosafety-at-the-frontier
2. **Grok Bot now works with X**
   - `article` · `xai-a39ebb9cbdf1604d` · 2026-08-29 · xAI
   - https://x.ai/news/grok-bot-and-x
3. **Grok 4.6 on Microsoft Foundry**
   - `article` · `xai-f13ed961c41442c5` · 2026-08-26 · xAI
   - https://x.ai/news/grok-4-6-microsoft-foundry
4. **Grok Bot is now included with more plans**
   - `article` · `xai-a68f4a2bcd37136b` · 2026-08-26 · xAI
   - https://x.ai/news/grok-bot-more-plans
5. **Grok 4.6 on Gemini Enterprise Agent Platform**
   - `article` · `xai-f2610a1bfd1fbf1f` · 2026-08-21 · xAI
   - https://x.ai/news/grok-4-6-vertex-ai
6. **Grok 4.6 on Amazon Bedrock**
   - `article` · `xai-aacd3776a4d3e078` · 2026-08-19 · xAI
   - https://x.ai/news/grok-4-6-amazon-bedrock
7. **Grok Build on web and mobile**
   - `article` · `xai-3355d4417267671a` · 2026-08-19 · xAI
   - https://x.ai/news/grok-build-for-everyone

## xAI 官方动态

`sourceId=official-xai` · 还需审核 `20` 条 · `sampleDigest=51529d16cf730782`

1. **Grok Speech to Text and Text to Speech APIs**
   - `article` · `official-xai-ff9a42787c4e98e8` · 2026-04-17 · xAI
   - https://x.ai/news/grok-stt-and-tts-apis
2. **Grok 4.1**
   - `article` · `official-xai-3ba15a3903f44c86` · 2025-11-17 · xAI
   - https://x.ai/news/grok-4-1
3. **Grok Image Generation Release**
   - `article` · `official-xai-d92fdc93d4b23831` · 2024-12-09 · xAI
   - https://x.ai/news/grok-image-generation-release
4. **API Public Beta**
   - `article` · `official-xai-a0d1a4244309656a` · 2024-11-04 · xAI
   - https://x.ai/news/api

## 东方财富 · 生物科技信源

`sourceId=user-source-source-auto-item-ddee68df` · 还需审核 `20` 条 · `sampleDigest=d6eb8c097e4eaf9a`

当前没有可追溯的精确匹配记录。

## 傅利叶智能 官方动态

`sourceId=official-fourier-intelligence` · 还需审核 `20` 条 · `sampleDigest=4b138df240df64d3`

当前没有可追溯的精确匹配记录。

## 华大基因 官方动态

`sourceId=official-bgi-genomics` · 还需审核 `20` 条 · `sampleDigest=04a46e78251de4cf`

当前没有可追溯的精确匹配记录。

## 启明创投 · 核心团队页

`sourceId=user-source-source-auto-institution-team-131095855545` · 还需审核 `20` 条 · `sampleDigest=c1a723028783b927`

1. **启明星 | 阶跃星辰朱亦博：进入Agent时代，AI基础设施要实现智能、速度与成本的综合最优 | WAIC 2026 | 启明创投**
   - `article` · `user-source-source-auto-institution-team-131095855545-9591c82e9cd8e74e` · 2026-08-31 · 科技产业
   - https://www.qimingvc.com/cn/news/%E5%90%AF%E6%98%8E%E6%98%9F-%E9%98%B6%E8%B7%83%E6%98%9F%E8%BE%B0%E6%9C%B1%E4%BA%A6%E5%8D%9A%EF%BC%9A%E8%BF%9B%E5%85%A5agent%E6%97%B6%E4%BB%A3%EF%BC%8Cai%E5%9F%BA%E7%A1%80%E8%AE%BE%E6%96%BD%E8%A6%81%E5%AE%9E%E7%8E%B0%E6%99%BA%E8%83%BD%E3%80%81%E9%80%9F%E5%BA%A6%E4%B8%8E%E6%88%90%E6%9C%AC%E7%9A%84%E7%BB%BC%E5%90%88%E6%9C%80%E4%BC%98-waic-2026
2. **启明星 | 芯光界完成亿元天使轮融资，启明创投独家投资 | 启明创投**
   - `article` · `user-source-source-auto-institution-team-131095855545-7b5da7a1fb11c00b` · 2026-08-25 · 科技产业
   - https://www.qimingvc.com/cn/news/%E5%90%AF%E6%98%8E%E6%98%9F-%E8%8A%AF%E5%85%89%E7%95%8C%E5%AE%8C%E6%88%90%E4%BA%BF%E5%85%83%E5%A4%A9%E4%BD%BF%E8%BD%AE%E8%9E%8D%E8%B5%84%EF%BC%8C%E5%90%AF%E6%98%8E%E5%88%9B%E6%8A%95%E7%8B%AC%E5%AE%B6%E6%8A%95%E8%B5%84
3. **启明星 | 生数科技骆怡航：从理解语言到理解世界，通用世界模型开启AI发展新主线 | WAIC 2026 | 启明创投**
   - `article` · `user-source-source-auto-institution-team-131095855545-a5bcc1277dbda268` · 2026-08-24 · 科技产业
   - https://www.qimingvc.com/cn/news/%E5%90%AF%E6%98%8E%E6%98%9F-%E7%94%9F%E6%95%B0%E7%A7%91%E6%8A%80%E9%AA%86%E6%80%A1%E8%88%AA%EF%BC%9A%E4%BB%8E%E7%90%86%E8%A7%A3%E8%AF%AD%E8%A8%80%E5%88%B0%E7%90%86%E8%A7%A3%E4%B8%96%E7%95%8C%EF%BC%8C%E9%80%9A%E7%94%A8%E4%B8%96%E7%95%8C%E6%A8%A1%E5%9E%8B%E5%BC%80%E5%90%AFai%E5%8F%91%E5%B1%95%E6%96%B0%E4%B8%BB%E7%BA%BF-waic-2026

## 地平线机器人 官方动态

`sourceId=official-horizon-robotics` · 还需审核 `20` 条 · `sampleDigest=417058ad172c92e5`

当前没有可追溯的精确匹配记录。

## 埃隆·马斯克

`sourceId=user-x-elonmusk` · 还需审核 `20` 条 · `sampleDigest=733283982fd80401`

1. **埃隆·马斯克：Extending consciousness beyond Earth, ultimately to the stars, is a fundamentally good goal**
   - `article` · `user-x-elonmusk-f8ac89c66b5c1d11` · 2026-08-30 · 埃隆·马斯克
   - https://x.com/elonmusk/status/2094130588047266206

## 壁仞科技 官方动态

`sourceId=official-biren` · 还需审核 `20` 条 · `sampleDigest=8e729718d1f93da7`

1. **壁仞科技 智绘全球 | BIRENTECH**
   - `article` · `official-biren-dea7fd11f0a99dda` · 2026-08-20 · 壁仞科技
   - https://www.birentech.com/news/vizrxlodk1aaff7yxgv2dzvc
2. **壁仞科技 智绘全球 | BIRENTECH**
   - `article` · `official-biren-f696051f7d34b1f9` · 2026-08-03 · 壁仞科技
   - https://www.birentech.com/news/e3s2i45qzb2twf3939kks6gj

## 媒体报道 · 官方网站 · Commonwealth Fusion Systems

`sourceId=user-source-source-manual-28a7a586b67e6a1c` · 还需审核 `20` 条 · `sampleDigest=9f8f3e553c6fdd77`

当前没有可追溯的精确匹配记录。

## 媒体报道 · 官方网站 · Commonwealth Fusion Systems

`sourceId=user-source-source-manual-4b8869ffacc82b25` · 还需审核 `20` 条 · `sampleDigest=8a488f2804bc0768`

当前没有可追溯的精确匹配记录。

## 媒体报道 · 官方网站 · Commonwealth Fusion Systems

`sourceId=user-source-source-manual-c33cd501cc2a969b` · 还需审核 `20` 条 · `sampleDigest=db17e98743300b8c`

当前没有可追溯的精确匹配记录。

## 字节跳动

`sourceId=bytedance` · 还需审核 `20` 条 · `sampleDigest=5388bc10736a0eff`

当前没有可追溯的精确匹配记录。

## 宁德时代 官方动态

`sourceId=official-catl` · 还需审核 `20` 条 · `sampleDigest=a75ca6f825713e34`

1. **CATL Announces Local Partnership, Showcases Full-Chain Storage at The Smarter E South America 2026**
   - `article` · `catl-70143af7e2c6dc37` · 2026-08-25 · 宁德时代
   - https://www.catl.com/en/news/6977.html
2. **CATL’s Zero-Carbon Campus Tour Hits 1,000-School Milestone, Creating the Ultimate Gateway for Youth Science Education**
   - `article` · `official-catl-48cb3ba6686d2fcf` · 2026-08-18 · 宁德时代
   - https://www.catl.com/en/news/6968.html
3. **CATL Achieves 2025 Core Operation Carbon Neutrality Target, Sets Path to 2035 Value-Chain Goal**
   - `article` · `official-catl-ba07486ab2fc6712` · 2026-08-17 · 宁德时代
   - https://www.catl.com/en/news/6953.html
4. **CATL and Quinbrook Build on Supernode Partnership Following Stage 2 and Stage 3 Major Milestones**
   - `article` · `official-catl-c494a7862e029f46` · 2026-08-14 · 宁德时代
   - https://www.catl.com/en/news/6951.html

## 宇树科技

`sourceId=unitree` · 还需审核 `20` 条 · `sampleDigest=5a0888f587f30149`

当前没有可追溯的精确匹配记录。

## 宇树科技 官方动态

`sourceId=official-unitree` · 还需审核 `20` 条 · `sampleDigest=666a7582b4125fe6`

当前没有可追溯的精确匹配记录。

## 寒武纪 官方动态

`sourceId=official-cambricon` · 还需审核 `20` 条 · `sampleDigest=9c9fdb11a155287e`

当前没有可追溯的精确匹配记录。

## 小马智行 官方动态

`sourceId=official-pony-ai` · 还需审核 `20` 条 · `sampleDigest=358ae0ce83f58068`

1. **PONY AI Inc. Reports Second Quarter 2026 Financial Results: Total Revenues Up 68.8% YoY to US$36.2 mm with Robotaxi Services Revenue Up 691.2% to US$12.1 mm | 2026-08-18**
   - `article` · `official-pony-ai-c4b95b0cc73ac594` · 2026-08-18 · 小马智行
   - https://ir.pony.ai/news-releases/news-release-details/pony-ai-inc-reports-second-quarter-2026-financial-results-total
2. **PONY AI Inc. Expands Collaboration with Uber to Deploy Over 2,000 Robotaxis Across Five Cities in Europe | 2026-08-13**
   - `article` · `official-pony-ai-b21d045db9d58b63` · 2026-08-13 · 小马智行
   - https://ir.pony.ai/news-releases/news-release-details/pony-ai-inc-expands-collaboration-uber-deploy-over-2000
3. **PONY AI Inc. to Report Second Quarter and Interim Financial Results for 2026 on August 18, 2026 | 2026-07-17**
   - `article` · `official-pony-ai-8c654a7098bce8e3` · 2026-07-17 · 小马智行
   - https://ir.pony.ai/news-releases/news-release-details/pony-ai-inc-report-second-quarter-and-interim-financial-results
4. **PONY AI Inc. and ComfortDelGro Expand Singapore Autonomous Mobility Service with Consumer-Facing App Access | 2026-06-22**
   - `article` · `official-pony-ai-8de493e35a421304` · 2026-06-21 · 小马智行
   - https://ir.pony.ai/news-releases/news-release-details/pony-ai-inc-and-comfortdelgro-expand-singapore-autonomous

## 小鹏汇天 官方动态

`sourceId=official-xpeng-aeroht` · 还需审核 `20` 条 · `sampleDigest=b39156c8c6d0a80c`

当前没有可追溯的精确匹配记录。

## 搜狐网 · 商业航天信源

`sourceId=user-source-source-auto-item-ca1e1423` · 还需审核 `20` 条 · `sampleDigest=d2c6a4bb2fd3065c`

1. **马斯克飙脏话，痛斥OpenAI CEO奥尔特曼：“完全不值得信任的混蛋”**
   - `article` · `user-source-source-auto-item-ca1e1423-af3b41f11dd39587` · 2026-08-30 · OpenAI
   - https://www.sohu.com/a/1069596041_116237?edtcode=i8%2FsYUCbzZnHdceuO53lHAa2oN2%2BAMpMDyHU9tYktFw%3D&edtsign=5968241383B8D753B6D1F72C47887D02C5A10816&scm=thor.280_14-200000.0.0-0-0-0-0.
2. **SpaceX官宣建设最大星际基地：10个发射台，目标每年发射数千次**
   - `article` · `user-source-source-auto-item-ca1e1423-6ddcfdcb65bcdb27` · 2026-08-26 · 科技产业
   - https://www.sohu.com/a/1067867944_260616?edtcode=t2LpbykuINx4I7go63iwYw%3D%3D&edtsign=EDF04807B519045272E81ADE3FBBBCB210F8EF43&scm=thor.283_14-200000.0.0-0-0-0-0.

## 搜狐网 官方动态

`sourceId=official-user-搜狐网` · 还需审核 `20` 条 · `sampleDigest=b627d43624d58c06`

当前没有可追溯的精确匹配记录。
