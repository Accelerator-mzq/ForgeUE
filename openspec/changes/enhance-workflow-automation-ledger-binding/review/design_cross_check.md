---
change_id: enhance-workflow-automation-ledger-binding
stage: S2
evidence_type: design_cross_check
contract_refs:
  - proposal.md
  - design.md
  - tasks.md
  - specs/examples-and-acceptance/spec.md
aligned_with_contract: true
detected_env: claude-code
triggered_by: cli-flag
codex_plugin_available: true
triggered_by_command: change-plan
runtime_enforcement_protocol_version: v2
autonomy_decision: claude_codex_concurred
codex_review_ref: review/codex_design_review.md
disputed_open: null
writeback_commit: null
resolved_at: null
created_at: 2026-05-06T13:53:29+08:00
---

# Design Cross-check — enhance-workflow-automation-ledger-binding

## A. Decision Summary(Claude 立场,冻结于 codex review 之前)

> **协议自我保护**:本段在 `/codex:adversarial-review` 调用之前完成,锁定 Claude 对 10 D-decision 的立场。codex 输出之后只填 `## B/C/D`,不回填 `## A`。

### A.1 D-Scope-F3Only(本 change scope 限 F3 cryptographic enforcement,不做 F2 wrapper-bound dispatch)

**Claude 立场**:F2(真 wrapper-bound dispatch)deferred 到独立 change `enhance-workflow-automation-skill-tool-binding`;本 change 只 ship F3(cryptographic ledger signing)。F2 需要 `~/.claude/settings.json` `PreToolUse` hook 改动,跨 project 污染 + 调试困难;F3 是 self-contained 改动,scope 干净。

**Why**:
- archived `executable-enforcement` design.md 已经 reject 全局 hook 路径(跨 project 污染 + 调试困难);本 change 沿同款边界
- F3 是 self-contained — 只动 wrapper / fence / 命令模板 frontmatter,不动 hook,不动 settings,不动 Skill 协议
- 实证 F3 cryptographic 是否能 catch controller drift,再决定是否值得做 F2(避免预设 F2 的工程量浪费)

**Anticipated codex challenge**:
- (a) F3 only 不解决 LLM 主动恶意 forge → 接受;threat model 已显式排除该攻击,留 future `enhance-workflow-automation-os-keystore` follow-on
- (b) F2 + F3 同时做减少 follow-on 数 → 拒绝;hook 改动跨 project 污染是已知 reject 边界
- (c) scope 应缩到 P12.8 schema 强化(无 crypto)→ 拒绝;不解决 F3 hand-edit / delete / forge 漏洞,只是 hygiene

### A.2 D-KeyLocation(HMAC key 持久化到 `~/.claude/forgeue_ledger_key`,JSON 单文件,跨 change 共享)

**Claude 立场**:Key 文件路径 `Path.home() / ".claude" / "forgeue_ledger_key"`;JSON 格式 `{"version": 1, "created_at": "...", "key_hex": "..."}`(64 hex chars = 32 bytes);跨 change 共享(任一 change 写的 ledger 都用同 key);wrapper 首次 invoke 时 `secrets.token_bytes(32)` 随机生成 + Linux/Mac `os.chmod(0o600)`(Windows 简化为 obscurity)。

**Why**:
- 跨 session 持久化必须(wrapper init 在 dispatch session,fence 在 finish session,跨 session env var 不可用)
- `~/.claude/` 是 Claude Code 配置区,LLM 在 ForgeUE 项目工作时不主动 ls 跨项目目录(obscurity layer)
- 跨 change 共享是 feature(任何 change 写的 ledger 都用同 key,无论谁 verify 都校验得了)
- pure stdlib(`secrets.token_bytes` + `hashlib` + `os.chmod` + `pathlib`),无第三方 dep

**Anticipated codex challenge**:
- (a) per-change key 比全局 key 隔离更好 → 拒绝;LLM 自然会读 change-dir 下文件(命令模板要求 LLM 在 change-dir 工作),defense 几乎=advisory
- (b) OS-level secret store(DPAPI / Keychain / libsecret)更安全 → 拒绝(本 change scope);跨平台 wrapper 易碎 + Linux 第三方 dep,违反 stdlib-only;留 future follow-on
- (c) Per-session env var only 简单 → 拒绝;跨 session 不持久化,功能 broken
- (d) Windows `os.chmod(0o600)` 不严格 → 接受 mitigation;接受 obscurity-not-strict-permission(用户目录 default user-only 访问已足够;真严格 ACL 需 pywin32 调 SetSecurityInfo,违反 stdlib-only)
- (e) 跨 change 共享 key:任一 change 泄漏 key → 所有 change ledger 可被 forge → 接受 mitigation(wrapper 不暴露 key 给 LLM;user 怀疑泄漏可手工 rm + 重新生成,旧 ledger 走 key_rotation WARN 路径可恢复)

