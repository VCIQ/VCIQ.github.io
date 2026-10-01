# 信源人工质量抽样队列

周期：`2026-10`；信源健康快照：`2026-10-01T06:10:45+00:00`。

目标为每个来源累计 **20** 条人工审查记录。当前有 **3** 个来源已具备足量候选，**913** 个来源仍缺少可审记录。

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
| Alibaba Group 官方动态 | B | 0/20 | 20 | 1 | 记录不足 | `cc5aadd41e53df4c` |
| Alibaba Group 官方网站 | B | 0/20 | 20 | 0 | 记录不足 | `f048d2b6eefe7a58` |
| AliExpress 官方动态 | B | 0/20 | 20 | 0 | 记录不足 | `14f3db6314bc0885` |
| AliExpress 官方网站 | B | 0/20 | 20 | 0 | 记录不足 | `f3032f7216d5ba9c` |
| Allen Institute 官方动态 | B | 0/20 | 20 | 2 | 记录不足 | `c9634fc6997ceba3` |
| AMD Newsroom | B | 0/20 | 20 | 16 | 记录不足 | `74aa8b5192a2b77d` |
| Anduril Industries 官方动态 | B | 0/20 | 20 | 4 | 记录不足 | `0cd980f441e6dce6` |
| Anthropic | B | 0/20 | 20 | 8 | 记录不足 | `19bcd43129eac36a` |
| Anthropic | B | 0/20 | 20 | 5 | 记录不足 | `08351e371a562a5a` |
| Anthropic 官方动态 | B | 0/20 | 20 | 0 | 记录不足 | `ce48668c9ee5725d` |
| arXiv · Core AI companies | B | 0/20 | 20 | 8 | 记录不足 | `7b20d28b7534be71` |
| Aurora Innovation 官方动态 | B | 0/20 | 20 | 0 | 记录不足 | `cac901da1a9ea146` |
| Axiom Space 官方动态 | B | 0/20 | 20 | 1 | 记录不足 | `77f90d0d4da65d9a` |
| Cartesia 官方动态 | B | 0/20 | 20 | 0 | 记录不足 | `b1c108fc0a680bf4` |
| CATL | B | 0/20 | 20 | 9 | 记录不足 | `dde6b3b106691d67` |
| Cerebras Systems | B | 0/20 | 20 | 0 | 记录不足 | `77b30b8a88051252` |
| Cerebras Systems · 官方网站 | B | 0/20 | 20 | 0 | 记录不足 | `577856b2048b3f6d` |
| Cerebras Systems · 官方网站 | B | 0/20 | 20 | 0 | 记录不足 | `7b41847bd48a261e` |
| Cerebras Systems · 官方网站 | B | 0/20 | 20 | 0 | 记录不足 | `d12a01499bac284c` |
| Cerebras Systems 官方动态 | B | 0/20 | 20 | 0 | 记录不足 | `4eaa13e5dfbed84c` |
| Commonwealth Fusion Systems 官方动态 | B | 0/20 | 20 | 0 | 记录不足 | `22309084a7a95cff` |
| Coursera 官方动态 | B | 0/20 | 20 | 2 | 记录不足 | `77ecda990ee3a78b` |
| Databricks 官方动态 | B | 0/20 | 20 | 3 | 记录不足 | `0d2b4df214346605` |
| DeepSeek | B | 0/20 | 20 | 0 | 记录不足 | `6f7ac1823da81d2e` |
| DeepSeek 官方动态 | B | 0/20 | 20 | 1 | 记录不足 | `38e8e7527f84ad1e` |
| Demis Hassabis | B | 0/20 | 20 | 1 | 记录不足 | `941252631a8e708d` |
| Figure AI | B | 0/20 | 20 | 4 | 记录不足 | `8f16e09e213b89d2` |
| Figure AI 官方动态 | B | 0/20 | 20 | 0 | 记录不足 | `093bd0070133b59f` |
| Form Energy 官方动态 | B | 0/20 | 20 | 2 | 记录不足 | `25f4c2561bb114a9` |
| Founders Fund · 核心团队页 | B | 0/20 | 20 | 0 | 记录不足 | `72a885255cad56d1` |
| Glean 官方动态 | B | 0/20 | 20 | 0 | 记录不足 | `8955a0c76b81e41a` |
| Google AI | B | 0/20 | 20 | 10 | 记录不足 | `1ca59dc15cf1ba05` |
| Google DeepMind | B | 0/20 | 20 | 10 | 记录不足 | `afe4651763557236` |
| Google DeepMind | B | 0/20 | 20 | 3 | 记录不足 | `225b16586fe4c1e2` |
| Google DeepMind | B | 0/20 | 20 | 5 | 记录不足 | `aa01262616cf3c6e` |
| Google 官方动态 | B | 0/20 | 20 | 0 | 记录不足 | `d3ab2de1f60c4c51` |
| Google 官方动态 | B | 0/20 | 20 | 0 | 记录不足 | `7f5249f68ce29d5c` |
| Google 官方网站 | B | 0/20 | 20 | 0 | 记录不足 | `c72519a0258f039a` |
| Groq 官方动态 | B | 0/20 | 20 | 1 | 记录不足 | `cbef05ac859f4ca4` |
| Harvey 官方动态 | B | 0/20 | 20 | 3 | 记录不足 | `a80b4696c671bf5b` |
| Helion Energy 官方动态 | B | 0/20 | 20 | 3 | 记录不足 | `cc4cb89eec4fa8d7` |
| Horizon3 官方动态 | B | 0/20 | 20 | 3 | 记录不足 | `76d36c18281d5212` |
| IonQ | B | 0/20 | 20 | 9 | 记录不足 | `bc2206aac4b1b1e3` |
| IonQ 官方动态 | B | 0/20 | 20 | 1 | 记录不足 | `ab22051ae4f8afce` |
| Joby Aviation 官方动态 | B | 0/20 | 20 | 2 | 记录不足 | `d9efe2c802e913e5` |
| Kleiner Perkins · 核心团队页 | B | 0/20 | 20 | 0 | 记录不足 | `f7fee307e61af721` |
| Lazada 官方动态 | B | 0/20 | 20 | 0 | 记录不足 | `38e572c3a964fe5b` |
| Lazada 官方网站 | B | 0/20 | 20 | 0 | 记录不足 | `a6f8710377754f07` |
| Lightspeed Venture Partners · 核心团队页 | B | 0/20 | 20 | 0 | 记录不足 | `98cff7d33f01cce9` |
| Manifold Bio 官方动态 | B | 0/20 | 20 | 1 | 记录不足 | `966ef5f3a286c540` |
| MiniMax | B | 0/20 | 20 | 0 | 记录不足 | `e1517be14d06cdb7` |
| MiniMax 官方动态 | B | 0/20 | 20 | 0 | 记录不足 | `70c1dd24e6287dda` |
| Mobileye 官方动态 | B | 0/20 | 20 | 0 | 记录不足 | `7c09e66fc7b197ee` |
| Modular 官方动态 | B | 0/20 | 20 | 0 | 记录不足 | `d780024534df0a83` |
| OLIX 官方动态 | B | 0/20 | 20 | 0 | 记录不足 | `704b8c63d3e81641` |
| Omilia 官方动态 | B | 0/20 | 20 | 1 | 记录不足 | `de5522fac8d054d9` |
| OpenAI | B | 0/20 | 20 | 4 | 记录不足 | `b4f6612292e93263` |
| OpenAI | B | 0/20 | 20 | 5 | 记录不足 | `378feccf53aa3983` |
| OpenAI 官方动态 | B | 0/20 | 20 | 4 | 记录不足 | `7f56e95d68fdaff3` |
| OpenAI 官方新闻 | B | 0/20 | 20 | 16 | 记录不足 | `982b74986340df2b` |
| Perplexity 官方动态 | B | 0/20 | 20 | 0 | 记录不足 | `ff22b92ab74ddce8` |
| Pony.ai Investor Relations | B | 0/20 | 20 | 3 | 记录不足 | `d79c3621badcaa49` |
| PR Newswire Consumer Technology | B | 0/20 | 20 | 3 | 记录不足 | `99cefcaa5662748d` |
| PsiQuantum 官方动态 | B | 0/20 | 20 | 3 | 记录不足 | `ba8b19ef3315c0c5` |
| Reach Capital 官方动态 | B | 0/20 | 20 | 2 | 记录不足 | `7708d7d6f31c24b2` |
| Recursion Pharmaceuticals 官方动态 | B | 0/20 | 20 | 0 | 记录不足 | `840715263d0f33f5` |
| Redwood Materials 官方动态 | B | 0/20 | 20 | 1 | 记录不足 | `1e73012db66f2b5e` |
| Relativity Space 官方动态 | B | 0/20 | 20 | 1 | 记录不足 | `e006ee40ff9b862e` |
| Rigetti Computing 官方动态 | B | 0/20 | 20 | 1 | 记录不足 | `822cf84505e8c80a` |
| Rocket Lab Investor Relations | B | 0/20 | 20 | 8 | 记录不足 | `37e84d65a19d6932` |
| Rocket Lab 官方动态 | B | 0/20 | 20 | 0 | 记录不足 | `77724e934eaa73a4` |
| SambaNova Systems 官方动态 | B | 0/20 | 20 | 1 | 记录不足 | `b9f6eb1ec92c9f3c` |
| Scale AI | B | 0/20 | 20 | 4 | 记录不足 | `bdb39dae34072b5b` |
| Scale AI 官方动态 | B | 0/20 | 20 | 0 | 记录不足 | `2f665fc1199b43e5` |
| Shield AI 官方动态 | B | 0/20 | 20 | 3 | 记录不足 | `a0579d70c179652c` |
| Shopify 官方动态 | B | 0/20 | 20 | 0 | 记录不足 | `51b883d0bcce0fe1` |
| Shopify 官方动态 | B | 0/20 | 20 | 0 | 记录不足 | `c5de1fb0e02dc3a7` |
| Shopify 官方网站 | B | 0/20 | 20 | 0 | 记录不足 | `2ddbee055a110ae8` |
| Sierra 官方动态 | B | 0/20 | 20 | 1 | 记录不足 | `556c7f3f7b97b21f` |
| SpaceX | B | 0/20 | 20 | 0 | 记录不足 | `e78bdebae031095b` |
| SpaceX 官方动态 | B | 0/20 | 20 | 0 | 记录不足 | `1c04218ff2296233` |
| Tempus AI 官方动态 | B | 0/20 | 20 | 0 | 记录不足 | `a6111d51beea3380` |
| The Washington Post | B | 0/20 | 20 | 10 | 记录不足 | `db3e0b1cef50d0eb` |
| The Washington Post | B | 0/20 | 20 | 0 | 记录不足 | `f7efb455dec04697` |
| Upstage 官方动态 | B | 0/20 | 20 | 0 | 记录不足 | `eaf4eef74aaa21d1` |
| Varda Space Industries 官方动态 | B | 0/20 | 20 | 0 | 记录不足 | `bb603f44803396fe` |
| WeRide Investor Relations | B | 0/20 | 20 | 4 | 记录不足 | `5ed888688b724260` |
| xAI | B | 0/20 | 20 | 10 | 记录不足 | `d9e3a51233efd057` |
| xAI 官方动态 | B | 0/20 | 20 | 0 | 记录不足 | `20a376500412b439` |
| Y Combinator · 核心团队页 | B | 0/20 | 20 | 1 | 记录不足 | `635e91c29c8778a0` |
| 东方财富 · 生物科技信源 | B | 0/20 | 20 | 0 | 记录不足 | `d6eb8c097e4eaf9a` |
| 傅利叶智能 官方动态 | B | 0/20 | 20 | 0 | 记录不足 | `4b138df240df64d3` |
| 华大基因 官方动态 | B | 0/20 | 20 | 0 | 记录不足 | `04a46e78251de4cf` |
| 启明创投 · 核心团队页 | B | 0/20 | 20 | 6 | 记录不足 | `48365a107a70c971` |

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

