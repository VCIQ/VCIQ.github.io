# 信源人工质量抽样队列

周期：`2026-11`；信源健康快照：`2026-11-01T04:51:00+00:00`。

目标为每个来源累计 **20** 条人工审查记录。当前有 **3** 个来源已具备足量候选，**989** 个来源仍缺少可审记录。

## 审核规则

1. 只按本页给出的 record ID 与原始 URL 审核，不用名称相似度自行补归属。
2. 对每个来源最多审核 `reviewNeeded` 条；若已人工审核过某条，不要重复计数。
3. 完成后仍将汇总结果写入现有 `config/source_quality_reviews.json`，不改 schema。
4. 在该 review 的 `notes` 中记录 `sampleDigest=<值>`，以便从 Git 历史追溯本次具体样本。

| 来源 | 等级 | 已审/目标 | 还需 | 可用记录 | 队列状态 | sampleDigest |
|---|---|---:|---:|---:|---|---|
| Yahoo奇摩 | C | 0/20 | 20 | 20 | 可审核 | `73695d5c92e4c19b` |
| 媒体报道 · 新浪 · 新浪财经 | C | 0/20 | 20 | 20 | 可审核 | `9a6440080d7d828a` |
| 媒体报道 · 新浪 · 新浪财经 | C | 0/20 | 20 | 20 | 可审核 | `72429465985e86be` |
| 上海证券交易所 | A | 0/20 | 20 | 1 | 记录不足 | `09e71bb6e39f1bd3` |
| 深圳证券交易所 | A | 0/20 | 20 | 0 | 记录不足 | `79d81b93ce9ef8d8` |
| 美国证券交易委员会 SEC | A | 0/20 | 20 | 0 | 记录不足 | `630e8adb9e4fccb2` |
| Alibaba Group 官方动态 | B | 0/20 | 20 | 1 | 记录不足 | `c75cbf194df5b40f` |
| Alibaba Group 官方网站 | B | 0/20 | 20 | 0 | 记录不足 | `f048d2b6eefe7a58` |
| AliExpress 官方动态 | B | 0/20 | 20 | 0 | 记录不足 | `14f3db6314bc0885` |
| AliExpress 官方网站 | B | 0/20 | 20 | 0 | 记录不足 | `f3032f7216d5ba9c` |
| Allen Institute 官方动态 | B | 0/20 | 20 | 2 | 记录不足 | `c9634fc6997ceba3` |
| AMD Newsroom | B | 0/20 | 20 | 16 | 记录不足 | `4b2c8ac44a14dfb4` |
| AMD 官方动态 | B | 0/20 | 20 | 4 | 记录不足 | `f587d2a9cc4ae38d` |
| Anduril Industries 官方动态 | B | 0/20 | 20 | 4 | 记录不足 | `dd4fee2784fb6414` |
| Anthropic | B | 0/20 | 20 | 6 | 记录不足 | `c2386cb723eda5b2` |
| Anthropic | B | 0/20 | 20 | 5 | 记录不足 | `a977b6969ade2e1c` |
| Anthropic 官方动态 | B | 0/20 | 20 | 3 | 记录不足 | `3923e3acf1e4755d` |
| arXiv · Core AI companies | B | 0/20 | 20 | 8 | 记录不足 | `5015349271074341` |
| ASML 官方动态 | B | 0/20 | 20 | 4 | 记录不足 | `7b2e1d2556763609` |
| Aurora Innovation 官方动态 | B | 0/20 | 20 | 0 | 记录不足 | `cac901da1a9ea146` |
| Axiom Space 官方动态 | B | 0/20 | 20 | 4 | 记录不足 | `121a5231de2cee27` |
| Cartesia 官方动态 | B | 0/20 | 20 | 2 | 记录不足 | `fe986346af06e69b` |
| CATL | B | 0/20 | 20 | 8 | 记录不足 | `c80b7afb8ef447de` |
| Cerebras Systems | B | 0/20 | 20 | 0 | 记录不足 | `77b30b8a88051252` |
| Cerebras Systems · 官方网站 | B | 0/20 | 20 | 0 | 记录不足 | `577856b2048b3f6d` |
| Cerebras Systems · 官方网站 | B | 0/20 | 20 | 0 | 记录不足 | `7b41847bd48a261e` |
| Cerebras Systems · 官方网站 | B | 0/20 | 20 | 0 | 记录不足 | `d12a01499bac284c` |
| Cerebras Systems 官方动态 | B | 0/20 | 20 | 0 | 记录不足 | `4eaa13e5dfbed84c` |
| Commonwealth Fusion Systems 官方动态 | B | 0/20 | 20 | 0 | 记录不足 | `22309084a7a95cff` |
| Coursera 官方动态 | B | 0/20 | 20 | 0 | 记录不足 | `c9e4d735f67257b5` |
| Databricks 官方动态 | B | 0/20 | 20 | 1 | 记录不足 | `609c3ff8e611bcc3` |
| DeepSeek | B | 0/20 | 20 | 0 | 记录不足 | `6f7ac1823da81d2e` |
| DeepSeek 官方动态 | B | 0/20 | 20 | 1 | 记录不足 | `38e8e7527f84ad1e` |
| Demis Hassabis | B | 0/20 | 20 | 0 | 记录不足 | `11d0129584e9072e` |
| Figure AI | B | 0/20 | 20 | 4 | 记录不足 | `8f16e09e213b89d2` |
| Figure AI 官方动态 | B | 0/20 | 20 | 0 | 记录不足 | `093bd0070133b59f` |
| Form Energy 官方动态 | B | 0/20 | 20 | 3 | 记录不足 | `d9c4551b498f3333` |
| Founders Fund · 核心团队页 | B | 0/20 | 20 | 0 | 记录不足 | `72a885255cad56d1` |
| Glean 官方动态 | B | 0/20 | 20 | 0 | 记录不足 | `8955a0c76b81e41a` |
| Google AI | B | 0/20 | 20 | 10 | 记录不足 | `9b967beee416de91` |
| Google DeepMind | B | 0/20 | 20 | 10 | 记录不足 | `fd645dd7032ef172` |
| Google DeepMind | B | 0/20 | 20 | 3 | 记录不足 | `dd7d2a346ca681fb` |
| Google DeepMind | B | 0/20 | 20 | 5 | 记录不足 | `f95c2c226130e391` |
| Google 官方动态 | B | 0/20 | 20 | 0 | 记录不足 | `d3ab2de1f60c4c51` |
| Google 官方动态 | B | 0/20 | 20 | 0 | 记录不足 | `7f5249f68ce29d5c` |
| Google 官方网站 | B | 0/20 | 20 | 0 | 记录不足 | `c72519a0258f039a` |
| Groq 官方动态 | B | 0/20 | 20 | 4 | 记录不足 | `cba6fb32c971d9cb` |
| Harvey 官方动态 | B | 0/20 | 20 | 4 | 记录不足 | `98b2fd767dacd191` |
| Helion Energy 官方动态 | B | 0/20 | 20 | 3 | 记录不足 | `4b42e30c7a257aec` |
| Horizon3 官方动态 | B | 0/20 | 20 | 6 | 记录不足 | `d9e66509933081f0` |
| Intuitive Surgical 官方动态 | B | 0/20 | 20 | 1 | 记录不足 | `cd4a83be056a83fc` |
| IonQ | B | 0/20 | 20 | 9 | 记录不足 | `b70561b130c8cf65` |
| IonQ 官方动态 | B | 0/20 | 20 | 0 | 记录不足 | `85ba6807c3d6b20b` |
| Joby Aviation 官方动态 | B | 0/20 | 20 | 3 | 记录不足 | `cbace9f204ffff47` |
| Kleiner Perkins · 核心团队页 | B | 0/20 | 20 | 0 | 记录不足 | `f7fee307e61af721` |
| Lazada 官方动态 | B | 0/20 | 20 | 0 | 记录不足 | `38e572c3a964fe5b` |
| Lazada 官方网站 | B | 0/20 | 20 | 0 | 记录不足 | `a6f8710377754f07` |
| Lightspeed Venture Partners · 核心团队页 | B | 0/20 | 20 | 0 | 记录不足 | `98cff7d33f01cce9` |
| Manifold Bio 官方动态 | B | 0/20 | 20 | 1 | 记录不足 | `966ef5f3a286c540` |
| MiniMax | B | 0/20 | 20 | 0 | 记录不足 | `e1517be14d06cdb7` |
| MiniMax 官方动态 | B | 0/20 | 20 | 2 | 记录不足 | `82b89403d90df10c` |
| Mobileye 官方动态 | B | 0/20 | 20 | 0 | 记录不足 | `7c09e66fc7b197ee` |
| Modular 官方动态 | B | 0/20 | 20 | 6 | 记录不足 | `1d5daf074c545e47` |
| OLIX 官方动态 | B | 0/20 | 20 | 1 | 记录不足 | `773351a227b7fdc9` |
| Omilia 官方动态 | B | 0/20 | 20 | 3 | 记录不足 | `efdcfbb249cf6955` |
| OpenAI | B | 0/20 | 20 | 4 | 记录不足 | `bdfed0456726ca1b` |
| OpenAI | B | 0/20 | 20 | 5 | 记录不足 | `8a8de2000f0aed42` |
| OpenAI 官方动态 | B | 0/20 | 20 | 4 | 记录不足 | `7f56e95d68fdaff3` |
| OpenAI 官方新闻 | B | 0/20 | 20 | 16 | 记录不足 | `c676957bd4d6c35b` |
| Perplexity 官方动态 | B | 0/20 | 20 | 0 | 记录不足 | `ff22b92ab74ddce8` |
| Pony.ai Investor Relations | B | 0/20 | 20 | 3 | 记录不足 | `d79c3621badcaa49` |
| PR Newswire Consumer Technology | B | 0/20 | 20 | 6 | 记录不足 | `6d1895f3662f0faf` |
| PsiQuantum 官方动态 | B | 0/20 | 20 | 4 | 记录不足 | `96464ede6fd5727a` |
| Reach Capital 官方动态 | B | 0/20 | 20 | 5 | 记录不足 | `fcb4ee3993598530` |
| Recursion Pharmaceuticals 官方动态 | B | 0/20 | 20 | 0 | 记录不足 | `840715263d0f33f5` |
| Redwood Materials 官方动态 | B | 0/20 | 20 | 3 | 记录不足 | `326188fd424d0d8f` |
| Relativity Space 官方动态 | B | 0/20 | 20 | 0 | 记录不足 | `29c381de752e380f` |
| Rigetti Computing 官方动态 | B | 0/20 | 20 | 1 | 记录不足 | `822cf84505e8c80a` |
| Rocket Lab Investor Relations | B | 0/20 | 20 | 8 | 记录不足 | `37e84d65a19d6932` |
| Rocket Lab 官方动态 | B | 0/20 | 20 | 0 | 记录不足 | `77724e934eaa73a4` |
| SambaNova Systems 官方动态 | B | 0/20 | 20 | 1 | 记录不足 | `16953aa327a5ffe8` |
| Scale AI | B | 0/20 | 20 | 4 | 记录不足 | `0563ca0e6587836d` |
| Scale AI 官方动态 | B | 0/20 | 20 | 0 | 记录不足 | `2f665fc1199b43e5` |
| Shield AI 官方动态 | B | 0/20 | 20 | 2 | 记录不足 | `3f3c717c9233392b` |
| Shopify 官方动态 | B | 0/20 | 20 | 4 | 记录不足 | `f2fdedcdb46f85b5` |
| Shopify 官方动态 | B | 0/20 | 20 | 0 | 记录不足 | `c5de1fb0e02dc3a7` |
| Shopify 官方网站 | B | 0/20 | 20 | 0 | 记录不足 | `2ddbee055a110ae8` |
| Sierra 官方动态 | B | 0/20 | 20 | 0 | 记录不足 | `d4f3869695b488d4` |
| SpaceX | B | 0/20 | 20 | 0 | 记录不足 | `e78bdebae031095b` |
| SpaceX 官方动态 | B | 0/20 | 20 | 2 | 记录不足 | `2ee599802d278cc1` |
| Tempus AI 官方动态 | B | 0/20 | 20 | 0 | 记录不足 | `a6111d51beea3380` |
| The Washington Post | B | 0/20 | 20 | 10 | 记录不足 | `e5f6b95e3e285dd3` |
| The Washington Post | B | 0/20 | 20 | 0 | 记录不足 | `f7efb455dec04697` |
| Upstage 官方动态 | B | 0/20 | 20 | 0 | 记录不足 | `eaf4eef74aaa21d1` |
| Varda Space Industries 官方动态 | B | 0/20 | 20 | 0 | 记录不足 | `bb603f44803396fe` |
| WeRide Investor Relations | B | 0/20 | 20 | 7 | 记录不足 | `7cc15f1a76941679` |
| xAI | B | 0/20 | 20 | 10 | 记录不足 | `69709675610ace1a` |
| xAI 官方动态 | B | 0/20 | 20 | 0 | 记录不足 | `20a376500412b439` |
| Y Combinator · 核心团队页 | B | 0/20 | 20 | 4 | 记录不足 | `4bf2ef81f7965993` |
| 东方财富 · 生物科技信源 | B | 0/20 | 20 | 0 | 记录不足 | `d6eb8c097e4eaf9a` |