### A.3 D-ProtocolVersion(新 v3 协议升级,fence dispatch 加 v3 分支;v2 archived ledger 完全 backward compatible)

**Claude 立场**:新 protocol version `v3`;evidence frontmatter `runtime_enforcement_protocol_version: v3`;ledger 行加 `protocol_version: "v3"`;fence dispatch matrix 4 档(legacy / v1 / v2 / v3);archived v2 evidence + ledger 完全不动。

**Why**:
- evidence frontmatter `runtime_enforcement_protocol_version` 字段已有 (legacy / v1 / v2) 三档 dispatch 习惯,加 v3 是自然延伸
- fence 入口统一 `dispatch on protocol_version`,各分支独立逻辑;后续若有新 enforcement 协议,可继续 v4 / v5 扩展
- v2 内部强化(同协议下 fence 检测 ledger 有无 hmac 字段)会让 fence dispatch 逻辑分裂,后续 follow-on 继续在 v2 堆叠会出现 "v2-with-X" / "v2-with-Y" 含糊
- archived `executable-enforcement` v2 evidence + ledger 完全 backward compatible

**Anticipated codex challenge**:
- (a) v2 内部强化(无新 protocol version)简化 → 拒绝;fence 逻辑分裂 + 后续 enforcement 不可扩展
- (b) 应该直接 break v2 兼容(archived 不再支持 replay)→ 拒绝;archived replay 兼容是 forgeue_finish_gate 既有协议(沿 archived runtime-enforcement / executable-enforcement 同款)

### A.4 D-HashChain(HMAC 用 hash chain,catch 删行 / reorder attack)

**Claude 立场**:每行 HMAC 计算覆盖 7 个原 v2 字段 + `protocol_version` + `key_id` + `prev_hmac`(即 10 字段),HMAC 自身不进 canonical;`prev_hmac` 字段值 = 上一行 `hmac` 值 hex string;首行 `prev_hmac` 固定全 0(`"0" * 64`)。

**Why**:
- 单行 HMAC 抓不住删行 — LLM 完全可以让 wrapper 正常 dispatch 一次写入合法行,然后偷偷删除中间几行(比如删除"被 reject 的失败 round")。剩余行 HMAC 仍合法,fence 通过
- Hash chain 是经典的防删行手法 — 任何修改 / 删除 / reorder 必然 break chain
- 性能不是 concern(ledger 通常 < 100 行)

**Anticipated codex challenge**:
- (a) Merkle tree(每行 hash 包含全文件 root)更安全 → 拒绝;过度工程,append-only ledger 用不上 tree 结构
- (b) 单行 HMAC 简单 → 拒绝;留删行 attack 漏洞,违反 cryptographic enforcement 初衷
- (c) chain 中间一行损坏导致后续全 fail,debugging 难 → 接受 mitigation(error message 指明具体行号 + 类型 prefix `[chain_break] line <K+1>`)
- (d) 首行 prev_hmac 全 0 是约定,不防 LLM 伪造首行 → 接受;首行 prev_hmac != all-zeros 触发 chain_break BLOCKER,fence 显式校

### A.5 D-CanonicalJSON(canonical JSON 序列化排除 hmac + 包含 prev_hmac + sort_keys + UTF-8)

**Claude 立场**:`canonical_payload(record)` 函数排除 `hmac` 字段(避免循环依赖)+ 包含 `prev_hmac` 字段(它是 chain 输入)+ `sort_keys=True` + `separators=(",", ":")` + `ensure_ascii=False`;输出 UTF-8 encoded bytes。

**Why**:
- 不规范化的 JSON 序列化跨 Python 版本 / 跨 wrapper 实现可能产生不同 bytes,导致 HMAC 重算时不匹配
- 字段顺序歧义:Python 3.7+ dict 保持插入顺序,但跨实现不保证
- whitespace 歧义:默认 `json.dumps` 加 ", " / ": "(后空格),不同库可能不加
- unicode 边界:`ensure_ascii=True` 会把非 ASCII 字符转义,但 ledger 文件以 UTF-8 存储,直接保留 unicode 更直观