`sourceId=official-user-alibaba-group` · 还需审核 `20` 条 · `sampleDigest=cc5aadd41e53df4c`

1. **Alibaba.com**
   - `article` · `official-user-alibaba-group-3e395829e89283e7` · 2026-09-29 · Alibaba Group
   - https://www.alibaba.com/premium/alibaba_login.html

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

`sourceId=amd-newsroom` · 还需审核 `20` 条 · `sampleDigest=74aa8b5192a2b77d`

1. **AMD Brings the Power of Agentic AI to Embedded Design and Development Cycle**
   - `article` · `amd-newsroom-7ae4d67e7a5a60b8` · 2026-09-30 · AMD
   - https://newsroom.amd.com/news/amd-ross-agentic-ai-embedded-design-development
2. **Media Alert: AMD CEO Lisa Su to Lead Keynote at 2026 OCP**
   - `article` · `amd-newsroom-6506c4a273efe728` · 2026-09-29 · AMD
   - https://newsroom.amd.com/news/media-alert-ceo-lisa-su-keynote-2026-ocp
3. **AMD to Acquire World Labs to Advance the Future of AI Compute**
   - `article` · `amd-newsroom-effcb19529443682` · 2026-09-28 · AMD
   - https://newsroom.amd.com/news/amd-acquire-world-labs
4. **With AMD Ryzen AI Max Series Processors, Perplexity Brings Portable Computer to Agentic PCs**
   - `article` · `amd-newsroom-f8760c7b2f8a5eb5` · 2026-09-24 · AMD
   - https://newsroom.amd.com/news/amd-perplexity-agentic-pcs
5. **‘Advanced Insights’: How ‘Zen’ Architecture Evolves for the Agentic AI Era (Video)**
   - `article` · `amd-newsroom-06b3644dd027b1a6` · 2026-09-23 · AMD
   - https://newsroom.amd.com/news/advanced-insights-zen-architecture-agentic-ai-era
6. **Media Alert: AMD to Showcase Physical AI and Robotics Innovation at ROSCon 2026**
   - `article` · `amd-newsroom-6f0df152f4b17d5d` · 2026-09-21 · AMD
   - https://newsroom.amd.com/news/media-alert-amd-roscon-2026
7. **AMD EPYC CPUs Deliver for Every Layer of the Agentic AI Stack**
   - `article` · `amd-newsroom-5b9f4efd6c94da41` · 2026-09-18 · AMD
   - https://newsroom.amd.com/news/amd-epyc-cpus-deliver-every-layer-agentic-ai-stack
8. **Building Infrastructure for an AI World in Motion**
   - `article` · `amd-newsroom-454e80d356e5e9f5` · 2026-09-17 · AMD
   - https://newsroom.amd.com/news/building-infrastructure-ai-world
9. **F-Secure and AMD Silo AI Help Secure Agentic AI Journeys**
   - `article` · `amd-newsroom-98fa2b8f92de6323` · 2026-09-14 · AMD
   - https://newsroom.amd.com/news/f-secure-amd-silo-ai-help-secure-agentic-ai-journeys
10. **From LEAP 2026 to What Comes Next: Advancing AI Across the Middle East**
   - `article` · `amd-newsroom-a32670cc5c68cba0` · 2026-09-09 · AMD
   - https://newsroom.amd.com/news/leap-2026-advancing-ai-across-the-middle-east
11. **‘Advanced Insights’: The Future of AI-Powered Storytelling (Video)**
   - `article` · `amd-newsroom-6c3257a323d89ed6` · 2026-09-09 · AMD
   - https://newsroom.amd.com/news/advanced-insights-future-ai-powered-storytelling-video
12. **AMD and Delhi University Collaborate to Build India’s AI Talent**
   - `article` · `amd-newsroom-57cb368ec7d2428b` · 2026-09-08 · AMD
   - https://newsroom.amd.com/news/amd-delhi-university-collaborate-build-india-ai-talent
13. **AMD Instinct GPUs and EPYC CPUs to Power Europe’s Next-Generation LUMI-AI Supercomputer**
   - `article` · `amd-newsroom-c9b3ba1144b3cd66` · 2026-08-31 · AMD
   - https://newsroom.amd.com/news/amd-instinct-gpus-epyc-cpus-power-lumi-ai-supercomputer
14. **AMD, Saudi Arabia’s Ministry of Communications and Information Technology and Digital Cooperation Organization Launch an Open Developer Ecosystem to Advance AI Innovation**
   - `article` · `amd-newsroom-c24762fdc2aec609` · 2026-08-31 · AMD
   - https://newsroom.amd.com/news/amd-saudi-arabia-digital-cooperation-organization-open-developer-ecosystem
15. **AMD, Cisco and HUMAIN Expand Saudi Arabia’s AI Infrastructure as AMD Instinct Systems Go Live**
   - `article` · `amd-newsroom-9aaad06d294c7222` · 2026-08-31 · AMD
   - https://newsroom.amd.com/news/amd-cisco-humain-expand-saudi-arabia-ai-infrastructure
16. **AMD ROCm 10: Bringing ROCm.AI’s AI-Native Developer Experiences to AMD Platforms**
   - `article` · `amd-newsroom-bcfd78404c1f0a87` · 2026-08-27 · AMD
   - https://newsroom.amd.com/news/rocm-10-software-ai-native-developer-experiences

## Anduril Industries 官方动态

`sourceId=official-anduril` · 还需审核 `20` 条 · `sampleDigest=0cd980f441e6dce6`

1. **Anduril and Voyager Establish Strategic Partnership Across Advanced Weapons and Propulsion**
   - `article` · `official-anduril-8bc0a2f162ab897a` · 2026-09-29 · Anduril Industries
   - https://www.anduril.com/news/anduril-and-voyager-establish-strategic-partnership-across-advanced-weapons-and-propulsion
2. **Barracuda Becomes First WOSA-Compliant Weapon in Large-Scale Production**
   - `article` · `official-anduril-e060d00115b66931` · 2026-09-23 · Anduril Industries
   - https://www.anduril.com/news/barracuda-becomes-first-wosa-compliant-weapon-in-large-scale-production
3. **Anduril Strengthens Security Partnership with Taiwan through Altius Milestones and Expanded Local Investment**
   - `article` · `official-anduril-be7a6cb0942f7fa1` · 2026-09-23 · Anduril Industries
   - https://www.anduril.com/news/anduril-strengthens-security-partnership-with-taiwan-through-altius-milestones-and-expanded-local-investment
4. **Boeing and Anduril's Midrange Interceptor Advances in U.S. Army Competition**
   - `article` · `official-anduril-99c77a3aa0088539` · 2026-09-09 · Anduril Industries
   - https://www.anduril.com/news/boeing-and-anduril-s-midrange-interceptor-advances-in-u-s-army-competition

## Anthropic

`sourceId=anthropic` · 还需审核 `20` 条 · `sampleDigest=19bcd43129eac36a`

1. **Claude discovers a novel enzyme system**
   - `article` · `anthropic-ef1b3a4772eab837` · 2026-09-23 · Anthropic
   - https://www.anthropic.com/news/claude-discovers-novel-enzyme-system