这里只展示前 100 个来源；完整队列见 JSON 文件。

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

## 上海证券交易所

`sourceId=regulatory:sse` · 还需审核 `20` 条 · `sampleDigest=09e71bb6e39f1bd3`

1. **关于中科寒武纪科技股份有限公司人民币普通股股票科创板上市交易的公告**
   - `regulatory-disclosure` · `disclosure-cambricon-sse-listing-20200717` · 2020-07-17 · 寒武纪
   - https://www.sse.com.cn/disclosure/announcement/listing/ipo/c/c_20200717_78749873.shtml

## 深圳证券交易所

`sourceId=regulatory:szse` · 还需审核 `20` 条 · `sampleDigest=79d81b93ce9ef8d8`

当前没有可追溯的精确匹配记录。

## 美国证券交易委员会 SEC

`sourceId=regulatory:sec` · 还需审核 `20` 条 · `sampleDigest=630e8adb9e4fccb2`

当前没有可追溯的精确匹配记录。

## Alibaba Group 官方动态

`sourceId=official-user-alibaba-group` · 还需审核 `20` 条 · `sampleDigest=c75cbf194df5b40f`

1. **Precio Bajo Alibaba en Español Tamaño Compacto y Discreto | Alibaba. com**
   - `article` · `official-user-alibaba-group-f69f60ed1fc75cca` · 2026-10-28 · Alibaba Group
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

## Allen Institute 官方动态

`sourceId=official-allen-institute` · 还需审核 `20` 条 · `sampleDigest=c9634fc6997ceba3`

1. **Education Resources from the Allen Institute**
   - `article` · `official-allen-institute-f9012376aa343e2c` · 2026-09-18 · Allen Institute
   - https://alleninstitute.org/education/resources
2. **The Battle Within**
   - `article` · `official-allen-institute-057b25204248b725` · 2026-09-18 · Allen Institute
   - https://alleninstitute.org/articles/battle-within

## AMD Newsroom

`sourceId=amd-newsroom` · 还需审核 `20` 条 · `sampleDigest=4b2c8ac44a14dfb4`

1. **AMD Expands AI and Cloud Infrastructure Collaboration with Oracle**
   - `article` · `amd-newsroom-bcccb402c725dc50` · 2026-10-27 · AMD
   - https://newsroom.amd.com/news/amd-expands-ai-cloud-infrastructure-oracle
2. **AMD and Intel Collaborate to Simplify AI Development on x86 CPUs with PyTorch**
   - `article` · `amd-newsroom-e430582d96f8be9b` · 2026-10-20 · AMD
   - https://newsroom.amd.com/news/amd-intel-collaborate-simplify-ai-development-on-x86-cpus-pytorch
3. **AMD FSR Upscaling 4.1 Boosts Frames and Image Quality on More Devices**
   - `article` · `amd-newsroom-0d2e5bb4830f0727` · 2026-10-20 · AMD
   - https://newsroom.amd.com/news/amd-fsr-upscaling-4-1-boosts-frames-image-quality
4. **From AI That Answers to AI That Acts**
   - `article` · `amd-newsroom-2aa248434cf70afa` · 2026-10-19 · AMD
   - https://newsroom.amd.com/news/ai-that-answers-ai-that-acts
5. **EE Times Interview: Mark Papermaster on the Future of AI and Semiconductor Innovation (Video)**
   - `article` · `amd-newsroom-a5f2a0e278e2332d` · 2026-10-15 · AMD
   - https://newsroom.amd.com/news/ee-times-interview-mark-papermaster-future-a-video
6. **OCP 2026 Keynote Replay: Building the Next Era of AI Infrastructure**
   - `article` · `amd-newsroom-6e3224deb8e80a66` · 2026-10-13 · AMD
   - https://newsroom.amd.com/news/ocp-2026-keynote-replay-next-era-ai-infrastructure
7. **OCP 2026: AMD CEO Lisa Su Highlights Open Infrastructure for the Future of AI**
   - `article` · `amd-newsroom-e5d708b337db899b` · 2026-10-12 · AMD
   - https://newsroom.amd.com/news/ocp-2026-amd-ceo-lisa-su-keynote-takeaways
8. **Introducing AMD Helion, Agentic AI Compute at Rack Scale**
   - `article` · `amd-newsroom-81bae7f0839feb3e` · 2026-10-12 · AMD
   - https://newsroom.amd.com/news/open-rack-blueprint-scale-agentic-ai
9. **AMD Helios: Designing and Building the Future of AI Infrastructure (Videos)**
   - `article` · `amd-newsroom-2f58b931d3be5036` · 2026-10-05 · AMD
   - https://newsroom.amd.com/news/amd-helios-designing-building-future-ai-infrastructure
10. **AMD Sampling Versal AI Core Adaptive SoC in Enhanced Space-Grade Package for the Most Demanding Missions**
   - `article` · `amd-newsroom-8a313548ef7c7e89` · 2026-10-01 · AMD
   - https://newsroom.amd.com/news/amd-sampling-versal-ai-core-adaptive-soc
11. **AMD Brings the Power of Agentic AI to Embedded Design and Development Cycle**
   - `article` · `amd-newsroom-7ae4d67e7a5a60b8` · 2026-09-30 · AMD
   - https://newsroom.amd.com/news/amd-ross-agentic-ai-embedded-design-development
12. **Media Alert: AMD CEO Lisa Su to Lead Keynote at 2026 OCP**
   - `article` · `amd-newsroom-6506c4a273efe728` · 2026-09-29 · AMD
   - https://newsroom.amd.com/news/media-alert-ceo-lisa-su-keynote-2026-ocp
13. **AMD to Acquire World Labs to Advance the Future of AI Compute**
   - `article` · `amd-newsroom-effcb19529443682` · 2026-09-28 · AMD
   - https://newsroom.amd.com/news/amd-acquire-world-labs
14. **With AMD Ryzen AI Max Series Processors, Perplexity Brings Portable Computer to Agentic PCs**
   - `article` · `amd-newsroom-f8760c7b2f8a5eb5` · 2026-09-24 · AMD
   - https://newsroom.amd.com/news/amd-perplexity-agentic-pcs
15. **‘Advanced Insights’: How ‘Zen’ Architecture Evolves for the Agentic AI Era (Video)**
   - `article` · `amd-newsroom-06b3644dd027b1a6` · 2026-09-23 · AMD
   - https://newsroom.amd.com/news/advanced-insights-zen-architecture-agentic-ai-era
16. **Media Alert: AMD to Showcase Physical AI and Robotics Innovation at ROSCon 2026**
   - `article` · `amd-newsroom-6f0df152f4b17d5d` · 2026-09-21 · AMD
   - https://newsroom.amd.com/news/media-alert-amd-roscon-2026

## AMD 官方动态

`sourceId=official-amd` · 还需审核 `20` 条 · `sampleDigest=f587d2a9cc4ae38d`

1. **AMD and Meta Advance Strategic Partnership to Power Meta’s Superintelligence Infrastructure**
   - `article` · `official-amd-a763319f57e7309e` · 2026-10-27 · AMD
   - https://ir.amd.com/news-events/press-releases/detail/1302/amd-and-meta-advance-strategic-partnership-to-power-metas-superintelligence-infrastructure
2. **Introducing AMD Helion, Agentic AI Compute at Rack Scale**
   - `article` · `official-amd-013238a25b04ff0a` · 2026-10-12 · AMD
   - https://ir.amd.com/news-events/press-releases/detail/1301/introducing-amd-helion-agentic-ai-compute-at-rack-scale
3. **AMD to Report Fiscal Third Quarter 2026 Financial Results**
   - `article` · `official-amd-fcb9e77270940ced` · 2026-10-06 · AMD
   - https://ir.amd.com/news-events/press-releases/detail/1300/amd-to-report-fiscal-third-quarter-2026-financial-results
4. **AMD to Acquire World Labs to Advance the Future of AI Compute**
   - `article` · `official-amd-0453a8f863b62b77` · 2026-09-28 · AMD
   - https://ir.amd.com/news-events/press-releases/detail/1299/amd-to-acquire-world-labs-to-advance-the-future-of-ai-compute

## Anduril Industries 官方动态

`sourceId=official-anduril` · 还需审核 `20` 条 · `sampleDigest=dd4fee2784fb6414`

1. **Anduril and Qualcomm Unveil BlueChip to Rebuild American Computer Manufacturing**
   - `article` · `official-anduril-2a5ef707ba02836d` · 2026-10-27 · Anduril Industries
   - https://www.anduril.com/news/anduril-and-qualcomm-unveil-bluechip-to-rebuild-american-computer-manufacturing
2. **Steelfin**
   - `article` · `official-anduril-18a41ee8afd95cdf` · 2026-10-12 · Anduril Industries
   - https://www.anduril.com/news/steelfin
3. **Anduril, U.S. Navy Invest $6.6 Billion to Expand America's Submarine Industrial Base**
   - `article` · `official-anduril-6538846abe3a4f0e` · 2026-10-06 · Anduril Industries
   - https://www.anduril.com/news/anduril-u-s-navy-invest-usd6-6-billion-to-expand-america-s-submarine-industrial-base
4. **Anduril Continues to Scale Next-Generation Command and Control Across the Army**
   - `article` · `official-anduril-01616e8817517544` · 2026-10-05 · Anduril Industries
   - https://www.anduril.com/news/anduril-continues-to-scale-next-generation-command-and-control-across-the-army

## Anthropic

`sourceId=anthropic` · 还需审核 `20` 条 · `sampleDigest=c2386cb723eda5b2`

1. **AI for Science expands to foundations and institutions**
   - `article` · `anthropic-e63c44ee253751eb` · 2026-10-28 · Anthropic
   - https://www.anthropic.com/news/ai-for-science-expands-foundations-research-institutions
2. **Expanding our partnership with GSA to bring Claude to all levels of government**
   - `article` · `anthropic-550f4d88633d4245` · 2026-10-27 · Anthropic
   - https://www.anthropic.com/news/expanding-partnership-gsa
3. **Anthropic files S-1 with the SEC for proposed initial public offering**
   - `article` · `anthropic-9a064d95901e645e` · 2026-10-26 · Anthropic
   - https://www.anthropic.com/news/s1-sec
4. **Donating Agent Skills to the Agentic AI Foundation**
   - `article` · `anthropic-bdc7b775ab8d2106` · 2026-10-22 · Anthropic
   - https://www.anthropic.com/news/donating-agent-skills-to-the-agentic-ai-foundation
5. **Open call for guest investigators in the life sciences**
   - `article` · `anthropic-6950f6169e819866` · 2026-10-22 · Anthropic
   - https://www.anthropic.com/news/open-call-guest-investigators-life-sciences
6. **Investing in the public benefit**
   - `article` · `anthropic-a0595c813318ccae` · 2026-10-18 · Anthropic
   - https://www.anthropic.com/news/public-benefit-fund

## Anthropic

`sourceId=x-anthropic` · 还需审核 `20` 条 · `sampleDigest=a977b6969ade2e1c`

1. **Anthropic：New Anthropic research: Automating subtle emergent misalignment research. Red-teaming is a vital part of model safety testing, but it’s also limited b**
   - `article` · `x-anthropic-0e255d5f70ebf763` · 2026-10-31 · Anthropic
   - https://x.com/AnthropicAI/status/2116349211549843666
2. **Anthropic：We’ve trained Claude to flag potential misuse in conversations, a technique we call self-assessment. Right after it responds, Claude gives a prelimina**
   - `article` · `x-anthropic-9f0c28e45e9fe785` · 2026-10-29 · Anthropic
   - https://x.com/AnthropicAI/status/2115871889549865429