**Anticipated codex challenge**:
- (a) 漏字段 / 加错字段导致 HMAC 永远不一致 → 接受 mitigation;测试 case `test_canonical_excludes_hmac_includes_prev_hmac` + `test_canonical_round_trip_stability` 守门
- (b) 应该用更严格的 canonical(如 RFC 8785 JSON Canonicalization)→ 拒绝;过度工程,Python `json.dumps(sort_keys=True, separators=...)` 已足够 + stdlib-only
- (c) 跨 Python 版本 sort_keys 行为差异 → 接受 mitigation;测试 fixture 不引入 unicode agent_id(沿现有 ledger 实践 agent_id 是 hex);若日后引入 unicode 字段,加 `unicodedata.normalize("NFC", ...)` 预处理 — 留 follow-on

### A.6 D-KeyRotationHandling(key 文件不存在 / 损坏 / rotation 三态分别处理)

**Claude 立场**:wrapper key file lifecycle 4 状态(首次 init / 正常 load / 文件损坏 / key rotation 检测),exit code 0/5/6/7 区分;**关键**:key rotation 是 WARN(允许 archived ledger replay),同一 ledger 内 key_id 不一致才是 BLOCKER。

**Why**:
- 首次 init 静默生成不打扰 user — wrapper 就是为隐藏 crypto 复杂度而存在;但打印 INFO 行让 user 看到 key 创建轨迹
- 文件损坏 fail-closed(不静默重建)— 静默重建会丢失 verify 旧 ledger 能力,user 必须显式介入
- key_rotation 不是 forge:user 主动 rm key 是合法操作(怀疑泄漏时);archived ledger 用旧 key_id 写,新 file 是新 key_id,跨 ledger 文件 key_id 不一致是预期 → WARN 不 BLOCKER
- 同一 ledger 内 key_id 不一致 是 forge 强信号(LLM 中途切换了 key 文件);BLOCKER

**Anticipated codex challenge**:
- (a) key 文件损坏静默重建更友好 → 拒绝;静默丢 verify 能力,违反 fail-closed 原则
- (b) key rotation 也 BLOCKER(不区分 forge)→ 拒绝;break archived ledger replay,违反 backward compatibility
- (c) exit code 6/7 与现有 forgeue_dispatch_ledger exit code 5(generic verify_fail)耦合 → 接受 audit trail;exit code 区分是 user-facing 信号,error message prefix 也区分

### A.7 D-FenceDispatchMatrix(fence dispatch 4 档矩阵,v3 = v2 + HMAC chain)

**Claude 立场**:`forgeue_finish_gate.py::_check_dispatch_ledger` 入口加 4 档 dispatch(legacy / v1 / v2 / v3);v3 = v2 schema check + HMAC chain verify;v3 fence 走 fail-closed(verify 失败 BLOCKER);key_rotation 例外走 WARN。

**Why**:
- 4 档矩阵清晰 — 每档独立 logic,后续 follow-on 加 v4 / v5 协议时可继续扩展
- archived v2 evidence + v2 ledger 完全 backward compatible(走 v2 路径,不触 v3)
- 本 change 自身 evidence 仍走 v2 advisory(self-dogfood gap;沿 D-SelfDogfoodGap)

**Anticipated codex challenge**:
- (a) 直接淘汰 v2 路径,统一走 v3 → 拒绝;break archived v2 evidence(`executable-enforcement` 等)replay 兼容
- (b) v3 fence 应该 inspect ledger schema 第一时间 fail(无 hmac 字段直接 fail)而非走 dispatch matrix → 拒绝;dispatch matrix 由 evidence frontmatter 决定(沿现有协议),ledger schema 是 dispatch 的 follow-on(verify_chain_v3 内部校)
- (c) 4 档矩阵复杂,日后维护负担 → 接受 mitigation;沿 archived runtime-enforcement / executable-enforcement v1 → v2 升级路径,矩阵扩展是设计目标(future-extensible)

### A.8 D-SelfDogfoodGap(本 change 自身 evidence 仍走 v2 advisory,ship 后下一个 change 才用 v3)

**Claude 立场**:本 change 自身 implementation evidence 走 v2 advisory(`runtime_enforcement_protocol_version: v2` + `ledger_forgery_resistance: advisory`);ship 完后下一个 change 起可用 v3。沿 archived `executable-enforcement` D-DogfoodGap 同款处理。

