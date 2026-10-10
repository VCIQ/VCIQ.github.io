# 全球科创投资机构：审核后快速发布（受控入口）

## 数据边界

每日 [Innovation investor official-source scout](../.github/workflows/innovation-investor-source-scout.yml)
只能发现原始官网导航链接。其审核产物不是公司融资、个人言论或项目退出的事实证明。
正式事件继续写入 `config/innovation_investor_evidence.json`，新项目身份只写入
`config/innovation_investor_project_identities.json`；首页使用既有
`lib/homepage-investor-publication.ts` 静态构建桥接，不新增新闻 writer、定时采集或生产 API。

## 审核操作

1. 在 GitHub Actions 找到最近 **14 天内成功运行、分支为 main、不是 PR 测试**的
   `Innovation investor official-source scout`，记录 run ID。
2. 下载该次的 `innovation-investor-source-scout-<run_id>` 产物，先看
   `innovation-investor-review-queue.md`，再根据
   `innovation-investor-review-queue.json` 内的 `candidateId` 和原文 URL 审核。
   必须实际打开官网原文，记录原文发表日期、投资对象、行为或署名作者、证据段落。
3. 为一篇原文填写一个 `reviews` 条目。涉及新项目时，必须手动登记规范项目 ID 和
   首个身份证据 URL；已有项目只传 `newProjectIdentity: null`。
   不得把整轮融资额当作机构单独出资额，不得以联合署名认定单人交易负责人，
   不得把上市/收购视为基金现金回报。
4. 打开 `Propose reviewed investor evidence release` 工作流，选择 main，
   先执行 `operation: validate`，填入 scout run ID、下述审核 JSON。
5. 校验通过后，将同一个输入以 `operation: propose` 提交。工作流仅在受控权限下修改
   临时 PR 工作树，先执行单测与 Pages 构建，再创建 **Draft PR**；
   **不会直接 push main、不会自动合并，也不会自动发布**。
6. 人工审查 PR 中的来源 URL、事实、角色、身份及差分，再决定是否合并。
   合并后沿用现有 Pages 发布。核实生产 SHA、首页「科创」、个性化「重点」及机构专题入口。

## 输入格式

`decisions_json` 仅包含公开证据和人工审核结论，禁止写密码、Token 或未公开资料。
以下是**占位结构，不能作为真实新闻提交**；具体字段必须以已核验的官网原文替换：

```json
{
  "schemaVersion": 1,
  "reviews": [
    {
      "candidateId": "<scout 审核队列中的 candidateId>",
      "decision": "approved",
      "originalArticleVerified": true,
      "records": [
        {
          "id": "example-official-announcement-yyyymmdd",
          "institutionId": "<机构规范 ID>",
          "project": "<已核验公司名称>",
          "kind": "investment",
          "date": "YYYY-MM-DD",
          "datePrecision": "day",
          "title": "<核验后的公开中文标题>",
          "summary": "<只转述官网证实的投资事实与限制>",
          "round": null,
          "participation": "disclosed-investor",
          "roundAmount": null,
          "investorAmount": null,
          "speakers": [],
          "linkedPerson": null,
          "resultStatus": null,
          "realizedProceeds": null,
          "source": {
            "url": "https://<官网域名>/<真实文章路径>",
            "title": "<官方原文标题>",
            "publisher": "<机构名称>",
            "kind": "investor-official",
            "publishedAt": "YYYY-MM-DD",
            "locator": "<原文段落位置与可核对事实>"
          },
          "nextCheck": "<后续需独立补充的证据>"
        }
      ],
      "newProjectIdentity": null
    }
  ]
}
```

若同一原文还包含**有明确来源的署名投资观点**，可在同一个 `records` 内追加
`kind: "viewpoint"` 的记录，必须提供 `speakers`；观点记录的
`round`、`participation`、`roundAmount`、`investorAmount` 必须是 `null`。
已有官网样例不可重复入库。快速发布仅处理最近14天的日精度公告，旧文章继续走普通研究审核，
不会为了上首页修改历史日期。

## 阻断规则

- 校验人及重跑发起人均需在 `config/tracking_admins.json` 许可名单内，并走现有 `tracking-admin` 环境。
- 源审核产物必须来自最近14天**成功的 main 官方 scout**，不能使用 PR、过期或自制 JSON 冒充。
- 原文 URL 必须是对应官方域名、与审核队列候选完全一致的 HTTPS 正式路径；
  媒体转载、正文未核验、无日期或非规范公司身份一律拒绝。
- 相同官网文章与事实类型不得重复；同一机构、项目、轮次及日期不能重复登记投资。
- 公司身份必须显式复用或创建；不得自动猜测别名、共同领投或投资者个人责任。
- 新数据生成 PR 前跑本地 Python 单测、首页投资机构回归和完整 Pages 构建。
  GitHub 默认 `GITHUB_TOKEN` 创建的 PR 可能不会触发 `pull_request` 工作流；
  因此本工作流的预检记录是必需证据，最终仍由审核人判断是否可以合并。

成功的审核 **不等于** 已有新事件，也不等于已上线：无合格原文时不产生 PR；
PR 合并和 Pages 回读才是生产发布的结束条件。