3. **Anthropic：We’ve expanded our AI for Science program beyond individual teams to support some of the world’s leading scientific foundations, institutions, and res**
   - `article` · `x-anthropic-59b6cea1e9548bf7` · 2026-10-29 · Anthropic
   - https://x.com/AnthropicAI/status/2115825653539025142
4. **Anthropic：We're expanding our partnership with @USGSA. Under a new OneGov agreement, we are bringing Claude to federal, state, local, tribal, and territorial go**
   - `article` · `x-anthropic-cafa8e625a66fffc` · 2026-10-27 · Anthropic
   - https://x.com/AnthropicAI/status/2115207004293853358
5. **Anthropic：Over the past few months, Anthropic scientists have engaged in deep research partnerships with six organizations developing new medicines. We've also**
   - `article` · `x-anthropic-1b49fd3bd1f0f9db` · 2026-10-27 · Anthropic
   - https://x.com/AnthropicAI/status/2115178675050307942

## Anthropic 官方动态

`sourceId=official-anthropic` · 还需审核 `20` 条 · `sampleDigest=3923e3acf1e4755d`

1. **Anthropic update on independent evaluators**
   - `article` · `official-anthropic-c3f9aa1e97f35f24` · 2026-10-15 · Anthropic
   - https://www.anthropic.com/news/an-update-on-independent-evaluators
2. **Preparing for the 2026 US midterms**
   - `article` · `official-anthropic-ad577cc4d385593c` · 2026-10-14 · Anthropic
   - https://www.anthropic.com/news/2026-us-midterms
3. **2026 Usage Policy update**
   - `article` · `official-anthropic-4e66a7e453a3193b` · 2026-10-08 · Anthropic
   - https://www.anthropic.com/news/2026-usage-policy-update

## arXiv · Core AI companies

`sourceId=arxiv-ai` · 还需审核 `20` 条 · `sampleDigest=5015349271074341`

1. **Evaluating Conversational Explainability in Healthcare: Comparing the Explainability Assistant and a Traditional XAI Dashboard**
   - `article` · `arxiv-ai-d5a53a480fc86db1` · 2026-10-29 · 科技产业
   - https://arxiv.org/abs/2610.39634v1
2. **Decision and System One models in rheumatology: accuracy and calibration on specialty-training examination questions and diagnostic case vignettes**
   - `article` · `arxiv-ai-a7c0e19db55c82df` · 2026-10-29 · 科技产业
   - https://arxiv.org/abs/2610.40318v1
3. **Sparse domination and an extended $L^p$ range for the trilinear Hilbert transform**
   - `article` · `arxiv-ai-37f182a197143a83` · 2026-10-29 · 科技产业
   - https://arxiv.org/abs/2610.39096v1
4. **Aligning Autoresearch: Co-Improvement between Agents and Humans**
   - `article` · `arxiv-ai-93725a05ce94c011` · 2026-10-28 · 科技产业
   - https://arxiv.org/abs/2610.38882v1
5. **A Defense-Aware Explainable AI Framework for Feature-Level Vulnerability Analysis in Optimal Power Flow**
   - `article` · `arxiv-ai-4da415496460d18b` · 2026-10-28 · 科技产业
   - https://arxiv.org/abs/2610.38945v1
6. **On the Sparsity of Direct Preference Optimization: Weight Disentanglement in the NTK Regime**
   - `article` · `arxiv-ai-c9fd0f558854dc74` · 2026-10-27 · 科技产业
   - https://arxiv.org/abs/2610.37085v1
7. **DocXEval: A Systematic Evaluation of Explainability in Multimodal Document Understanding**
   - `article` · `arxiv-ai-5d2f99ff50b7b401` · 2026-10-27 · 科技产业
   - https://arxiv.org/abs/2610.36929v1
8. **Square-root logarithmic bounds for the arithmetic complexity of factorial multiples**
   - `article` · `arxiv-ai-3da362a4b3fff3f2` · 2026-10-27 · 科技产业
   - https://arxiv.org/abs/2610.36588v1

## ASML 官方动态

`sourceId=official-asml` · 还需审核 `20` 条 · `sampleDigest=7b2e1d2556763609`

1. **Samsung Electronics and ASML expand strategic collaboration for next-generation semiconductor manufacturing | Tue, 09/08/2026 - 08:05**
   - `article` · `official-asml-f76d591696ab4c5d` · 2026-09-21 · ASML
   - https://investor.asml.com/news-releases/news-release-details/samsung-electronics-and-asml-expand-strategic-collaboration-next-generation-semiconductor-manufacturing
2. **Intel Foundry and ASML Collaborate to Accelerate Industry Readiness for High-NA EUV | Tue, 09/08/2026 - 08:10**
   - `article` · `official-asml-bebff9d1108d2c20` · 2026-09-21 · ASML
   - https://investor.asml.com/news-releases/news-release-details/intel-foundry-and-asml-collaborate-accelerate-industry-readiness-high-na-euv
3. **ASML begins construction of new Eindhoven campus, strengthening its presence in the Brainport region | Tue, 09/08/2026 - 13:20**
   - `article` · `official-asml-89e63e816e0925b2` · 2026-09-08 · ASML
   - https://investor.asml.com/news-releases/news-release-details/asml-begins-construction-new-eindhoven-campus-strengthening-its-presence-brainport-region
4. **ASML and TSMC Announce Initiative to Pioneer Industry Transition to Large-Format Photomasks for High NA EUV | Tue, 09/08/2026 - 08:04**
   - `article` · `official-asml-16f3a93d0c21e74c` · 2026-09-08 · ASML
   - https://investor.asml.com/news-releases/news-release-details/asml-and-tsmc-announce-initiative-pioneer-industry-transition-large-format-photomasks-high-na-euv

## Aurora Innovation 官方动态

`sourceId=official-aurora` · 还需审核 `20` 条 · `sampleDigest=cac901da1a9ea146`

当前没有可追溯的精确匹配记录。

## Axiom Space 官方动态

`sourceId=official-axiom-space` · 还需审核 `20` 条 · `sampleDigest=121a5231de2cee27`

1. **Axiom Space, National Stem Cell Foundation, Saudi Space Agency Collaborate to Expand Study of Neurodegenerative Disease in Microgravity**
   - `article` · `official-axiom-space-ea0217694b23456b` · 2026-10-14 · Axiom Space
   - https://www.axiomspace.com/news/national-stem-cell-foundation-joins-with-axiom-space-and-the-saudi-space-agency-to-expand-study-of-neurodegenerative-disease-in-microgravity
2. **Axiom Space is Building the Future of Research in Space**
   - `article` · `official-axiom-space-efb45dd1e0a3f5d4` · 2026-10-08 · Axiom Space
   - https://www.axiomspace.com/news/axiom-space-building-the-future-of-research-in-space
3. **Axiom Space, Exobiosphere Sign Memorandum of Understanding to Advance Drug Discovery in Space**
   - `article` · `official-axiom-space-5182ba169736e9e2` · 2026-10-07 · Axiom Space
   - https://www.axiomspace.com/news/mou-exobiosphere
4. **Celebrating National Sewing Month in the Axiom Space Soft Goods Lab**
   - `article` · `official-axiom-space-723c425176fd3189` · 2026-09-28 · Axiom Space
   - https://www.axiomspace.com/news/celebrating-national-sewing-month-in-the-axiom-space-soft-goods-lab

## Cartesia 官方动态

`sourceId=official-cartesia` · 还需审核 `20` 条 · `sampleDigest=fe986346af06e69b`

1. **Introducing Managed Agents**
   - `article` · `official-cartesia-691558dbfed99d57` · 2026-10-29 · Cartesia
   - https://www.cartesia.ai/blog/managed-agents
2. **Raise Financial Services x Cartesia: Voice AI for Financial Access in India**
   - `article` · `official-cartesia-8d1903ec9d7deb39` · 2026-10-12 · Cartesia
   - https://www.cartesia.ai/blog/raise-financial-services

## CATL

`sourceId=catl` · 还需审核 `20` 条 · `sampleDigest=c80b7afb8ef447de`

1. **IRENA Releases 'Storage+' Report to Explore Innovative Paths for Energy Storage with Diverse Industries**
   - `article` · `catl-3f82d9c756f0d4f6` · 2026-10-16 · 宁德时代
   - https://www.catl.com/en/news/7042.html
2. **Dr. Robin Zeng: From Rapid Expansion to Long-Term Reliability, Energy Storage as Critical Infrastructure**
   - `article` · `catl-5111fd59e4115a7e` · 2026-10-15 · 宁德时代
   - https://www.catl.com/en/news/7041.html
3. **CATL Becomes First Battery Company to Join All Three GBA Battery Passport Pilot Waves**
   - `article` · `catl-79fd596b9e692698` · 2026-10-12 · 宁德时代
   - https://www.catl.com/en/news/7016.html
4. **CATL and SERES Sign Long-Term Strategic Cooperation Agreement**
   - `article` · `catl-b402271c22be11cd` · 2026-10-10 · 宁德时代
   - https://www.catl.com/en/news/7014.html
5. **Europe’s Largest NING SERVICE Experience Center Opens in Norway**
   - `article` · `catl-8be22ad3fe35af0c` · 2026-09-24 · 宁德时代
   - https://www.catl.com/en/news/7013.html
6. **CATL Debrecen Kicks Off Trial Operations in its New Cell Building**
   - `article` · `catl-f81b4656bae6ac0b` · 2026-09-22 · 宁德时代
   - https://www.catl.com/en/news/7000.html
7. **Kuehne+Nagel and CATL partner to advance battery logistics and fleet electrification**
   - `article` · `catl-f3e02afa3fb78fc4` · 2026-09-18 · 宁德时代
   - https://www.catl.com/en/news/7012.html
8. **CATL Partners with BME to Advance Battery Pack Manufacturing in Egypt Through Technology Licensing**
   - `article` · `catl-d3f6b4d5622ccf82` · 2026-09-16 · 宁德时代
   - https://www.catl.com/en/news/6998.html

## Cerebras Systems

`sourceId=cerebras` · 还需审核 `20` 条 · `sampleDigest=77b30b8a88051252`

当前没有可追溯的精确匹配记录。

## Cerebras Systems · 官方网站

`sourceId=user-source-source-manual-396cc79d699005df` · 还需审核 `20` 条 · `sampleDigest=577856b2048b3f6d`

当前没有可追溯的精确匹配记录。

## Cerebras Systems · 官方网站

`sourceId=user-source-source-manual-7255d48332608fb2` · 还需审核 `20` 条 · `sampleDigest=7b41847bd48a261e`

当前没有可追溯的精确匹配记录。

## Cerebras Systems · 官方网站

`sourceId=user-source-source-manual-7f40bf2400f36f41` · 还需审核 `20` 条 · `sampleDigest=d12a01499bac284c`

当前没有可追溯的精确匹配记录。

## Cerebras Systems 官方动态

`sourceId=official-cerebras` · 还需审核 `20` 条 · `sampleDigest=4eaa13e5dfbed84c`

当前没有可追溯的精确匹配记录。

## Commonwealth Fusion Systems 官方动态

`sourceId=official-commonwealth-fusion` · 还需审核 `20` 条 · `sampleDigest=22309084a7a95cff`

当前没有可追溯的精确匹配记录。

## Coursera 官方动态

`sourceId=official-coursera` · 还需审核 `20` 条 · `sampleDigest=c9e4d735f67257b5`

当前没有可追溯的精确匹配记录。

## Databricks 官方动态

`sourceId=official-databricks` · 还需审核 `20` 条 · `sampleDigest=609c3ff8e611bcc3`

1. **All | Databricks Blog**
   - `article` · `official-databricks-3e6baf52cce5b5fc` · 2026-10-31 · Databricks
   - https://www.databricks.com/blog/category/all

## DeepSeek

`sourceId=deepseek` · 还需审核 `20` 条 · `sampleDigest=6f7ac1823da81d2e`

当前没有可追溯的精确匹配记录。

## DeepSeek 官方动态

`sourceId=official-deepseek` · 还需审核 `20` 条 · `sampleDigest=38e8e7527f84ad1e`

1. **DeepSeek V4.1 Flash：更强、更快、更普惠**
   - `article` · `official-deepseek-ef1a570fe50dec94` · 2026-09-10 · DeepSeek
   - https://www.deepseek.com/news/deepseek-v4-1-flash

