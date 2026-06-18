# Claude Worker Task

你是外部 Claude Code CLI worker，只做只读 final review。Codex 是 supervisor。

Codex 已根据你的 review 修复：

- `--limit` 改为正整数校验，负数会被 argparse 拒绝。
- `--interval` 改为非负整数校验。
- `WxautoAdapter` 为 wxauto 消息生成 `source_message_fingerprint`。
- 同一批次中同 sender/text 的重复消息用 `raw_index` 区分。
- wxauto 没有原始时间戳时，fingerprint 使用稳定的 `no-timestamp`，避免同一可见消息每轮重复入库。
- `raw_index` 写入 `raw_json`。
- 新增测试覆盖重复消息 fingerprint、重复轮询稳定 fingerprint、负数 limit 拒绝。
- 测试通过：`29 passed`。

请 review：

- `agent-workflow/backend/scripts/poll_wechat_messages.py`
- `agent-workflow/backend/app/adapters/chat/wxauto_adapter.py`
- `agent-workflow/backend/tests/test_phase9_wechat_adapters.py`
- `agent-workflow/backend/README.md`

重点确认：

1. 两个 blocking 是否已解决。
2. 是否引入新的边界问题。
3. 是否仍满足“只抓取白名单群、保存 ChatMessage、记录 @WorkBot 命令，不创建 WorkDoc/AgentRun/Git”的约束。

输出：

```markdown
# Poller Final Review

## Blocking Findings

## Non-Blocking Notes

## Confidence
```

不要编辑文件。不要提交。不要推送。