2. **Partnering with Accenture on embedded evaluation**
   - `article` · `anthropic-5ec4e61a2a5169eb` · 2026-09-18 · Anthropic
   - https://www.anthropic.com/news/accenture-embedded-evaluation
3. **Introducing the Life Sciences Verification Program**
   - `article` · `anthropic-a3c8e138d995ff55` · 2026-09-17 · Anthropic
   - https://www.anthropic.com/news/life-sciences-verification-program
4. **Developing Enterprise Frontier Safeguards with our customers**
   - `article` · `anthropic-b085c7f1762bfee8` · 2026-09-01 · Anthropic
   - https://www.anthropic.com/news/enterprise-frontier-safeguards
5. **Improving our alignment and security practices**
   - `article` · `anthropic-8ed1599eb95bc766` · 2026-08-31 · Anthropic
   - https://www.anthropic.com/news/improving-alignment-security-efforts
6. **Previewing the Model Hardware Standard**
   - `article` · `anthropic-35305757066a6f71` · 2026-08-27 · Anthropic
   - https://www.anthropic.com/news/model-hardware-standard-research-preview
7. **Expanding our support for scientists**
   - `article` · `anthropic-3368e02f484edc23` · 2026-08-27 · Anthropic
   - https://www.anthropic.com/news/expanding-support-for-scientists
8. **Funding better evaluations of AI’s impact on wellbeing**
   - `article` · `anthropic-1e032b3767d6bbcd` · 2026-08-25 · Anthropic
   - https://www.anthropic.com/news/wellbeing-research-grants

## Anthropic

`sourceId=x-anthropic` · 还需审核 `20` 条 · `sampleDigest=08351e371a562a5a`

1. **Anthropic：What do you want from AI? We’re launching a new study with Anthropic Interviewer to learn more about your experiences using AI, what role you want it**
   - `article` · `x-anthropic-8e7e87b647d0401b` · 2026-09-29 · Anthropic
   - https://x.com/AnthropicAI/status/2104982629884063840
2. **Anthropic：Making your interview public is completely optional. Our blog post covers the benefits and possible risks of doing so. Read it here: https://t.co/Gh4v**
   - `article` · `x-anthropic-7667706671ca602d` · 2026-09-29 · Anthropic
   - https://x.com/AnthropicAI/status/2104982631037436201
3. **Anthropic：Claude Sonnet 5.5 is now available:**
   - `article` · `x-anthropic-3ee14f4f5e2872e6` · 2026-09-28 · Anthropic
   - https://x.com/AnthropicAI/status/2104633259925630995
4. **Anthropic：New on the Science Blog: Yes, Claude can do Nine Loops. Theoretical physicists predict how particles behave using formulas called scattering amplitude**
   - `article` · `x-anthropic-e8a0ab8a7bef0123` · 2026-09-25 · Anthropic
   - https://x.com/AnthropicAI/status/2103541577083719888
5. **Anthropic：In the Democratic Republic of the Congo, global health organizations including @CEPIvaccines, @WHOAFRO, and @inrb_kinshasa are using Claude to acceler**
   - `article` · `x-anthropic-4b05f96cfb578a26` · 2026-09-23 · Anthropic
   - https://x.com/AnthropicAI/status/2102897863097545197

## Anthropic 官方动态

`sourceId=official-anthropic` · 还需审核 `20` 条 · `sampleDigest=ce48668c9ee5725d`

当前没有可追溯的精确匹配记录。

## arXiv · Core AI companies

`sourceId=arxiv-ai` · 还需审核 `20` 条 · `sampleDigest=7b20d28b7534be71`

1. **Cascadia: A Control-Plane-Free Alternative to Hyperconverged AI Infrastructure**
   - `article` · `arxiv-ai-c5e3774a4c87d9ff` · 2026-09-30 · 科技产业
   - https://arxiv.org/abs/2609.38697v1
2. **The Invisible Language Tax: Token Premiums of French and Regional Languages in 2026 LLM Tokenizers, and a French-Optimized Prototype**
   - `article` · `arxiv-ai-467d938b4dab9ea9` · 2026-09-30 · 科技产业
   - https://arxiv.org/abs/2609.39001v1
3. **SkillSeek: Revisiting Agent Skill Retrieval at Marketplace Scale**
   - `article` · `arxiv-ai-0e0dd5b6e55f6014` · 2026-09-30 · 科技产业
   - https://arxiv.org/abs/2609.38822v1
4. **How People Use ChatGPT: Conversation-Level Evidence from India, Nigeria, Brazil, and Pakistan**
   - `article` · `arxiv-ai-dd437d808488c7c2` · 2026-09-29 · OpenAI
   - https://arxiv.org/abs/2609.38279v1
5. **When Does Randomized Oversight Align AI Agents That Can Conceal?**
   - `article` · `arxiv-ai-d7833fdaa0054b89` · 2026-09-29 · 科技产业
   - https://arxiv.org/abs/2609.38262v1
6. **Evaluating Whether GPT-6 Astra Performs Unsanctioned Supply-Chain Attacks**
   - `article` · `arxiv-ai-c70b866961de39e3` · 2026-09-29 · 科技产业
   - https://arxiv.org/abs/2609.38415v1
7. **Analytic next-to-leading-order helicity cross sections for vector-boson production at finite transverse momentum**
   - `article` · `arxiv-ai-7c9b24dc8237a74f` · 2026-09-29 · 科技产业
   - https://arxiv.org/abs/2609.37238v1
8. **Strong Multilingual Privacy Tagging at Encoder Speed**
   - `article` · `arxiv-ai-6b0654c6f71a163d` · 2026-09-29 · 科技产业
   - https://arxiv.org/abs/2609.38630v1

## Aurora Innovation 官方动态

`sourceId=official-aurora` · 还需审核 `20` 条 · `sampleDigest=cac901da1a9ea146`

当前没有可追溯的精确匹配记录。

## Axiom Space 官方动态

`sourceId=official-axiom-space` · 还需审核 `20` 条 · `sampleDigest=77f90d0d4da65d9a`

1. **Celebrating National Sewing Month in the Axiom Space Soft Goods Lab**
   - `article` · `official-axiom-space-723c425176fd3189` · 2026-09-28 · Axiom Space
   - https://www.axiomspace.com/news/celebrating-national-sewing-month-in-the-axiom-space-soft-goods-lab

## Cartesia 官方动态

`sourceId=official-cartesia` · 还需审核 `20` 条 · `sampleDigest=b1c108fc0a680bf4`

当前没有可追溯的精确匹配记录。

## CATL

`sourceId=catl` · 还需审核 `20` 条 · `sampleDigest=dde6b3b106691d67`

1. **CATL Debrecen Kicks Off Trial Operations in its New Cell Building**
   - `article` · `catl-f81b4656bae6ac0b` · 2026-09-22 · 宁德时代
   - https://www.catl.com/en/news/7000.html
2. **Kuehne+Nagel and CATL partner to advance battery logistics and fleet electrification**
   - `article` · `catl-f3e02afa3fb78fc4` · 2026-09-18 · 宁德时代
   - https://www.catl.com/en/news/7012.html
3. **CATL Partners with BME to Advance Battery Pack Manufacturing in Egypt Through Technology Licensing**
   - `article` · `catl-d3f6b4d5622ccf82` · 2026-09-16 · 宁德时代
   - https://www.catl.com/en/news/6998.html
4. **CATL Launches TECTRANS II at IAA Transportation 2026 to Accelerate Global Commercial Vehicle Electrification**
   - `article` · `catl-973ce00ed571161d` · 2026-09-14 · 宁德时代
   - https://www.catl.com/en/news/6997.html
5. **CATL and DHL Group Sign MoU to Jointly Advance Green Freight Corridors Across Europe**
   - `article` · `catl-0b42845c21419b56` · 2026-09-14 · 宁德时代
   - https://www.catl.com/en/news/6999.html
6. **CATL Signs Strategic Cooperation Agreements with Copper Foil Suppliers**
   - `article` · `catl-52ccefc93237de41` · 2026-09-06 · 宁德时代
   - https://www.catl.com/en/news/6993.html
7. **Dr. Robin Zeng on the "CATL Standard": Safety, Reliability, and Longevity at the Core**
   - `article` · `catl-300fd4926261ce71` · 2026-09-03 · 宁德时代
   - https://www.catl.com/en/news/6992.html
8. **CATL Announces Local Partnership, Showcases Full-Chain Storage at The Smarter E South America 2026**
   - `article` · `catl-70143af7e2c6dc37` · 2026-08-25 · 宁德时代
   - https://www.catl.com/en/news/6977.html
9. **CATL Signs Memorandum of Understanding with Schaeffler**
   - `article` · `catl-eee686edff0f28eb` · 2026-08-24 · 宁德时代
   - https://www.catl.com/en/news/6978.html

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

`sourceId=official-coursera` · 还需审核 `20` 条 · `sampleDigest=77ecda990ee3a78b`

1. **2025 Micro-Credentials Impact Report**
   - `article` · `official-coursera-68e2d6c0199ff7c1` · 2026-09-28 · Coursera
   - https://www.coursera.org/enterprise/resources/ebooks/micro-credentials-report-2025?_gl=1%2Aj62h6z%2A_gcl_aw%2AR0NMLjE3NDk2NTkyOTQuQ2owS0NRancwcVRDQmhDbUFSSXNBQWo4QzRhMktvZ0xhLXBEU3JJc2ZqRmZsV1VueU9ld25GMi1YUDc4S01EY3JJUVlaVUFaalYwTW9JY2FBdXRaRUFMd193Y0I.%2A_gcl_au%2ANzE3NzUxODMyLjE3NDM3MDM1MzAuNDUxODIxODQ5LjE3NDk0OTM0MDQuMTc0OTQ5MzQ5MA..