## Demis Hassabis

`sourceId=x-demis` · 还需审核 `20` 条 · `sampleDigest=11d0129584e9072e`

当前没有可追溯的精确匹配记录。

## Figure AI

`sourceId=figure` · 还需审核 `20` 条 · `sampleDigest=8f16e09e213b89d2`

1. **F.02 Decommission**
   - `article` · `figure-7535f31f798a108e` · 2026-09-30 · Figure AI
   - https://www.figure.ai/news/f-02-decommission
2. **Helix 2.5: Zero-Shot 30-Home Generalization**
   - `article` · `figure-d12ee081a0882850` · 2026-09-17 · Figure AI
   - https://www.figure.ai/news/helix-2-5-zero-shot-30-home-generalization
3. **Figure and Nscale Sign Strategic Partnership For Up to 100,000 GPUs on the NVIDIA Vera Rubin Platform**
   - `article` · `figure-68ba598f5ceb484c` · 2026-09-03 · Figure AI
   - https://www.figure.ai/news/figure-and-nscale-sign-strategic-partnership
4. **Introducing Index: Building The World’s Largest and Most Diverse Physical Dataset**
   - `article` · `figure-04b4433654fb4020` · 2026-08-25 · Figure AI
   - https://www.figure.ai/news/introducing-index

## Figure AI 官方动态

`sourceId=official-figure-ai` · 还需审核 `20` 条 · `sampleDigest=093bd0070133b59f`

当前没有可追溯的精确匹配记录。

## Form Energy 官方动态

`sourceId=official-form-energy` · 还需审核 `20` 条 · `sampleDigest=d9c4551b498f3333`

1. **Form Energy Announces Closing of $270M Credit Facility**
   - `article` · `official-form-energy-199103653ab491e0` · 2026-09-21 · Form Energy
   - https://formenergy.com/form-energy-announces-closing-of-270m-credit-facility
2. **Form Energy Launches Technician Hiring Sprint In Weirton, WV**
   - `article` · `official-form-energy-7f5377b6174512b9` · 2026-09-09 · Form Energy
   - https://formenergy.com/form-energy-launches-technician-hiring-sprint-in-weirton-wv
3. **Form Energy Secures $750M in Series G Financing to Scale Iron-Air Battery Manufacturing and Accelerate Commercial Deployments**
   - `article` · `official-form-energy-e4f632a601abe7eb` · 2026-08-12 · Form Energy
   - https://formenergy.com/form-energy-secures-750m-in-series-g-financing

## Founders Fund · 核心团队页

`sourceId=user-source-source-auto-institution-team-founders-fund` · 还需审核 `20` 条 · `sampleDigest=72a885255cad56d1`

当前没有可追溯的精确匹配记录。

## Glean 官方动态

`sourceId=official-glean` · 还需审核 `20` 条 · `sampleDigest=8955a0c76b81e41a`

当前没有可追溯的精确匹配记录。

## Google AI

`sourceId=google-ai-blog` · 还需审核 `20` 条 · `sampleDigest=9b967beee416de91`

1. **Our newest AI Quest: Mapping the human brain**
   - `article` · `google-ai-blog-9a15b40232fdbf82` · 2026-10-26 · Google
   - https://blog.google/products-and-platforms/products/education/ai-quests-polar-peaks
2. **Introducing Playground: Create and play custom games**
   - `article` · `google-ai-blog-e04d1da693503b0f` · 2026-10-07 · Google
   - https://blog.google/innovation-and-ai/technology/ai/playground-experimental-gaming-platform
3. **The latest AI news we announced in September 2026**
   - `article` · `google-ai-blog-aacb8ca8a4a96bc0` · 2026-10-02 · Google
   - https://blog.google/innovation-and-ai/technology/ai/google-ai-updates-september-2026
4. **New experts join Google’s AI & Economy team**
   - `article` · `google-ai-blog-2ad49dd9b65fe3ae` · 2026-09-18 · Google
   - https://blog.google/innovation-and-ai/technology/ai/expanding-ai-economy-research-bench
5. **AI for Societal Impact**
   - `article` · `google-ai-blog-dfe2f7f06070ffbc` · 2026-09-15 · Google
   - https://blog.google/innovation-and-ai/technology/ai/ai-for-societal-impact
6. **AI for everyone in every language**
   - `article` · `google-ai-blog-7a00acf92df0c96e` · 2026-09-15 · Google
   - https://blog.google/innovation-and-ai/technology/ai/ai-for-every-language
7. **New insights from Google’s AI & Economy ATLAS**
   - `article` · `google-ai-blog-64730bcdfc3a3522` · 2026-09-15 · Google
   - https://blog.google/innovation-and-ai/technology/ai/ai-economy-atlas-september-2026
8. **Building AI to accelerate science and improve lives**
   - `article` · `google-ai-blog-419a0d7bd8653188` · 2026-09-15 · Google
   - https://blog.google/innovation-and-ai/technology/ai/ai-applications-science-people
9. **Get ready for the game with new football features in Search**
   - `article` · `google-ai-blog-77adb66885449411` · 2026-09-09 · Google
   - https://blog.google/products-and-platforms/products/search/football-features-google-search
10. **Proactive cyber defense for governments and enterprises**
   - `article` · `google-ai-blog-445c9f3e3d31d266` · 2026-09-02 · Google
   - https://blog.google/innovation-and-ai/technology/safety-security/fairwind-program

## Google DeepMind

`sourceId=deepmind-blog` · 还需审核 `20` 条 · `sampleDigest=fd645dd7032ef172`

1. **Google DeepMind and Singapore Government collaborate to build fine-tuned AI model for scam detection**
   - `article` · `google-deepmind-b76b11a1199f73b7` · 2026-10-14 · Google
   - https://deepmind.google/blog/on-device-ai-scam-detection-mddi
2. **Introducing SynthID Bio**
   - `article` · `google-deepmind-08aa8115cb5d9c89` · 2026-09-30 · Google
   - https://deepmind.google/blog/introducing-synthid-bio
3. **Introducing Gemini 3.8 Live with Live Avatar**
   - `article` · `deepmind-blog-6add3dd62456569f` · 2026-09-24 · Google
   - https://deepmind.google/blog/introducing-gemini-38-live-with-live-avatar
4. **Advancing Private AI Compute with secure, server-side memory**
   - `article` · `google-deepmind-1043d9fe80283e6f` · 2026-09-23 · Google
   - https://deepmind.google/blog/advancing-private-ai-compute-with-secure-server-side-memory
5. **Introducing Gemini 3.8 Live and 3.8 Live Extended Thinking**
   - `article` · `deepmind-blog-6aae488b1bb65e59` · 2026-09-15 · Google
   - https://deepmind.google/blog/introducing-gemini-3-8-live-and-3-8-live-extended-thinking
6. **Introducing WeatherNext 3, our most advanced and accurate global weather AI model**
   - `article` · `deepmind-blog-d5ea4bcadd66b1af` · 2026-09-03 · Google
   - https://deepmind.google/blog/introducing-weathernext-3-our-most-advanced-and-accurate-global-weather-ai-model
7. **Introducing Gemini 3.8 Flash and 3.8 Flash Cyber**
   - `article` · `deepmind-blog-355be2cf6d2d139c` · 2026-09-02 · Google
   - https://deepmind.google/blog/introducing-gemini-3-8-flash-and-38-flash-cyber
8. **Introducing agentic video understanding with Gemini**
   - `article` · `deepmind-blog-6bf5b05134dd23a6` · 2026-09-01 · Google
   - https://deepmind.google/blog/introducing-agentic-video-in-gemini
9. **Piloting the world's first double-blind AI evaluations**
   - `article` · `deepmind-blog-f0dc85dcc6d3444f` · 2026-08-27 · Google
   - https://deepmind.google/blog/piloting-the-worlds-first-double-blind-ai-evaluations
10. **From Atari to EVE Online: Building on 15 Years of AI Research in Games**
   - `article` · `deepmind-blog-76900827bd8bbfff` · 2026-08-21 · Google
   - https://deepmind.google/blog/from-atari-to-eve-online-building-on-15-years-of-ai-research-in-games

## Google DeepMind

`sourceId=google-deepmind` · 还需审核 `20` 条 · `sampleDigest=dd7d2a346ca681fb`

1. **Genie 4: A new generation of world simulation**
   - `article` · `google-deepmind-e960e8891f7d7ad8` · 2026-10-27 · Google
   - https://deepmind.google/blog/genie-4-a-new-generation-of-world-simulation
2. **Google Antigravity: Accelerating Antimicrobial Peptide Search**
   - `article` · `official-google-3b88e63140868036` · 2026-10-15 · Google
   - https://deepmind.google/blog/accelerating-antimicrobial-discovery
3. **AlphaGenome Atlas: Molecular predictions for 9 Billion human DNA variants**
   - `article` · `google-deepmind-825546b9e9e150a7` · 2026-09-08 · Google
   - https://deepmind.google/blog/alphagenome-atlas-a-predictive-map-of-every-possible-dna-letter-change-in-the-human-genome

## Google DeepMind

`sourceId=user-x-googledeepmind` · 还需审核 `20` 条 · `sampleDigest=f95c2c226130e391`

1. **Google DeepMind：RT @a_ron_saunders: While most jack-o-lanterns just sit on porches, the @GoogleDeepMind team decided to let AI agents design, simulate, and…**
   - `article` · `user-x-googledeepmind-b4052d368f6a8fb3` · 2026-10-31 · 科技产业
   - https://x.com/GoogleDeepMind/status/2116567624310251711
2. **Google DeepMind：We built PlanAssist to help UK Government planning officers speed up building and renovations across the country. Built with Gemini, it has shown it c**
   - `article` · `user-x-googledeepmind-ad7958d08cba14d6` · 2026-10-31 · 科技产业
   - https://x.com/GoogleDeepMind/status/2116524000977285321
3. **Google DeepMind：Carbon can work through complex tasks for days without getting stuck or taking shortcuts – delivering high-quality, reliable code. Feedback from an in**
   - `article` · `user-x-googledeepmind-ff8f9c488d9ea68e` · 2026-10-28 · 科技产业
   - https://x.com/GoogleDeepMind/status/2115489359415890211
4. **Google DeepMind：Gemini 4 Carbon is our next frontier model. It’s state-of-the-art across cybersecurity and long-horizon capabilities. https://t.co/o7lmCE1ggD**
   - `article` · `user-x-googledeepmind-03975e8c91dee7f1` · 2026-10-28 · 科技产业
   - https://x.com/GoogleDeepMind/status/2115489356437651654
5. **Google DeepMind：This is Genie 4, our most realistic and interactive world model yet. 🌐 Explore dynamic environments in real time to see how the scene responds, sounds**
   - `article` · `user-x-googledeepmind-efd8020db3f5babf` · 2026-10-27 · 科技产业
   - https://x.com/GoogleDeepMind/status/2115114028338962672

## Google 官方动态

`sourceId=official-google` · 还需审核 `20` 条 · `sampleDigest=d3ab2de1f60c4c51`

当前没有可追溯的精确匹配记录。

## Google 官方动态

`sourceId=official-user-google` · 还需审核 `20` 条 · `sampleDigest=7f5249f68ce29d5c`

当前没有可追溯的精确匹配记录。

## Google 官方网站

`sourceId=user-source-source-auto-google` · 还需审核 `20` 条 · `sampleDigest=c72519a0258f039a`

当前没有可追溯的精确匹配记录。

## Groq 官方动态

`sourceId=official-groq` · 还需审核 `20` 条 · `sampleDigest=cba6fb32c971d9cb`

1. **Meta's Muse Spark open-weight release Is Now in Limited Preview on GroqCloud**
   - `article` · `official-groq-28190cbcfc36a505` · 2026-10-15 · Groq
   - https://groq.com/blog/meta-s-muse-spark-open-release-is-now-in-limited-preview-on-groqcloud
2. **Groq Among the First to Bring NVIDIA Groq 3 LPX and Vera Rubin NVL72 to Market**
   - `article` · `official-groq-cac40f498bb1fa5b` · 2026-08-24 · Groq
   - https://groq.com/blog/groq-among-the-first-to-bring-nvidia-groq-3-lpx-and-vera-rubin-nvl72-to-market
