# LinkedIn 与科创人物关系接入

首批核验日期：2026-10-13（UTC）。入口：`/innovation-capital/people/`。

本次连接的 LinkedIn 插件仅提供按姓名（至少姓或名之一）、公司、地区、职位搜索人物的能力。实测返回人物 URL，没有任职履历、联系人列表、动态流或供网站后台使用的凭证。不要在 GitHub Pages 客户端放置密钥，也不要声称网站已直接调用 ChatGPT 插件或开启实时同步。

## 已落地

- 人物注册表：`config/innovation_people_network.json`。首批 Alfred Lin、Sonya Huang、Josh Wolfe、周志峰、Brett Adcock。
- 所属机构复用现有 canonical ID：sequoia、lux、qiming。Sequoia 与 HongShan 不混同。
- LinkedIn URL 均来自本次插件查询，保存查询条件与查询日期；`candidate` 表示待绑定复核，不表示身份已由 LinkedIn 确认。
- 职业身份依据官网资料。未注明发表日期时保留 null；抓取/核验日期不充当任职开始日期。
- 项目观点与组合关联人复用现有审查台账，按明确人物名与机构 ID 组合匹配。多人混合署名不自动拆成独立身份。
- 页面按人物、机构、项目和人物类型筛选，逐条展示证据、来源日期及责任边界；列出尚待人物映射的现有署名。

## 扩展操作

1. 从机构团队页或公司官网找出具名人物，核对现有站内人物/公司 ID。
2. 使用插件按姓名和机构检索，未命中保持无结果；不要构造人物 URL。
3. 将精简查询结果写入人物注册表的 `linkedin`，状态保持 candidate。新增人物必须有官网身份证据。
4. 将已审查的项目/观点台账署名填入 `evidenceNames`。准确机构 ID 与姓名同时匹配，禁止按关键词猜测投资关系。
5. 运行 `node --import tsx --test tests/innovation-people-network.test.ts`，再运行项目类型检查与既有发布流程。

页面不建立 LinkedIn 好友、共同联系人或私人联系方式档案。不从同项目、同事、同校、点赞、发言推断私人关系或交易签约责任。领投、董事席位与个人天使投资必须另有明确、带日期的公开证据。

## 后续自动化前提

当前不配置无数据接口支撑的定时任务。若后续申请独立 LinkedIn 开发者应用，应按实际获批产品与权限选择后端授权路径。官方说明：

- https://learn.microsoft.com/en-us/linkedin/shared/authentication/getting-access
- https://learn.microsoft.com/en-us/linkedin/shared/integrations/people/connections-api

Connections API 需要特批，且仅针对授权用户的一度联系人；不能据此抓取二度关系或任意人物的人脉网络。官网人物页和公开项目公告仍是职业及投资关系的证据基础。
