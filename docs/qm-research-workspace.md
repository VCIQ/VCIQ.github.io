# VCIQ × QM Research Workspace

## 目标

VCIQ 的公开站继续作为可复核、只读的发布层；QM 作为独立部署的交互式 Research Workspace，提供持续会话、Memory、Skills、Watch、文件和 Sandbox 能力。

QM 不是 VCIQ 的生产数据写入器，也不替代现有 GitHub Actions、Research Agent Daily、证据合同或 Pages 发布流程。

## 架构边界

```text
VCIQ GitHub Actions
  -> quality gates
  -> reviewed public/data/*.json
  -> GitHub Pages
        |
        | read-only public datasets
        v
QM Research Workspace
  -> conversations / memory / skills / watches / sandbox
  -> candidate findings
  -> optional GitHub branch + pull request
        |
        v
VCIQ validation + review + existing production pipeline
```

### QM 可以做

- 只读检索 VCIQ 已发布的数据集；
- 将公开 VCIQ 数据与网页研究、用户文件和工作区 Memory 联合分析；
- 保存研究假设、待验证事项和长期研究上下文；
- 创建内部 Watch / Cron；
- 生成候选变更；
- 在后续授予最小 GitHub 权限后创建分支或 Pull Request；
- 在 PR 中运行现有 VCIQ 校验和测试。

### QM 不可以直接做

- 直接 push 到 `main`；
- 绕过 `tools/run_pipeline.py` 或现有 quality gate；
- 直接把模型生成内容写入生产 `public/data/` 后发布；
- 在浏览器或公开仓库中保存 API key、GitHub token、QM session secret、OIDC secret；
- 用 QM Cron 重复替代已有的生产抓取和正式数据刷新计划。

## 第一阶段：只读 Research Workspace

第一阶段不授予 QM 仓库写权限，只提供公开数据读取能力。

建议单独创建私有部署仓库，例如：

```text
VCIQ/vciq-qm-deployment
```

不要把 QM 的 deployment layer、认证配置或 secret 放入 `VCIQ.github.io` 公开仓库。

QM 官方初始化方式：

```bash
mkdir vciq-qm-deployment
cd vciq-qm-deployment

npm exec --yes --package=@yc-software/qm@latest -- \
  qm init . --org vciq --target fly

npm install
```

如需 AWS，可把 `--target fly` 改为 `--target aws`。部署目标一旦确定，应按 QM 的 deployment contract 初始化新的空目录，而不是在同一目录中随意切换 provider。

## VCIQ 只读数据面

QM 第一阶段应优先读取 VCIQ 已审核的公开产物，而不是直接依赖工作树中的临时文件。

建议至少接入：

```text
https://vciq.github.io/data/venture_profiles.json
https://vciq.github.io/data/people.json
https://vciq.github.io/data/market_profiles.json
https://vciq.github.io/data/institution_entities.json
https://vciq.github.io/data/institution_events.json
https://vciq.github.io/data/listed_company_disclosures.json
https://vciq.github.io/data/articles.json
https://vciq.github.io/data/research_agent_daily.json
https://vciq.github.io/data/data_lineage.json
https://vciq.github.io/data/pipeline_health.json
```

研究结果应保留原始 URL、VCIQ evidence id（若存在）、数据时间和来源层级，避免把模型推断与原始事实混为一层。

## 建议的 VCIQ Skills

第一阶段建议实现以下只读 Skills：

### `vciq-search`

跨核心技术、赛道、人物、公司和辅助证据层检索实体与事件。

### `vciq-investigate`

围绕指定实体或主题形成 investigation workspace，结合 VCIQ 数据、公开网页与工作区文件，并显式区分事实、推断和待验证项。

### `vciq-diff`

比较不同时间点的实体状态、事件和 evidence，识别融资、产品、团队、客户、监管和技术变化。

### `vciq-thesis`

在 QM Memory 中维护研究假设、bull case、bear case、反证、置信度与下一证据需求。Memory 不作为公开事实源。

### `vciq-watch`

监控研究者指定的待验证事项。Watch 只生成内部研究任务或提示，不直接修改生产数据。

## 第二阶段：PR-only GitHub 权限

只读阶段稳定后，可以给 QM 一个最小权限 GitHub 身份。目标不是让 Agent 直接发布，而是让它生成可审查候选变更：