3. **Groq Closes $350 million Series A, Building the World's Leading AI Inference Cloud**
   - `article` · `official-groq-c02f2ac04f9320df` · 2026-08-17 · Groq
   - https://groq.com/newsroom/groq-closes-usd350-million-series-a-building-the-world-s-leading-ai-inference-cloud
4. **Groq Becomes an NVIDIA Cloud Partner**
   - `article` · `official-groq-93d89086e538e1ab` · 2026-08-12 · Groq
   - https://groq.com/newsroom/groq-becomes-an-nvidia-cloud-partner

## Harvey 官方动态

`sourceId=official-harvey` · 还需审核 `20` 条 · `sampleDigest=98b2fd767dacd191`

1. **How We Made Review Tables Faster and More Reliable**
   - `article` · `official-harvey-36491c3e4d001313` · 2026-10-22 · Harvey
   - https://www.harvey.ai/blog/making-review-tables-faster-and-more-reliable
2. **How Harvey is Building a Frontier Marketing Org**
   - `article` · `official-harvey-0ef82b75eba5c875` · 2026-10-21 · Harvey
   - https://www.harvey.ai/blog/how-harvey-is-building-a-frontier-marketing-org
3. **Build and Update Review Tables With the Harvey Agent**
   - `article` · `official-harvey-85a463c96347c227` · 2026-09-17 · Harvey
   - https://www.harvey.ai/blog/review-table-agent-actions
4. **Harvey Tenet Research Preview**
   - `article` · `official-harvey-4e6bdb0d82198725` · 2026-08-20 · Harvey
   - https://www.harvey.ai/blog/post-training-update-harvey-tenet

## Helion Energy 官方动态

`sourceId=official-helion` · 还需审核 `20` 条 · `sampleDigest=4b42e30c7a257aec`

1. **Inside Helion's capacitor manufacturing line**
   - `article` · `official-helion-b84aeea40930fae1` · 2026-10-16 · Helion Energy
   - https://www.helionenergy.com/blog/inside-helions-capacitor-manufacturing-line
2. **Building the foundations for fusion at scale**
   - `article` · `official-helion-0a139255a7eb88ec` · 2026-09-29 · Helion Energy
   - https://www.helionenergy.com/blog/building-the-foundations-for-fusion-at-scale
3. **Does fusion produce radiation?**
   - `article` · `official-helion-df2f06440fad1829` · 2026-09-04 · Helion Energy
   - https://www.helionenergy.com/blog/does-fusion-produce-radiation

## Horizon3 官方动态

`sourceId=official-horizon3` · 还需审核 `20` 条 · `sampleDigest=d9e66509933081f0`

1. **NodeZero Integration With Cortex XSOAR**
   - `article` · `official-horizon3-0d1d143ca8c58acd` · 2026-10-27 · Horizon3
   - https://horizon3.ai/news/press-release/nodezero-integration-palo-alto-networks-cortex-xsoar
2. **Horizon3 Surpasses $100 Million ARR with 120%+ Growth**
   - `article` · `official-horizon3-e24e96eef01d2a65` · 2026-10-20 · Horizon3
   - https://horizon3.ai/news/press-release/horizon3-surpasses-100-million-arr
3. **Horizon3 Expands in Singapore with EDBI and SG Growth Capital**
   - `article` · `official-horizon3-9f7b039a6bdc331b` · 2026-10-20 · Horizon3
   - https://horizon3.ai/news/press-release/horizon3-singapore-expansion-asean-headquarters
4. **Horizon3 and Pax8 Bring NodeZero to MSPs Across Europe**
   - `article` · `official-horizon3-e1020e7fe3f1121e` · 2026-10-16 · Horizon3
   - https://horizon3.ai/news/press-release/horizon3-pax8-partnership-expansion-europe
5. **Horizon3 Promotes Keith Poyser to General Manager, EMEA**
   - `article` · `official-horizon3-59ee07cd75732725` · 2026-10-15 · Horizon3
   - https://horizon3.ai/news/press-release/keith-poyser-general-manager-emea-horizon3
6. **Horizon3 Promotes Ellen Sundra to Chief Customer Officer**
   - `article` · `official-horizon3-3df04739f8badd8f` · 2026-10-15 · Horizon3
   - https://horizon3.ai/news/press-release/ellen-sundra-chief-customer-officer-horizon3

## Intuitive Surgical 官方动态

`sourceId=official-intuitive-surgical` · 还需审核 `20` 条 · `sampleDigest=cd4a83be056a83fc`

1. **New meta-analysis shows statistically significant improvements in patient outcomes associated with da Vinci surgery versus laparoscopic and open surgery across 13 common benign conditions**
   - `article` · `official-intuitive-surgical-f98aca3be43d0c7b` · 2026-09-08 · Intuitive Surgical
   - https://isrg.intuitive.com/news-releases/news-release-details/new-meta-analysis-shows-statistically-significant-improvements

## IonQ

`sourceId=ionq` · 还需审核 `20` 条 · `sampleDigest=b70561b130c8cf65`

1. **IonQ Secures $7.5M AFRL Award for Quantum Network Expansion**
   - `article` · `ionq-8b420aec2ba8afa1` · 2026-10-27 · IonQ
   - https://ionq.com/news/ionq-awarded-7-5-million-follow-on-funding-from-afrl-to-advance-full-stack-quantum-networking
2. **IonQ Opens First Quantum Innovation Centre at Cambridge**
   - `article` · `ionq-f2bb83de4aa4b0c3` · 2026-10-15 · IonQ
   - https://ionq.com/news/ionq-and-the-university-of-cambridge-open-the-ionq-quantum-innovation-centre-at-cavendish-laboratorys-ray-dolby-centre
3. **IonQ to Acquire Elisity for $1.3B to Advance Quantum Security**
   - `article` · `ionq-111cf26e142c6e33` · 2026-10-12 · IonQ
   - https://ionq.com/news/ionq-to-acquire-elisity-to-accelerate-zero-trust-for-the-quantum-era
4. **IonQ Achieves Record 1 kHz Quantum Interconnect Speed**
   - `article` · `ionq-d6a031743c9de9fb` · 2026-10-09 · IonQ
   - https://ionq.com/news/ionq-demonstrates-world-first-quantum-memory-enhanced-interconnect-for-distributed-quantum-applications
5. **IonQ Advances to DARPA QBI Stage C in $300M Agreement**
   - `article` · `ionq-c7f214680abba010` · 2026-10-07 · IonQ
   - https://ionq.com/news/ionq-advances-to-final-stage-of-darpas-quantum-benchmarking-initiative
6. **FIU Secures Florida’s First IonQ Superion Quantum System**
   - `article` · `ionq-3ada0a6f08048c2e` · 2026-09-24 · IonQ
   - https://ionq.com/news/ionqs-superion-256-platform-selected-by-florida-international-university-for-flagship-deployment
7. **IonQ Superion 256 to Power NVIDIA Quantum Research Center**
   - `article` · `ionq-6a80c6850a63732f` · 2026-09-23 · IonQ
   - https://ionq.com/news/ionq-to-advance-quantum-supercomputing-by-bringing-first-qpu-to-nvidia-accelerated-quantum-research-center
8. **IonQ Breakthrough: CPU-Powered Quantum Error Correction**
   - `article` · `ionq-fa39c641d66b0169` · 2026-09-22 · IonQ
   - https://ionq.com/news/ionq-demonstrates-industrys-first-end-to-end-real-time-quantum-error-decoder
9. **IonQ and SDT Announce the First Strategic Partnership to Bring Both Advanced Quantum Computing and Quantum Networking to the Asia-Pacific Region**
   - `article` · `ionq-fc8f4f7211fb881a` · 2026-09-21 · IonQ
   - https://ionq.com/news/ionq-and-sdt-announce-the-first-strategic-partnership-to-bring-both-advanced-quantum-computing-and-quantum-networking-to-the-asia-pacific-region

## IonQ 官方动态

`sourceId=official-ionq` · 还需审核 `20` 条 · `sampleDigest=85ba6807c3d6b20b`

当前没有可追溯的精确匹配记录。

## Joby Aviation 官方动态

`sourceId=official-joby` · 还需审核 `20` 条 · `sampleDigest=cbace9f204ffff47`

1. **Joby Aviation to Report Third Quarter 2026 Financial Results**
   - `article` · `official-joby-506250a8381776a5` · 2026-10-15 · Joby Aviation
   - https://www.jobyaviation.com/news/joby-aviation-to-report-third-quarter-2026-financial-results
2. **Blade’s BLADEone Enhanced Jet Service Returns with Flights between the New York City area and South Florida, in Partnership with Aero**
   - `article` · `official-joby-98c280fed73b7b1d` · 2026-10-02 · Joby Aviation
   - https://www.jobyaviation.com/news/blades-bladeone-enhanced-jet-service-returns-with-flights-between-the-new-york-city-area-and-south-florida-in-partnership-with-aero
3. **Joby Completes First-Ever Fully Autonomous Flight Across the United States**
   - `article` · `official-joby-408a225b57323ad3` · 2026-09-18 · Joby Aviation
   - https://www.jobyaviation.com/news/joby-completes-first-ever-fully-autonomous-flight-across-the-united-states

## Kleiner Perkins · 核心团队页

`sourceId=user-source-source-auto-institution-team-kleiner-perkins` · 还需审核 `20` 条 · `sampleDigest=f7fee307e61af721`

当前没有可追溯的精确匹配记录。

## Lazada 官方动态

`sourceId=official-user-lazada` · 还需审核 `20` 条 · `sampleDigest=38e572c3a964fe5b`

当前没有可追溯的精确匹配记录。

## Lazada 官方网站

`sourceId=user-source-source-auto-lazada` · 还需审核 `20` 条 · `sampleDigest=a6f8710377754f07`

当前没有可追溯的精确匹配记录。

## Lightspeed Venture Partners · 核心团队页

`sourceId=user-source-source-auto-institution-team-lightspeed-venture-partners` · 还需审核 `20` 条 · `sampleDigest=98cff7d33f01cce9`

当前没有可追溯的精确匹配记录。

## Manifold Bio 官方动态

`sourceId=official-manifold-bio` · 还需审核 `20` 条 · `sampleDigest=966ef5f3a286c540`

1. **mBER-2: Scaling AI Protein Design to Learn from Living Systems | Manifold Bio News**
   - `article` · `official-manifold-bio-5d9002509349cf43` · 2026-09-22 · Manifold Bio
   - https://www.manifold.bio/news/mber-2-scaling-ai-protein-design-to-learn-from-living-systems

## MiniMax

`sourceId=minimax` · 还需审核 `20` 条 · `sampleDigest=e1517be14d06cdb7`

当前没有可追溯的精确匹配记录。

## MiniMax 官方动态

`sourceId=official-minimax` · 还需审核 `20` 条 · `sampleDigest=82b89403d90df10c`

1. **MiniMax M3.1 Flash：重新定义 Agent 的性能与成本 - MiniMax Research**
   - `article` · `official-minimax-52a6db02c82060ba` · 2026-10-19 · MiniMax
   - https://www.minimax.cn/blog/minimax-m31f
2. **MiniMax Music 3.0：新一代开放权重、生产级全能音乐模型 - MiniMax Research**
   - `article` · `official-minimax-31f1c996080f5d7c` · 2026-08-13 · MiniMax
   - https://www.minimax.cn/blog/minimax-music-3-0-cn

## Mobileye 官方动态

`sourceId=official-mobileye` · 还需审核 `20` 条 · `sampleDigest=7c09e66fc7b197ee`

当前没有可追溯的精确匹配记录。

## Modular 官方动态

`sourceId=official-modular` · 还需审核 `20` 条 · `sampleDigest=1d5daf074c545e47`

1. **Modular: MAX is now source available and open to everyone**
   - `article` · `official-modular-b723b45de297f4ab` · 2026-10-22 · Modular
   - https://www.modular.com/blog/max-license
2. **Modular: Modular 26.7: Opening up MAX**
   - `article` · `official-modular-78416e55b7ddb987` · 2026-10-22 · Modular
   - https://www.modular.com/blog/26-7
3. **Modular: Nurturing the Modular ecosystem: the Modular Community Grant Program**
   - `article` · `official-modular-831bf35072658226` · 2026-10-21 · Modular
   - https://www.modular.com/blog/nurturing-the-modular-ecosystem-the-modular-community-grant-program
