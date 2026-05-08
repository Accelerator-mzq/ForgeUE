# Codex Review

Target: branch diff against main

补丁中的 follow-on finish gate 新逻辑既有正常 completed 取消被误拦截的路径,也有 tombstone/受保护字段漏检路径,会影响归档守门的正确性。另有新 enum checker 的 Windows 输出安全问题。

Full review comments:

- [P2] 用归档前条目校验 completed 取消 — D:\ClaudeProject\ForgeUE_claude\tools\forgeue_finish_gate.py:2529-2532
  当一个 follow-on 被正常完成时,当前 change 会先把该 id 从 `active.md` 移到 `archived.md`,再在 `tasks.md` 写 `[cancelled-completed: <commit>]`;这里却用"当前" `active.md` 构造 `registry_entries`,已删除的 id 查不到,`_validate_cancel_tag_completed` 就没有 source/contract_refs 可比对,导致实际触达相关文件的裸 commit 也被误报,只能靠 `evidence:` 绕过。应改用 baseline/prior entry 或 tombstone snapshot 来校验 completed commit。

- [P2] 让 follow-on 正则识别 TBD 编号 — D:\ClaudeProject\ForgeUE_claude\tools\forgeue_finish_gate.py:1464-1471
  `active.md` 中的 `requirements-tbd-pointer` id 是 `TBD-001` 这类大写编号,但这里的 follow-on item 和 registry heading 正则只接受 `[a-z0-9-]+`。当某个 SRS TBD 完成并从 active registry 移除时,`_check_followon_continuity` 看不到 prior/current 条目或 tasks 声明,tombstone/cancel 校验会被跳过,只剩 SRS set check;这违反 README 中三类 active entry 都走 tombstone 的协议。

- [P2] 缺失 tasks 取消标签时阻断 tombstone — D:\ClaudeProject\ForgeUE_claude\tools\forgeue_finish_gate.py:1741-1743
  如果 `active.md` 条目被移除且 `archived.md` 写了 tombstone,但当前 `tasks.md` 漏写对应的 resolved cancel 行,`tasks_cancel_tag` 会是空 dict,`expected_reason_prefix` 变成空字符串,而任意 `cancellation_reason.startswith("")` 都为真。这样缺失 tasks cancel 声明的 tombstone 会通过第 5 项一致性检查,应显式要求 tag type 非空并匹配。

- [P2] 将受保护字段删除视为违规 — D:\ClaudeProject\ForgeUE_claude\tools\forgeue_finish_gate.py:2388-2396
  D-TombstoneProtocol 要求 archived tombstone 的 4 个 protected fields 不得修改或删除;但这里仅在 `- **field**` 后 4 行内找到匹配的 `+ **field**` 时才记录违规。若保留 H3 entry 但直接删除 `archived_at_commit` / `registry_entry_snapshot` 等字段且不替换,循环不会添加任何 blocker,append-only fence 会漏报字段删除。

- [P3] 保持 enum checker 输出编码安全 — D:\ClaudeProject\ForgeUE_claude\tools\forgeue_enum_cross_ref_check.py:330-330
  该新工具文档声称 ASCII-only / Windows GBK 安全,但 warning 文本会输出 Unicode `∈` 和 `…`,且 `main()` 没有像其他 ForgeUE tools 一样调用 `_common.setup_utf8_stdout()` 或做 ASCII coercion。在 Windows GBK 环境下只要出现 mapped enum 缺文档或 docs-only enum warning,`print()` 可能抛 `UnicodeEncodeError` 并中断 doc-sync gate。