2. **Closing the GenAI Gender Gap: Research & Strategies**
   - `article` · `official-coursera-555e9a50ac23e144` · 2026-09-28 · Coursera
   - https://www.coursera.org/enterprise/resources/ebook/genai-gender-gap?_gl=1%2Acveatc%2A_gcl_aw%2AR0NMLjE3NDk2NTkyOTQuQ2owS0NRancwcVRDQmhDbUFSSXNBQWo4QzRhMktvZ0xhLXBEU3JJc2ZqRmZsV1VueU9ld25GMi1YUDc4S01EY3JJUVlaVUFaalYwTW9JY2FBdXRaRUFMd193Y0I.%2A_gcl_au%2ANzE3NzUxODMyLjE3NDM3MDM1MzAuNDUxODIxODQ5LjE3NDk0OTM0MDQuMTc0OTQ5MzQ5MA..

## Databricks 官方动态

`sourceId=official-databricks` · 还需审核 `20` 条 · `sampleDigest=0d2b4df214346605`

1. **Introducing ai_decide: make fast decisions on your governed data**
   - `article` · `official-databricks-0392785bf204a953` · 2026-09-30 · Databricks
   - https://www.databricks.com/blog/introducing-aidecide-make-fast-decisions-your-governed-data
2. **Genie One MCP: Give any AI Agent the Right Business Context**
   - `article` · `official-databricks-cd03132bf549e99c` · 2026-09-22 · Databricks
   - https://www.databricks.com/blog/genie-one-mcp-give-any-ai-agent-right-business-context
3. **Object Storage + WAL: Lakebase Postgres for the agentic era**
   - `article` · `official-databricks-0d7a2bb2bd31060c` · 2026-08-27 · Databricks
   - https://www.databricks.com/blog/object-storage-wal-lakebase-postgres-agentic-era

## DeepSeek

`sourceId=deepseek` · 还需审核 `20` 条 · `sampleDigest=6f7ac1823da81d2e`

当前没有可追溯的精确匹配记录。

## DeepSeek 官方动态

`sourceId=official-deepseek` · 还需审核 `20` 条 · `sampleDigest=38e8e7527f84ad1e`

1. **DeepSeek V4.1 Flash：更强、更快、更普惠**
   - `article` · `official-deepseek-ef1a570fe50dec94` · 2026-09-10 · DeepSeek
   - https://www.deepseek.com/news/deepseek-v4-1-flash

## Demis Hassabis

`sourceId=x-demis` · 还需审核 `20` 条 · `sampleDigest=941252631a8e708d`

1. **Demis Hassabis：For 20+ years @ShaneLegg and I've discussed AGI’s potential impact on the economy, science & society. With the DeepMind Institute, we're expanding int**
   - `article` · `x-demis-94c82a90bdf4a846` · 2026-09-16 · Demis Hassabis
   - https://x.com/demishassabis/status/2100230524383981702

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

`sourceId=official-form-energy` · 还需审核 `20` 条 · `sampleDigest=25f4c2561bb114a9`

1. **Form Energy Announces Closing of $270M Credit Facility**
   - `article` · `official-form-energy-199103653ab491e0` · 2026-09-21 · Form Energy
   - https://formenergy.com/form-energy-announces-closing-of-270m-credit-facility
2. **Form Energy Launches Technician Hiring Sprint In Weirton, WV**
   - `article` · `official-form-energy-7f5377b6174512b9` · 2026-09-09 · Form Energy
   - https://formenergy.com/form-energy-launches-technician-hiring-sprint-in-weirton-wv

## Founders Fund · 核心团队页

`sourceId=user-source-source-auto-institution-team-founders-fund` · 还需审核 `20` 条 · `sampleDigest=72a885255cad56d1`

当前没有可追溯的精确匹配记录。

## Glean 官方动态

`sourceId=official-glean` · 还需审核 `20` 条 · `sampleDigest=8955a0c76b81e41a`

当前没有可追溯的精确匹配记录。

## Google AI

`sourceId=google-ai-blog` · 还需审核 `20` 条 · `sampleDigest=1ca59dc15cf1ba05`

1. **New experts join Google’s AI & Economy team**
   - `article` · `google-ai-blog-2ad49dd9b65fe3ae` · 2026-09-18 · Google
   - https://blog.google/innovation-and-ai/technology/ai/expanding-ai-economy-research-bench
2. **AI for Societal Impact**
   - `article` · `google-ai-blog-dfe2f7f06070ffbc` · 2026-09-15 · Google
   - https://blog.google/innovation-and-ai/technology/ai/ai-for-societal-impact
3. **AI for everyone in every language**
   - `article` · `google-ai-blog-7a00acf92df0c96e` · 2026-09-15 · Google
   - https://blog.google/innovation-and-ai/technology/ai/ai-for-every-language
4. **New insights from Google’s AI & Economy ATLAS**
   - `article` · `google-ai-blog-64730bcdfc3a3522` · 2026-09-15 · Google
   - https://blog.google/innovation-and-ai/technology/ai/ai-economy-atlas-september-2026
5. **Building AI to accelerate science and improve lives**
   - `article` · `google-ai-blog-419a0d7bd8653188` · 2026-09-15 · Google
   - https://blog.google/innovation-and-ai/technology/ai/ai-applications-science-people
6. **3 ways to prep for your next big race with Search**
   - `article` · `google-ai-blog-338a77b082d6e9b8` · 2026-09-10 · Google
   - https://blog.google/products-and-platforms/products/search/running-race-training-tips
7. **Get ready for the game with new football features in Search**
   - `article` · `google-ai-blog-77adb66885449411` · 2026-09-09 · Google
   - https://blog.google/products-and-platforms/products/search/football-features-google-search
8. **Proactive cyber defense for governments and enterprises**
   - `article` · `google-ai-blog-445c9f3e3d31d266` · 2026-09-02 · Google
   - https://blog.google/innovation-and-ai/technology/safety-security/fairwind-program
9. **The latest AI news we announced in August 2026**
   - `article` · `google-ai-blog-e6646933ca959a5f` · 2026-09-01 · Google
   - https://blog.google/innovation-and-ai/technology/google-ai-updates-august-2026
10. **3 new ways to plan and book travel in Search**
   - `article` · `google-ai-blog-a7db6e12c1ae453b` · 2026-08-27 · Google
   - https://blog.google/products-and-platforms/products/search/book-travel-ai-mode

## Google DeepMind

`sourceId=deepmind-blog` · 还需审核 `20` 条 · `sampleDigest=afe4651763557236`

1. **Introducing SynthID Bio**
   - `article` · `google-deepmind-08aa8115cb5d9c89` · 2026-09-30 · Google
   - https://deepmind.google/blog/introducing-synthid-bio
2. **Gemini 4 Argon: our next era of frontier intelligence**
   - `article` · `deepmind-blog-b49099cde7e97e60` · 2026-09-30 · Google
   - https://deepmind.google/blog/gemini-4-argon-our-next-era-of-frontier-intelligence
3. **Introducing Gemini 3.8 Live with Live Avatar**
   - `article` · `deepmind-blog-6add3dd62456569f` · 2026-09-24 · Google
   - https://deepmind.google/blog/introducing-gemini-38-live-with-live-avatar
4. **Advancing Private AI Compute with secure, server-side memory**
   - `article` · `google-deepmind-1043d9fe80283e6f` · 2026-09-23 · Google
   - https://deepmind.google/blog/advancing-private-ai-compute-with-secure-server-side-memory
5. **Gemini 3.8 text-to-speech says hello**
   - `article` · `deepmind-blog-721de6922a1a6b9f` · 2026-09-23 · Google
   - https://deepmind.google/blog/say-hello-to-gemini-38-text-to-speech
6. **Introducing Gemini 3.8 Live and 3.8 Live Extended Thinking**
   - `article` · `deepmind-blog-6aae488b1bb65e59` · 2026-09-15 · Google
   - https://deepmind.google/blog/introducing-gemini-3-8-live-and-3-8-live-extended-thinking
7. **Introducing WeatherNext 3, our most advanced and accurate global weather AI model**
   - `article` · `deepmind-blog-d5ea4bcadd66b1af` · 2026-09-03 · Google
   - https://deepmind.google/blog/introducing-weathernext-3-our-most-advanced-and-accurate-global-weather-ai-model
8. **Introducing Gemini 3.8 Flash and 3.8 Flash Cyber**
   - `article` · `deepmind-blog-355be2cf6d2d139c` · 2026-09-02 · Google
   - https://deepmind.google/blog/introducing-gemini-3-8-flash-and-38-flash-cyber
9. **Introducing agentic video understanding with Gemini**
   - `article` · `deepmind-blog-6bf5b05134dd23a6` · 2026-09-01 · Google
   - https://deepmind.google/blog/introducing-agentic-video-in-gemini
10. **Gemini Omni 1.1 Flash lets you build with more control**
   - `article` · `deepmind-blog-90ba20dc32b53edf` · 2026-08-27 · Google
   - https://deepmind.google/blog/gemini-omni-1-1-flash-lets-you-build-with-more-control

## Google DeepMind

`sourceId=google-deepmind` · 还需审核 `20` 条 · `sampleDigest=225b16586fe4c1e2`