**Why**:
- 本 change 实施时 v3 fence 还没 ship,本 change 自身 evidence 用 v3 协议会触发 fence 但 fence 自身代码还在改 — 自循环依赖
- 沿 self-dogfood gap 模式:本 change 自身 evidence 标 v2 + advisory,evidence frontmatter 加 audit 注释 `# v3 协议本 change ship 后才生效`
- archived `executable-enforcement` 同款处理过(自身 evidence v1,本 change ship v2)

**Anticipated codex challenge**:
- (a) 本 change 自身用 v3 协议自我验证 → 拒绝;自循环依赖(fence 还在改 + evidence 已要求 v3),技术不可行
- (b) 应该 ship 后立即开 follow-on 用 v3 实证 → 接受 follow-on tracking(P9.4 已 list);本 change scope 不实施
- (c) self-dogfood gap 是工程缺陷应该解决 → 接受 future enhancement(留 follow-on `enhance-workflow-automation-bootstrap-protocol` 若实证不足)

### A.9 D-DispatchPath(推荐 `change-apply-direct` 路径,scope 聚焦 + < 6h 工程量)

**Claude 立场**:推荐 `/forgeue:change-apply-direct` 路径(沿 D-DirectWorktreeRefinement 不强制 isolated worktree,`worktree_consent_outcome: declined / already_isolated`,`worktree_mode: in_place`)。

**Why**:
- scope 聚焦 — 纯 wrapper / fence / 测试,无跨子系统;3 个核心改动文件
- 工程量 ~4-6h(code 250 行 + test 350 行 + doc 100 行)
- subagent 路径 overhead(per-task 4 类 evidence + worktree 初始化 + dispatch ledger v2 fence 自循环)对这种聚焦 change 反而增加摩擦
- ADR-013 worktree consent gate 在 direct 路径下仍生效,但 framework 层修改默认 in_place(沿 D-DirectWorktreeRefinement)

**Anticipated codex challenge**:
- (a) `change-apply-subagent` 多 review 视角更稳 → 接受 trade-off;subagent overhead 不划算(per-task 4 evidence + final review)
- (b) `change-apply-parallel` 加速 → 拒绝;tasks 不独立(crypto helper / dispatch_ledger / finish_gate 互相依赖)
- (c) framework 层修改应强制 worktree → 拒绝;ADR-013 default decline + main repo 路径已经平衡 risk vs friction;direct 路径 in_place 是 D-DirectWorktreeRefinement 已 ship 的默认

### A.10 D-WrapperVersionBump(`wrapper_version` 从 "1.0" 升到 "2.0",标记 v3 schema break)

**Claude 立场**:`tools/forgeue_dispatch_ledger.py::WRAPPER_VERSION` 从 `"1.0"` 升到 `"2.0"`;`cmd_append` 写入 ledger 行 `wrapper_version: "2.0"`;`cmd_verify` 不强制校 wrapper_version 具体值(仅校非空,沿现有 v2 fence 逻辑)。

**Why**:
- v3 schema 加了 4 字段 + HMAC chain 协议,wrapper 实施 break,版本号 bump 标记
- archived v2 ledger 行 `wrapper_version: "1.0"` 仍合法,fence 不强制具体值(允许混合 ledger 行,虽然实际不会发生)
- 后续 wrapper 改动(如 schema 加字段)继续 bump(2.0 → 2.1 → 3.0)

**Anticipated codex challenge**:
- (a) wrapper_version 不升(仍 1.0)简化 → 拒绝;v3 ledger 行实施与 v2 完全不同,不升版本号失去 audit trail
- (b) wrapper_version 应该用 SemVer 严格(major.minor.patch)→ 接受 future;本 change 用简化 X.Y(major.minor),沿现有 wrapper_version 实践
- (c) wrapper_version 与 protocol_version 重复 → 接受讨论但保留(wrapper bug fix 不必 bump protocol);protocol_version 是协议层版本号,wrapper_version 是工具实施版本号,语义不同

## B. Codex Findings + Resolution(round 1)

逐条 codex finding(全 verbatim 见 `review/codex_design_review.md`)对照 + Resolution。Resolution enum:`aligned` / `accepted-codex` / `accepted-claude` / `disputed-pending` / `disputed-permanent-drift`。

### B.1 F1 [high] — Spec line 264 "调用前先 wrapper append" 与 design + archived 命令模板矛盾(等于重新打开 archived F2)