4. **Modular: Modular and Qualcomm: Same code, new silicon**
   - `article` · `official-modular-b1a3e876e3a08fda` · 2026-08-18 · Modular
   - https://modular.com/blog/modcon-qualcomm
5. **Modular: Mojo🔥 is now open source!**
   - `article` · `official-modular-2d0194a0df57864b` · 2026-08-18 · Modular
   - https://modular.com/blog/mojo-open-source
6. **Modular: Modular 26.5: Mojo 1.0 is here!**
   - `article` · `official-modular-d90b2d52a09c655a` · 2026-08-11 · Modular
   - https://www.modular.com/blog/modular-26-5-mojo-1-0-is-here

## OLIX 官方动态

`sourceId=official-olix` · 还需审核 `20` 条 · `sampleDigest=773351a227b7fdc9`

1. **Scaling, Shortage, Salvation: Why AI Must Go Optical**
   - `article` · `official-olix-29ea083acd96d054` · 2026-08-20 · OLIX
   - https://olix.com/blog/scaling-shortage-salvation-why-ai-must-go-optical

## Omilia 官方动态

`sourceId=official-omilia` · 还需审核 `20` 条 · `sampleDigest=efdcfbb249cf6955`

1. **From Know-Your-Customer to Know-Their-Agent**
   - `article` · `official-omilia-c3690b41d4e286da` · 2026-10-15 · Omilia
   - https://omilia.com/resources/blog/from-know-your-customer-to-know-their-agent
2. **Omilia Appoints David Stone as Head of Asia-Pacific**
   - `article` · `official-omilia-4faedbaf4371f1aa` · 2026-09-28 · Omilia
   - https://omilia.com/resources/news/omilia-appoints-david-stone-as-head-of-asia-pacific
3. **IDC MarketScape 2026 | Vendor Assessment Report**
   - `article` · `official-omilia-ee16b1d3c30bc5c2` · 2026-09-25 · Omilia
   - https://omilia.com/resources/analyst-reports/leader-in-idc-marketscape-worldwide-conversational-intelligence-analytics-software-2026

## OpenAI

`sourceId=openai` · 还需审核 `20` 条 · `sampleDigest=bdfed0456726ca1b`

1. **Our approach to EU text provenance rules**
   - `article` · `openai-d2b5b29b4c815525` · 2026-10-08 · OpenAI
   - https://openai.com/index/eu-text-provenance
2. **A model guide for the GPT-6 family**
   - `article` · `openai-c38af6e5cae43e23` · 2026-10-07 · OpenAI
   - https://openai.com/index/practical-guide-building-gpt-6
3. **GPT-6 and Intelligent UI for everyone**
   - `article` · `openai-a097ef0d441a7216` · 2026-10-07 · OpenAI
   - https://openai.com/index/gpt-6-for-everyone
4. **Atlassian and OpenAI expand partnership to turn enterprise knowledge into action**
   - `article` · `openai-2896758265cec81d` · 2026-10-01 · OpenAI
   - https://openai.com/index/atlassian-partnership

## OpenAI

`sourceId=x-openai` · 还需审核 `20` 条 · `sampleDigest=8a8de2000f0aed42`

1. **OpenAI：There are many futures. Which do you want to build? https://t.co/19NY7tgPHM**
   - `article` · `x-openai-e2871d1f7fe5cda0` · 2026-10-30 · OpenAI
   - https://x.com/OpenAI/status/2116253388883345623
2. **OpenAI：Privacy should advance as fast as intelligence. OpenAI Private Intelligence gives businesses stronger controls over their data while using our most ca**
   - `article` · `x-openai-26a5526074ab2ec4` · 2026-10-30 · OpenAI
   - https://x.com/OpenAI/status/2116186509384815084
3. **OpenAI：Today, we’re sharing a look at our expanded system for monitoring frontier models at OpenAI, which in September helped us catch a model’s attempt to a**
   - `article` · `x-openai-da646989d5ab7cbe` · 2026-10-29 · OpenAI
   - https://x.com/OpenAI/status/2115896329645723836
4. **OpenAI：RT @thsottiaux: Day 25/ We are doubling all usage limits for all Pro 100/200/500 tiers and Business Premium, effective today. We heard yo…**
   - `article` · `x-openai-2e9fb4871b47d5c9` · 2026-10-29 · OpenAI
   - https://x.com/OpenAI/status/2115854368566321594
5. **OpenAI：GPT-6.1 Terra: delivering fast and capable computer use at a lower price. GPT-6.1 Terra understands what’s on screen, takes action across apps, writes**
   - `article` · `x-openai-eb8b42b95c851c43` · 2026-10-26 · OpenAI
   - https://x.com/OpenAI/status/2114780711664398349

## OpenAI 官方动态

`sourceId=official-openai` · 还需审核 `20` 条 · `sampleDigest=7f56e95d68fdaff3`

1. **OpenAI Newsroom | Safety**
   - `article` · `official-openai-d2b596499ef3df4b` · 2026-09-23 · OpenAI
   - https://openai.com/news/safety-alignment
2. **OpenAI Newsroom | Research**
   - `article` · `official-openai-bfa154c0291e1b23` · 2026-09-23 · OpenAI
   - https://openai.com/news/research
3. **Product News and Updates**
   - `article` · `official-openai-ae9391e0836460dc` · 2026-09-23 · OpenAI
   - https://openai.com/news/product-releases
4. **OpenAI Newsroom | Engineering**
   - `article` · `official-openai-ab2ba528fbe2ac49` · 2026-09-11 · OpenAI
   - https://openai.com/news/engineering

## OpenAI 官方新闻

`sourceId=openai-newsroom` · 还需审核 `20` 条 · `sampleDigest=c676957bd4d6c35b`

1. **Making it easier for websites to express AI training preferences**
   - `article` · `openai-newsroom-84abd1857de5dfd9` · 2026-10-30 · OpenAI
   - https://openai.com/index/helping-websites-express-ai-training-preferences
2. **Fair use benefits everyone**
   - `article` · `openai-newsroom-574dbaf7fc8731e4` · 2026-10-30 · OpenAI
   - https://openai.com/index/fair-use-benefits-everyone
3. **How Ropes & Gray is developing AI for transactional diligence**
   - `article` · `openai-newsroom-d948735545c20cf3` · 2026-10-29 · OpenAI
   - https://openai.com/index/ropes-gray-ai-diligence
4. **An updated Model Spec for more capable and beneficial AI**
   - `article` · `openai-newsroom-9349f418e7bc7ab4` · 2026-10-29 · OpenAI
   - https://openai.com/index/updated-model-spec
5. **How we detect frontier model misalignment**
   - `article` · `openai-newsroom-0f01adb2acab0a67` · 2026-10-29 · OpenAI
   - https://openai.com/index/how-we-detect-frontier-model-misalignment
6. **The future of the firm**
   - `article` · `openai-newsroom-e2ed7680c50ae3f0` · 2026-10-28 · OpenAI
   - https://openai.com/index/the-future-of-the-firm
7. **OpenAI and ServiceNow expand partnership across enterprise workflows**
   - `article` · `openai-newsroom-a395c7da350b5086` · 2026-10-28 · OpenAI
   - https://openai.com/index/openai-servicenow-partnership-expansion
8. **OpenAI expands partnership with Oracle to bring its apps to ChatGPT**
   - `article` · `openai-newsroom-c417f8e3d39d0b89` · 2026-10-27 · OpenAI
   - https://openai.com/index/oracle-apps-in-chatgpt
9. **Retell uses OpenAI models to help power 100M monthly calls**
   - `article` · `openai-newsroom-1e3ebf94e41ebe19` · 2026-10-27 · OpenAI
   - https://openai.com/index/retell-ai
10. **GPT-6.1 Sol helps CodeRabbit strengthen security across complex codebases**
   - `article` · `openai-newsroom-7d972df501d01ba1` · 2026-10-26 · OpenAI
   - https://openai.com/index/gpt-6-1-sol-coderabbit-code-security
11. **Introducing GPT-6.1 Terra**
   - `article` · `openai-newsroom-35e334c198740f74` · 2026-10-26 · OpenAI
   - https://openai.com/index/introducing-gpt-6-1-terra
12. **OpenAI and Poland’s NASK partner to advance AI safety and security**
   - `article` · `openai-newsroom-1a543055a02f9816` · 2026-10-23 · OpenAI
   - https://openai.com/index/openai-nask-ai-safety-security-partnership
13. **Build more responsive apps with the Decisions API**
   - `article` · `openai-newsroom-891b7e0bbf66f86d` · 2026-10-22 · OpenAI
   - https://openai.com/index/decisions-api
14. **Democratic governance of frontier AI, part II: Empowering cyber defenders**
   - `article` · `openai-newsroom-e270f5ba4688033d` · 2026-10-21 · OpenAI
   - https://openai.com/index/empowering-cyber-defenders
15. **Patch the Planet: global response coordination as agents uncover critical vulnerabilities**
   - `article` · `openai-newsroom-de9db6f384cbc788` · 2026-10-21 · OpenAI
   - https://openai.com/index/coordinated-disclosure-of-critical-vulnerabilities
16. **Using thousands of AI agents to uncover new leads in biological data**
   - `article` · `openai-newsroom-64ddfb139fec8a1c` · 2026-10-21 · OpenAI
   - https://openai.com/index/scaling-ai-research-for-complex-biological-data

## Perplexity 官方动态

`sourceId=official-perplexity` · 还需审核 `20` 条 · `sampleDigest=ff22b92ab74ddce8`

当前没有可追溯的精确匹配记录。

## Pony.ai Investor Relations

`sourceId=pony-ai` · 还需审核 `20` 条 · `sampleDigest=d79c3621badcaa49`

1. **PONY AI Inc. Unveils New Gen-4 Robotruck in Collaboration with GAC Commercial Vehicle**
   - `article` · `pony-ai-f80f5ffae796c820` · 2026-09-14 · 小马智行
   - https://ir.pony.ai/news-releases/news-release-details/pony-ai-inc-unveils-new-gen-4-robotruck-collaboration-gac
2. **PONY AI Inc. and Verne Kick Off Fully Driverless Robotaxi Test Rides in Zagreb**
   - `article` · `pony-ai-f0c32afdf3619f8c` · 2026-09-10 · 小马智行
   - https://ir.pony.ai/news-releases/news-release-details/pony-ai-inc-and-verne-kick-fully-driverless-robotaxi-test-rides
3. **PONY AI Inc. Highlights Progress of Doha Robotaxi Commercial Operations at AEMOB Forum**
   - `article` · `pony-ai-fff6eb1d708505d6` · 2026-09-08 · 小马智行
   - https://ir.pony.ai/news-releases/news-release-details/pony-ai-inc-highlights-progress-doha-robotaxi-commercial

## PR Newswire Consumer Technology

`sourceId=prnewswire-tech` · 还需审核 `20` 条 · `sampleDigest=6d1895f3662f0faf`

1. **Cognizant zet meer dan 25.000 professionals in voor de implementatie van OpenAI-oplossingen nu ondernemingen geavanceerde AI in productie nemen**
   - `article` · `prnewswire-tech-cd652bf418a1a784` · 2026-11-01 · OpenAI
   - https://www.prnewswire.com/news-releases/cognizant-zet-meer-dan-25-000-professionals-in-voor-de-implementatie-van-openai-oplossingen-nu-ondernemingen-geavanceerde-ai-in-productie-nemen-302925664.html
2. **Context Labs AI Distillery™ Lets Enterprises Run Sovereign AI on Data They Own**
   - `article` · `prnewswire-tech-bfafdb44e1584fcd` · 2026-11-01 · 科技产业
   - https://www.prnewswire.com/news-releases/context-labs-ai-distillery-lets-enterprises-run-sovereign-ai-on-data-they-own-302925650.html
3. **A new way to explore Japan with AI: Naviu AR Travel Companion for Japan Launches November 1 2026**
   - `article` · `prnewswire-tech-82fb9c00f58920a4` · 2026-11-01 · 科技产业
   - https://www.prnewswire.com/news-releases/a-new-way-to-explore-japan-with-ai-naviu-ar-travel-companion-for-japan-launches-november-1-2026-302925556.html
4. **ScienceOra Demonstrates AI-Assisted Hydrogen-Production Catalyst Design Workflow at Tencent Global Digital Ecosystem Summit**
   - `article` · `prnewswire-tech-afd938da1a05aad2` · 2026-10-31 · 科技产业
   - https://www.prnewswire.com/news-releases/scienceora-demonstrates-ai-assisted-hydrogen-production-catalyst-design-workflow-at-tencent-global-digital-ecosystem-summit-302925517.html
