## Context

archived `enhance-workflow-automation-executable-enforcement` change(2026-05-05)pre-P0 codex 对抗 review round 1 raise 5 个 high finding,F2 + F3 两条 deferred 到本 follow-on:

- **F2 deferred 部分**(真 wrapper-bound dispatch):agent_id 是 dispatch 后 capture,LLM 仍可在 dispatch 完成后写假 agent_id;真 deterministic enforcement 需要 hook system 拦截 Skill(Task) 调用 + 写 ledger 前拒绝 dispatch — 但 `~/.claude/settings.json` hook 跨 project 污染 + 调试困难,Skill tool 协议扩展不在我们控制内
- **F3 deferred 部分**(cryptographic ledger signing):当前 fence 仅校 schema(wrapper_version + monotonic timestamp),LLM 完全可以 hand-edit ledger 行 / 写 well-formed forge / 删除中间一行,fence 全部通过

archived `executable-enforcement` 实施时 evidence frontmatter 加了 2 advisory 标注字段(`pre_dispatch_metadata: advisory` + `ledger_forgery_resistance: advisory`),诚实暴露当前 enforcement 等级。本 change 的目标是把 `ledger_forgery_resistance` 从 advisory 升级到 `cryptographic`(F3 deferred 部分);F2 deferred 部分仍留 advisory(本 change scope 不动 hook)。

**当前依赖关系**:
- archived `executable-enforcement` P12.7(`enhance-workflow-automation-final-review-fence-strictness`)+ P12.8(`enhance-workflow-automation-v2-fence-hardening`)两个 follow-on 的触发条件均含 "若 follow-on `enhance-workflow-automation-ledger-binding` ship 后 v2 ledger cross-check 已经覆盖此 gap,可 cancel" — 本 change 是这两个 follow-on 的前置依赖
- 本 change 自身不依赖任何 active change(空 active changes pipeline)

**Threat model 边界(important)**:
本 change 真正能改善的是 **catch unintentional controller drift / sloppy bypass / hand-edit ledger / 删除一行 attack**。**不**承担"防 LLM 主动恶意 forge"(LLM 可读所有文件,包括 `~/.claude/forgeue_ledger_key`)— 那是 OS-level sandbox 边界,留 future `enhance-workflow-automation-os-keystore` follow-on(用 Windows DPAPI / Mac Keychain / Linux libsecret)。本 change 的 defense 来自:
1. cryptographic chain — 任何 hand-edit / delete / reorder 必然 break HMAC chain → fence 拒
2. obscurity — `~/.claude/` 是 Claude Code 配置区,LLM 在 ForgeUE 项目工作时不主动跨项目 read 该目录
3. audit — evidence 中出现 key_hex 字面值 = drift signal,user review 时会注意

## Goals / Non-Goals

**Goals**:
- 升级 ledger schema v2(7 字段)→ v3(11 字段),新增 `protocol_version` / `key_id` / `prev_hmac` / `hmac` 4 字段
- HMAC-SHA256 + hash chain over canonical JSON,catch 任何 hand-edit / delete / reorder
- HMAC key 持久化到 `~/.claude/forgeue_ledger_key`(JSON 单文件,跨 change 共享,wrapper 自管 lifecycle)
- evidence frontmatter `ledger_forgery_resistance` 从 `advisory` 升级到 `cryptographic`
- fence dispatch matrix 扩到 4 档(legacy / v1 / v2 / v3),archived v2 evidence 完全 backward compatible
- 测试矩阵 12+ case 覆盖 happy path + forge attack + key boundary + canonical 稳定性 + dispatch matrix
- `tests/integration/test_v2_e2e_synthetic_change.py` 加 v3 平行 case,monkey-patched `Path.home()` 隔离真实 user key

**Non-Goals**:
- **不**做 F2 deferred 部分(真 wrapper-bound dispatch)— 需要 hook system 改动,留独立 change `enhance-workflow-automation-skill-tool-binding` 若 F3 实证不足
- **不**用 OS-level secret store(DPAPI / Keychain / libsecret)— 突破 stdlib-only 边界,留 future `enhance-workflow-automation-os-keystore`
- **不**支持 multi-key / key history / key versioning — 单 key 文件,user 手工 rm 重置;复杂 key management 留 future
- **不**改 `forgeue_dispatch_ledger` CLI 接口(LLM 调用方式不变)
- **不**升级现有 archived change 的 ledger 到 v3(archived 不动)
- **不**做 ledger 跨 change consolidation / global ledger(每 change 独立 ledger 文件不变)
- **不**承担"防 LLM 主动恶意 forge"威胁模型(threat model 限定为 unintentional drift / sloppy bypass)

## Decisions

### D-Scope-F3Only — 本 change scope 限 F3 cryptographic enforcement,不做 F2 wrapper-bound dispatch

**决策**:本 change 只 ship F3 deferred 部分(cryptographic ledger signing);F2 deferred 部分(wrapper / Hook 拦截 Skill(Task))**不在本 change scope**。

**Why**:
- F2 需要 `~/.claude/settings.json` `PreToolUse` hook 改动(archived `executable-enforcement` design.md 已标 reject — 跨 project 污染 + 调试困难)
- 或 project-local `.claude/settings.json` hook(scope 限本 repo,但跨 project 测试不便)
- 或申请 Claude Code Skill tool 协议扩展(out of our control)
- F3 是 self-contained 改动 — 只动 wrapper / fence / 命令模板 frontmatter;不动 hook,不动 settings,不动 Skill 协议
- 实证 F3 cryptographic 是否能 catch controller drift,再决定是否值得做 F2

**Alternatives considered**:
- (a)F2 + F3 一起做 — **拒绝**;hook 改动跨 project 污染 + 调试困难 + Skill 协议扩展不可控
- (b)scope 缩到 P12.8 schema 强化(7 字段 enum + path validation,无 crypto)— **拒绝**;不解决 F3 hand-edit / delete / forge 漏洞,只是 hygiene
- (c)F3 only(本 change 选)— **接受**

### D-KeyLocation — HMAC key 持久化到 `~/.claude/forgeue_ledger_key`(JSON 单文件,跨 change 共享)

**决策**:HMAC key 文件路径 `Path.home() / ".claude" / "forgeue_ledger_key"`;JSON 格式 `{"version": 1, "created_at": "...", "key_hex": "..."}`(64 hex chars = 32 bytes);跨 change 共享(任一 change 写的 ledger 都用同 key);wrapper 首次 invoke 时 `secrets.token_bytes(32)` 随机生成 + Linux/Mac `os.chmod(0o600)`。

