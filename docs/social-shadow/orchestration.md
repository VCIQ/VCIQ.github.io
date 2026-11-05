# PR-09：统一影子运行、恢复、停止与评估

代码入口：`python -m tools.social.shadow_run`。所有输出均为 shadow，禁止发布。
本入口不调用原生产爬虫、不写 public/data 或正式科创池，也不合并 PR。
通过合成数据测试不代表真实登录、签名、源站数据形状或抓取效果已验收。

## 一、组成与运行边界

`run`：读取原配置或显式配置快照 → 公平轮询计划 → 现有独立 Worker →
原调度 checkpoint → 冻结完成集合 → 密封批次 → 幂等内容库 → 待审核队列。

`recover`：只读取此前已经获得的结果，恢复密封/导入/审核；从不重新查询平台。

`health`：只读调度状态、平台暂停、内容计数、审核积压和运行报告。

`stop`：在私有 STATE 写停止标记。`resume --confirmed` 仅清除这个标记，
不会清除认证、验证码或尚未到期的限流暂停，不会修改运行配置。

`evaluate`：按明确的人工事件判定和生产基线快照，统计新增有效事件；
不以帖子量、点赞量或审核接受数充当收益。

输入、运行日志、数据库、批次、结果及审核证据全部在仓库外 STATE。
新的 orchestrator 与旧的单平台命令不得在同一 STATE 并行调度；
平台租约/浏览器锁仍提供底层隔离，但不能代替统一运行边界。

## 二、首次准备

需要 Python 3.12+；MediaCrawler 部署与专用浏览器会话按各平台文档准备，
上游仍固定 `8f583999006d5b692272c608440e193ca282e73b`。
不使用日常 Chrome Profile，不把 Cookie、密码或 STATE 交给公开 Actions。

STATE 必须已存在，权限700；输入JSON、数据库权限600。
Mac 应使用实际解析路径：系统 `/tmp` 通常是软链接，不能降低路径护栏来绕过。
首次创建配置、安装浏览器和人工登录是显式的本机准备，不由 run 自动安装或自动登录。
开发/测试过程不会创建真实采集凭证。

假设 STATE 和 RUNTIME 指向已准备的真实绝对路径，先预览：

```sh
python -m tools.social.shadow_run run \
  --state-dir "$STATE" --runtime-config "$RUNTIME" \
  --platform xhs --platform wb --platform bili --platform zhihu
```

不加 `--live` 时不创建数据库、租约、运行日志，不启动子进程。
本地 runtime 中总开关与目标平台开关必须开启，且另有 `--live` 才执行。
仓库中 `config/social_discovery.json` 的静态默认开关继续关闭。
动态 runtime 只能选择是否运行，不能扩大既有 policy 的预算。

准备完成后的一次有界影子运行：

```sh
python -m tools.social.shadow_run run \
  --state-dir "$STATE" --runtime-config "$RUNTIME" \
  --platform xhs --platform wb --platform bili --platform zhihu \
  --wall-seconds 900 --live
```

微信必须再提供现有格式的联合请求预算文件：

```sh
python -m tools.social.shadow_run run \
  --state-dir "$STATE" --runtime-config "$RUNTIME" \
  --platform wechat --wechat-provider sogou-weixin --wechat-provider bing-rss \
  --budget-file "$STATE/wechat-budget.json" --wall-seconds 900 --live
```

预算字段仍为 windowStart、windowEnd、combinedMaxRequests、productionReservedRequests。
不得借换文件/重开进程重置同一窗口；本入口不修改原生产任务的实际请求计数。
其他平台继续沿用各自认证/搜索/详情请求上限、最小请求间隔和单任务超时。
`--wall-seconds` 是新任务准入预算，不是包含Git核查、数据库I/O和清理时间的OS硬截止；
只有剩余时间能容纳任务预算与清理余量时才启动，超出的任务列为 wall_budget。

## 三、运行日志与恢复协议

每轮使用原计划的 runId：

```text
STATE/orchestration/<runId>/
  intent.json           不可覆盖的计划、查询上下文、策略和公司注册表快照
  journal.json          各任务的实际执行进度
  results/<attemptId>.json  校验过的原始规范化结果
  closure.json          不可追加的本轮完成集合及其结果哈希
  batch/                PR-07规定的3个JSONL和manifest
  report.json           completed / degraded / blocked及明确分母
```

日志带 SHA-256 和大小限制；不可覆盖文件先完整写临时文件再原子发布。
哈希用于校验意外变化，不是来源签名，不保证对抗能重写整个STATE的恶意本机用户。
新 run 不能越过尚未完成存储/审核的旧 run。

```sh
python -m tools.social.shadow_run recover \
  --state-dir "$STATE" --runtime-config "$RUNTIME" --run-id '<实际runId>'
```

恢复顺序是本轮保存结果 → 调度checkpoint → 私有pending；同时存在时必须一致。
一律重新验证完整回执、身份、计数和观察，退出码0不是成功证据。
认证/验证/限流之后的部分数据可以保留，但不提升为成功覆盖。
没有回执的任务只记录 not_started、disabled、stopped、wall_budget 或
interrupted_without_receipt，绝不补造平台“空结果”。