**Codex 立场**:proposal/design 明确 F2 wrapper-bound dispatch out-of-scope;archived 命令模板 step 10a 是 post-dispatch capture 真实 agent_id;但本 change spec line 264 字面"调用前先 wrapper append" — append CLI 必填 `--agent-id`,调用前没有真实 agent_id,只能失败或退回 synthetic ID,等于重开 archived F2 deferred。

**Claude 独立 verify**:
- `specs/examples-and-acceptance/spec.md:264` 字面"SHALL 在每次 Skill(Task) / Skill(SendMessage) 调用前先 wrapper append" — confirmed
- 我写 spec MODIFIED Requirement 时直接 copy 了 archived `enhance-workflow-automation-executable-enforcement` 的 archived spec line 1014 文本,而 archived spec 文本本身就是 archived F2 round 1 inline writeback **未完整传播**到 spec 的遗留 bug(archived 命令模板 step 10a 已改为 post-dispatch,但 spec 文本未跟改)
- 本 change 定位 F3-only,不 reopen F2 — Codex finding 与 D-Scope-F3Only 一致

**Resolution**:`accepted-codex,inline writeback`
- 改 spec line 264 "调用前先 wrapper append" → "调用后 capture 真实 agent_id 再 append wrapper(沿 archived `executable-enforcement` F2 round 1 inline writeback,post-dispatch capture)"
- 同时 archived spec 同位置文本 bug **不**回写(archived 不动是协议;archived spec 作为历史快照保持不一致是接受的)— 本 change MODIFIED Requirement 重写后即为新真源
- 不动 D-Scope-F3Only(已对齐)

### B.2 F2 [high] — key_rotation WARN 把 unverifiable ledger 当 pass(攻击/事故场景下 bypass HMAC enforcement)

**Codex 立场**:v3 verify 流程只有当前 key_bytes,但 spec 规定 ledger key_id 与当前 key_id 不一致时 WARN 不阻断。没有旧 key 时无法重算旧 HMAC — 先重算会全部 hmac_mismatch;先 detect key_id mismatch 走 WARN 就接受 unverifiable ledger。LLM 替换 key 文件即可把 HMAC 校验降级为 WARN — 等于 cryptographic enforcement 被 trivially bypass。

**Claude 独立 verify**:
- `specs/examples-and-acceptance/spec.md:148-165` v3 verify 流程 step 4 "ledger key_id ≠ 当前 file key_id 但 ledger 自身一致 → key_rotation_detected WARN" — confirmed
- `design.md` D-KeyRotationHandling 同款描述
- 攻击场景:LLM 不读 key 文件,只 forge ledger + 在某行 inject 假 hmac;然后**修改 `~/.claude/forgeue_ledger_key`** 用新 key 替换,fence 跑 verify 时 key_id mismatch → WARN,绕过 HMAC 校。
  - 进一步攻击:LLM 不需要"读 key 替换 ledger",只需要"替换 key 文件" — fence 自动 WARN ledger,所有 forge 通过
- F2 finding 完全 valid,WARN 路径是设计 hole,不是 trade-off

**Resolution**:`accepted-codex,inline writeback`
- D-KeyRotationHandling 改写:active v3 evidence(本 change ship 后新 evidence)对 key_id mismatch **fail-closed BLOCKER**(exit 5),**不** WARN
- archived replay 兼容性走 **explicit user override** — evidence frontmatter 加 opt-in 字段 `ledger_archived_replay: true`(default false / null);本字段为 true 时 fence 接受 key_id mismatch WARN 路径(audit 友好,user 显式承担风险)
- 删除 verify 状态 `key_rotation_detected WARN` 自动路径;exit 6 重命名为 `key_rotation_user_override_required`(只在 evidence 标 `ledger_archived_replay: true` 时取此 exit)
- spec 改写 `## B.2 F2` 影响段 + 新增 frontmatter 字段 Scenario

### B.3 F3 [high] — Hash chain 抓不住 tail truncation;单行 ledger 无链约束

**Codex 立场**:prev_hmac 串联行能抓中间删行和 reorder,但删除最后 N 行后剩余前缀仍是合法链。单行 ledger(prev_hmac 全 0 + 单 hmac)删了之后什么都没有,无 anchor。当前 v2 `_check_round_fix_continuity` 在 evidence `subagent_continuity` 缺失时跳过 ledger 计数约束 — v3 设计也没有 `ledger_line_count` / `final_hmac` 这种外部锚点。结果:LLM 删除尾部失败的 reviewer/fix 记录(round 1 reviewer 拒绝 implementer → 删除该行让 evidence 看起来 round 1 即通过)不破坏 HMAC chain。