5. **White Paper Outlining Strategies to Address Rural AI Skills Gaps and Support Workforce Retention Published by the University of Phoenix College of Doctoral Studies**
   - `article` · `prnewswire-tech-a5f43758a0b42c66` · 2026-10-31 · 科技产业
   - https://www.prnewswire.com/news-releases/white-paper-outlining-strategies-to-address-rural-ai-skills-gaps-and-support-workforce-retention-published-by-the-university-of-phoenix-college-of-doctoral-studies-302924623.html
6. **ModelBest and OpenBMB Open-Source MiniCPM-OCR Series, Delivering High-Performance Document Parsing and AI-Powered Quality Control**
   - `article` · `prnewswire-tech-9bcfb13f35c29651` · 2026-10-31 · 科技产业
   - https://www.prnewswire.com/news-releases/modelbest-and-openbmb-open-source-minicpm-ocr-series-delivering-high-performance-document-parsing-and-ai-powered-quality-control-302925594.html

## PsiQuantum 官方动态

`sourceId=official-psiquantum` · 还需审核 `20` 条 · `sampleDigest=96464ede6fd5727a`

1. **PsiQuantum Unveils Optical Circuit Switch Technology Built on Advanced, Low-Loss Silicon Photonics Platform**
   - `article` · `official-psiquantum-1858db31aa988490` · 2026-10-28 · PsiQuantum
   - https://www.psiquantum.com/news-import/psiquantum-unveils-optical-circuit-switch-technology-built-on-advanced-low-loss-silicon-photonics-platform
2. **PsiQuantum Receives Conditional $150 Million Loan Commitment from the U.S. Department of War to Advance Domestic Quantum Computing**
   - `article` · `official-psiquantum-5c37624fec866b1d` · 2026-10-08 · PsiQuantum
   - https://www.psiquantum.com/news-import/psiquantum-receives-conditional-150-million-loan-commitment-from-the-us-department-of-war
3. **PsiQuantum at IEEE Quantum Week 2026**
   - `article` · `official-psiquantum-47acda46da768caa` · 2026-09-09 · PsiQuantum
   - https://www.psiquantum.com/news-import/psiquantum-at-ieee-quantum-week-2026
4. **PsiQuantum Finalizes $100 Million Award with the U.S. Department of Commerce**
   - `article` · `official-psiquantum-cb11d91d6241ac46` · 2026-09-08 · PsiQuantum
   - https://www.psiquantum.com/news-import/psiquantum-finalizes-100-million-award-with-the-us-department-of-commerce

## Reach Capital 官方动态

`sourceId=official-reach-capital` · 还需审核 `20` 条 · `sampleDigest=fcb4ee3993598530`

1. **Help That Knows Your Home: Why We Invested in Rosie**
   - `article` · `official-reach-capital-cf6fd4f6d91d1e22` · 2026-10-20 · Reach Capital
   - https://www.reachcapital.com/resources/news/rosie-childcare-ai
2. **Announcing Rich Yang as Reach’s Newest Venture Partner**
   - `article` · `official-reach-capital-3e8a62376265cebe` · 2026-10-20 · Reach Capital
   - https://www.reachcapital.com/resources/news/rich-yang-venture-partner
3. **Investing in the Machinery of Human Judgment**
   - `article` · `official-reach-capital-a66c8835086ab07a` · 2026-10-14 · Reach Capital
   - https://www.reachcapital.com/resources/thought-leadership/human-judgment-work-ai
4. **Metabolic Health and Allergy: 2 Routes to Family-Based Pediatric Care**
   - `article` · `official-reach-capital-9ea890c7f6f03b46` · 2026-09-03 · Reach Capital
   - https://www.reachcapital.com/resources/thought-leadership/metabolic-health-allergy-family-based-pediatric-care
5. **The Family as Patient: Investing in the Next Wave of Pediatric Health**
   - `article` · `official-reach-capital-c8af80ec9148b725` · 2026-08-31 · Reach Capital
   - https://www.reachcapital.com/resources/thought-leadership/family-pediatric-health

## Recursion Pharmaceuticals 官方动态

`sourceId=official-recursion` · 还需审核 `20` 条 · `sampleDigest=840715263d0f33f5`

当前没有可追溯的精确匹配记录。

## Redwood Materials 官方动态

`sourceId=official-redwood-materials` · 还需审核 `20` 条 · `sampleDigest=326188fd424d0d8f`

1. **How Redwood is delivering energy faster and cheaper**
   - `article` · `official-redwood-materials-dfee1b4edd6f4684` · 2026-10-23 · Redwood Materials
   - https://www.redwoodmaterials.com/news/how-redwood-is-delivering-energy-faster-and-cheaper
2. **The Redwood Energy Ecosystem**
   - `article` · `official-redwood-materials-18b125d82cea6c9f` · 2026-10-14 · Redwood Materials
   - https://www.redwoodmaterials.com/news/the-redwood-energy-ecosystem
3. **Cal Lankton named Chief Operating Officer at Redwood Materials**
   - `article` · `official-redwood-materials-e50c66af8e485bb5` · 2026-09-21 · Redwood Materials
   - https://www.redwoodmaterials.com/news/cal-lankton-named-chief-operating-officer-at-redwood-materials

## Relativity Space 官方动态

`sourceId=official-relativity-space` · 还需审核 `20` 条 · `sampleDigest=29c381de752e380f`

当前没有可追溯的精确匹配记录。

## Rigetti Computing 官方动态

`sourceId=official-rigetti` · 还需审核 `20` 条 · `sampleDigest=822cf84505e8c80a`

1. **Rigetti Signs Definitive Agreement for $100M with U.S. Government to Accelerate R&D for Superconducting Quantum Computing | Rigetti & Co, LLC**
   - `article` · `official-rigetti-4c37cef1e84de925` · 2026-09-08 · Rigetti Computing
   - https://investors.rigetti.com/news-releases/news-release-details/rigetti-signs-definitive-agreement-100m-us-government-accelerate

## Rocket Lab Investor Relations

`sourceId=rocket-lab` · 还需审核 `20` 条 · `sampleDigest=37e84d65a19d6932`

1. **Rocket Lab Secures Largest-Ever Electron Commercial Deal: 20-Launch Contract for Synspective**
   - `article` · `rocket-lab-a930c8de646354b3` · 2026-09-30 · Rocket Lab
   - https://investors.rocketlabcorp.com/news-releases/news-release-details/rocket-lab-secures-largest-ever-electron-commercial-deal-20
2. **MISSION SUCCESS: Rocket Lab Launches 97th Electron Mission**
   - `article` · `rocket-lab-6e1c589a66c51a0c` · 2026-09-25 · Rocket Lab
   - https://investors.rocketlabcorp.com/news-releases/news-release-details/mission-success-rocket-lab-launches-97th-electron-mission
3. **Iridium Stockholders Approve Acquisition by Rocket Lab**
   - `article` · `rocket-lab-ed0c28b187e2d092` · 2026-09-24 · Rocket Lab
   - https://investors.rocketlabcorp.com/news-releases/news-release-details/iridium-stockholders-approve-acquisition-rocket-lab
4. **MISSION SUCCESS: Rocket Lab Launches 96th Electron Mission**
   - `article` · `rocket-lab-4f27a6a7a7ae0034` · 2026-09-19 · Rocket Lab
   - https://investors.rocketlabcorp.com/news-releases/news-release-details/mission-success-rocket-lab-launches-96th-electron-mission
5. **Rocket Lab Fully Funds Iridium Acquisition, Including Completion of $1.94 Billion ATM**
   - `article` · `rocket-lab-486509f20f401ac4` · 2026-09-15 · Rocket Lab
   - https://investors.rocketlabcorp.com/news-releases/news-release-details/rocket-lab-fully-funds-iridium-acquisition-including-completion
6. **Rocket Lab Successfully Launches 16th Electron Mission Of The Year, Solidifies Status as World’s Leading Small Launch Provider**
   - `article` · `rocket-lab-f254d91e1cab360b` · 2026-09-11 · Rocket Lab
   - https://investors.rocketlabcorp.com/news-releases/news-release-details/rocket-lab-successfully-launches-16th-electron-mission-year
7. **Rocket Lab Introduces High-Efficiency Solar Cell to Reduce Reliance on Supply-Constrained Critical Minerals**
   - `article` · `rocket-lab-6c090fe614901594` · 2026-09-08 · Rocket Lab
   - https://investors.rocketlabcorp.com/news-releases/news-release-details/rocket-lab-introduces-high-efficiency-solar-cell-reduce-reliance
8. **MISSION SUCCESS: Rocket Lab Launches 94th Electron Mission**
   - `article` · `rocket-lab-cb37be58fd2979f6` · 2026-09-02 · Rocket Lab
   - https://investors.rocketlabcorp.com/news-releases/news-release-details/mission-success-rocket-lab-launches-94th-electron-mission

## Rocket Lab 官方动态

`sourceId=official-rocket-lab` · 还需审核 `20` 条 · `sampleDigest=77724e934eaa73a4`

当前没有可追溯的精确匹配记录。

## SambaNova Systems 官方动态

`sourceId=official-sambanova` · 还需审核 `20` 条 · `sampleDigest=16953aa327a5ffe8`

1. **MiniMax M3.1 Flash Now Available on SambaCloud**
   - `article` · `official-sambanova-f742df6a4c5f9066` · 2026-10-24 · SambaNova Systems
   - https://sambanova.ai/blog/minimax-m3.1-flash-now-available-on-sambacloud

## Scale AI

`sourceId=scale-ai` · 还需审核 `20` 条 · `sampleDigest=0563ca0e6587836d`

1. **Developed with UMSL and Lindbergh Schools, the new program advances Scale's White House commitment to help train 1,000 teachers and equip 500,000 students with AI skills by 2029.**
   - `article` · `scale-ai-2f6624d28db9fe00` · 2026-10-30 · Scale AI
   - https://scale.com/blog/ai-literacy-microcredential-launch
2. **DualChem: Evaluating AI Safety in Dual-Use Chemistry**
   - `article` · `scale-ai-abc825f73a91a01a` · 2026-10-28 · Scale AI
   - https://scale.com/blog/dualchem-evaluating-ai-models-dual-use-chemistry-risks
3. **Scale Expands in Qatar With a Long-Term Home at The Pearl**
   - `article` · `scale-ai-65a4224ed91e84d8` · 2026-10-28 · Scale AI
   - https://scale.com/blog/scales-long-term-investment-in-qatar
4. **Scale Is Open for Business in the UAE**
   - `article` · `scale-ai-cec2751441069dcb` · 2026-10-26 · Scale AI
   - https://scale.com/blog/scale-in-uae

## Scale AI 官方动态

`sourceId=official-scale-ai` · 还需审核 `20` 条 · `sampleDigest=2f665fc1199b43e5`

当前没有可追溯的精确匹配记录。

## Shield AI 官方动态

`sourceId=official-shield-ai` · 还需审核 `20` 条 · `sampleDigest=3f3c717c9233392b`

1. **X-BAT for Europe: A Conversation with Former RAF Typhoon Pilot Andrew “Geeky” Hawkes**
   - `article` · `official-shield-ai-b87f179fb39211af` · 2026-10-29 · Shield AI
   - https://shield.ai/x-bat-for-europe-a-conversation-with-former-raf-typhoon-pilot-andrew-geeky-hawkes
2. **Shield AI and Rheinmetall Barzan Advanced Technologies to advance autonomy for ISR on Qatari Unmanned Surface Vessels (USVs)**
   - `article` · `official-shield-ai-f8251f0ea8df8da0` · 2026-10-28 · Shield AI
   - https://shield.ai/shield-ai-and-rheinmetall-barzan-advanced-technologies-to-advance-autonomy-for-isr-on-qatari-unmanned-surface-vessels-usvs

## Shopify 官方动态

`sourceId=official-shopify` · 还需审核 `20` 条 · `sampleDigest=f2fdedcdb46f85b5`

1. **What makes Shopify more than software: Fall '26 Edition**
   - `article` · `official-shopify-709109ffa23517f1` · 2026-10-29 · Shopify
   - https://www.shopify.com/news/fall-26-edition-feature