**Why**:
- 跨 session 持久化必须(wrapper init 在 dispatch session,fence 在 finish session,跨 session env var 不可用)
- `~/.claude/` 是 Claude Code 配置区,LLM 在 ForgeUE 项目工作时不主动 ls 跨项目目录(obscurity layer)
- 跨 change 共享是 feature(任何 change 写的 ledger 都用同 key,无论谁 verify 都校验得了)
- JSON 而非裸 hex:留出 future schema(若日后加 multi-key / key history)
- pure stdlib(`secrets.token_bytes` + `hashlib` + `os.chmod` + `pathlib`),无第三方 dep

**Alternatives considered**:
- (a)`<change-dir>/.ledger_key`(每 change 一个 key)— **拒绝**;LLM 自然会读 change-dir 下文件(命令模板要求 LLM 在 change-dir 工作),defense 几乎=advisory
- (b)`~/.claude/forgeue_ledger_key`(本 change 选)— **接受**;obscurity 比 (a) 强一档,跨 change 共享便利
- (c)OS-level secret store(Windows DPAPI / Mac Keychain / Linux libsecret)— **拒绝**;跨平台 wrapper:Windows 用 ctypes 调 DPAPI 易碎,Linux 需第三方 `secretstorage` dep,平台分支 ~150 行,违反 stdlib-only 边界(沿 forgeue_dispatch_ledger / forgeue_preflight_wrapper 协定)
- (d)Per-session env var only — **拒绝**;跨 session 不持久化,功能 broken
- (e)user-managed key file via env var path — **拒绝**;user 体验复杂(要先生成 key 再设 env var),增加 onboarding 摩擦

**Risk + Mitigation**:
- 跨 change 共享 key:任一 change 泄漏 key → 所有 change ledger 可被 forge → mitigation:wrapper 不暴露 key 给 LLM(命令模板不指示 read);user 怀疑泄漏可手工 `rm`,wrapper 重新生成,旧 ledger key_id 不一致触发 key_rotation WARN(可恢复)

### D-ProtocolVersion — 新 v3 协议升级,fence dispatch 加 v3 分支;v2 archived ledger 完全 backward compatible

**决策**:新 protocol version `v3`(evidence frontmatter `runtime_enforcement_protocol_version: v3`);ledger 行加字段 `protocol_version: "v3"`(可独立判定行 schema 等级);fence dispatch matrix 4 档:`legacy(no field) / v1 / v2 / v3`;archived v2 evidence + ledger 完全不动。

**Why**:
- evidence frontmatter `runtime_enforcement_protocol_version` 字段已有 (legacy / v1 / v2) 三档 dispatch 习惯,加 v3 是自然延伸
- fence 入口统一 `dispatch on protocol_version`,各分支独立逻辑;后续若有新 enforcement 协议,可继续 v4 / v5 扩展
- v2 内部强化(同协议下 fence 检测 ledger 有无 hmac 字段决定是否校)会让 fence dispatch 逻辑分裂("v2-with-hmac" / "v2-without-hmac"),概念混乱
- archived `executable-enforcement` v2 evidence + ledger 完全 backward compatible(沿 forgeue_finish_gate "archived enhance-workflow-automation-runtime-enforcement 等历史 change replay 兼容" 既有协议)

**Alternatives considered**:
- (a)v2 内部强化(无新 protocol version)— **拒绝**;fence 逻辑分裂 + 后续 enforcement 不可扩展
- (b)v3 协议升级(本 change 选)— **接受**

### D-HashChain — HMAC 用 hash chain(不是单行 HMAC),catch 中间删行 / reorder attack;tail truncation 由 D-LedgerTerminalProof 单独覆盖(round 1 codex F3 inline writeback)

**决策**:每行 HMAC 计算覆盖 7 个原 v2 字段 + `protocol_version` + `key_id` + `prev_hmac`(即 10 字段),HMAC 自身不进 canonical(避免循环依赖);`prev_hmac` 字段值 = 上一行 `hmac` 值 hex string;首行 `prev_hmac` 固定全 0(`"0" * 64`)。

**Why**:
- 单行 HMAC 抓不住删行 — LLM 完全可以让 wrapper 正常 dispatch 一次写入合法行,然后偷偷删除中间几行(比如删除"被 reject 的失败 round")。剩余行 HMAC 仍合法,fence 通过
- Hash chain 是经典的防中间删行 / reorder 手法 — 中间任意行修改 / 删除 / reorder 必然 break chain(后续行的 prev_hmac 与新"上一行" hmac 不匹配)
- 性能不是 concern(ledger 通常 < 100 行)

**Tail truncation 边界**(round 1 codex F3 inline writeback):

**hash chain 抓不住 tail truncation** — 删除最后 N 行后,剩余前缀仍是合法 chain(每行 prev_hmac 与上一行 hmac 仍对得上),fence 通过。单行 ledger 也无实际链约束(prev_hmac 全 0 + 单 hmac,删了什么都没有)。原 round 1 设计声称"任何修改 / 删除 / reorder 必然 break chain"是 **overclaim** — codex 揭穿后修正。

**Tail truncation mitigation 走 D-LedgerTerminalProof**(独立 D-decision,新加):evidence frontmatter 必填 `ledger_line_count` + `ledger_final_hmac`;finish_gate `_check_ledger_terminal_proof` fence cross-check 与实际 ledger 行数 / 末行 hmac 一致。LLM 删行后若不更新 evidence frontmatter → 抓;若同时更新 evidence + ledger → willful forge(threat model 之外)。

**Alternatives considered**:
- (a)单行 HMAC-SHA256(每行独立)— **拒绝**;留删行 attack 漏洞
- (b)Hash chain(本 change 选)— **接受**(对中间删行 / reorder 有效)
- (c)Merkle tree(每行 hash 包含全文件 root)— **拒绝**;过度工程,append-only ledger 用不上 tree 结构
- (d)Hash chain + tail anchor(本 change 实施 = b + D-LedgerTerminalProof)— **接受**;chain 防中间篡改,terminal proof 防 tail truncation,组合后覆盖完整删行 attack 空间(中间 + 尾部)

### D-LedgerTerminalProof — evidence frontmatter `ledger_line_count` + `ledger_final_hmac` 必填(round 1 codex F3 inline writeback)

**决策**:v3 evidence frontmatter MUST 含两个字段:
- `ledger_line_count: <int>`(声明 ledger 行数)
- `ledger_final_hmac: <64 hex chars>`(声明 ledger 最后一行 hmac 值)