1. **AlphaGenome Atlas: Molecular predictions for 9 Billion human DNA variants**
   - `article` · `google-deepmind-825546b9e9e150a7` · 2026-09-08 · Google
   - https://deepmind.google/blog/alphagenome-atlas-a-predictive-map-of-every-possible-dna-letter-change-in-the-human-genome
2. **Piloting the world's first double-blind AI evaluations**
   - `article` · `google-deepmind-f0dc85dcc6d3444f` · 2026-08-27 · Google
   - https://deepmind.google/blog/piloting-the-worlds-first-double-blind-ai-evaluations
3. **Exploring new frontiers of AI and games research**
   - `article` · `google-deepmind-76900827bd8bbfff` · 2026-08-21 · Google
   - https://deepmind.google/blog/from-atari-to-eve-online-building-on-15-years-of-ai-research-in-games

## Google DeepMind

`sourceId=user-x-googledeepmind` · 还需审核 `20` 条 · `sampleDigest=aa01262616cf3c6e`

1. **Google DeepMind：RT @GoogleCloudTech: Power your agents: Gemini 3.8 Live with Live Avatar is now generally available in Gemini Enterprise. Key capabilities…**
   - `article` · `user-x-googledeepmind-d794b01d76329d3d` · 2026-09-24 · 科技产业
   - https://x.com/GoogleDeepMind/status/2103176711479402748
2. **Google DeepMind：Fine-tune the delivery line by line, shaping pacing, emotion, and cues like laughs or pauses. All generated audio is watermarked with SynthID so it ca**
   - `article` · `user-x-googledeepmind-b11a0ee0d2d39597` · 2026-09-23 · 科技产业
   - https://x.com/GoogleDeepMind/status/2102781533274734801
3. **Google DeepMind：Create and deploy custom audio with our new text-to-speech models: 🔵 Gemini 3.8 Flash TTS: Design unique voices with distinct accents and characterist**
   - `article` · `user-x-googledeepmind-7cb26034cdf5dbce` · 2026-09-23 · 科技产业
   - https://x.com/GoogleDeepMind/status/2102781530867126505
4. **Google DeepMind：Every second, millions of genome switches dictate how our cells function and adapt. 🧬 Working with @ScienceStowers, Atlas mapped 2,500+ regulatory pat**
   - `article` · `user-x-googledeepmind-9aff44ea2009516a` · 2026-09-17 · 科技产业
   - https://x.com/GoogleDeepMind/status/2100586768248562157
5. **Google DeepMind：These discoveries are just the beginning. AlphaGenome Atlas is freely accessible to empower researchers everywhere to decode the genetic causes of dis**
   - `article` · `user-x-googledeepmind-2d95318fc27b1796` · 2026-09-17 · 科技产业
   - https://x.com/GoogleDeepMind/status/2100586770572177551

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

`sourceId=official-groq` · 还需审核 `20` 条 · `sampleDigest=cbef05ac859f4ca4`

1. **Groq Among the First to Bring NVIDIA Groq 3 LPX and Vera Rubin NVL72 to Market**
   - `article` · `official-groq-cac40f498bb1fa5b` · 2026-08-24 · Groq
   - https://groq.com/blog/groq-among-the-first-to-bring-nvidia-groq-3-lpx-and-vera-rubin-nvl72-to-market

## Harvey 官方动态

`sourceId=official-harvey` · 还需审核 `20` 条 · `sampleDigest=a80b4696c671bf5b`

1. **Build and Update Review Tables With the Harvey Agent**
   - `article` · `official-harvey-85a463c96347c227` · 2026-09-17 · Harvey
   - https://www.harvey.ai/blog/review-table-agent-actions
2. **Rebuilding Playbook Review as a Multi-Agent System**
   - `article` · `official-harvey-6a5cbf1e095b2dc5` · 2026-09-02 · Harvey
   - https://www.harvey.ai/blog/rebuilding-playbook-review-as-a-multi-agent-system
3. **Harvey Tenet Research Preview**
   - `article` · `official-harvey-4e6bdb0d82198725` · 2026-08-20 · Harvey
   - https://www.harvey.ai/blog/post-training-update-harvey-tenet

## Helion Energy 官方动态

`sourceId=official-helion` · 还需审核 `20` 条 · `sampleDigest=cc4cb89eec4fa8d7`

1. **Building the foundations for fusion at scale**
   - `article` · `official-helion-0a139255a7eb88ec` · 2026-09-29 · Helion Energy
   - https://www.helionenergy.com/blog/building-the-foundations-for-fusion-at-scale
2. **Does fusion produce radiation?**
   - `article` · `official-helion-df2f06440fad1829` · 2026-09-04 · Helion Energy
   - https://www.helionenergy.com/blog/does-fusion-produce-radiation
3. **Why is fusion plasma pink?**
   - `article` · `official-helion-4e3895267fef4680` · 2026-09-02 · Helion Energy
   - https://www.helionenergy.com/blog/why-is-fusion-plasma-pink

## Horizon3 官方动态

`sourceId=official-horizon3` · 还需审核 `20` 条 · `sampleDigest=76d36c18281d5212`

1. **Horizon3 Earns Cyber Essentials Certification**
   - `article` · `official-horizon3-59e94609bbaf81c7` · 2026-09-28 · Horizon3
   - https://horizon3.ai/news/press-release/horizon3-earns-cyber-essentials-certification-covering-nodezero-eu-network
2. **Horizon3 Integrates with CrowdStrike Falcon Next-Gen SIEM**
   - `article` · `official-horizon3-ac1d964f5917a650` · 2026-09-15 · Horizon3
   - https://horizon3.ai/news/press-release/crowdstrike-falcon-next-gen-siem-integration
3. **Horizon3 Names Chad Keefer VP of Federal Sales**
   - `article` · `official-horizon3-58e662d3040ed793` · 2026-08-25 · Horizon3
   - https://horizon3.ai/news/press-release/chad-keefer-vp-federal-sales

## IonQ

`sourceId=ionq` · 还需审核 `20` 条 · `sampleDigest=bc2206aac4b1b1e3`

1. **FIU Secures Florida’s First IonQ Superion Quantum System**
   - `article` · `ionq-3ada0a6f08048c2e` · 2026-09-24 · IonQ
   - https://ionq.com/news/ionqs-superion-256-platform-selected-by-florida-international-university-for-flagship-deployment
2. **IonQ Superion 256 to Power NVIDIA Quantum Research Center**
   - `article` · `ionq-6a80c6850a63732f` · 2026-09-23 · IonQ
   - https://ionq.com/news/ionq-to-advance-quantum-supercomputing-by-bringing-first-qpu-to-nvidia-accelerated-quantum-research-center
3. **IonQ Breakthrough: CPU-Powered Quantum Error Correction**
   - `article` · `ionq-fa39c641d66b0169` · 2026-09-22 · IonQ
   - https://ionq.com/news/ionq-demonstrates-industrys-first-end-to-end-real-time-quantum-error-decoder
4. **IonQ and SDT Announce the First Strategic Partnership to Bring Both Advanced Quantum Computing and Quantum Networking to the Asia-Pacific Region**
   - `article` · `ionq-fc8f4f7211fb881a` · 2026-09-21 · IonQ
   - https://ionq.com/news/ionq-and-sdt-announce-the-first-strategic-partnership-to-bring-both-advanced-quantum-computing-and-quantum-networking-to-the-asia-pacific-region
5. **Quantum Algorithms Accelerate Engineering Simulations**
   - `article` · `ionq-9c58c309fdfa05dc` · 2026-09-17 · IonQ
   - https://ionq.com/news/ionq-demonstrates-computer-aided-engineering-workload-acceleration-by-up-to-14-6-with-quantum-technology
6. **Generative AI Accelerates Quantum Optimization | IonQ & NVIDIA**
   - `article` · `ionq-f09ca82ec5e4b507` · 2026-09-16 · IonQ
   - https://ionq.com/news/ionq-ornl-nvidia-and-the-university-of-tennessee-knoxville-show-ai-method-reduces-quantum-optimization-trade-off
7. **IonQ Earns Four Best Paper Awards at IEEE Quantum Week 2026**
   - `article` · `ionq-b4b7df5822c90f18` · 2026-09-15 · IonQ
   - https://ionq.com/news/ionq-earns-four-best-paper-awards-ahead-of-ieee-quantum-week-2026-for-breakthroughs-in-ai-hybrid-computing-and-life-sciences
8. **Company research leaders will deliver a keynote address, lead a tutorial, and contribute to workshops and panels throughout the QCE26 program**
   - `article` · `ionq-628a9574d34c9616` · 2026-09-14 · IonQ
   - https://ionq.com/news/ionq-to-present-nine-peer-reviewed-papers-and-take-part-in-seven-events-at-2026-ieee-quantum-week
9. **IonQ & Congruity360 Ink $8.18M Quantum Security Agreement**
   - `article` · `ionq-1da51d345a714bbd` · 2026-09-08 · IonQ
   - https://ionq.com/news/ionq-and-congruity360-partner-to-enhance-quantum-safe-protection

## IonQ 官方动态

`sourceId=official-ionq` · 还需审核 `20` 条 · `sampleDigest=ab22051ae4f8afce`

1. **IonQ Demonstrates Quantum Generative Modeling for High Resolution Radar Change Detection**
   - `article` · `official-ionq-f37e472428fd4d39` · 2026-09-24 · IonQ
   - https://ionq.com/news/ionq-demonstrates-quantum-generative-modeling-for-high-resolution-radar-change-detection

## Joby Aviation 官方动态

`sourceId=official-joby` · 还需审核 `20` 条 · `sampleDigest=d9efe2c802e913e5`