2. **Exponential: Shopify's Fall '26 Edition**
   - `article` · `official-shopify-5dd8eebbfb3bc639` · 2026-10-28 · Shopify
   - https://www.shopify.com/news/fall-26-edition-merchant
3. **Bringing shopping into the future: The Fall '26 Edition for developers**
   - `article` · `official-shopify-181904615f66410a` · 2026-10-28 · Shopify
   - https://www.shopify.com/news/fall-26-edition-developer
4. **Introducing Canvas: Opening the aperture on online store design**
   - `article` · `official-shopify-a88fdd5e12e85060` · 2026-10-01 · Shopify
   - https://www.shopify.com/news/introducing-canvas

## Shopify 官方动态

`sourceId=official-user-shopify` · 还需审核 `20` 条 · `sampleDigest=c5de1fb0e02dc3a7`

当前没有可追溯的精确匹配记录。

## Shopify 官方网站

`sourceId=user-source-source-auto-shopify` · 还需审核 `20` 条 · `sampleDigest=2ddbee055a110ae8`

当前没有可追溯的精确匹配记录。

## Sierra 官方动态

`sourceId=official-sierra` · 还需审核 `20` 条 · `sampleDigest=d4f3869695b488d4`

当前没有可追溯的精确匹配记录。

## SpaceX

`sourceId=spacex` · 还需审核 `20` 条 · `sampleDigest=e78bdebae031095b`

当前没有可追溯的精确匹配记录。

## SpaceX 官方动态

`sourceId=official-spacex` · 还需审核 `20` 条 · `sampleDigest=2ee599802d278cc1`

1. **SpaceX - Investor Relations**
   - `article` · `official-spacex-f0595d205f836407` · 2026-10-20 · SpaceX
   - https://ir.spacex.com/investors/default.aspx
2. **SpaceX - Stock Information**
   - `article` · `official-spacex-588b60530c989fb8` · 2026-10-20 · SpaceX
   - https://ir.spacex.com/stock-information/default.aspx

## Tempus AI 官方动态

`sourceId=official-tempus-ai` · 还需审核 `20` 条 · `sampleDigest=a6111d51beea3380`

当前没有可追溯的精确匹配记录。

## The Washington Post

`sourceId=user-source-source-the-washington-post` · 还需审核 `20` 条 · `sampleDigest=e5f6b95e3e285dd3`

1. **The Washington Post：Ukrainian President Volodymyr Zelensky welcomed a U.S. deal for Kyiv to purchase $2.1 billion in Patriot missiles but pressed Washington to allow soon**
   - `article` · `user-source-source-the-washington-post-f7bc04ceac87b416` · 2026-10-31 · 科技产业
   - https://x.com/washingtonpost/status/2116647707422949519
2. **The Washington Post：Democratic nominee Troy Jackson and Republican Sen. Susan Collins. are locked in one of the year’s tightest and most expensive races. Read more: https**
   - `article` · `user-source-source-the-washington-post-ed4ed8ac04d2fdcf` · 2026-10-31 · 科技产业
   - https://x.com/washingtonpost/status/2116666621150335481
3. **The Washington Post：New York Judge Jennifer L. Rochon blocked the Trump administration from airing three ads that a lawsuit alleged violated restrictions on using taxpaye**
   - `article` · `user-source-source-the-washington-post-e5118fb7ada82a3c` · 2026-10-31 · 科技产业
   - https://x.com/washingtonpost/status/2116643886315474992
4. **The Washington Post：Frustrations with President Trump are spreading in deeply red territories home to agriculture. Oklahoma has emerged as one of the most surprising late**
   - `article` · `user-source-source-the-washington-post-aeb97b95c7e3e883` · 2026-10-31 · 科技产业
   - https://x.com/washingtonpost/status/2116636367853699394
5. **The Washington Post：As any spooky history tour guide will tell you, D.C. is no stranger to the supernatural. The only problem? Not all of the stories are true. We researc**
   - `article` · `user-source-source-the-washington-post-ac6e1b71f2bfe051` · 2026-10-31 · 科技产业
   - https://x.com/washingtonpost/status/2116674091734184122
6. **The Washington Post：President Trump agreed to grant a visa to the mother of a 15-year-old boy who was fatally shot on his way to school, allowing her to travel to New Yor**
   - `article` · `user-source-source-the-washington-post-4b082f87b47e6ad9` · 2026-10-31 · 科技产业
   - https://x.com/washingtonpost/status/2116655205877989377
7. **The Washington Post：A Florida sheriff’s office is investigating after several swastikas were found painted on trees near an early-voting site in Orlando. The swastikas ha**
   - `article` · `user-source-source-the-washington-post-2466101f9bc3f1ba` · 2026-10-31 · 科技产业
   - https://x.com/washingtonpost/status/2116658991702876250
8. **The Washington Post：On Nov. 1, Dave Obelkevich, 83, will be running his 50th New York City Marathon. He holds the record for the longest streak and the most finishes in t**
   - `article` · `user-source-source-the-washington-post-22bbdbb524b9f012` · 2026-10-31 · 科技产业
   - https://x.com/washingtonpost/status/2116651445067841566
9. **The Washington Post：Kennedy Center leaders jeopardized the institution’s operations by tying millions in funding to keeping President Trump’s name on its building, a Demo**
   - `article` · `user-source-source-the-washington-post-0dca2334c31faeab` · 2026-10-31 · 科技产业
   - https://x.com/washingtonpost/status/2116640109936173383
10. **The Washington Post：Former vice president Kamala Harris spent the closing stretch of her midterms campaign blitz urging Georgia Democrats to turn out so many voters that**
   - `article` · `user-source-source-the-washington-post-00db9e0c90464415` · 2026-10-31 · 科技产业
   - https://x.com/washingtonpost/status/2116628799211143260

## The Washington Post

`sourceId=user-x-washingtonpost` · 还需审核 `20` 条 · `sampleDigest=f7efb455dec04697`

当前没有可追溯的精确匹配记录。

## Upstage 官方动态

`sourceId=official-upstage` · 还需审核 `20` 条 · `sampleDigest=eaf4eef74aaa21d1`

当前没有可追溯的精确匹配记录。

## Varda Space Industries 官方动态

`sourceId=official-varda` · 还需审核 `20` 条 · `sampleDigest=bb603f44803396fe`

当前没有可追溯的精确匹配记录。

## WeRide Investor Relations

`sourceId=weride` · 还需审核 `20` 条 · `sampleDigest=7cc15f1a76941679`

1. **WeRide Unveils Global Insurance Partnership Program to Scale Autonomous Vehicles Worldwide**
   - `article` · `weride-645d6fcd3f237ec4` · 2026-10-27 · 文远知行
   - https://ir.weride.ai/news-releases/news-release-details/weride-unveils-global-insurance-partnership-program-scale
2. **From Physical AI to Scaled Deployment: WeRide Named Among WICV 2026's Top 10 Automotive AI Application Cases**
   - `article` · `weride-307675065ceb10b6` · 2026-10-23 · 文远知行
   - https://ir.weride.ai/news-releases/news-release-details/physical-ai-scaled-deployment-weride-named-among-wicv-2026s-top
3. **WeRide Recognized on Fortune's 2026 Change the World List as the Only Autonomous Driving Company Honored**
   - `article` · `weride-2d8c053724b5f015` · 2026-09-24 · 文远知行
   - https://ir.weride.ai/news-releases/news-release-details/weride-recognized-fortunes-2026-change-world-list-only
4. **WRD 3.0 Powers the AION i60 with Championship-Winning Technology Available from Delivery**
   - `article` · `weride-80a91d205374a9e2` · 2026-09-15 · 文远知行
   - https://ir.weride.ai/news-releases/news-release-details/wrd-30-powers-aion-i60-championship-winning-technology-available
5. **WeRide, Uber, and AVOMO receive Spain’s First National Operating Permit for Level 4 Autonomous Passenger Vehicles**
   - `article` · `weride-63722d0eac892015` · 2026-09-10 · 文远知行
   - https://ir.weride.ai/news-releases/news-release-details/weride-uber-and-avomo-receive-spains-first-national-operating
6. **WeRide Included in HKEX Tech 100 Index Following September 2026 Quarterly Review**
   - `article` · `weride-f15807f8d1b64ad7` · 2026-08-31 · 文远知行
   - https://ir.weride.ai/news-releases/news-release-details/weride-included-hkex-tech-100-index-following-september-2026
7. **Accelerating European Expansion Through Proven Asset-Light Model, Driving Rapid Overseas Revenue Growth; 2Q2026 Total Revenue Reached RMB231.7 Million, Up 82.2% Year over Year**
   - `article` · `weride-a38062677ff8081f` · 2026-08-12 · 文远知行
   - https://ir.weride.ai/news-releases/news-release-details/accelerating-european-expansion-through-proven-asset-light-model

## xAI

`sourceId=xai` · 还需审核 `20` 条 · `sampleDigest=69709675610ace1a`

1. **Your next sales teammate should be a Grok Bot**
   - `article` · `xai-2cf69418651c9e4a` · 2026-10-27 · xAI
   - https://x.ai/news/grok-bot-sales
2. **Introducing the SpaceX Super Intelligence Partner Network**
   - `article` · `xai-da5fa7cddb0bb321` · 2026-10-22 · xAI
   - https://x.ai/news/partnernetworkannouncement
3. **Using Grok Bot to detect and respond to incidents**
   - `article` · `xai-0de9428d3548b15f` · 2026-10-20 · xAI
   - https://x.ai/news/incident-sweep
4. **Introducing Grok Voice 3.0**
   - `article` · `xai-12251940b3b4d223` · 2026-10-14 · xAI
   - https://x.ai/news/grok-voice-3
5. **Introducing The X Subscription**
   - `article` · `xai-ec0714e7c8ff9438` · 2026-10-12 · xAI
   - https://x.ai/news/x-subscription
6. **Team Bots: shared AI teammates that learn as they work**
   - `article` · `xai-52b14ec01b86fb13` · 2026-09-28 · xAI
   - https://x.ai/news/team-bots
7. **How SpaceXSI is using Grok Bot to scale customer support**
   - `article` · `xai-03d2992c5a1bb0eb` · 2026-09-22 · xAI
   - https://x.ai/news/grok-bot-customer-support
8. **Introducing Grok 4.7**
   - `article` · `xai-39b901174b543376` · 2026-09-21 · xAI
   - https://x.ai/news/grok-4-7
9. **Introducing Grok Voice Transcribe 2.0**
   - `article` · `xai-ce5508c16c0a4e20` · 2026-09-18 · xAI
   - https://x.ai/news/grok-voice-transcribe-2
10. **Memory in Grok Build**
   - `article` · `xai-e3779e8809a662a0` · 2026-09-16 · xAI
   - https://x.ai/news/grok-build-memory

## xAI 官方动态

`sourceId=official-xai` · 还需审核 `20` 条 · `sampleDigest=20a376500412b439`

当前没有可追溯的精确匹配记录。

## Y Combinator · 核心团队页

`sourceId=user-source-source-auto-institution-team-y-combinator` · 还需审核 `20` 条 · `sampleDigest=4bf2ef81f7965993`

1. **How Yair Alon went from building Portrait Mode at Google to founding researcher at Poetiq**
   - `article` · `user-source-source-auto-institution-team-y-combinator-7f2ac422b8825a59` · 2026-10-30 · 科技产业
   - https://www.ycombinator.com/blog/how-yair-alon-went-from-building-portrait-mode-at-google-to-founding-researcher-at-poetiq
2. **Y Combinator**
   - `article` · `user-source-source-auto-institution-team-y-combinator-1a75fc63d5c987c4` · 2026-10-22 · 科技产业
   - https://www.ycombinator.com/events
3. **Vivian Midha Shen and Raphael Schaad Join YC as General Partners**
   - `article` · `user-source-source-auto-institution-team-y-combinator-6971eb1254dd814e` · 2026-10-01 · 科技产业
   - https://www.ycombinator.com/blog/welcome-vivian-and-raphael
4. **Vivian Midha Shen: YC Partner | Y Combinator**
   - `article` · `user-source-source-auto-institution-team-y-combinator-bcfb26ff8de7a453` · 2026-09-03 · 科技产业
   - https://www.ycombinator.com/people/vivian-midha%20shen

## 东方财富 · 生物科技信源

`sourceId=user-source-source-auto-item-ddee68df` · 还需审核 `20` 条 · `sampleDigest=d6eb8c097e4eaf9a`

当前没有可追溯的精确匹配记录。