`forgeue_dispatch_ledger.py::cmd_append` SHALL 在每次成功 append 后 stdout 打印 `[LEDGER] line_count=<N> final_hmac=<hex>`(LLM 可读取此输出复制到 evidence frontmatter)。

新 fence `_check_ledger_terminal_proof` 在 finish_gate 校验:
- v3 evidence 缺字段 → BLOCKER
- 字段 format 不对(line_count 非正整数 / final_hmac 非 64 hex chars)→ BLOCKER
- evidence `ledger_line_count` ≠ 实际 ledger 非空行数 → BLOCKER `tail_truncation_detected`
- evidence `ledger_final_hmac` ≠ 实际 ledger 最后一行 hmac → BLOCKER `final_hmac_mismatch`

**Why**:
- D-HashChain 抓不住 tail truncation(参见 D-HashChain "Tail truncation 边界")
- evidence frontmatter 是 audit anchor — LLM 删除尾部不更新 frontmatter 时 fence 抓
- 实施成本低 — wrapper stdout 加一行 + evidence frontmatter 加 2 字段 + 1 个新 fence 函数

**Threat model 边界**:
- catch:LLM hand-edit 删行 / 删尾部 + 不更新 evidence(常见 sloppy bypass)
- catch:wrapper 跑过的 happy path(LLM 不能伪造 wrapper stdout 因为 wrapper 在子进程内算 hmac)
- **不** catch:LLM 同时 forge ledger + 重写 evidence frontmatter line_count + final_hmac(willful forge,threat model 之外;留 `enhance-workflow-automation-os-keystore` follow-on)

**Alternatives considered**:
- (a)独立 receipt JSON 锚点 ledger 末行(沿 archived `executable-enforcement` W1 receipt 模式)— **拒绝**(本 change scope);多文件维护成本 + receipt 自身的 race / corruption 风险;evidence frontmatter 字段更轻量
- (b)wrapper 自动写 evidence frontmatter — **拒绝**;wrapper 不知道 evidence 文件路径(evidence 在 stage 末由 LLM 决定写哪个文件);手动复制是显式 audit edge
- (c)evidence frontmatter `ledger_line_count` + `ledger_final_hmac` 必填(本 change 选)— **接受**

**Risk + Mitigation**:
- LLM 抄错 line_count / final_hmac → fence 报错 + LLM 重新跑 wrapper stdout 看正确值(self-heal)
- LLM 故意 mismatch → fence BLOCKER(与 forge 等价处理)
- ledger 文件中途坏(部分行)→ wrapper cmd_append 失败,evidence frontmatter 不会得到正确 stdout;走 wrapper 错误路径

### D-FrontmatterAuditConsistency — `ledger_forgery_resistance` 字段与 `runtime_enforcement_protocol_version` 强 enum 绑定(round 1 codex F4 inline writeback)

**决策**:`forgeue_finish_gate.py` 加新 fence `_check_ledger_forgery_resistance_consistency` 强校字段一致性:

| `runtime_enforcement_protocol_version` | `ledger_forgery_resistance` 强制值 |
|---|---|
| 无字段(legacy) | 无字段约束 |
| `v1` | 无字段约束(advisory pass-through) |
| `v2` | 必须 `advisory` |
| `v3` | 必须 `cryptographic` |

不匹配 → BLOCKER `frontmatter_audit_inconsistency`。

**Why**:
- 原 round 1 设计的"finish_gate 不强制 enum,字段是 audit 标注非 gate"被 codex 揭穿是 audit 信号脱钩 — LLM 可写 v3 evidence + `ledger_forgery_resistance: advisory`(谎称 advisory 实际走 v3 cryptographic 路径),或 v2 evidence + `ledger_forgery_resistance: cryptographic`(虚报 cryptographic 实际 v2 advisory)
- 本 change ship v3 cryptographic,审计字段必须与协议版本绑定才能 audit 有意义
- v2 evidence 强制 advisory 是 self-dogfood gap 路径的 invariant(v2 evidence 不能伪装 cryptographic)

**Alternatives considered**:
- (a)round 1 原设计 — finish_gate 不强制 enum,字段仅 audit 标注 — **拒绝**(round 1 codex F4 finding 完全 valid);制造错误的安全信号
- (b)字段废除(只用 protocol_version 决定 enforcement 等级)— **拒绝**;沿 archived `executable-enforcement` 已 ship 的字段实践,break compatibility
- (c)强 enum gate(本 change 选)— **接受**

### D-Scope-F3-MergeWithP12.8 — 本 change 合并 archived `executable-enforcement` P12.8 follow-on 的 schema validation,P12.8 superseded(round 1 codex F5 scope expansion)

**决策**:把 archived `executable-enforcement` P12.8(`enhance-workflow-automation-v2-fence-hardening`)的 schema validation 部分合并进本 change v3 verify(strict 11-field schema + role enum + agent_id format + dispatched_at tz-aware + 拒未知字段);本 change ship 后 P12.8 follow-on 标 **superseded**(取消 follow-on tracking)。

**v3 ledger 行 strict 11-field schema**:见 specs MODIFIED Requirement "v3 ledger strict 11-field schema validation"。

**Why**:
- HMAC 仅保护字节完整性,不校 schema 语义。LLM 可写 ledger 行 `{"agent_id": "<arbitrary 1MB string>", "round": -42, "extra_field": "anything", ..., "hmac": "<合法 HMAC over the garbage>"}` — fence v3 chain verify pass,但 schema broken
- P12.8 schema validation 与 F3 cryptographic 是 orthogonal 必需层 — codex 警告"P12.8 不应仅因 HMAC ship 自动 cancel"完全 valid
- 合并 P12.8 进本 change 是 atomic ship 模式 — 一次性 ship cryptographic + schema strict,避免中间状态(本 change ship 后 P12.8 仍 active 半年 schema 风险)

**Alternatives considered**:
- (a)本 change 仅 ship F3 cryptographic,P12.8 留 follow-on(round 1 原设计)— **拒绝**(round 1 codex F5 finding 完全 valid);schema 风险与 cryptographic 同等关键
- (b)本 change 合并 P12.8 schema 部分(本 change 选)— **接受**;P12.8 follow-on tracking 标 superseded(本 change archive 后正式 cancel)
- (c)scope 全合并(P12.7 + P12.8 都进本 change)— **拒绝**;P12.7 是 evidence_provenance 字段升级(SKIP stub vs dispatched 区分),与本 change F3 cryptographic 不直接关联;留 P12.7 单独评估