1. **Joby Autonomous Aircraft Begins Cross-Country Tour**
   - `article` · `official-joby-e4f6b1433fa5a48f` · 2026-09-10 · Joby Aviation
   - https://www.jobyaviation.com/news/joby-autonomous-aircraft-begins-cross-country-tour
2. **Joby Launches eIPP Flights in Texas**
   - `article` · `official-joby-188dfae0b57ed656` · 2026-09-10 · Joby Aviation
   - https://www.jobyaviation.com/news/joby-launches-eipp-flights-in-texas

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

`sourceId=official-minimax` · 还需审核 `20` 条 · `sampleDigest=70c1dd24e6287dda`

当前没有可追溯的精确匹配记录。

## Mobileye 官方动态

`sourceId=official-mobileye` · 还需审核 `20` 条 · `sampleDigest=7c09e66fc7b197ee`

当前没有可追溯的精确匹配记录。

## Modular 官方动态

`sourceId=official-modular` · 还需审核 `20` 条 · `sampleDigest=d780024534df0a83`

当前没有可追溯的精确匹配记录。

## OLIX 官方动态

`sourceId=official-olix` · 还需审核 `20` 条 · `sampleDigest=704b8c63d3e81641`

当前没有可追溯的精确匹配记录。

## Omilia 官方动态

`sourceId=official-omilia` · 还需审核 `20` 条 · `sampleDigest=de5522fac8d054d9`

1. **IDC MarketScape 2026 | Vendor Assessment Report**
   - `article` · `official-omilia-ee16b1d3c30bc5c2` · 2026-09-25 · Omilia
   - https://omilia.com/resources/analyst-reports/leader-in-idc-marketscape-worldwide-conversational-intelligence-analytics-software-2026

## OpenAI

`sourceId=openai` · 还需审核 `20` 条 · `sampleDigest=b4f6612292e93263`

1. **Better prompt caching for GPT-6**
   - `article` · `openai-f9027d80e820682e` · 2026-09-23 · OpenAI
   - https://openai.com/index/better-prompt-caching-for-gpt-6
2. **Expanding OpenAI Academy with new learning paths**
   - `article` · `openai-2f8d9b98fc157bb3` · 2026-09-23 · OpenAI
   - https://openai.com/index/expanding-openai-academy-with-new-learning-paths
3. **Airbnb widens access to GPT-6 Astra and OpenAI frontier models**
   - `article` · `openai-0765deb144589280` · 2026-09-23 · OpenAI
   - https://openai.com/index/airbnb-gpt-6-astra
4. **ChatGPT Ads expands to Southeast Asia and Taiwan**
   - `article` · `openai-bb71e409dd7f29f7` · 2026-09-22 · OpenAI
   - https://openai.com/index/chatgpt-ads-expands-southeast-asia-taiwan

## OpenAI

`sourceId=x-openai` · 还需审核 `20` 条 · `sampleDigest=378feccf53aa3983`

1. **OpenAI：Introducing dots, powered by GPT-6 Astra. Remarkably capable, always-on agents built to handle everything. https://t.co/inY5BZj3Kz**
   - `article` · `x-openai-c6b21166191d4ea4` · 2026-09-29 · OpenAI
   - https://x.com/OpenAI/status/2104984504133918973
2. **OpenAI：Codex Security Cloud is getting a major upgrade, with access to cyber-capable models through Daybreak Blue included by default. It scans entire GitHub**
   - `article` · `x-openai-b07c7f96f57275c2` · 2026-09-29 · OpenAI
   - https://x.com/OpenAI/status/2104987422308335828
3. **OpenAI：Ultrafast is available today for GPT-6 Astra in Codex, ChatGPT Work, and the API, with GPT-6.1 Sol coming soon. To access it in Codex and ChatGPT Work**
   - `article` · `x-openai-9c2e751f480158fc` · 2026-09-29 · OpenAI
   - https://x.com/OpenAI/status/2104993967985381673
4. **OpenAI：This is Ultrafast. Our premium speed tier, Ultrafast offers up to 8x faster token generation (300 tokens per second) in Codex and up to 6x in the API.**
   - `article` · `x-openai-27d08b7fd1e78307` · 2026-09-29 · OpenAI
   - https://x.com/OpenAI/status/2104993966043320759
5. **OpenAI：We’re also reopening Pro 200 subscriptions, with continued access to frontier models like Astra, including our new GPT-6.1 Sol model which brings near**
   - `article` · `x-openai-112e285b367229e7` · 2026-09-29 · OpenAI
   - https://x.com/OpenAI/status/2104993969486930015

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

`sourceId=openai-newsroom` · 还需审核 `20` 条 · `sampleDigest=982b74986340df2b`

1. **Helping small businesses put AI to work**
   - `article` · `openai-newsroom-061338e668ed6974` · 2026-09-30 · OpenAI
   - https://openai.com/index/helping-small-businesses-put-ai-to-work
2. **Introducing dots**
   - `article` · `openai-newsroom-dec620cb7225d243` · 2026-09-29 · OpenAI
   - https://openai.com/index/introducing-dots
3. **Introducing GPT-6.1 Sol**
   - `article` · `openai-newsroom-d6b9f5e651b1891e` · 2026-09-29 · OpenAI
   - https://openai.com/index/introducing-gpt-6-1-sol
4. **Basis completes a tax workbook 2x faster with GPT-6 Astra**
   - `article` · `openai-newsroom-eb674100bb687fff` · 2026-09-28 · OpenAI
   - https://openai.com/index/basis-tax-workbook-with-astra
5. **Towards safety cases for frontier AI training**
   - `article` · `openai-newsroom-2fc54b690d7b20a2` · 2026-09-28 · OpenAI
   - https://openai.com/index/towards-safety-cases-for-frontier-ai-training
6. **The Lenfest Institute grows landmark program with expanded OpenAI support**
   - `article` · `openai-newsroom-0adf5bb2a473897d` · 2026-09-28 · OpenAI
   - https://openai.com/index/lenfest-ai-collaborative-expansion
7. **Grab and OpenAI bring practical AI skills to Southeast Asia**
   - `article` · `openai-newsroom-5ab590850491008e` · 2026-09-23 · OpenAI
   - https://openai.com/index/grab-openai-ai-skills-southeast-asia
8. **Two years of OpenAI Academy**
   - `article` · `openai-newsroom-52e46e8371e1f699` · 2026-09-23 · OpenAI
   - https://openai.com/index/two-years-of-openai-academy
9. **Harvey turns legal context into stronger drafts with GPT-6 Astra**
   - `article` · `openai-newsroom-52b80abd4e046c04` · 2026-09-23 · OpenAI
   - https://openai.com/index/harvey-from-context-to-confidence-with-astra
10. **Ringg’s AI agents resolve up to 65% of customer calls with OpenAI**
   - `article` · `openai-newsroom-4e56c7312349a760` · 2026-09-23 · OpenAI
   - https://openai.com/index/ringg
11. **Introducing MentalHealthBench**
   - `article` · `openai-newsroom-3d7b9aab56c8f4fe` · 2026-09-23 · OpenAI
   - https://openai.com/index/introducing-mentalhealthbench
12. **Sam Altman’s remarks at the United Nations Security Council**
   - `article` · `openai-newsroom-347b65ce144a221e` · 2026-09-23 · OpenAI
   - https://openai.com/index/sam-altman-un-security-council-remarks
13. **Introducing GPT-6 Sol and Luna**
   - `article` · `openai-newsroom-73461b3e97af0d93` · 2026-09-22 · OpenAI
   - https://openai.com/index/introducing-gpt-6-sol-and-luna
14. **Priorities and principles for effective third party assessments**
   - `article` · `openai-newsroom-60efaf744a4d6c2c` · 2026-09-22 · OpenAI
   - https://openai.com/index/priorities-principles-third-party-assessments
15. **Parallel cut research time and cost in half with GPT‑6 Astra**
   - `article` · `openai-newsroom-3fcefd9c665fb2c2` · 2026-09-22 · OpenAI
   - https://openai.com/index/parallel-cuts-time-and-cost-with-astra
16. **Higgsfield AI ships new video features in a day with GPT-6 Astra**
   - `article` · `openai-newsroom-8fe4474fdbb9c4c4` · 2026-09-21 · OpenAI
   - https://openai.com/index/higgsfield-from-prompt-to-production-with-astra

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

`sourceId=prnewswire-tech` · 还需审核 `20` 条 · `sampleDigest=99cefcaa5662748d`

1. **IBM Introduces Self-Hosted Deployment for IBM Bob to Help Enterprises Advance AI Sovereignty and Governance**
   - `article` · `prnewswire-tech-5be31de593332e68` · 2026-10-01 · 科技产业
   - https://www.prnewswire.com/news-releases/ibm-introduces-self-hosted-deployment-for-ibm-bob-to-help-enterprises-advance-ai-sovereignty-and-governance-302893486.html
2. **SEMIFIVE Signs Turnkey Contract with Mobilint to Develop Robotics AI Chip Under 'K-On-Device AI Semiconductor' Program**
   - `article` · `prnewswire-tech-4f2224f32633d457` · 2026-10-01 · 科技产业
   - https://www.prnewswire.com/news-releases/semifive-signs-turnkey-contract-with-mobilint-to-develop-robotics-ai-chip-under-k-on-device-ai-semiconductor-program-302895266.html
