## Why

`enhance-workflow-automation-executable-enforcement` change(2026-05-05 archived)pre-P0 codex 对抗 review round 1 raise F2 + F3 两个 high finding,均为 `accepted-codex,partial inline + deferred to follow-on`:

- **F2**(dispatch ledger 在 Task 之前写 synthetic uuid_v4 与真实 agent_id 无关):inline 改 post-dispatch capture 真实 agent_id,evidence frontmatter `pre_dispatch_metadata: advisory` 诚实标注;真 wrapper-bound dispatch deferred 到本 follow-on
- **F3**(ledger fence 仅校验公开字段 wrapper_version + monotonic timestamp,LLM 可写 well-formed forge 通过):inline 加 evidence frontmatter `ledger_forgery_resistance: advisory` 标注 well-formed forge 不阻断;cryptographic enforcement(HMAC + LLM 不可见 key)deferred 到本 follow-on

**当前 advisory 协议的 hygiene gap**:
- ledger 行可被 LLM hand-edit(改 agent_id / dispatched_at / 删除某行)而 fence 检不出 — fence 仅校 schema-level wrapper_version + monotonic timestamp,任何"看起来合法"的 forge 都会通过
- evidence frontmatter `subagent_continuity` 字段虽 cross-check ledger 是否含 agent_id,但 ledger 本身的真实性无加密绑定
- `executable-enforcement` 自身 P10.0 e2e fixture 用 self-dogfood gap 协议(本 change 不 dispatch 真实 subagent),advisory 只能 catch unintentional drift,catch 不了 willful forge

**触发条件确认**:本 change 选 **F3 only(cryptographic ledger signing)scope**;F2 deferred 部分(wrapper / Hook 拦截 Skill(Task))需要 `~/.claude/settings.json` hook 改动 — 跨 project 污染 + 调试困难 + Skill tool 协议扩展不在我们控制内,**本 follow-on 不 ship**,留给将来独立 change `enhance-workflow-automation-skill-tool-binding` 若实证 F3 cryptographic 仍不足以挡 controller drift。

**Why now**:
- archived `executable-enforcement` P12.7 + P12.8 两个 follow-on 触发条件均含"若 follow-on `enhance-workflow-automation-ledger-binding` ship 后 v2 ledger cross-check 已经覆盖此 gap,可 cancel" — 本 change 是这两个 follow-on 的前置依赖
- round 1 codex F5 scope expansion:**本 change 合并 P12.8(`enhance-workflow-automation-v2-fence-hardening`)的 schema validation 部分**(strict 11-field schema + role enum + agent_id format + dispatched_at tz-aware + 拒未知字段);本 change ship 后 P12.8 follow-on 标 **superseded**(取消 follow-on tracking);P12.7 单独评估(F3 ledger terminal proof + F5 schema validation 是否 cover P12.7 hygiene gap)
- 当前 active changes 列表为空(无并行 contention),适合插入此 architectural follow-on
- threat model:catch unintentional controller drift / sloppy bypass / hand-edit ledger / 删除中间一行 attack / 删除尾部 N 行 attack(round 1 codex F3 inline writeback,加 D-LedgerTerminalProof);**不**承担"防 LLM 主动恶意 forge"(那是 OS-level sandbox 边界,留 future `enhance-workflow-automation-os-keystore` follow-on)

**Round 1 codex adversarial review 摘要**(2026-05-06):codex `/codex:adversarial-review` raise 5 finding(F1+F2+F3 high + F4+F5 medium),全 accepted-codex:
- **F1 [high]**:spec line 264 "调用前先 wrapper append" 与 archived 命令模板 step 10a "post-dispatch capture" 矛盾 → inline writeback,改 spec 为 post-dispatch
- **F2 [high]**:key_rotation WARN 把 unverifiable ledger 当 pass(LLM 替换 key 文件即可降级 HMAC 校)→ inline writeback,改 default fail-closed BLOCKER + archived replay 走 `ledger_archived_replay: true` evidence frontmatter explicit user opt-in
- **F3 [high]**:hash chain 抓不住 tail truncation(删除最后 N 行不破坏 chain)+ 单行 ledger 无链约束 → inline writeback,加 D-LedgerTerminalProof + evidence frontmatter `ledger_line_count` + `ledger_final_hmac` 必填字段 + 新 fence `_check_ledger_terminal_proof`
- **F4 [medium]**:`ledger_forgery_resistance` audit 字段未与 protocol_version 绑定 → inline writeback,加 D-FrontmatterAuditConsistency + 新 fence `_check_ledger_forgery_resistance_consistency` 强 enum
- **F5 [medium]**:HMAC 不替代 schema validation;P12.8 不应仅因 HMAC ship 自动 cancel → scope expansion,合并 P12.8 schema validation 进本 change(strict 11-field schema + role enum + agent_id format)+ P12.8 follow-on 标 superseded

完整 cross-check 见 `review/design_cross_check.md` `## B/C/D` 段;5/5 finding file:line claim 独立 verify 通过(沿 ForgeUE memory `feedback_verify_external_reviews`)。

## What Changes