**Scope 影响**:
- 本 change 工程量从 ~4-6h 升到 ~6-9h(+50%;schema strict + 测试 case + ledger schema 文档)
- 合并后本 change 一次性闭合 archived `executable-enforcement` P12.3 follow-on 的两个 deferred 部分(F3 cryptographic 主线 + F5 schema strict 副线)
- 测试 case 加 ~10 个 schema strict 案例

### D-CanonicalJSON — canonical JSON 序列化用 sort_keys + 无空格 + UTF-8 + 排除 hmac 字段

**决策**:`canonical_payload(record)` 函数:
```python
def canonical_payload(record: dict) -> bytes:
    payload = {k: v for k, v in record.items() if k != "hmac"}
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
```

**关键约束**:
- 排除 `hmac` 字段本身(避免循环依赖 — hmac 是输出而非输入)
- **包含** `prev_hmac` 字段(它是 chain 输入)
- `sort_keys=True`:字段顺序确定;`separators=(",", ":")`:无空格;`ensure_ascii=False`:UTF-8 编码 unicode

**Why**:
- 不规范化的 JSON 序列化在不同 Python 版本 / 不同 wrapper 实现下可能产生不同 bytes,导致 HMAC 重算时不匹配
- 字段顺序歧义:Python 3.7+ dict 保持插入顺序,但跨实现不保证
- whitespace 歧义:默认 `json.dumps` 加 ", " / ": "(后空格),不同库可能不加
- unicode 边界:`ensure_ascii=True` 会把非 ASCII 字符转义,但 ledger 文件以 UTF-8 存储,直接保留 unicode 更直观且与文件编码一致

**Risk + Mitigation**:
- canonical 字段排除规则错(漏 prev_hmac 或加 hmac 自己)→ HMAC 计算不一致 → fence 永远失败 → mitigation:测试 case `test_canonical_excludes_hmac_includes_prev_hmac` + `test_canonical_round_trip_stability` 守门
- 跨 Python 版本 sort_keys 行为差异 → mitigation:测试 case `test_canonical_field_order_invariant`(打乱字段顺序写入 record,canonical bytes 应相同)

### D-KeyRotationHandling — key 文件 lifecycle + key_id mismatch 默认 fail-closed,archived replay 走 explicit user opt-in(round 1 codex F2 inline writeback)

**决策**(round 1 codex F2 inline writeback 后):wrapper key file lifecycle 6 状态:

| 状态 | 触发 | wrapper 行为 | exit code |
|---|---|---|---|
| **首次 init** | key 文件不存在 + `append` 调用 | `secrets.token_bytes(32)` 生成 + `os.O_EXCL` flag 创建 + chmod 0600 + 打印 INFO 行 | 0(继续 append) |
| **正常 load** | key 文件存在 + JSON 合法 + key_hex 64 chars | 读 key + 计算 key_id + 用于 append/verify | 0 |
| **文件损坏** | key 文件存在但 JSON 解析失败 / key_hex 长度错误 / version 不识别 | abort,不静默重建;提示 user backup + 删除 + 重新 init | 7(`key_file_corrupted`) |
| **key_id mismatch active v3**(verify 时) | active v3 evidence(`evidence_frontmatter.ledger_archived_replay` ≠ `true`)+ ledger key_id ≠ 当前 file key_id | **fail-closed BLOCKER**(攻击场景:LLM 替换 key 文件即可降级 HMAC 校;**不**走 WARN 自动 pass) | 5(`key_id_mismatch` 类 verify_fail) |
| **key_id mismatch archived replay opt-in**(verify 时;round 2 codex F1 inline writeback 后加路径限定) | evidence frontmatter `ledger_archived_replay: true`(user 显式 opt-in)+ cmd_verify 配套 `--allow-archived-replay` flag + ledger key_id ≠ 当前 file key_id + ledger 自身 key_id 一致 + **evidence 文件路径在 `openspec/changes/archive/` 段下**(沿 D-ArchivedReplayPathBoundary;active change 路径 = BLOCKER `archived_replay_path_violation`)| WARN(`key_rotation_user_override_required`);user 显式承担"无法重算 HMAC"风险 | 6(WARN,user override) |
| **forge 检测同 ledger 内不同 key_id**(verify 时) | 同一 ledger 内不同行 key_id 不一致(LLM 中途切换 key) | BLOCKER | 5(`key_id_inconsistent` 类 verify_fail) |

**Why(round 1 codex F2 inline writeback,fail-closed default)**:

原 round 1 设计的 key_rotation WARN 自动路径被 codex 揭穿是 critical hole — **LLM 不需读 key 文件,只需替换 `~/.claude/forgeue_ledger_key`** 用新 key,fence 检测 key_id mismatch → WARN 自动 pass,所有 forge ledger 通过校验。原设计声称"WARN 路径允许 archived replay 兼容"是真实需求,但实施模式错误 — 不能把"无法验证"和"archived 兼容"混在一个 default WARN 里。

**修正后双路径**:
- **default**:active v3 evidence + key_id mismatch → fail-closed BLOCKER(攻击防御)
- **opt-in**:user 在 evidence frontmatter 显式标 `ledger_archived_replay: true`(audit 友好,user 必须手工添加;LLM 不能 default 写)+ cmd_verify 配套 `--allow-archived-replay` flag → WARN 路径,user 显式承担"无法重算 HMAC"风险

**核心 invariant**:任何"无法 cryptographically verify 的 ledger"都不允许走 default pass 路径。user override 是承认风险而非隐藏风险。

**Alternatives considered**:
- (a)round 1 原设计 — key_rotation 自动 WARN 不阻断 — **拒绝**(round 1 codex F2 finding 完全 valid);LLM 替换 key 文件即可 trivially bypass HMAC enforcement,违反 cryptographic enforcement 设计目标
- (b)key_rotation 也 BLOCKER 完全不允许 archived replay — **拒绝**(过严);break user 怀疑泄漏后手工 rotation 的合法路径
- (c)key history(wrapper 自动维护多个旧 key)— **拒绝**(本 change scope);多 key 管理 + lifecycle 复杂度 + 不解决 active forge 攻击;留 future follow-on `enhance-workflow-automation-key-history` 若实证需要
- (d)ledger terminal proof(独立 receipt 锚点 ledger 末行 hmac)— **接受 D-LedgerTerminalProof,本 change 实施**;沿 round 1 codex F3 inline writeback 同款 mitigation
- (e)default fail-closed + explicit user opt-in WARN(本 change 选)— **接受**;沿 fail-closed-by-default 原则,opt-in user override 是审计友好的 escape hatch