3. **Kyndryl Report: As AI Broadens Modernization Agenda, Leaders Prioritize Business Outcomes Over Replacing Legacy Systems**
   - `article` · `prnewswire-tech-235487cf4f862c74` · 2026-10-01 · 科技产业
   - https://www.prnewswire.com/news-releases/kyndryl-report-as-ai-broadens-modernization-agenda-leaders-prioritize-business-outcomes-over-replacing-legacy-systems-302895199.html

## PsiQuantum 官方动态

`sourceId=official-psiquantum` · 还需审核 `20` 条 · `sampleDigest=ba8b19ef3315c0c5`

1. **PsiQuantum at IEEE Quantum Week 2026**
   - `article` · `official-psiquantum-47acda46da768caa` · 2026-09-09 · PsiQuantum
   - https://www.psiquantum.com/news-import/psiquantum-at-ieee-quantum-week-2026
2. **PsiQuantum Finalizes $100 Million Award with the U.S. Department of Commerce**
   - `article` · `official-psiquantum-cb11d91d6241ac46` · 2026-09-08 · PsiQuantum
   - https://www.psiquantum.com/news-import/psiquantum-finalizes-100-million-award-with-the-us-department-of-commerce
3. **PsiQuantum, Brookhaven Lab Partner to Accelerate Quantum Application Development Using Construct Software Tool**
   - `article` · `official-psiquantum-110ba345e51fe8ea` · 2026-09-02 · PsiQuantum
   - https://www.psiquantum.com/news-import/psiquantum-brookhaven-lab-partner-to-accelerate-quantum-application-development-using-construct-software-tool

## Reach Capital 官方动态

`sourceId=official-reach-capital` · 还需审核 `20` 条 · `sampleDigest=7708d7d6f31c24b2`

1. **Metabolic Health and Allergy: 2 Routes to Family-Based Pediatric Care**
   - `article` · `official-reach-capital-9ea890c7f6f03b46` · 2026-09-03 · Reach Capital
   - https://www.reachcapital.com/resources/thought-leadership/metabolic-health-allergy-family-based-pediatric-care
2. **The Family as Patient: Investing in the Next Wave of Pediatric Health**
   - `article` · `official-reach-capital-c8af80ec9148b725` · 2026-08-31 · Reach Capital
   - https://www.reachcapital.com/resources/thought-leadership/family-pediatric-health

## Recursion Pharmaceuticals 官方动态

`sourceId=official-recursion` · 还需审核 `20` 条 · `sampleDigest=840715263d0f33f5`

当前没有可追溯的精确匹配记录。

## Redwood Materials 官方动态

`sourceId=official-redwood-materials` · 还需审核 `20` 条 · `sampleDigest=1e73012db66f2b5e`

1. **Cal Lankton named Chief Operating Officer at Redwood Materials**
   - `article` · `official-redwood-materials-e50c66af8e485bb5` · 2026-09-21 · Redwood Materials
   - https://www.redwoodmaterials.com/news/cal-lankton-named-chief-operating-officer-at-redwood-materials

## Relativity Space 官方动态

`sourceId=official-relativity-space` · 还需审核 `20` 条 · `sampleDigest=e006ee40ff9b862e`

1. **August 2026 Company Update**
   - `article` · `official-relativity-space-2250b1b4454f8011` · 2026-09-11 · Relativity Space
   - https://www.relativityspace.com/press-release/2026/9/10/august-2026-company-update

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

`sourceId=official-sambanova` · 还需审核 `20` 条 · `sampleDigest=b9f6eb1ec92c9f3c`

1. **Sovereign AI: Own Your Infrastructure, Models & Inference**
   - `article` · `official-sambanova-1c4cab4d36f321b1` · 2026-09-28 · SambaNova Systems
   - https://sambanova.ai/blog/sovereign-ai

## Scale AI

`sourceId=scale-ai` · 还需审核 `20` 条 · `sampleDigest=bdb39dae34072b5b`

1. **To Steer the AI Frontier, Washington Must Build Its Testing Power**
   - `article` · `scale-ai-b10eb381e6fd015d` · 2026-09-25 · Scale AI
   - https://scale.com/blog/steer-the-ai-frontier-washington-must-build-its-testing-power
2. **Deploying Enterprise AI Agents with Scale and Google Cloud**
   - `article` · `scale-ai-ac287aeabc889d77` · 2026-09-22 · Scale AI
   - https://scale.com/blog/deploying-enterprise-ai-agents-with-scale-and-google-cloud
3. **Why You Need to Red Team Your Enterprise AI**
   - `article` · `scale-ai-821d1c79cab2b368` · 2026-09-16 · Scale AI
   - https://scale.com/blog/why-you-need-to-red-team-your-enterprise-ai
4. **In An Agentic World Where Automation Gets Cheap, Which Work Is Worth Routing to a Human?**
   - `article` · `scale-ai-f52309ebc2b9adca` · 2026-09-15 · Scale AI
   - https://scale.com/blog/hitl-routing

## Scale AI 官方动态

`sourceId=official-scale-ai` · 还需审核 `20` 条 · `sampleDigest=2f665fc1199b43e5`

当前没有可追溯的精确匹配记录。

## Shield AI 官方动态

`sourceId=official-shield-ai` · 还需审核 `20` 条 · `sampleDigest=a0579d70c179652c`

1. **Shield AI names Kansas and Washington the flight test and production homes of X-BAT**
   - `article` · `official-shield-ai-7bda32cedafa7982` · 2026-09-30 · Shield AI
   - https://shield.ai/shield-ai-names-kansas-and-washington-the-flight-test-and-production-homes-of-x-bat
2. **Shield AI and Kraken Technology Group demonstrate Hivemind-enabled autonomous maritime teaming**
   - `article` · `official-shield-ai-661368f71d54faed` · 2026-09-28 · Shield AI
   - https://shield.ai/shield-ai-and-kraken-technology-group-demonstrate-hivemind-enabled-autonomous-maritime-teaming
3. **A New Tempo for Defense Software**
   - `article` · `official-shield-ai-3d017845e7806c86` · 2026-09-24 · Shield AI
   - https://shield.ai/a-new-tempo-for-defense-software

## Shopify 官方动态

`sourceId=official-shopify` · 还需审核 `20` 条 · `sampleDigest=51b883d0bcce0fe1`

当前没有可追溯的精确匹配记录。

## Shopify 官方动态

`sourceId=official-user-shopify` · 还需审核 `20` 条 · `sampleDigest=c5de1fb0e02dc3a7`

当前没有可追溯的精确匹配记录。

## Shopify 官方网站

`sourceId=user-source-source-auto-shopify` · 还需审核 `20` 条 · `sampleDigest=2ddbee055a110ae8`

当前没有可追溯的精确匹配记录。

## Sierra 官方动态

`sourceId=official-sierra` · 还需审核 `20` 条 · `sampleDigest=556c7f3f7b97b21f`

1. **Ghostwriter: When AI goes from tool to teammate**
   - `article` · `official-sierra-aaad91451343c5e9` · 2026-09-28 · Sierra
   - https://sierra.ai/blog/ghostwriter-ai-tool-to-teammate

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

`sourceId=user-source-source-the-washington-post` · 还需审核 `20` 条 · `sampleDigest=db3e0b1cef50d0eb`

1. **The Washington Post：The votes are in, and a new fat bear champion has been crowned in Alaska: 89 “Backpack.” He earned his nickname by climbing on his mother’s back as a**
   - `article` · `user-source-source-the-washington-post-fe399b81b54d71de` · 2026-09-30 · 科技产业
   - https://x.com/washingtonpost/status/2105258888836587719
2. **The Washington Post：With grocery prices going up, every extra day of freshness counts. Take our quiz to find out whether your storage habits are helping your food last or**
   - `article` · `user-source-source-the-washington-post-bade560259d87687` · 2026-09-30 · 科技产业
   - https://x.com/washingtonpost/status/2105266486050689414
3. **The Washington Post：Fatima Zahra El Mansouri was named Morocco’s first female prime minister after her party swept parliamentary elections last week. https://t.co/jePXeQg**
   - `article` · `user-source-source-the-washington-post-7deca56b9a50d7b6` · 2026-09-30 · 科技产业
   - https://x.com/washingtonpost/status/2105175836579996149
4. **The Washington Post：U.S. forces are set to depart from bases in Iraq following two decades of American involvement that resulted in the deaths of hundreds of thousands of**
   - `article` · `user-source-source-the-washington-post-7d213c395772fb07` · 2026-09-30 · 科技产业
   - https://x.com/washingtonpost/status/2105221141958717716
5. **The Washington Post：The remnants of Hurricane Polo are racing across the panhandles of Texas and Oklahoma early Wednesday, following days of flooding in the Southwest. ht**
   - `article` · `user-source-source-the-washington-post-71e71f670065f446` · 2026-09-30 · 科技产业
   - https://x.com/washingtonpost/status/2105273992311349619
6. **The Washington Post：$1.5 billion has been spent on advertising for Senate and House races overall, an increase of $317 million from last week, according to a Post analysi**
   - `article` · `user-source-source-the-washington-post-46357b7b3f51ecfb` · 2026-09-30 · 科技产业
   - https://x.com/washingtonpost/status/2105206051800834300
7. **The Washington Post：In February, the Kansas state legislature passed a law that required all driver’s licenses to reflect sex at birth. Roughly 1,700 intersex and transge**
   - `article` · `user-source-source-the-washington-post-3c7f4e1dabdfcb7c` · 2026-09-30 · 科技产业
   - https://x.com/washingtonpost/status/2105251392780718201