若子进程可能仍运行，恢复先写 stop，等待原租约边界，返回 blocked；不强行续租、
不伪造过去时间完成 checkpoint，不绕过原平台暂停。过期但有效的结果可用于入库，
但报告 checkpointReconciliationRequired=true，保持 stop 等待本机核查。
仅存储/审核中断时可幂等重试：内容不会重复记账，原决定与证据pin保留。
closure 完成后迟到结果不会追加到本轮。需要另行保留调查，不能改写已密封run。

清理 `.tmp-*` 必须在确认没有相应进程后进行；不要删除原批次、checkpoint或pin。
如果崩溃留下同一不可覆盖文件的临时硬链接，私有文件检查会拒绝多链接文件，
应先核对内容和进程再处理临时项，不允许自动放宽文件边界。

## 四、停止和状态检查

```sh
python -m tools.social.shadow_run stop --state-dir "$STATE" --runtime-config "$RUNTIME"
python -m tools.social.shadow_run health --state-dir "$STATE" --runtime-config "$RUNTIME"
python -m tools.social.shadow_run resume --confirmed --state-dir "$STATE" --runtime-config "$RUNTIME"
```

统一入口在每个任务前重新读runtime；独立子进程在每个受管API请求前再检查
stop及平台启用状态。微信在配额扣减之前检查；其他平台在间隔等待结束后、HTTP发送前检查。
已在途请求和Chromium内部资源请求不保证立即中止；这不是OS网络沙箱。
限流/验证码仍立即停止该平台任务，不自动登录、换IP或重试规避。
损坏、软链接或目录形式的停止标记也视为停止，不跟随到外部位置。

completed：所有计划任务有正常回执且存储/审核完成，不等于搜索全站穷尽。
degraded：完成了可用数据处理，但有部分失败、暂停、未执行或checkpoint待核对。
blocked：数据或状态校验/存储/审核未完成，需要恢复；不能据此宣称成功。
idle：本轮无可调度任务，查看health中的暂停与覆盖状态，不解释为平台健康。

report逐条保留回执completeness、耗时和观察数；collectorInvocations是调用次数，
不是HTTP请求量。health中的liveAcceptance始终not_attested；不会从合成测试/人工接受推断平台已验收。
私有历史目录显式上限1000轮，不静默删除旧审计材料，达到上限应停机归档再设计扩展。

## 五、收益评估输入

`baseline.json` 为操作者在相同窗口导出的生产文章ID快照：

```json
{"windowStart":"2026-11-01T00:00:00Z","windowEnd":"2026-11-02T00:00:00Z","complete":false,"articleIds":[]}
```

`assessment.json` 使用规范JSON的 SHA-256（tools.social.contracts.digest）绑定baseline，
由实际复核者将多个平台帖归成一个eventId，并填写valid/invalid/uncertain：

```json
{"baselineHash":"<实际baseline哈希>","reviewedBy":"local-reviewer","events":[
  {"eventId":"reviewed-event-001","verdict":"uncertain",
   "evidence":[{"signalId":"<实际signalId>","contentHash":"<实际证据版本哈希>"}],
   "baselineArticleIds":[],"identityError":false}
]}
```

同一个signal不能重复分配，证据版本必须存在，生产引用ID必须属于所给baseline，
信号首次发现时间必须位于窗口内。不能用随机示例代替真实判断。

```sh
python -m tools.social.shadow_run evaluate --state-dir "$STATE" --runtime-config "$RUNTIME" \
  --assessment "$STATE/assessment.json" --baseline "$STATE/baseline.json"
```

未审核时比率为null；baseline不完整时“新增有效事件”是null而非0。
报告明确已审核/未审核信号、人工事件分组、非随机抽样限制；不外推到全部帖子。
没有成本/发现时间数据时cost和discoveryLatency保持null。
baseline完整性和事实判定来自显式操作者快照，不是工具独立认证；更不能据此自动入池。

## 六、验收与回滚

公共CI只运行合成数据、离线契约和本机HTTP；不设置真实采集定时任务、账号秘密或自托管Runner。
新Mac连接仅用独立副本测试，原生产目录不切换。Mac临时目录使用解析后的真实路径，
不删除软链接检查；GitHub Linux CI使用原生产版本Python3.12验证。

复验：

```sh
python -m unittest tests.test_social_orchestration tests.test_social_shadow_control tests.test_social_shadow_cli tests.test_social_evaluation
python -m tools.social.shadow_run --help
python -m tools.social.cli doctor --offline
node --test tests/social-review-ui.test.cjs
python -m tests.social_review_loopback_smoke
```

正式放量前仍要完成：全部PR基线回归与依赖安全检查、专用环境安装/人工登录、
每平台小预算查询与原文抽查、浏览器界面验收、相同窗口的真实增益评估。
本提交没有完成这些live验收；默认不合并、不发布、不启用任何平台。
回滚先stop并关闭本机runtime，确认worker结束，停止调用统一入口即可。
保留私有数据库、回执、固定证据及人工决定；不需要回滚生产数据。