**Risk + Mitigation**(round 2 codex F1 inline writeback 后):
- archived ledger replay 操作复杂度增加(user 必须手工标 frontmatter `ledger_archived_replay: true` + 命令行 `--allow-archived-replay` + evidence 必须在 archive/ 路径)→ Mitigation:`forgeue_change_state.py` 检测 archived change replay 时 alert user 是否需要 opt-in;命令模板默认不写本字段,LLM 不能 default 把"无法验证"漂白成"通过"
- LLM 学到"可以加 `ledger_archived_replay: true` 绕过 fence" — **本 change ship D-ArchivedReplayPathBoundary fence 守门,active change(非 archive/ 路径)evidence 用此字段 = BLOCKER `archived_replay_path_violation`,不再 defer 到 follow-on**(round 2 codex F1 inline writeback;原 round 1 设计 defer P9.6 被 codex 揭穿是 escape hatch reopen round1-F2 bypass,本 change 直接修复);active change LLM 即使 forge `ledger_archived_replay: true` 也无法绕 fence — fence 校 evidence 文件绝对路径必须 contains `/archive/` segment

### D-ArchivedReplayPathBoundary — `ledger_archived_replay: true` 仅在 archive/ 路径 evidence 接受,active change 路径 BLOCKER(round 2 codex F1 inline writeback)

**决策**:`forgeue_finish_gate.py` 加新 fence `_check_archived_replay_path_boundary` 守门 `ledger_archived_replay` evidence frontmatter 字段使用边界:

| evidence 文件路径 | `ledger_archived_replay` 字段值 | fence 行为 |
|---|---|---|
| 任何路径 | 缺失 / `false` / `null` | pass-through(default 路径) |
| 含 `openspec/changes/archive/` segment | `true` | 接受 archived replay opt-in;走 D-KeyRotationHandling user override 路径(WARN exit 6) |
| 不含 `archive/` segment(active change `openspec/changes/<id>/`) | `true` | **BLOCKER `archived_replay_path_violation`** |

`tools/forgeue_dispatch_ledger.py::cmd_verify` `--allow-archived-replay` flag 同款边界 — 仅在 ledger 路径在 `openspec/changes/archive/` 内才 honor flag;active change ledger 路径 + `--allow-archived-replay` flag → BLOCKER + 提示用户 ledger 不在 archive 路径。

**Why(round 2 codex F1 inline writeback)**:

round 1 设计的 `ledger_archived_replay: true` opt-in 路径已经引入双重 explicit user override(frontmatter 字段 + cmd_verify flag),但 codex round 2 揭穿仍有 escape hatch:**evidence frontmatter 是 controller-written,LLM 在 active change 评估时 forge `ledger_archived_replay: true` + 替换 key 文件 + 用 `--allow-archived-replay` flag → fence 走 user override 路径接受 unverifiable ledger,等于 reopens round1-F2 bypass under different flag**。

原 round 1 R10 mitigation 把"active change 用此字段 = drift signal WARN"留 P9.6 follow-on 是 codex F1 揭穿的核心问题 — P9.6 触发条件是"实证 LLM 滥用",但 P9.6 不会 ship 直到滥用发生 → 修复永远 deferred → 等于不修复。

**核心 invariant 升级**:archived replay 路径不仅要 user explicit opt-in(双 flag),还要 evidence 物理位置在 archive/ 目录(物证驱动);LLM 即使 forge frontmatter + 替换 key 文件,只要 evidence 不在 archive/ 段,fence BLOCKER。

**实施**:fence 校 `evidence_path.resolve()` 字符串含 `os.sep + "archive" + os.sep` segment;`forgeue_change_state.py --writeback-check` 同步加此 invariant 检测。

**Alternatives considered**:
- (a)round 1 原设计 — defer P9.6 follow-on(沿"实证驱动"原则)— **拒绝**(round 2 codex F1 finding 完全 valid);P9.6 实际不会 ship,defer = 不修复
- (b)evidence 路径强校 archive/ segment(本 change 选)— **接受**;物证驱动,LLM 不能伪造文件物理位置(LLM 写 evidence 时由 stage 决定路径,active change 写到 `openspec/changes/<id>/`,无法跨写到 archive/)
- (c)finish_gate 强校 evidence 必须有 archived 时间戳 prefix(`archived_at` frontmatter 字段)— **拒绝**(过严);时间戳是 controller-written,可被伪造;不如 archive/ 目录路径物证强

**Risk + Mitigation**:
- archived replay 时 user 必须把 evidence 文件移进 archive/ 才能跑 fence — Mitigation:archived change 已经在 `archive/2026-MM-DD-<id>/` 目录(沿 `openspec archive` 协议),evidence 自然在 archive/ 段;active change 的 evidence 在 `openspec/changes/<id>/`,如需 replay 必须先 archive(物证-驱动符合直觉)
- LLM 在 active change 把 evidence 移到 archive/ 段绕 fence — Mitigation:`forgeue_change_state.py --writeback-check` 检测 active change 的 evidence 出现在 archive/ 路径 = drift signal;同时本 change ship D-ArchivedReplayPathBoundary 的 fence 物证强(`Path.resolve()` 后包含 archive segment 必然在归档路径)

### D-RuntimeEnforcementProtocolVersionValidity — unknown protocol_version 默认 BLOCKER 而非 silent pass(round 2 codex F2 inline writeback)

**决策**:`forgeue_finish_gate.py` 加新 fence `_check_runtime_enforcement_protocol_version_validity` 守门 `runtime_enforcement_protocol_version` 字段值合法性:

| evidence frontmatter `runtime_enforcement_protocol_version` | fence 行为 |
|---|---|
| 字段缺失(legacy) | pass-through(全 v1/v2/v3 fence skip) |
| 字段值 `v1` / `v2` / `v3` | 走对应 fence dispatch matrix |
| 字段值 present 但不在 {`v1`, `v2`, `v3`} 内(`v4` / typo / empty string / null) | **BLOCKER `unknown_protocol_version`** |

**Why(round 2 codex F2 inline writeback)**:

round 1 dispatch matrix 只列 absent / v1 / v2 / v3,没说 unknown value 怎么处理。codex round 2 揭穿:现有 gate helpers 用 exact equality 检测 active protocol(如 `_runtime_enforcement_v3_active` 检测 `== "v3"`),unknown value(`v4` / typo / empty)被 treat as inactive(skip v3 fence)— LLM 可写 `v4` 自动跳过 fence,等于 controller-written 字段提供 fence skip escape hatch。

**修正**:加新 fence 校 enum 合法性。default behavior 改为 fail-closed unknown(LLM 不能 silently skip fence)。