**Claude 独立 verify**:
- `design.md` D-HashChain section "任何修改 / 删除 / reorder 必然 break chain" — confirmed,这是错误声明;tail truncation 是已知的 hash chain weakness,设计文本严重 overclaim
- spec.md v3 verify 流程没有任何 line_count / final_hmac 外部 anchor 校验
- 攻击场景:LLM 跑 wrapper 5 次合法 dispatch(implementer / spec_reviewer / cqr / round 2 fix / round 2 review);失败 round 后 LLM 删除最后 2 行(round 2 fix + round 2 review)伪装 round 1 即通过 — 剩 3 行链合法,fence 通过
- F3 finding 完全 valid,这是 cryptographic enforcement 的 critical hole

**Resolution**:`accepted-codex,inline writeback`
- evidence frontmatter 加 v3 必填字段:
  - `ledger_line_count: <int>`(声明 ledger 行数;wrapper-side **不**自动写,由 LLM 复制写入,fence cross-check 与实际 ledger 行数一致)
  - `ledger_final_hmac: <64 hex chars>`(声明 ledger 最后一行 hmac;同上 LLM 复制,fence cross-check 与实际 ledger 最后一行 hmac 一致)
- 新 fence `_check_ledger_terminal_proof`:
  - evidence frontmatter `ledger_line_count` 必填 v3 evidence(缺失 → BLOCKER)
  - evidence frontmatter `ledger_final_hmac` 必填 v3 evidence(缺失 → BLOCKER)
  - 实际 ledger 行数 vs evidence `ledger_line_count` 不等 → BLOCKER `tail_truncation_detected`
  - 实际 ledger 最后一行 hmac vs evidence `ledger_final_hmac` 不等 → BLOCKER `final_hmac_mismatch`
- spec MODIFIED Requirement 加新 ADDED Requirement "v3 ledger terminal proof"(line_count + final_hmac frontmatter audit)
- design.md D-HashChain 加 sub-section "Tail truncation mitigation" + 修正 overclaim 文本
- tasks.md P1.1 / P2.1 / P3.1 加测试:
  - `test_v3_verify_fail_tail_truncation`(删除最后一行 → BLOCKER tail_truncation_detected)
  - `test_v3_verify_fail_single_line_ledger_truncated_to_zero`(单行 ledger 删除后 line_count 不一致 BLOCKER)
  - `test_v3_evidence_missing_ledger_line_count`(v3 evidence 缺 line_count → BLOCKER)
  - `test_v3_evidence_missing_ledger_final_hmac`(v3 evidence 缺 final_hmac → BLOCKER)
- 本字段 audit 强度边界:LLM 仍可同时 forge ledger + 重写 evidence frontmatter line_count + final_hmac(LLM 完全可以读 ledger 末行 hmac 然后写到 evidence;F3 cryptographic 不解决主动恶意 forge — 沿 design.md threat model 边界)
- 但本 fence 抓 **常见 sloppy bypass**:LLM 删除尾部后 evidence frontmatter 不更新就被抓;若 LLM 同时更新两边,这是 willful forge(threat model 之外,但比 advisory 强)

### B.4 F4 [medium] — v3 protocol 与 ledger_forgery_resistance audit 字段未 gate 绑定(审计信号脱钩)

**Codex 立场**:spec 要求 v3 evidence 写 `ledger_forgery_resistance: cryptographic` 但又明确 `forgeue_finish_gate` 不强制 enum。结果:v2 evidence 可自称 cryptographic,v3 evidence 可写 advisory — 审计字段与实际 protocol_version 脱钩。考虑 tasks.md P9.4 计划用本 change 评估 cancel P12.7+P12.8 follow-on,这会制造错误的安全信号(假装 cryptographic 实际是 v2 advisory)。

**Claude 独立 verify**:
- `specs/examples-and-acceptance/spec.md:217-223` 字面"finish_gate **不**强制 `ledger_forgery_resistance` 字段值的 enum" — confirmed
- 设计 intent 是"audit 标注,非 gate";但因为本 change 加 v3 cryptographic 升级,标注与协议必须一致才能 audit 有意义
- 我之前写"沿 v2 advisory 同款实践"是错误的 anchor — v2 advisory 本来就承认 audit only,但 v3 cryptographic 是新升级,强 enum 是配套要求