- **新增 stdlib helper**:`tools/_forgeue_ledger_crypto.py` — `load_or_init_key()` / `canonical_payload()` / `compute_hmac()` / `compute_key_id()` / `verify_chain_v3()`;纯 stdlib(`hashlib` + `hmac` + `secrets` + `json` + `pathlib` + `os.chmod`),无第三方依赖
- **HMAC key 持久化**:文件路径 `~/.claude/forgeue_ledger_key`(JSON 单文件;version + created_at + key_hex);wrapper 首次 invoke 时 `secrets.token_bytes(32)` 随机生成 + `os.chmod(0o600)`(Linux/Mac;Windows 简化为不在 git 跟踪 + 用户目录 obscurity);跨 change 共享(任一 change 写的 ledger 都用同 key 校)
- **ledger schema v3**:新增 4 字段 `protocol_version: "v3"` / `key_id`(SHA256(key)[:16] fingerprint)/ `prev_hmac`(上一行 hmac,首行全 0)/ `hmac`(HMAC-SHA256 over canonical JSON of 前 9 字段 + prev_hmac);hash chain 防删行 attack
- **`tools/forgeue_dispatch_ledger.py` 升级**:
  - `cmd_append`:加载 key + 读 prev_hmac + 计算 hmac + 写 11 字段;exit code 加 7(`key_file_corrupted`)
  - `cmd_verify`:protocol_version dispatch — `v3` 走整链 verify 分支;exit code 加 6(`key_rotation_detected`,WARN 而非 fail)
- **`tools/forgeue_finish_gate.py` 升级**:
  - `_check_dispatch_ledger` 加 v3 分支(整链 verify + key_id rotation 区分 forge BLOCKER vs key-rotation WARN)
  - 新 helper `_runtime_enforcement_v3_active(frontmatter)`
  - fence dispatch matrix 扩到 4 档:`legacy(no field) / v1 / v2 / v3`
- **命令模板升级**(`.claude/commands/forgeue/change-apply-{subagent,parallel}.md`):evidence frontmatter 模板字段 `runtime_enforcement_protocol_version: v3` + `ledger_forgery_resistance: cryptographic`;Step 10a `forgeue_dispatch_ledger.py append` 调用接口不变(wrapper 自管 hmac 计算,LLM 不参与)
- **测试矩阵新增 ~12 case**(`tests/unit/test_dispatch_ledger.py`):happy path + forge attack(hand-edit / delete / reorder)+ key boundary(rotation / corrupted)+ canonical 稳定性 + dispatch matrix v1/v2/v3 三档
- **e2e fixture 平行 case**(`tests/integration/test_v2_e2e_synthetic_change.py` 加 `test_v3_e2e_cryptographic_synthetic_change`):用 monkey-patched `Path.home()` 隔离真实 user key
- **doc 更新**:`docs/ai_workflow/forgeue_integrated_ai_workflow.md` §C 加 v3 dispatch matrix + 新增 §C.10 Cryptographic Ledger Binding;`CLAUDE.md` Runtime enforcement frontmatter 字段段加 v3 说明
- **Self-dogfood gap**(沿 `executable-enforcement` D-DogfoodGap):本 change 自身 implementation evidence 仍走 v2 advisory(因为 v3 fence ship 时本 change 已经 archive);ship 完后下一个 change 起可用 v3

## Capabilities

### New Capabilities

无。

### Modified Capabilities

- `examples-and-acceptance`:加 v3 cryptographic ledger enforcement protocol delta — ledger schema + HMAC chain + key lifecycle + fence dispatch matrix v3 分支 + frontmatter 字段升级 + e2e fixture v3 平行 case

## Impact

**受影响代码**:
- `tools/_forgeue_ledger_crypto.py`(新建,~100 行)
- `tools/forgeue_dispatch_ledger.py`(升级,~50 行 diff)
- `tools/forgeue_finish_gate.py`(升级,~80 行 diff:新 v3 fence 分支 + helper)
- `.claude/commands/forgeue/change-apply-subagent.md`(frontmatter 模板字段升级,~5 行 diff)
- `.claude/commands/forgeue/change-apply-parallel.md`(同上,~5 行 diff)
- `tests/unit/test_dispatch_ledger.py`(新增 ~350 行测试,12+ case)
- `tests/integration/test_v2_e2e_synthetic_change.py`(加 v3 平行 case,~100 行)

**受影响 docs**:
- `docs/ai_workflow/forgeue_integrated_ai_workflow.md`(§C 协议矩阵 + 新加 §C.10)
- `CLAUDE.md`(Runtime enforcement frontmatter 字段段)
- `CHANGELOG.md`(release entry)

**API 边界**:
- `forgeue_dispatch_ledger.py append` CLI 接口**不变**(LLM 调用方式不变;wrapper 内部 transparently 加 hmac);v3 升级对 LLM 透明
- `forgeue_dispatch_ledger.py verify` CLI 接口**不变**;新 exit code 6/7 加进去
- `forgeue_finish_gate` Blocker.type 不增加(仍 `dispatch_ledger_violation`);error message 内容更细(区分 hmac_mismatch / chain_break / key_id_inconsistent / key_rotation)

**依赖**:
- 不引入第三方 dep(stdlib only:`hashlib` / `hmac` / `secrets` / `json` / `pathlib` / `os` / `datetime`)
- 不动 settings.json / 不动 hook system / 不申请 Claude Code Skill tool 协议扩展

**Backward compatibility**:
- archived `enhance-workflow-automation-executable-enforcement` v2 evidence + v2 ledger:**完全不动**;fence v3 分支不触发(evidence frontmatter 是 v2);archived replay 100% 兼容
- v1 / legacy(无 frontmatter)evidence:同上不影响
- 本 change 自身 evidence 沿 v2 advisory 协议(self-dogfood gap;沿 D-SelfDogfoodGap)

**Breaking changes**:
- 无。新协议(v3)opt-in,evidence frontmatter 不写 `v3` 则不触发 v3 fence