**核心 invariant**:**fence skip 必须由 absence 决定(legacy),不能由 invalid value 决定**(LLM 写错值不应该意外 unlock 旁路)。

**实施细节**:
- 新 helper `_VALID_PROTOCOL_VERSIONS = frozenset({"v1", "v2", "v3"})` 模块常量
- 新 fence `_check_runtime_enforcement_protocol_version_validity(frontmatter) -> list[str]`:
  - `runtime_enforcement_protocol_version` not in frontmatter → return `[]`(legacy pass)
  - 字段值 in `_VALID_PROTOCOL_VERSIONS` → return `[]`(跑后续 dispatch matrix)
  - 其他 → return `[error]`(BLOCKER)
- 此 fence 在 `_check_dispatch_ledger` / `_check_round_fix_continuity` / `_check_skill_cascade` 等所有 protocol-version-dependent fence 之前跑(防 fence 内部 silent dispatch)
- forgeue_change_state.py canonical frozenset 加 `_VALID_PROTOCOL_VERSIONS`(沿 forgeue_enum_cross_ref_check.py 协议;`CLAUDE.md` + `forgeue_integrated_ai_workflow.md` 文档同步声明)

**Alternatives considered**:
- (a)round 1 原设计 — unknown value silent skip(default behavior)— **拒绝**(round 2 codex F2 finding 完全 valid);LLM 可 typo / 写错绕 fence
- (b)unknown value warn 而非 BLOCKER — **拒绝**;warn 不阻断 archive,与 fail-closed 原则违背
- (c)unknown value BLOCKER + future v4/v5 ship 时同步扩 frozenset(本 change 选)— **接受**;严格 enum 是 future-extensible 的(扩值同步扩 frozenset)

**Risk + Mitigation**:
- 后续 follow-on 加新 protocol(v4)— Mitigation:沿 forgeue_enum_cross_ref_check.py 协议,扩 `_VALID_PROTOCOL_VERSIONS` frozenset 时同步扩 docs(`CLAUDE.md` + `forgeue_integrated_ai_workflow.md`),工具自动 catch drift
- 测试 fixture 用错 protocol value 触发 BLOCKER — Mitigation:测试 fixture 显式列 valid value;archive/ 兼容性测试 case 显式覆盖 legacy(absent field) + 各 valid value

### D-FenceDispatchMatrix — fence dispatch 4 档矩阵 (legacy / v1 / v2 / v3) + unknown value BLOCKER(round 2 codex F2 inline writeback 后),v3 = v2 + HMAC chain

**决策**(round 2 codex F2 inline writeback 后):`forgeue_finish_gate.py::_check_dispatch_ledger` 入口加 dispatch matrix:
- 无 frontmatter 字段(legacy)→ 全 v1/v2/v3 fence pass-through
- `runtime_enforcement_protocol_version: v1` → 走 v1 fence(沿 ADR-011)
- `runtime_enforcement_protocol_version: v2` → 走 v1 + v2 fence(advisory schema-only,沿 ADR-012)
- `runtime_enforcement_protocol_version: v3` → 走 v1 + v2 + v3 fence(v3 = v2 schema check + HMAC chain verify + terminal proof + audit consistency + strict 11-field schema)
- **其他 present value(unknown protocol)→ BLOCKER `unknown_protocol_version`**(沿 D-RuntimeEnforcementProtocolVersionValidity)

**Why**:
- 4 档矩阵 + unknown BLOCKER 清晰 — 每档独立 logic,unknown silent skip 路径已封死
- archived v2 evidence + v2 ledger 完全 backward compatible(走 v2 路径,不触 v3)
- 本 change 自身 evidence 仍走 v2 advisory(self-dogfood gap;沿 D-SelfDogfoodGap)

**实施细节**:
- 新 helper `_runtime_enforcement_v3_active(frontmatter) -> bool`,检测 `runtime_enforcement_protocol_version == "v3"`
- `_check_dispatch_ledger` v3 分支调 `_forgeue_ledger_crypto.verify_chain_v3(key_bytes, lines, evidence_frontmatter)` 整链 verify + terminal proof + strict schema
- 新 Blocker.type 不增加(仍 `dispatch_ledger_violation`);error message 内容更细(区分 hmac_mismatch / chain_break / key_id_inconsistent / key_id_mismatch / tail_truncation_detected / final_hmac_mismatch / schema_violation / audit_mismatch / archived_replay_path_violation / unknown_protocol_version)

### D-SelfDogfoodGap — 本 change 自身 evidence 仍走 v2 advisory,ship 后下一个 change 才用 v3

**决策**:本 change 自身 implementation evidence 仍走 v2 advisory 协议(`runtime_enforcement_protocol_version: v2` + `ledger_forgery_resistance: advisory`);ship 完后下一个 change 起可用 v3。沿 archived `executable-enforcement` D-DogfoodGap 同款处理。

**Why**:
- 本 change 实施时 v3 fence 还没 ship,本 change 自身 evidence 用 v3 协议会触发 fence 但 fence 自身代码还在改 — 自循环依赖
- 沿 self-dogfood gap 模式:本 change 自身 evidence 标 v2 + advisory,evidence frontmatter 加 audit 注释 `# v3 协议本 change ship 后才生效;本 change evidence 沿 v2 self-dogfood`
- archived `executable-enforcement` 同款处理过(自身 evidence v1,本 change ship v2)

**Alternatives considered**:
- (a)本 change 自身用 v3 协议 — **拒绝**;自循环依赖(fence 还在改 + evidence 已要求 v3)
- (b)沿 D-SelfDogfoodGap v2 advisory(本 change 选)— **接受**

### D-DispatchPath — 推荐 `change-apply-direct` 路径,scope 聚焦 + < 6h 工程量

**决策**:推荐 `/forgeue:change-apply-direct` 路径(沿 D-DirectWorktreeRefinement 不强制 isolated worktree,`worktree_consent_outcome: declined / already_isolated`,`worktree_mode: in_place`)。

**Why**:
- scope 聚焦 — 纯 wrapper / fence / 测试,无跨子系统;3 个核心改动文件(`_forgeue_ledger_crypto.py` 新建 + `forgeue_dispatch_ledger.py` 升级 + `forgeue_finish_gate.py` v3 分支)
- 工程量 ~4-6h(code 250 行 + test 350 行 + doc 100 行)
- subagent 路径 overhead(per-task 4 类 evidence + worktree 初始化 + dispatch ledger v2 fence 自循环)对这种聚焦 change 反而增加摩擦
- ADR-013 worktree consent gate 在 direct 路径下仍生效,但 framework 层修改默认 in_place(沿 D-DirectWorktreeRefinement)