```text
QM finding
  -> new branch
  -> candidate patch
  -> tests / validation
  -> pull request
  -> human / repository policy review
  -> merge
  -> existing VCIQ production pipeline
```

推荐硬约束：

- 禁止直接 push `main`；
- 禁止修改 branch protection；
- 禁止修改 repository secrets；
- PR 必须通过现有 unit tests、pipeline validation、artifact audit 和 Pages build；
- 模型提出的新事实必须能绑定到允许的公开 evidence；
- 涉及生产数据的 PR 不应自动 merge。

## Pages 工作台入口

`/research-agent/` 的工作台入口由 GitHub Repository Variable 控制：

```text
QM_WORKSPACE_URL
```

Pages workflow 会在构建阶段将它映射为：

```text
NEXT_PUBLIC_QM_WORKSPACE_URL
```

这是一个公开 URL，不是 secret。

未配置时，页面显示“工作台尚未发布”，不会生成可点击的外部入口。QM 部署并验证完成后，在仓库 Settings -> Secrets and variables -> Actions -> Variables 中设置：

```text
QM_WORKSPACE_URL=https://<your-qm-portal-host>/
```

随后重新运行 Pages workflow 即可启用入口。

## 单条情报 contextual handoff

首页的卡片级研究入口不再直接跳转到通用 `/research-agent/`。`深研此条` 先进入：

```text
/research-agent/investigate/?event=<VCIQ event id>
```

该页只在用户主动进入时读取 `articles.json` 与 `ranked-intelligence.json`，按事件 ID 恢复当前情报，并整理：

- 标题、原始 URL、摘要、发布时间、赛道、公司和人物；
- 主来源、关联来源、来源层级与质量状态；
- 重要度；
- 命中的追踪词、是否人工精选、是否显式关注赛道、是否加入稍后读；
- 一份明确区分事实、推断和待验证项的研究指令。

如果 `QM_WORKSPACE_URL` 已配置，公开站会在工作台 URL 上附加一个有版本的 VCIQ handoff 合同：

```text
vciq_handoff=1
vciq_event=<event id>
vciq_context=https://vciq.github.io/research-agent/investigate/?event=<event id>
vciq_articles=https://vciq.github.io/data/articles.json
vciq_ranked=https://vciq.github.io/data/ranked-intelligence.json
```

这里刻意不把完整摘要、个人偏好或任何私有凭据塞进 URL。当前页面同时提供“复制研究指令”，并在打开工作台时复制该指令；这样即使某个 QM 部署尚未实现 URL 参数自动接管，也不会把一个普通跳转伪装成已经完成上下文注入。

QM 的 `vciq-investigate` 适配器实现后，应优先读取 `vciq_event`，再从 `vciq_articles` / `vciq_ranked` 对应的公开数据集中解析事件；`vciq_context` 用作人类可检查的回链。适配器必须忽略未知字段，并且不得根据 URL 参数获得任何额外生产写权限。

## Secret 与身份边界

以下信息只能存在于 QM deployment provider、QM keychain、OIDC provider 或 GitHub Secrets 等私有控制面：

- LLM provider API keys；
- QM session / identity secrets；
- OIDC client secret；
- SMTP / Resend credentials；
- GitHub App / token；
- 私有 connector credentials。

不得把这些值写入：

```text
app/
components/
lib/
config/
public/
docs/
NEXT_PUBLIC_*
```

`NEXT_PUBLIC_*` 变量会进入浏览器可见构建产物，只允许存放非敏感公开配置。

## 验收顺序

1. 合并本仓库的 gated workspace 入口；
2. 创建独立私有 QM deployment repository；
3. 在 Fly.io 或 AWS 部署 QM；
4. 配置仅限研究人员的登录；
5. 接入 VCIQ 公开数据并实现 `vciq-search` / `vciq-investigate`；
6. 验证 QM 无法写 `VCIQ.github.io`；
7. 设置 `QM_WORKSPACE_URL`，启用公开站入口；
8. 验证 `深研此条 -> contextual handoff -> Research Workspace` 的 event id、数据集和回链均能被正确消费；
9. 运行一段时间后再评估 PR-only GitHub 权限；
10. 最后再增加 `vciq-watch`、`vciq-thesis` 和更广泛协作能力。