**Resolution**:`accepted-codex,inline writeback`
- spec.md MODIFIED 这段:`forgeue_finish_gate.py` 强制字段一致性 fence(`_check_ledger_forgery_resistance_consistency`):
  - `runtime_enforcement_protocol_version: v3` ↔ `ledger_forgery_resistance: cryptographic`(必须严格匹配)
  - `runtime_enforcement_protocol_version: v2` ↔ `ledger_forgery_resistance: advisory`(同上)
  - `runtime_enforcement_protocol_version: v1` 无此字段约束(advisory pass-through)
  - 不匹配 → BLOCKER `frontmatter_audit_inconsistency`
- design.md D-FrontmatterAuditConsistency 新加 D-decision(11 个 D-decision)
- tasks.md P3.1 加测试:`test_v3_evidence_with_advisory_blocked` + `test_v2_evidence_with_cryptographic_blocked`
- finish_gate fence 数量:v2 6 fence → v3 加 `_check_ledger_terminal_proof`(F3)+ `_check_ledger_forgery_resistance_consistency`(F4)= 8 fence

### B.5 F5 [medium] — HMAC 不替代 schema validation;cancel P12.8 follow-on 会漏 schema 风险

**Codex 立场**:cmd_verify 仍描述 well-formed JSON / timestamp / wrapper_version + v3 HMAC chain — 没要求 strict 11-field schema / round positive int / agent_id format / 拒未知字段。当前 v2 append 只校 role,agent_id 可任意字符串 / round 可为负数 / float / bool;v3 会把无效记录"签得很完整"但语义 broken。tasks.md P9.4 计划"本 change v3 ledger HMAC chain verify 是否已覆盖 P12.7 + P12.8 hygiene gap?若是,这 2 个 follow-on 可标 cancelled" — Codex 警告 P12.8 schema validation 不应仅因 HMAC ship 自动 cancel(HMAC 只保护 bytes 完整,不保护 schema 语义)。

**Claude 独立 verify**:
- `specs/examples-and-acceptance/spec.md:238-256` cmd_verify 描述沿 v2 schema-only + v3 HMAC chain — confirmed,无字段 enum / round positive / agent_id format / 拒未知字段
- 攻击场景:LLM 写 ledger 行 `{"agent_id": "<arbitrary 1MB string>", "round": -42, "role": "implementer", ..., "extra_field_123": "anything", "hmac": "<合法 HMAC over the garbage>"}` — fence v3 chain verify pass,但 schema 完全 broken
- F5 finding 完全 valid;HMAC + schema validation 是 orthogonal,需要并存

**Resolution**:`accepted-codex,scope expansion`
- 把 archived `executable-enforcement` P12.8(`enhance-workflow-automation-v2-fence-hardening`)的 schema validation 内容**合并进本 change v3 verify**:
  - v3 ledger 行严格 11 字段 schema(精确字段集 + 拒未知字段)
  - `agent_id`:`^[a-f0-9]{17,}$` 正则(沿 archived 同款 hex format,长度 ≥ 17)
  - `round`:正整数(`isinstance(round, int) and round > 0 and not isinstance(round, bool)`,显式拒 bool 因为 `bool` 是 `int` 子类)
  - `role`:`VALID_ROLES` enum(沿 forgeue_dispatch_ledger.py 现有 frozenset)
  - `task_subject_hash`:None 或 `^sha256:[a-f0-9]{64}$`
  - `dispatched_at`:ISO8601 tz-aware(`datetime.fromisoformat(...)` parse-able + `tzinfo is not None`)
  - `parent_session_id`:None 或 UUID format(`^[a-f0-9-]{36}$`)
  - `wrapper_version`:`^\d+\.\d+$` 正则(major.minor)
  - `protocol_version`:精确 `"v3"`
  - `key_id`:`^[a-f0-9]{16}$` 正则(64-bit fingerprint)
  - `prev_hmac`:`^[a-f0-9]{64}$` 正则
  - `hmac`:`^[a-f0-9]{64}$` 正则