**Alternatives considered**:
- (a)`change-apply-subagent` 路径 — **拒绝**;subagent overhead 不划算(per-task 4 evidence + final review)
- (b)`change-apply-parallel` 路径 — **拒绝**;tasks 不独立(crypto helper / dispatch_ledger / finish_gate 互相依赖)
- (c)`change-apply-direct`(本 change 选)— **接受**

### D-WrapperVersionBump — `wrapper_version` 从 "1.0" 升到 "2.0",标记 v3 schema break

**决策**:`tools/forgeue_dispatch_ledger.py` 模块常量 `WRAPPER_VERSION` 从 `"1.0"` 升到 `"2.0"`;`cmd_append` 写入 ledger 行 `wrapper_version: "2.0"`;`cmd_verify` 不强制校 wrapper_version 具体值(仅校非空,沿现有 v2 fence 逻辑)。

**Why**:
- v3 schema 加了 4 字段 + HMAC chain 协议,wrapper 实施 break,版本号 bump 标记
- archived v2 ledger 行 `wrapper_version: "1.0"` 仍合法,fence 不强制具体值(允许混合 ledger 行,虽然实际不会发生)
- 后续 wrapper 改动(如 schema 加字段)继续 bump(2.0 → 2.1 → 3.0)

**Alternatives considered**:
- (a)wrapper_version 不升(仍 1.0)— **拒绝**;v3 ledger 行实施与 v2 完全不同,不升版本号失去 audit trail
- (b)wrapper_version 升到 2.0(本 change 选)— **接受**

## Risks / Trade-offs