8. **The Washington Post：Analysis: In an unpredictable election, with an unpopular president, anything could happen. We just ranked the Senate races most likely to flip party**
   - `article` · `user-source-source-the-washington-post-37f1a07907104065` · 2026-09-30 · 科技产业
   - https://x.com/washingtonpost/status/2105236259920609615
9. **The Washington Post：For over a decade, the question has haunted Mexico: What happened to the 43 rural college students who were taken into police custody in 2014 — and th**
   - `article` · `user-source-source-the-washington-post-23109efe83212706` · 2026-09-30 · 科技产业
   - https://x.com/washingtonpost/status/2105190954533540122
10. **The Washington Post：Breaking news: A flight carrying about 180 passengers to Tel Aviv from Dubai was diverted to Saudi Arabia after a midair altercation prompted a hijack**
   - `article` · `user-source-source-the-washington-post-0f6331693a34e430` · 2026-09-30 · 科技产业
   - https://x.com/washingtonpost/status/2105263287432544393

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

`sourceId=weride` · 还需审核 `20` 条 · `sampleDigest=5ed888688b724260`

1. **WeRide Recognized on Fortune's 2026 Change the World List as the Only Autonomous Driving Company Honored**
   - `article` · `weride-2d8c053724b5f015` · 2026-09-24 · 文远知行
   - https://ir.weride.ai/news-releases/news-release-details/weride-recognized-fortunes-2026-change-world-list-only
2. **WRD 3.0 Powers the AION i60 with Championship-Winning Technology Available from Delivery**
   - `article` · `weride-80a91d205374a9e2` · 2026-09-15 · 文远知行
   - https://ir.weride.ai/news-releases/news-release-details/wrd-30-powers-aion-i60-championship-winning-technology-available
3. **WeRide, Uber, and AVOMO receive Spain’s First National Operating Permit for Level 4 Autonomous Passenger Vehicles**
   - `article` · `weride-63722d0eac892015` · 2026-09-10 · 文远知行
   - https://ir.weride.ai/news-releases/news-release-details/weride-uber-and-avomo-receive-spains-first-national-operating
4. **WeRide Included in HKEX Tech 100 Index Following September 2026 Quarterly Review**
   - `article` · `weride-f15807f8d1b64ad7` · 2026-08-31 · 文远知行
   - https://ir.weride.ai/news-releases/news-release-details/weride-included-hkex-tech-100-index-following-september-2026

## xAI

`sourceId=xai` · 还需审核 `20` 条 · `sampleDigest=d9e3a51233efd057`

1. **Team Bots: AI coworkers that learn from your team**
   - `article` · `xai-52b14ec01b86fb13` · 2026-09-28 · xAI
   - https://x.ai/news/team-bots
2. **How SpaceXAI is using Grok Bot to scale customer support**
   - `article` · `xai-03d2992c5a1bb0eb` · 2026-09-22 · xAI
   - https://x.ai/news/grok-bot-customer-support
3. **Introducing Grok 4.7**
   - `article` · `xai-39b901174b543376` · 2026-09-21 · xAI
   - https://x.ai/news/grok-4-7
4. **Introducing Grok Voice Transcribe 2.0**
   - `article` · `xai-ce5508c16c0a4e20` · 2026-09-18 · xAI
   - https://x.ai/news/grok-voice-transcribe-2
5. **Memory in Grok Build**
   - `article` · `xai-e3779e8809a662a0` · 2026-09-16 · xAI
   - https://x.ai/news/grok-build-memory
6. **Setting Grok Bot loose on procurement**
   - `article` · `xai-b0f85a5b072300fb` · 2026-09-04 · xAI
   - https://x.ai/news/grok-bot-procurement
7. **Grok Bot for Enterprise**
   - `article` · `xai-eef9c9e362bd416f` · 2026-09-03 · xAI
   - https://x.ai/news/grok-bot-for-enterprise
8. **Designing Grok Bot for a world of persistent agents**
   - `article` · `xai-c3a0d443767e88bd` · 2026-09-03 · xAI
   - https://x.ai/news/designing-grok-bot
9. **Biosecurity at the frontier**
   - `article` · `xai-d4276b2db9013a3c` · 2026-09-01 · xAI
   - https://x.ai/news/biosafety-at-the-frontier
10. **Grok Bot now works with X**
   - `article` · `xai-a39ebb9cbdf1604d` · 2026-08-29 · xAI
   - https://x.ai/news/grok-bot-and-x

## xAI 官方动态

`sourceId=official-xai` · 还需审核 `20` 条 · `sampleDigest=20a376500412b439`

当前没有可追溯的精确匹配记录。

## Y Combinator · 核心团队页

`sourceId=user-source-source-auto-institution-team-y-combinator` · 还需审核 `20` 条 · `sampleDigest=635e91c29c8778a0`

1. **Y Combinator**
   - `article` · `user-source-source-auto-institution-team-y-combinator-1a75fc63d5c987c4` · 2026-09-28 · 科技产业
   - https://www.ycombinator.com/events

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

`sourceId=user-source-source-auto-institution-team-131095855545` · 还需审核 `20` 条 · `sampleDigest=48365a107a70c971`

1. **启明创投 | 以智启众 以勤得明**
   - `article` · `user-source-source-auto-institution-team-131095855545-360d355e488723e7` · 2026-09-16 · 科技产业
   - https://www.qimingvc.com/cn
2. **启明星 | Robochallenge全球化进展与生态共建发布| WAIC 2026 | 启明创投**
   - `article` · `user-source-source-auto-institution-team-131095855545-4b1561ba3cfdd04e` · 2026-09-14 · 科技产业
   - https://www.qimingvc.com/cn/news/%E5%90%AF%E6%98%8E%E6%98%9F-robochallenge%E5%85%A8%E7%90%83%E5%8C%96%E8%BF%9B%E5%B1%95%E4%B8%8E%E7%94%9F%E6%80%81%E5%85%B1%E5%BB%BA%E5%8F%91%E5%B8%83-waic-2026
3. **启明星 | 佳量脑科学连续完成C轮及D轮两轮融资，启明创投领投C轮 | 启明创投**
   - `article` · `user-source-source-auto-institution-team-131095855545-0fc87012f374b083` · 2026-09-08 · 科技产业
   - https://www.qimingvc.com/cn/news/%E5%90%AF%E6%98%8E%E6%98%9F-%E4%BD%B3%E9%87%8F%E8%84%91%E7%A7%91%E5%AD%A6%E8%BF%9E%E7%BB%AD%E5%AE%8C%E6%88%90c%E8%BD%AE%E5%8F%8Ad%E8%BD%AE%E4%B8%A4%E8%BD%AE%E8%9E%8D%E8%B5%84%EF%BC%8C%E5%90%AF%E6%98%8E%E5%88%9B%E6%8A%95%E9%A2%86%E6%8A%95c%E8%BD%AE
4. **启明ESG | 启明创投捐赠驰援西藏吉隆泥石流灾区 助力抢险救灾与灾后重建 | 启明创投**
   - `article` · `user-source-source-auto-institution-team-131095855545-b88926d6ae83b8ac` · 2026-09-04 · 科技产业
   - https://www.qimingvc.com/cn/news/%E5%90%AF%E6%98%8Eesg-%E5%90%AF%E6%98%8E%E5%88%9B%E6%8A%95%E6%8D%90%E8%B5%A0%E9%A9%B0%E6%8F%B4%E8%A5%BF%E8%97%8F%E5%90%89%E9%9A%86%E6%B3%A5%E7%9F%B3%E6%B5%81%E7%81%BE%E5%8C%BA-%E5%8A%A9%E5%8A%9B%E6%8A%A2%E9%99%A9%E6%95%91%E7%81%BE%E4%B8%8E%E7%81%BE%E5%90%8E%E9%87%8D%E5%BB%BA
5. **启明星 | 阶跃星辰朱亦博：进入Agent时代，AI基础设施要实现智能、速度与成本的综合最优 | WAIC 2026 | 启明创投**
   - `article` · `user-source-source-auto-institution-team-131095855545-9591c82e9cd8e74e` · 2026-08-31 · 科技产业
   - https://www.qimingvc.com/cn/news/%E5%90%AF%E6%98%8E%E6%98%9F-%E9%98%B6%E8%B7%83%E6%98%9F%E8%BE%B0%E6%9C%B1%E4%BA%A6%E5%8D%9A%EF%BC%9A%E8%BF%9B%E5%85%A5agent%E6%97%B6%E4%BB%A3%EF%BC%8Cai%E5%9F%BA%E7%A1%80%E8%AE%BE%E6%96%BD%E8%A6%81%E5%AE%9E%E7%8E%B0%E6%99%BA%E8%83%BD%E3%80%81%E9%80%9F%E5%BA%A6%E4%B8%8E%E6%88%90%E6%9C%AC%E7%9A%84%E7%BB%BC%E5%90%88%E6%9C%80%E4%BC%98-waic-2026
6. **启明星 | 芯光界完成亿元天使轮融资，启明创投独家投资 | 启明创投**
   - `article` · `user-source-source-auto-institution-team-131095855545-7b5da7a1fb11c00b` · 2026-08-25 · 科技产业
   - https://www.qimingvc.com/cn/news/%E5%90%AF%E6%98%8E%E6%98%9F-%E8%8A%AF%E5%85%89%E7%95%8C%E5%AE%8C%E6%88%90%E4%BA%BF%E5%85%83%E5%A4%A9%E4%BD%BF%E8%BD%AE%E8%9E%8D%E8%B5%84%EF%BC%8C%E5%90%AF%E6%98%8E%E5%88%9B%E6%8A%95%E7%8B%AC%E5%AE%B6%E6%8A%95%E8%B5%84