- 新 fence `_check_ledger_schema_strict_v3`:任何 schema 违反 → BLOCKER `dispatch_ledger_violation` + error message prefix `[schema_violation]`
- tasks.md P9.4 (follow-on tracking)更新:`enhance-workflow-automation-v2-fence-hardening` (P12.8) 标 **superseded by enhance-workflow-automation-ledger-binding**(本 change ship 后正式 cancel)
- tasks.md P9.4 (follow-on tracking)的 P12.7 (`enhance-workflow-automation-final-review-fence-strictness`)单独评估 — F3 ledger terminal proof + F5 schema validation 是否已 cover P12.7 hygiene gap?后续 cancel 评估留 ship 后实证(本 change 不预设 cancel)
- design.md D-Scope 段加新 sub-decision **D-Scope-F3-MergeWithP12.8**:本 change 合并 P12.8 schema hardening,scope 扩展但 atomic 一次 ship
- tasks.md P1.1 / P2.1 / P3.1 加测试:
  - `test_v3_verify_fail_unknown_field`
  - `test_v3_verify_fail_missing_field`
  - `test_v3_verify_fail_negative_round`
  - `test_v3_verify_fail_float_round`
  - `test_v3_verify_fail_bool_round`(`True` is `1` int 子类,但 schema 应显式拒)
  - `test_v3_verify_fail_oversize_agent_id`(>1KB)
  - `test_v3_verify_fail_invalid_role`
  - `test_v3_verify_fail_naive_dispatched_at`(无 tzinfo)

## C. Disputed Open Count

`disputed_open: 0`

> 5 codex finding 全 `accepted-codex,inline writeback`(F1+F2+F3+F4)+ `accepted-codex,scope expansion`(F5)。无 disputed-pending。无 disputed-permanent-drift。

> writeback 完成后 commit SHA 填回 frontmatter `writeback_commit` + `resolved_at`;writeback 触及 design.md / proposal.md / tasks.md / specs/examples-and-acceptance/spec.md 4 份 contract artifact。

## D. Independent Verification(file:line 独立验证)

> 沿 ForgeUE memory `feedback_verify_external_reviews`,不把 codex claim 当结论。每条 file:line 由 Claude Read source 重新 verify(verify trace 在 `review/codex_design_review.md` "Independent Verification" 表)。

| Codex finding | claimed file:line | Claude 独立 verify | match |
|---|---|---|---|
| F1 | `spec.md:264` "调用前先 wrapper append" | Read line 264 字面 confirmed | ✅ |
| F2 | `spec.md:148-165` v3 verify 流程 + key_rotation WARN | Read line 148-165 verify 流程 step 4 "ledger key_id ≠ 当前 file key_id 触发 key_rotation WARN(非 BLOCKER)" 字面 confirmed | ✅ |
| F3 | `design.md:93-100` D-HashChain "任何修改/删除/reorder 必然 break chain" | Read design.md D-HashChain section 字面 confirmed | ✅ |
| F4 | `spec.md:217-223` finish_gate 不强制 ledger_forgery_resistance enum | Read line 221 字面"`forgeue_finish_gate.py` **不**强制 `ledger_forgery_resistance` 字段值的 enum" | ✅ |
| F5 | `spec.md:238-256` cmd_verify schema 校 | Read line 238-256 周边 — cmd_verify 描述沿 v2 schema-only + v3 HMAC chain;无字段 enum / round positive / agent_id format 校 | ✅ |

5/5 codex file:line claim 独立 verify 通过。无 phantom claim / 无 stale anchor。

## Round 1 Status

- Total findings: 5(high=3 + medium=2)
- All accepted-codex(0 disputed)
- 4 inline writeback + 1 scope expansion
- Writeback target:`design.md`(D-KeyRotationHandling 改 + D-HashChain 加 sub-section 修 overclaim + 加 D-FrontmatterAuditConsistency / D-Scope-F3-MergeWithP12.8 2 新 D-decision)+ `proposal.md`(scope expansion 描述加 P12.8 合并)+ `specs/examples-and-acceptance/spec.md`(spec line 264 改 + key_rotation BLOCKER + ADDED Requirement "v3 ledger terminal proof" + 加 strict schema validation Requirement)+ `tasks.md`(P1.1 / P2.1 / P3.1 测试加 ~10 case + P9.4 P12.8 standby cancel 标记 superseded)

下一步:
- inline writeback 实施(并行 4 文件 Edit)
- writeback commit
- 更新 cross-check frontmatter `writeback_commit` + `resolved_at`
- round 2 codex adversarial review(继承 round 1 verdict;沿 codex command 协议)
- round 2 cross-check `## B/C/D round 2` 段
- round 2 disputed_open == 0 → 进 S3
