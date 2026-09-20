# 可选手动追踪传输关联协议 v1

本变更只给既有 batch workflow 增加两个可选公开输入，不增加自动触发、不改允许名单、写锁、environment、写入文件清单或提交/交接步骤。

`dispatch_token` 必须是随机 UUIDv4。不得填写邮箱、账户ID、私有操作ID或含个人信息的值。`dispatch_digest` 是 UTF-8 字节串 `v1\n{invalid_policy}\n{exact batch_json}` 的 SHA256 小写十六进制。原始 batch 仍必须遵守已有公开数据规则，不允许凭据或私人笔记。

两者同时为空走旧流程；否则只允许 apply，格式及hash须完全匹配，失败则在 authorize 阶段阻止后续 apply。值仅经 env 传入Python，不插入shell脚本。公开 run-name 是 `VCIQ durable apply {token} {digest}`。名称本身不证明授权或执行成功；消费者必须核对唯一run、仓库、workflow、branch、event、attempt，以及 `Authorize internal operator` 与 `Validate durable dispatch correlation v1` 步骤成功。业务结果仍由原apply输出/提交判定。

这个标记不是GitHub提供的幂等键，也不自动避免直接重复调用公开workflow；调用端必须先持久化唯一派发claim。查不到run不能成为重新派发的依据。本变更不重放任何历史请求、不导出私有账本、不声称已启用跨会话自动恢复。