- **R1 LLM 主动恶意 forge 不可防** → 本 change 不解决(threat model 之外);Mitigation:obscurity layer + audit signal + 留 future `enhance-workflow-automation-os-keystore` follow-on 用 OS-level secret store
- **R2 key 文件并发 race** → 多 wrapper 并发 init 时可能竞态(同时检测文件不存在 → 同时 generate → 后写覆盖前写,导致 ledger 行 key_id 不一致)。Mitigation:用 `os.O_EXCL` flag 创建文件(`os.open(path, O_CREAT | O_EXCL | O_WRONLY)`),已存在则 EEXIST,wrapper retry-load 一次;并发 race 测试 case `test_key_file_concurrent_init_no_race`(可选,实际 ForgeUE 工作流 wrapper 串行调用,race 概率极低)
- **R3 ledger 文件并发 append race**(round 3 codex F4 inline writeback 后)→ 多 wrapper 并发 append 时 prev_hmac 读取 + 写入不原子,可能导致 chain 断裂。**Mitigation 升级为 invariant**:命令模板 `/forgeue:change-apply-{subagent,parallel}` SHALL **主 session 串行 append wrapper**(implementer subagent dispatch 之间 parallel,但 append 是主 session 跑 — Skill(Task) 返回后由 controller 主 session 调 wrapper,自然 serialize;沿 archived `executable-enforcement` 同款 sequential append 模式)。本 change scope 内**不**实施 cross-platform file lock(`fcntl` / `msvcrt`);若 ship 后实证并发 append race 实际发生(如非 ForgeUE 工作流外部并发跑 wrapper)→ 触发 follow-on `enhance-workflow-automation-ledger-append-lock`(P9.7);本 change 命令模板 explicit 加"主 session 串行 append"约束
- **R4 canonical JSON 跨 Python 版本不稳定** → `json.dumps(sort_keys=True)` 跨 Python 3.7-3.13 行为应一致,但 unicode normalization 边界(NFC vs NFD)可能差异。Mitigation:测试 fixture 不引入 unicode agent_id(沿现有 ledger 实践 agent_id 是 hex);若日后引入 unicode 字段,加 `unicodedata.normalize("NFC", ...)` 预处理 — 留 follow-on
- **R5 key 文件 0600 在 Windows 上不严格** → `os.chmod(0o600)` 在 Windows 上 NTFS 不识别 POSIX permission,实际只标 read-only bit。Mitigation:接受 Windows 上 obscurity-not-strict-permission(沿 D-KeyLocation 边界);用户目录 `C:\Users\<user>\.claude\` 默认 user-only 访问已足够;真严格 ACL 需 `pywin32` 调 SetSecurityInfo,违反 stdlib-only,留 future follow-on
- **R6 v3 ledger 行 size 增长** → 4 字段 ~150 bytes/行,100 行 ledger ~15KB → 30KB(2x)。Mitigation:可接受(ledger 不进 git,文件大小不是 concern)
- **R7 fence error message 区分度** → hmac_mismatch / chain_break / key_id_inconsistent / key_id_mismatch / tail_truncation_detected / final_hmac_mismatch / schema_violation / frontmatter_audit_inconsistency / key_rotation_user_override 9 类错误必须区分清晰,user 看到能判断 forge vs key rotation vs schema 错。Mitigation:每类错误加结构化 prefix(`[hmac_mismatch]` / `[chain_break]` / `[key_id_inconsistent]` / `[key_id_mismatch]` / `[tail_truncation_detected]` / `[final_hmac_mismatch]` / `[schema_violation]` / `[audit_mismatch]` / `[key_rotation_user_override]`),fence 测试 case 校验 prefix
- **R8 archived change 的 ledger 行 key_id 与新 key 不一致**(round 1 codex F2 inline writeback 后)→ archived ledger 是用 archived 时刻的 key 写的,user rotation 后 key_id 变,verify 时**默认 fail-closed BLOCKER**(攻击防御);archived replay 走 `ledger_archived_replay: true` evidence frontmatter opt-in + cmd_verify `--allow-archived-replay` flag 双重显式 user override 路径(WARN 不阻断,但 audit trail 永久保留)。Mitigation:`forgeue_change_state.py` 检测 archived change replay 时 alert user 是否需要 opt-in
- **R9 schema strict v3 误报**(round 1 codex F5 scope expansion 后)→ strict 11-field schema + format 正则严格匹配,正常 dispatch 写出的字段必然合规;但若 wrapper 自身 bug(如 ISO8601 没带 tzinfo / round 取 0)→ schema fence 阻断 + wrapper 错误难诊断。Mitigation:wrapper test 覆盖 schema 边界(tz-aware datetime / round positive / agent_id format);正常 ForgeUE 工作流不会触发 schema_violation,触发即 wrapper 实施 bug;fence error message 指明字段名 + 期望 format,user 能快速定位 wrapper bug
- **R10 evidence frontmatter `ledger_archived_replay: true` 滥用**(round 1 codex F2 inline writeback 副作用)→ LLM 学到"加 `ledger_archived_replay: true` + `--allow-archived-replay` flag 可绕过 fail-closed,在 active change 也用此字段虚报 archived"。Mitigation:本字段 audit trail 永久保留(任何 archive / commit 都带 trail);finish_gate 加守门"active change(非 archived)evidence 用 `ledger_archived_replay: true` = WARN drift signal";真严格的 audit 留 follow-on tracking 在 P9.6
- **R11 LLM 同时 forge ledger + 重写 evidence frontmatter line_count + final_hmac**(D-LedgerTerminalProof 边界)→ 主动恶意 forge,fence 抓不住。Mitigation:沿 threat model 边界(本 change 不承担主动恶意 forge);留 future `enhance-workflow-automation-os-keystore` follow-on 用 OS-level secret store

## Migration Plan

**Phase 实施顺序**(建议 P0-P8 阶段;详见 tasks.md;round 1 codex F1+F2+F3+F4+F5 inline writeback 后 scope expansion 增加 ~3h 工程量):
- **P0**:codex `/codex:adversarial-review` design hook(必跑,本阶段 round 1+2 review;raise 的 finding 全 inline writeback 或 deferred to follow-on)— round 1 完成,5 finding 全 accepted-codex inline writeback / scope expansion(F1+F2+F3+F4+F5)
- **P1**:`tools/_forgeue_ledger_crypto.py` 新建 + 单元测试(canonical / compute_hmac / verify_chain_v3 / load_or_init_key 各 case);`verify_chain_v3` 加 evidence_frontmatter 参数(D-LedgerTerminalProof + D-KeyRotationHandling 双路径)
- **P2**:`tools/forgeue_dispatch_ledger.py` 升级(cmd_append + cmd_verify v3 分支 + exit code 5/6/7 + `--allow-archived-replay` flag + cmd_append stdout `[LEDGER]` line)+ 单元测试
- **P3**:`tools/forgeue_finish_gate.py` 升级(`_check_dispatch_ledger` v3 分支 + `_runtime_enforcement_v3_active` helper + 新 fence `_check_ledger_terminal_proof` + `_check_ledger_forgery_resistance_consistency` + v3 strict schema validation)+ 单元测试
- **P4**:命令模板 frontmatter 字段升级(`change-apply-{subagent,parallel}.md` 加 `ledger_line_count` / `ledger_final_hmac` 必填 v3 + Step 10a 加 stdout 解析复制到 evidence frontmatter)+ e2e fixture v3 平行 case(覆盖 happy path + tail truncation + key rotation override + schema strict)
- **P5**:doc 更新(`forgeue_integrated_ai_workflow.md` §C / `CLAUDE.md` / `CHANGELOG.md`)+ codex `/codex:review --base main` 验证 hook
- **P6**:`/forgeue:change-doc-sync` Documentation Sync Gate(10 文档静态扫 + §4.3 提示词)
- **P7**:`/forgeue:change-finish` Finish Gate(12-key frontmatter + writeback 真实性 + cross-check `disputed_open == 0`)
- **P8**:archive change

**测试矩阵 size**(round 1 codex inline writeback 后):
- 原 ~22 case → 加 ~12 个新 case(tail truncation / key_id mismatch fail-closed / archived replay opt-in / schema strict 11-field / forgery_resistance audit consistency)
- 总测试 case ~34;tests/unit/test_dispatch_ledger.py 新增 ~450 行

**Rollback strategy**:
- 本 change archive 前任何一步可 rollback — 改动全在 wrapper / fence / 命令模板,无 schema migration / 数据 migration
- archive 后若实证 v3 fence 误报 → 紧急 follow-on 加 `runtime_enforcement_protocol_version: v3` opt-out flag(本 change 不预设 opt-out,沿 fail-closed 原则)
- key 文件 corruption 已通过 D-KeyRotationHandling exit 7 / fail-closed 处理,user 手工 backup + 删除 + 重新 init 即可

**Self-dogfood gap 边界**(沿 D-SelfDogfoodGap):
- 本 change 自身 implementation evidence 走 v2 advisory(`runtime_enforcement_protocol_version: v2` + `ledger_forgery_resistance: advisory`)
- ship 完后下一个 change(如 follow-on `enhance-workflow-automation-final-review-fence-strictness`)起可用 v3

## Open Questions

- **OQ-1**:wrapper_version 升到 "2.0" 后,ledger 同时存在 1.0 行(archived)+ 2.0 行(本 change ship 后新写入)是否合规?**Resolution**:archived ledger 不会被新 change 写入(每 change 独立 ledger),所以单 ledger 内不会混 wrapper_version;若日后某 change 复用 archived change 的 ledger 文件(罕见),fence 不强制 wrapper_version 具体值,只校非空,放过
- **OQ-2**:v3 evidence frontmatter `ledger_forgery_resistance: cryptographic` 是字符串字面值还是 enum?**Resolution**(round 1 codex F4 inline writeback 后):字符串字面值,但 `forgeue_finish_gate.py` 加新 fence `_check_ledger_forgery_resistance_consistency` 强校字段值与 `runtime_enforcement_protocol_version` 强 enum 绑定(v3 ↔ cryptographic / v2 ↔ advisory;不匹配 BLOCKER `frontmatter_audit_inconsistency`);沿 D-FrontmatterAuditConsistency。未来若加 multi-level enforcement(`cryptographic_strict` / `cryptographic_advisory`),扩 enum 时同步扩 fence dispatch matrix
- **OQ-3**:codex adversarial review round 1 是否会 raise 新的 high finding?**Resolution**(round 1 完成后):是,raise 5 finding(F1+F2+F3 high + F4+F5 medium),全 accepted-codex,4 inline writeback + 1 scope expansion;均完成 inline writeback。round 2 review 在 P0.5 验证 5 finding 修复闭合;disputed_open == 0 后 unlock P1
- **OQ-4**:测试 fixture 用 monkey-patched `Path.home()` 隔离用户真实 key — pytest 跨平台路径能否兼容?**Resolution**:用 `monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)`,Linux/Mac/Windows 都通用;ATM 测试时 wrapper 真实在 tmp_path/.claude/ 下创建 key 文件,不污染 user home
- **OQ-5**:CHANGELOG.md 里 entry 标记 release tag 是 v0.X.Y?**Resolution**:沿现有 CHANGELOG 习惯(2026-04 系列 entries),archive 时由 `/forgeue:change-doc-sync` 统一加;不预先填
