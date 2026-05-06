## ADDED Requirements

### Requirement: HMAC key lifecycle for v3 cryptographic ledger binding

ForgeUE SHALL 提供 stdlib-only helper module `tools/_forgeue_ledger_crypto.py`,负责 HMAC key 文件 lifecycle 管理。

**Key 文件路径**:`Path.home() / ".claude" / "forgeue_ledger_key"`(跨 change 共享;Windows / Linux / Mac 都解析到当前用户 home)。

**Key 文件 schema**(JSON 单文件):
```json
{
  "version": 1,
  "created_at": "<ISO8601 timestamp>",
  "key_hex": "<64 hex chars = 32 bytes random>"
}
```

**`load_or_init_key()` 函数 SHALL 返回 `(key_bytes: bytes, key_id: str)` tuple**:
- `key_bytes`:32 字节 raw key(`bytes.fromhex(key_hex)`)
- `key_id`:`hashlib.sha256(key_bytes).hexdigest()[:16]`(16 hex chars = 64-bit fingerprint;不暴露 raw key)

**Lifecycle 4 状态**:

| 状态 | 触发条件 | wrapper 行为 | 退出/返回 |
|---|---|---|---|
| 首次 init | key 文件不存在 + `append` 调用 | `secrets.token_bytes(32)` 生成 + 用 `os.O_EXCL` flag 创建文件 + Linux/Mac `os.chmod(0o600)` + 打印 `[INFO] HMAC key initialized at <path> (key_id=<fingerprint>)` | 0 (继续 append) |
| 正常 load | 文件存在 + JSON 合法 + key_hex 长度恰好 64 chars | 读 key + 计算 key_id | 0 |
| 文件损坏 | 文件存在但 JSON 解析失败 / key_hex 长度错误 / version 不识别 | abort,**不**静默重建;打印 ERROR 提示 user backup + 删除 + 重新 init | 7 (`key_file_corrupted`) |
| key rotation 检测 | (verify 时)ledger 行 key_id ≠ 当前 file key_id,但 ledger 自身 key_id 一致 | WARN,不阻断 | 6 (`key_rotation_detected`) |

**关键约束**:
- Key 文件**不**进 git 追踪(由用户目录自然隔离;`.gitignore` 不需加入,因为不在 repo 内)
- 命令模板**不暴露** key 文件路径给 LLM Read / Write / Edit tool(LLM 不直接接触 key)
- 实施 stdlib-only:`secrets` / `hashlib` / `hmac` / `json` / `pathlib` / `os.chmod`,无第三方依赖

#### Scenario: 首次 init 自动生成 key 文件

- **WHEN** `~/.claude/forgeue_ledger_key` 不存在 + 跑 `forgeue_dispatch_ledger.py append`
- **THEN** wrapper 自动 `secrets.token_bytes(32)` 生成 32 字节 random + 用 `os.O_EXCL` flag 创建 JSON 文件
- **AND** 文件含 `version: 1` + `created_at` ISO8601 + `key_hex`(64 hex chars)
- **AND** Linux/Mac 文件权限 `0600`(stat 校 `S_IRUSR | S_IWUSR`,无 group/other 位)
- **AND** stdout 打印 `[INFO] HMAC key initialized at <path> (key_id=<16 hex>)` 一行

#### Scenario: 正常 load 已存在 key 文件

- **WHEN** key 文件已存在 + JSON 合法 + key_hex 长度 64 chars + 跑 append/verify
- **THEN** wrapper 读文件 + 解析 JSON + 用 key_hex 派生 key_bytes 与 key_id
- **AND** key_id == sha256(key_bytes).hexdigest()[:16]

#### Scenario: 文件损坏 fail-closed

- **WHEN** key 文件存在但 JSON 解析失败(如末尾被 truncate) OR key_hex 长度 ≠ 64 OR version 字段不是 1
- **THEN** wrapper exit 7
- **AND** stderr 打印 `[ERROR] key file corrupted at <path>: <reason>; backup + remove file to re-init`
- **AND** **不**自动重建 key(避免静默丢失 verify 旧 ledger 能力)

#### Scenario: 文件锁防 race(并发 init)

- **WHEN** 两个 wrapper 进程同时检测 key 文件不存在并尝试 init
- **THEN** 用 `os.open(path, O_CREAT | O_EXCL | O_WRONLY)` 创建文件
- **AND** 第二个进程触发 EEXIST,捕获后 retry-load,读到第一个进程刚写入的 key
- **AND** 两个 wrapper 最终用同一 key + 同一 key_id

### Requirement: v3 ledger schema with HMAC chain

ForgeUE SHALL 升级 ledger 行 schema 到 v3 — v2 的 7 字段基础上加 4 字段:`protocol_version` / `key_id` / `prev_hmac` / `hmac`。

**v3 ledger 行 schema**(11 字段):
```json
{
  "agent_id": "<hex>",
  "round": <int>,
  "role": "<implementer|spec_reviewer|code_quality_reviewer|final_reviewer|implementer_round_2_fix|spec_reviewer_round_2_review>",
  "task_subject_hash": "<sha256:...|null>",
  "dispatched_at": "<ISO8601>",
  "parent_session_id": "<uuid|null>",
  "wrapper_version": "2.0",
  "protocol_version": "v3",
  "key_id": "<16 hex chars>",
  "prev_hmac": "<64 hex chars; first line: '0' * 64>",
  "hmac": "<64 hex chars = HMAC-SHA256(key, canonical_payload)>"
}
```

**Wrapper 版本**:`tools/forgeue_dispatch_ledger.py::WRAPPER_VERSION` SHALL 升到 `"2.0"`(标记 v3 schema break)。

**HMAC 计算规则**:
- `canonical_payload(record)` 函数:`json.dumps(record_without_hmac_field, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")`
- `hmac` 字段从 canonical 中**排除**(避免循环依赖)
- `prev_hmac` 字段**包含**(它是 chain 输入)
- `compute_hmac(key, record)` 调 `hmac.new(key, canonical_payload(record), hashlib.sha256).hexdigest()`

**Hash chain 协议**:
- 首行 `prev_hmac` 固定 `"0" * 64`(64 个 0)
- 第 N 行(N >= 2)`prev_hmac` 等于第 N-1 行的 `hmac` 字段值
- 任何修改 / 删除 / reorder 必然 break chain(后续行 prev_hmac 不匹配新"上一行" hmac)

**Append 流程**(`cmd_append` 升级):
1. 加载或初始化 key (`load_or_init_key()`)
2. 读 ledger 末尾行的 hmac(若 ledger 不存在或为空 → 用 `"0" * 64`)
3. 构建 record(11 字段全填,`hmac` 字段先留空)
4. 算 `hmac = compute_hmac(key, record)`,填入 record
5. 写一行(json.dumps 同 canonical 规则,逐行 append)

#### Scenario: 首行 prev_hmac 全 0

- **WHEN** ledger 文件不存在 + wrapper append 第一行
- **THEN** record 含 `prev_hmac: "0000000000000000000000000000000000000000000000000000000000000000"`(64 chars)
- **AND** record 的 hmac 字段 = `compute_hmac(key, record_with_prev_hmac_zeros)`

#### Scenario: 后续行 prev_hmac 链接上一行 hmac

- **WHEN** ledger 已有 N 行 + wrapper append 第 (N+1) 行
- **THEN** 新行 `prev_hmac` 等于第 N 行的 `hmac` 值(64 hex chars)
- **AND** 新行 `hmac = compute_hmac(key, new_record_with_prev_hmac_chained)`

#### Scenario: hmac 字段从 canonical 排除

- **WHEN** wrapper 计算 `canonical_payload(record)` 用于 HMAC 输入
- **THEN** canonical bytes 不含 `hmac` 字段(避免循环依赖)
- **AND** canonical bytes 含 `prev_hmac` 字段(它是 chain 输入)

#### Scenario: canonical JSON 字段顺序无关

- **WHEN** 同一 record 字段以不同写入顺序构造(insertion order 1 vs insertion order 2)
- **THEN** `canonical_payload(record)` 返回完全相同的 bytes(`sort_keys=True` 保证)
- **AND** `compute_hmac` 输出 hex 也相同

#### Scenario: wrapper_version 升到 "2.0"

- **WHEN** v3 wrapper append 一行
- **THEN** record 含 `wrapper_version: "2.0"`(常量,不可配置)
- **AND** archived v2 ledger 行(`wrapper_version: "1.0"`)在 v2 fence 路径下仍合法(fence 不强制具体值,仅校非空)

### Requirement: v3 fence dispatch matrix and HMAC chain verification

`forgeue_finish_gate.py::_check_dispatch_ledger` SHALL 加入 v3 dispatch 分支,fence dispatch matrix 扩到 4 档:

| evidence frontmatter `runtime_enforcement_protocol_version` | fence 行为 |
|---|---|
| 无字段(legacy) | 全 v1/v2/v3 fence pass-through |
| `v1` | 走 v1 fence(沿 ADR-011) |
| `v2` | 走 v1 + v2 fence(advisory schema-only,沿 ADR-012) |
| `v3` | 走 v1 + v2 + v3 fence(v3 = v2 schema check + HMAC chain verify + terminal proof + audit consistency + strict 11-field schema) |
| 其他 present value(`v4` / typo / empty / null)| **BLOCKER `unknown_protocol_version`**(沿 D-RuntimeEnforcementProtocolVersionValidity 沿 round 2 codex F2 inline writeback;**fence skip 必须由 absence 决定,不能由 invalid value 决定**) |

**新 helper**:`_runtime_enforcement_v3_active(frontmatter) -> bool`,检测 `frontmatter.get("runtime_enforcement_protocol_version") == "v3"`。

**新 helper**(round 2 codex F2 inline writeback):`_VALID_PROTOCOL_VERSIONS = frozenset({"v1", "v2", "v3"})` 模块常量;新 fence `_check_runtime_enforcement_protocol_version_validity` 在所有 protocol-version-dependent fence 之前跑(防 unknown value 走 skip 路径)。

**v3 verify 流程**(`_forgeue_ledger_crypto.verify_chain_v3(key_bytes, lines, evidence_frontmatter)`):
1. 解析 ledger 全行为 list of dict
2. 检查 ledger 内所有行 `key_id` 一致(沿"同 ledger 同 key" invariant)
3. 检查 ledger 内 key_id vs 当前文件 key_id(**round 1 codex F2 inline writeback,key_rotation 默认 fail-closed**):
   - **active v3 evidence**(`evidence_frontmatter.get("ledger_archived_replay") != True`):key_id 不一致 → `key_id_mismatch` BLOCKER(攻击场景:LLM 替换 key 文件即可降级 HMAC 校 — 必须 fail-closed)
   - **archived replay 模式**(`evidence_frontmatter.ledger_archived_replay: true` opt-in):key_id 不一致 → `key_rotation_user_override_required` 走 user explicit override 路径(audit 友好,user 显式承担"无法重算 HMAC"风险)
4. 从首行起整链 verify(仅在 key_id 与当前 file 一致时跑;archived replay 模式 skip 此步)`:
   - 首行 `prev_hmac` 必须 `"0" * 64`
   - 每行 `hmac == compute_hmac(key, record)`(canonical 重算)
   - 每行 `prev_hmac == 上一行 hmac`(chain 连续)
5. 检查 ledger terminal proof(沿 round 1 codex F3 inline writeback,新加;`evidence_frontmatter.ledger_line_count` + `ledger_final_hmac` 字段必填 v3 evidence;cross-check 与实际 ledger 一致)— 见独立 Requirement "v3 ledger terminal proof"

**verify 状态枚举 + 处理**(round 1 codex F2 inline writeback 后):

| 状态 | 触发 | 等级 | exit code |
|---|---|---|---|
| `ok` | 全链 HMAC 正确 + key_id 一致 + terminal proof 一致 | pass | 0 |
| `hmac_mismatch` | 某行 HMAC 重算 ≠ 写入值 | BLOCKER | 5 |
| `chain_break` | 某行 prev_hmac ≠ 上一行 hmac OR 首行 prev_hmac ≠ all-zeros | BLOCKER | 5 |
| `key_id_inconsistent` | 同一 ledger 内不同行 key_id 不一致 | BLOCKER | 5 |
| `key_id_mismatch` | active v3 evidence + ledger key_id ≠ 当前 file key_id | BLOCKER | 5 |
| `tail_truncation_detected` | evidence `ledger_line_count` ≠ 实际 ledger 行数 | BLOCKER | 5 |
| `final_hmac_mismatch` | evidence `ledger_final_hmac` ≠ 实际 ledger 最后一行 hmac | BLOCKER | 5 |
| `schema_violation` | ledger 行 strict schema 违反(沿 F5 scope expansion;字段集 / 字段类型 / 字段 format) | BLOCKER | 5 |
| `frontmatter_audit_inconsistency` | evidence frontmatter `ledger_forgery_resistance` 与 `runtime_enforcement_protocol_version` 不一致 | BLOCKER | 5 |
| `key_rotation_user_override_required` | archived replay 模式 + ledger key_id ≠ 当前 file key_id | user override(WARN 输出,exit 6) | 6 |
| `key_file_corrupted` | key 文件 JSON 损坏 / key_hex 长度错 / version 不识别 | wrapper abort | 7 |

**关键 invariants**(round 1 codex inline writeback 后):
- v3 fence 仅 inspect ledger + evidence frontmatter,**不**修改 ledger 内容
- v3 fence 走 fail-closed — verify 失败时 finish_gate exit 非 0(BLOCKER 级别)
- **key_id mismatch 默认 BLOCKER**(round 1 codex F2 inline writeback;不再 WARN 自动 pass);archived replay 兼容走 evidence frontmatter `ledger_archived_replay: true` explicit user opt-in 路径(exit 6 仅在此路径触发,user 显式承担风险)
- evidence frontmatter `ledger_line_count` + `ledger_final_hmac` 是 v3 必填(F3 inline writeback);缺失或与实际不一致 → BLOCKER
- ledger 行 strict 11-field schema(F5 scope expansion):字段集精确 + 字段类型 strict + 字段 format 正则校

#### Scenario: v3 evidence + 合法 v3 ledger 整链 verify 通过

- **WHEN** evidence frontmatter `runtime_enforcement_protocol_version: v3` + ledger 含 N 行 v3 schema 合法行(chain 连续 + key_id 一致 + HMAC 正确)
- **THEN** `_check_dispatch_ledger` v3 fence pass + 无 Blocker

#### Scenario: hand-edit 某行字段触发 hmac_mismatch BLOCKER

- **WHEN** v3 ledger 任意一行的 `agent_id` / `dispatched_at` / 其他原 7 字段 / `protocol_version` / `key_id` / `prev_hmac` 被 hand-edit 修改
- **THEN** `verify_chain_v3` 重算 HMAC ≠ 行内 hmac 字段
- **AND** fence exit 非 0,Blocker.type `dispatch_ledger_violation`,error message prefix `[hmac_mismatch] line <N>`

#### Scenario: 删除中间一行触发 chain_break BLOCKER

- **WHEN** v3 ledger 第 K 行(2 ≤ K ≤ N-1)被删除
- **THEN** 第 K+1 行的 `prev_hmac` ≠ 第 K-1 行的 `hmac`(chain 断裂)
- **AND** fence exit 非 0,error message prefix `[chain_break] line <K+1>`

#### Scenario: reorder 两行触发 chain_break BLOCKER

- **WHEN** v3 ledger 第 K 行与第 K+1 行交换顺序
- **THEN** 第 K+1 行(原第 K 行)的 `prev_hmac` ≠ 上一行(原第 K+1 行)的 `hmac`
- **AND** fence exit 非 0,error message prefix `[chain_break] line <K+1>`

#### Scenario: 首行 prev_hmac 非全 0 触发 chain_break BLOCKER

- **WHEN** v3 ledger 首行 `prev_hmac` ≠ `"0" * 64`(LLM 伪造首行 hmac)
- **THEN** fence exit 非 0,error message prefix `[chain_break] line 1: first-line prev_hmac MUST be all zeros`

#### Scenario: 同 ledger 内不同 key_id 触发 key_id_inconsistent BLOCKER

- **WHEN** v3 ledger 内不同行 `key_id` 不一致(如 LLM 中途切换 key)
- **THEN** fence exit 非 0,error message prefix `[key_id_inconsistent] line <N>: expected <key_id>, got <key_id>`

#### Scenario: ledger key_id ≠ 文件 key_id active v3 evidence 默认 fail-closed BLOCKER(round 1 codex F2 inline writeback)

- **WHEN** active v3 evidence(`evidence_frontmatter.ledger_archived_replay` 字段缺失或 `false` / `null`)+ ledger key_id 与当前 `~/.claude/forgeue_ledger_key` 派生的 key_id 不一致
- **THEN** fence BLOCKER(`key_id_mismatch`),error message prefix `[key_id_mismatch] ledger key_id <X> ≠ current file key_id <Y>; HMAC verify cannot proceed without rotated-from key — finish_gate fail-closed`
- **AND** **不**走 WARN 路径(攻击场景:LLM 替换 key 文件即可降级 HMAC 校 — 必须 fail-closed)
- **AND** Blocker.type `dispatch_ledger_violation`

#### Scenario: ledger key_id ≠ 文件 key_id archived replay 模式 user override(round 1 codex F2 inline writeback)

- **WHEN** evidence frontmatter `ledger_archived_replay: true`(opt-in user override;archived `enhance-workflow-automation-ledger-binding` 之前的归档 v3 evidence replay 时 user 显式标注)+ ledger key_id ≠ 当前 file key_id + ledger 自身 key_id 一致
- **THEN** fence WARN(`key_rotation_user_override_required`,exit 6 from cmd_verify;非 BLOCKER 但 audit 友好);error message prefix `[key_rotation_user_override] ledger key_id <X> ≠ current key_id <Y>; HMAC verify skipped per user opt-in — risk acknowledged`
- **AND** finish_gate 接受 archived replay,**但** evidence frontmatter `ledger_archived_replay: true` 字段 audit trail(任何回写 / archive 都保留此字段)
- **AND** `ledger_archived_replay: true` 字段需 user 显式手工添加(命令模板 default 不写入此字段;LLM 可在 controller drift 检测时 alert user 是否需要 opt-in)

#### Scenario: legacy / v1 / v2 evidence 不触 v3 fence

- **WHEN** evidence frontmatter 无 `runtime_enforcement_protocol_version` 字段 OR 值是 `v1` / `v2`
- **THEN** v3 fence 分支 pass-through(不 inspect ledger 的 v3 字段)
- **AND** archived v2 ledger 行(无 hmac 字段)在 v2 路径走 schema-only 校验,不强制 hmac 字段存在

### Requirement: ledger_forgery_resistance frontmatter field upgrade to cryptographic with strict gate

evidence frontmatter SHALL 含 `ledger_forgery_resistance` 字段(字符串字面值;沿 archived `enhance-workflow-automation-executable-enforcement` 同款字段);本字段 SHALL 与 `runtime_enforcement_protocol_version` 字段强 enum 绑定(沿 round 1 codex F4 inline writeback,审计字段必须与协议版本一致才能 audit 有意义)。

`forgeue_finish_gate.py` SHALL 含新 fence `_check_ledger_forgery_resistance_consistency`(本 change ship 加,沿 D-FrontmatterAuditConsistency)守门字段一致性:

| `runtime_enforcement_protocol_version` | `ledger_forgery_resistance` 强制值 | 不匹配处理 |
|---|---|---|
| 无字段(legacy) | 无字段约束(legacy pass-through) | — |
| `v1` | 无字段约束(v1 advisory pass-through) | — |
| `v2` | 必须 `advisory` | BLOCKER `frontmatter_audit_inconsistency` |
| `v3` | 必须 `cryptographic` | BLOCKER `frontmatter_audit_inconsistency` |

未来若加 multi-level enforcement(如 `cryptographic_strict` / `cryptographic_advisory`),扩 enum 时**同步扩 fence dispatch matrix**;不允许字段单独扩值不扩 fence(避免 audit 信号脱钩重现)。

命令模板 `change-apply-{subagent,parallel}.md` 的 evidence frontmatter 模板 SHALL 在 v3 协议路径下写 `ledger_forgery_resistance: cryptographic`;v2 路径写 `advisory`(self-dogfood gap 路径,沿 D-SelfDogfoodGap)。

#### Scenario: v3 evidence frontmatter 含 cryptographic 标注 fence pass

- **WHEN** evidence frontmatter `runtime_enforcement_protocol_version: v3` + `ledger_forgery_resistance: cryptographic`
- **THEN** `_check_ledger_forgery_resistance_consistency` fence pass

#### Scenario: v2 evidence frontmatter 含 advisory 标注 fence pass

- **WHEN** evidence frontmatter `runtime_enforcement_protocol_version: v2` + `ledger_forgery_resistance: advisory`(self-dogfood gap 路径)
- **THEN** `_check_ledger_forgery_resistance_consistency` fence pass

#### Scenario: v3 evidence 标 advisory(LLM 自降级伪造)BLOCKER

- **WHEN** evidence frontmatter `runtime_enforcement_protocol_version: v3` + `ledger_forgery_resistance: advisory`
- **THEN** `_check_ledger_forgery_resistance_consistency` fence exit 非 0
- **AND** Blocker.type `frontmatter_audit_inconsistency`,error message prefix `[audit_mismatch] v3 protocol requires ledger_forgery_resistance: cryptographic, got: advisory`

#### Scenario: v2 evidence 自称 cryptographic(LLM 虚报)BLOCKER

- **WHEN** evidence frontmatter `runtime_enforcement_protocol_version: v2` + `ledger_forgery_resistance: cryptographic`
- **THEN** `_check_ledger_forgery_resistance_consistency` fence exit 非 0
- **AND** Blocker.type `frontmatter_audit_inconsistency`,error message prefix `[audit_mismatch] v2 protocol requires ledger_forgery_resistance: advisory, got: cryptographic`

#### Scenario: legacy / v1 evidence 不强制字段(pass-through)

- **WHEN** evidence frontmatter 无 `runtime_enforcement_protocol_version` 字段 OR 值为 `v1`
- **THEN** `_check_ledger_forgery_resistance_consistency` fence pass-through(advisory pass)

### Requirement: v3 ledger terminal proof (line_count + final_hmac frontmatter audit)

evidence frontmatter SHALL 含 v3 必填字段(沿 round 1 codex F3 inline writeback;hash chain 抓不住 tail truncation 的 mitigation):

- `ledger_line_count: <int>`(声明 ledger 行数;**LLM 复制 wrapper `cmd_append` stdout 提示的行数**;wrapper-side 不自动写入 evidence;fence 校验与实际 ledger 行数一致)
- `ledger_final_hmac: <64 hex chars>`(声明 ledger 最后一行 hmac 值;**LLM 复制 wrapper `cmd_append` stdout 提示的 hmac**;fence 校验与实际 ledger 最后一行 hmac 一致)

`tools/forgeue_dispatch_ledger.py::cmd_append` SHALL 在每次成功 append 后 stdout 打印 `[LEDGER] line_count=<N> final_hmac=<hex>`(LLM 可读取此输出复制到 evidence frontmatter)。

`forgeue_finish_gate.py` SHALL 含新 fence `_check_ledger_terminal_proof`(本 change ship 加;沿 D-LedgerTerminalProof D-decision):

- v3 evidence(`runtime_enforcement_protocol_version: v3`)缺 `ledger_line_count` 字段 → BLOCKER `tail_truncation_undeclared`
- v3 evidence 缺 `ledger_final_hmac` 字段 → BLOCKER `final_hmac_undeclared`
- evidence `ledger_line_count` 不是正整数 → BLOCKER `tail_truncation_undeclared`(format check)
- evidence `ledger_final_hmac` 不是 `^[a-f0-9]{64}$` → BLOCKER `final_hmac_undeclared`(format check)
- evidence `ledger_line_count` ≠ 实际 ledger 非空行数 → BLOCKER `tail_truncation_detected`
- evidence `ledger_final_hmac` ≠ 实际 ledger 最后一行 hmac → BLOCKER `final_hmac_mismatch`
- v2 evidence 不强制本字段(pass-through)
- legacy / v1 evidence 不强制本字段(pass-through)

**Threat model 边界**(沿 design.md threat model 段):本 fence 抓 **常见 sloppy bypass**(LLM 删除尾部不更新 evidence frontmatter)+ **wrapper 跑过的 happy path**(LLM 不能伪造 wrapper stdout)。但 **不**承担 willful forge — LLM 可同时 forge ledger + 重写 evidence frontmatter line_count + final_hmac;那是 `enhance-workflow-automation-os-keystore` follow-on 的 threat model。

#### Scenario: v3 evidence 缺 ledger_line_count 字段 BLOCKER

- **WHEN** evidence frontmatter `runtime_enforcement_protocol_version: v3` + 缺 `ledger_line_count` 字段
- **THEN** `_check_ledger_terminal_proof` fence exit 非 0
- **AND** Blocker.type `dispatch_ledger_violation`,error message prefix `[tail_truncation_undeclared] v3 evidence MUST carry ledger_line_count field`

#### Scenario: v3 evidence 缺 ledger_final_hmac 字段 BLOCKER

- **WHEN** evidence frontmatter `runtime_enforcement_protocol_version: v3` + 缺 `ledger_final_hmac` 字段
- **THEN** `_check_ledger_terminal_proof` fence exit 非 0,error message prefix `[final_hmac_undeclared]`

#### Scenario: v3 evidence ledger_line_count 不匹配实际行数 BLOCKER(tail truncation 抓)

- **WHEN** v3 evidence `ledger_line_count: 5` 但实际 ledger 4 行(LLM 删了最后 1 行未更新 evidence)
- **THEN** `_check_ledger_terminal_proof` fence exit 非 0,error message prefix `[tail_truncation_detected] declared 5 lines, actual 4 lines`

#### Scenario: v3 evidence ledger_final_hmac 不匹配实际末行 BLOCKER

- **WHEN** v3 evidence `ledger_final_hmac: <X>` 但实际 ledger 最后一行 hmac = `<Y>`(LLM 删行后 evidence 字段未跟改 OR forge 攻击)
- **THEN** `_check_ledger_terminal_proof` fence exit 非 0,error message prefix `[final_hmac_mismatch] declared <X>, actual <Y>`

#### Scenario: v3 evidence terminal proof 全对 + chain verify 全对 fence pass

- **WHEN** v3 evidence + ledger N 行 chain 合法 + evidence `ledger_line_count: N` + `ledger_final_hmac` 等于实际末行 hmac
- **THEN** `_check_ledger_terminal_proof` fence pass + `_check_dispatch_ledger` v3 fence pass

#### Scenario: 单行 ledger v3 evidence 必含 line_count: 1

- **WHEN** v3 evidence + ledger 仅 1 行(prev_hmac 全 0)
- **THEN** evidence frontmatter MUST 含 `ledger_line_count: 1`(否则 BLOCKER tail_truncation_undeclared)
- **AND** evidence frontmatter MUST 含 `ledger_final_hmac` 等于该唯一行的 hmac(否则 BLOCKER final_hmac_mismatch)

### Requirement: v3 ledger strict 11-field schema validation

`tools/forgeue_dispatch_ledger.py::cmd_verify` v3 路径 + `forgeue_finish_gate.py::_check_dispatch_ledger` v3 分支 SHALL 在 HMAC chain verify 之外加 strict schema validation(沿 round 1 codex F5 scope expansion;HMAC 仅保护字节完整性,schema 校验是 orthogonal 必需层;本 change 合并 archived `executable-enforcement` P12.8 follow-on `enhance-workflow-automation-v2-fence-hardening` 的 schema 部分,P12.8 follow-on superseded)。

**v3 ledger 行 strict schema(11 字段精确)**:

| 字段 | 类型 | format / 约束 | 缺失行为 |
|---|---|---|---|
| `agent_id` | str | `^[a-f0-9]{17,}$`(沿 archived 同款 hex format,长度 ≥ 17) | BLOCKER `schema_violation` |
| `round` | int | 正整数(`isinstance(round, int) and round > 0 and not isinstance(round, bool)`,显式拒 bool;Python `bool` 是 `int` 子类) | BLOCKER |
| `role` | str | `VALID_ROLES` enum(沿 forgeue_dispatch_ledger 现有 frozenset:`implementer` / `spec_reviewer` / `code_quality_reviewer` / `final_reviewer` / `implementer_round_2_fix` / `spec_reviewer_round_2_review`) | BLOCKER |
| `task_subject_hash` | str / null | `null` 或 `^sha256:[a-f0-9]{64}$` | BLOCKER 若类型不对 |
| `dispatched_at` | str | ISO8601 tz-aware(`datetime.fromisoformat(...)` parse-able + `tzinfo is not None`) | BLOCKER |
| `parent_session_id` | str / null | `null` 或 UUID v4 format(`^[a-f0-9-]{36}$`) | BLOCKER 若类型不对 |
| `wrapper_version` | str | `^\d+\.\d+$`(major.minor) | BLOCKER |
| `protocol_version` | str | 精确 `"v3"` | BLOCKER |
| `key_id` | str | `^[a-f0-9]{16}$`(64-bit fingerprint) | BLOCKER |
| `prev_hmac` | str | `^[a-f0-9]{64}$` | BLOCKER |
| `hmac` | str | `^[a-f0-9]{64}$` | BLOCKER |

**严格性约束**:
- ledger 行字段集 **精确 11 字段**(任何 unknown 字段 → BLOCKER `schema_violation`,error prefix `[schema_violation] unknown field <field_name>`)
- 任何字段缺失 → BLOCKER `schema_violation`,error prefix `[schema_violation] missing field <field_name>`
- 字段类型 strict(`type(value) is <expected>`;不接受隐式转换 / 子类如 bool→int)
- 字段 format 正则严格匹配(全字符串)

**v2 ledger 行 schema validation**(沿现有 v2 fence advisory,本 change **不**加 v2 schema strict — 留给 cancelled P12.8 之外的独立 follow-on 若需要;沿 D-Scope-F3-MergeWithP12.8 边界本 change 仅做 v3 schema strict)。

#### Scenario: v3 ledger 行字段集精确 11 字段

- **WHEN** v3 ledger 行字段集恰好 11 字段(无多无少)+ 每字段类型 + format 正确
- **THEN** `_check_dispatch_ledger` v3 schema check pass

#### Scenario: v3 ledger 行未知字段 BLOCKER

- **WHEN** v3 ledger 行含 12 字段(11 标准 + `extra_field_xyz`)
- **THEN** fence exit 非 0,error prefix `[schema_violation] unknown field 'extra_field_xyz' at line <N>`

#### Scenario: v3 ledger 行字段缺失 BLOCKER

- **WHEN** v3 ledger 行缺 `key_id` 字段(其他 10 字段都在)
- **THEN** fence exit 非 0,error prefix `[schema_violation] missing field 'key_id' at line <N>`

#### Scenario: v3 ledger 行 round 为负数 BLOCKER

- **WHEN** v3 ledger 行 `round: -1`
- **THEN** fence exit 非 0,error prefix `[schema_violation] field 'round' MUST be positive integer, got: -1`

#### Scenario: v3 ledger 行 round 为 bool BLOCKER

- **WHEN** v3 ledger 行 `round: true`(JSON true 序列化为 Python bool;Python bool 是 int 子类但 schema 应显式拒)
- **THEN** fence exit 非 0,error prefix `[schema_violation] field 'round' MUST be positive integer (not bool), got: True`

#### Scenario: v3 ledger 行 round 为 float BLOCKER

- **WHEN** v3 ledger 行 `round: 1.0`
- **THEN** fence exit 非 0,error prefix `[schema_violation] field 'round' MUST be int, got: float`

#### Scenario: v3 ledger 行 agent_id 格式不对 BLOCKER

- **WHEN** v3 ledger 行 `agent_id: "not-a-hex"` OR `agent_id: ""`
- **THEN** fence exit 非 0,error prefix `[schema_violation] field 'agent_id' MUST match ^[a-f0-9]{17,}$`

#### Scenario: v3 ledger 行 role 不在 enum BLOCKER

- **WHEN** v3 ledger 行 `role: "unknown_role"`
- **THEN** fence exit 非 0,error prefix `[schema_violation] field 'role' MUST be in VALID_ROLES`

#### Scenario: v3 ledger 行 dispatched_at 无 tzinfo BLOCKER

- **WHEN** v3 ledger 行 `dispatched_at: "2026-05-06T14:00:00"`(无 timezone offset)
- **THEN** fence exit 非 0,error prefix `[schema_violation] field 'dispatched_at' MUST be ISO8601 tz-aware`

#### Scenario: v3 ledger 行 protocol_version 不是 "v3" BLOCKER

- **WHEN** v3 ledger 行 `protocol_version: "v2"` OR 任何其他值
- **THEN** fence exit 非 0,error prefix `[schema_violation] field 'protocol_version' MUST be exactly "v3"`

### Requirement: Runtime enforcement protocol_version validity gate

`forgeue_finish_gate.py` SHALL 含新 fence `_check_runtime_enforcement_protocol_version_validity`(本 change ship 加;沿 round 2 codex F2 inline writeback + D-RuntimeEnforcementProtocolVersionValidity)守门 evidence frontmatter `runtime_enforcement_protocol_version` 字段值合法性;此 fence SHALL 在所有 protocol-version-dependent fence 之前跑(`_check_dispatch_ledger` / `_check_round_fix_continuity` / `_check_skill_cascade` / `_check_ledger_terminal_proof` / `_check_ledger_forgery_resistance_consistency` / `_check_archived_replay_path_boundary`)以防 unknown value 走 skip 路径。

**核心 invariant**:fence skip 必须由 absence 决定(legacy pass-through),**不能**由 invalid value 决定(LLM 写错值不应该意外 unlock fence skip)。

**字段值合法性 dispatch**:

| evidence frontmatter `runtime_enforcement_protocol_version` | fence 行为 |
|---|---|
| 字段缺失(legacy) | pass-through(全 v1/v2/v3 fence skip) |
| 字段值 `v1` / `v2` / `v3`(in `_VALID_PROTOCOL_VERSIONS = frozenset({"v1", "v2", "v3"})`) | 走对应 fence dispatch matrix |
| 字段值 present 但不在 frozenset 内(`v4` / typo / empty / null) | **BLOCKER `unknown_protocol_version`** |

`_VALID_PROTOCOL_VERSIONS` SHALL 在 `tools/forgeue_finish_gate.py` / `tools/forgeue_change_state.py` / docs(`CLAUDE.md` + `forgeue_integrated_ai_workflow.md`)中保持一致;扩 frozenset 时同步扩 docs(沿 `forgeue_enum_cross_ref_check.py` 协议)。

#### Scenario: legacy evidence 无字段 pass-through

- **WHEN** evidence frontmatter 无 `runtime_enforcement_protocol_version` 字段
- **THEN** `_check_runtime_enforcement_protocol_version_validity` fence pass(legacy pass-through)
- **AND** 后续 protocol-version-dependent fence 全 skip(legacy 兼容)

#### Scenario: v1 / v2 / v3 evidence 走对应 fence dispatch

- **WHEN** evidence frontmatter `runtime_enforcement_protocol_version: v1` OR `v2` OR `v3`
- **THEN** `_check_runtime_enforcement_protocol_version_validity` fence pass
- **AND** 后续 fence 走对应 dispatch 路径

#### Scenario: unknown protocol_version v4 BLOCKER(round 2 codex F2 inline writeback)

- **WHEN** evidence frontmatter `runtime_enforcement_protocol_version: v4`
- **THEN** `_check_runtime_enforcement_protocol_version_validity` fence exit 非 0
- **AND** Blocker.type `dispatch_ledger_violation`,error message prefix `[unknown_protocol_version] runtime_enforcement_protocol_version='v4' not in valid set {v1, v2, v3}; fence skip MUST come from absence not invalid value`

#### Scenario: typo protocol_version `v 3` BLOCKER

- **WHEN** evidence frontmatter `runtime_enforcement_protocol_version: 'v 3'`(空格 typo)OR `'v3 '`(尾空格)OR `'V3'`(大小写不一致)
- **THEN** fence exit 非 0,error prefix `[unknown_protocol_version]`(LLM typo 不能 silent skip fence)

#### Scenario: empty / null protocol_version BLOCKER

- **WHEN** evidence frontmatter `runtime_enforcement_protocol_version: ''` OR `runtime_enforcement_protocol_version: null`
- **THEN** fence exit 非 0,error prefix `[unknown_protocol_version]`(present 但空值不等于 absent;absent 是字段完全不在 frontmatter 中)
- **NOTE**:absent(字段完全不在 frontmatter)走 legacy pass-through;present-but-empty 走 BLOCKER

### Requirement: Archived replay path boundary

`forgeue_finish_gate.py` SHALL 含新 fence `_check_archived_replay_path_boundary`(本 change ship 加;沿 round 2 codex F1 inline writeback + D-ArchivedReplayPathBoundary)守门 `ledger_archived_replay` evidence frontmatter 字段使用边界。

**字段使用规则**:

| evidence 文件路径 | `ledger_archived_replay` 字段值 | fence 行为 |
|---|---|---|
| 任何路径 | 缺失 / `false` / `null` | pass-through(default 路径) |
| 含 `openspec/changes/archive/` segment(`Path.resolve()` 后) | `true` | 接受 archived replay opt-in;走 D-KeyRotationHandling user override 路径(WARN exit 6) |
| 不含 `archive/` segment(active change `openspec/changes/<id>/`) | `true` | **BLOCKER `archived_replay_path_violation`**(LLM 在 active change forge 此字段企图绕 fail-closed) |

`tools/forgeue_dispatch_ledger.py::cmd_verify` `--allow-archived-replay` flag 同款边界 — 仅在 ledger 路径在 `openspec/changes/archive/` 内才 honor flag;active change ledger 路径 + flag → BLOCKER + 提示 ledger 不在 archive 路径。

`tools/forgeue_change_state.py --writeback-check` SHALL 同步加此 invariant 检测(active change evidence 出现 `ledger_archived_replay: true` = drift signal,作为 4 类 named DRIFT 之一)。

**核心 invariant**:archived replay 路径不仅要 user explicit opt-in(双 flag),还要 evidence 物理位置在 archive/ 目录(物证驱动);LLM 即使 forge frontmatter + 替换 key 文件,只要 evidence 不在 archive/ 段,fence BLOCKER。

#### Scenario: active change evidence + ledger_archived_replay: true BLOCKER(round 2 codex F1 inline writeback)

- **WHEN** evidence 文件路径 `openspec/changes/<id>/review/foo.md`(active change,不在 archive/)+ frontmatter `ledger_archived_replay: true`
- **THEN** `_check_archived_replay_path_boundary` fence exit 非 0
- **AND** Blocker.type `dispatch_ledger_violation`,error message prefix `[archived_replay_path_violation] evidence path '<path>' does not contain 'archive/' segment but ledger_archived_replay=true; archived replay opt-in only allowed for archived evidence`

#### Scenario: archive evidence + ledger_archived_replay: true 走 user override(allowed)

- **WHEN** evidence 文件路径 `openspec/changes/archive/2026-MM-DD-<id>/review/foo.md`(archived)+ frontmatter `ledger_archived_replay: true` + cmd_verify 配套 `--allow-archived-replay` flag + ledger key_id ≠ 当前 file key_id
- **THEN** `_check_archived_replay_path_boundary` fence pass(在 archive/ 路径,字段允许)
- **AND** 后续 v3 verify 走 D-KeyRotationHandling user override 路径(WARN exit 6)

#### Scenario: archive evidence + ledger_archived_replay: true 但缺 cmd_verify flag

- **WHEN** evidence 在 archive/ 路径 + frontmatter `ledger_archived_replay: true` + cmd_verify 缺 `--allow-archived-replay` flag
- **THEN** `_check_archived_replay_path_boundary` fence pass(字段允许),但 cmd_verify v3 verify 走 default 路径
- **AND** key_id mismatch → BLOCKER(default fail-closed,沿 D-KeyRotationHandling default 路径)
- **AND** 仅在 user 显式加 flag + frontmatter 字段 + archive/ 路径**三重 explicit opt-in** 时才走 user override

#### Scenario: cmd_verify --allow-archived-replay flag + ledger 不在 archive/ 路径 BLOCKER

- **WHEN** ledger 路径 `openspec/changes/<active-id>/dispatch_ledger.jsonl`(active)+ cmd_verify `--allow-archived-replay` flag
- **THEN** cmd_verify exit 5(`archived_replay_path_violation`),stderr 提示 ledger 不在 archive/ 路径,`--allow-archived-replay` flag rejected

#### Scenario: forgeue_change_state.py --writeback-check 检测 active change evidence 误用

- **WHEN** 跑 `python tools/forgeue_change_state.py --change <active-id> --writeback-check --json` + active change evidence 含 `ledger_archived_replay: true`
- **THEN** writeback-check exit 5 + 4 类 named DRIFT 之一标记
- **AND** alert user 字段使用错误,提示移除字段或 archive change 后再标

## MODIFIED Requirements

### Requirement: Dispatch ledger append-only contract

ForgeUE SHALL 提供 stdlib-only 工具 `tools/forgeue_dispatch_ledger.py`,提供子命令:
- `append --change <id> --agent-id <id> --round <N> --role <role> [--task-subject-hash <sha256>]`:向 `<change>/dispatch_ledger.jsonl` append 一行 JSON
- `verify --change <id>`:校验 ledger JSONL 每行 well-formed + timestamp 单调递增 + wrapper_version 字段非空 + (v3 协议)HMAC chain 整链 verify

`<change>/dispatch_ledger.jsonl` SHALL 是 append-only 文件,每行一个 JSON 记录。schema 沿 `runtime_enforcement_protocol_version` 字段分两档:

**v2 schema(7 字段;archived `executable-enforcement` ship)**:`agent_id` / `round`(int)/ `role` / `task_subject_hash`(可空)/ `dispatched_at`(ISO8601)/ `parent_session_id`(可空)/ `wrapper_version`。

**v3 schema(11 字段;本 change ship)**:v2 7 字段 + `protocol_version: "v3"` / `key_id`(SHA256(key)[:16] fingerprint)/ `prev_hmac`(64 hex chars,首行全 0)/ `hmac`(HMAC-SHA256 over canonical JSON)。

`tools/forgeue_dispatch_ledger.py` SHALL 在 `cmd_append` 中按当前 wrapper 版本(`WRAPPER_VERSION`)决定写哪档 schema:
- v2 wrapper(`WRAPPER_VERSION = "1.0"`):写 7 字段
- v3 wrapper(`WRAPPER_VERSION = "2.0"`,本 change ship):写 11 字段(含 HMAC chain)

`cmd_verify` SHALL 沿 ledger 行的 `protocol_version` 字段 dispatch:
- 行内无 `protocol_version` 字段(v2 ledger):走 schema-only 校验(timestamp 单调 + wrapper_version 非空 + JSON well-formed)
- 行内 `protocol_version: "v3"`:走 schema-only + HMAC chain 整链 verify

`cmd_verify` exit code(round 1 codex F2 inline writeback 后):
- 0:校验通过
- 5:`verify_fail`(任何 schema / HMAC / chain / terminal proof / frontmatter audit 错误,BLOCKER)— 含 `hmac_mismatch` / `chain_break` / `key_id_inconsistent` / `key_id_mismatch`(active v3,默认 fail-closed)/ `tail_truncation_detected` / `final_hmac_mismatch` / `schema_violation` / `frontmatter_audit_inconsistency`
- 6:`key_rotation_user_override_required`(仅在 evidence frontmatter `ledger_archived_replay: true` opt-in 时触发;user 显式承担"无法重算 HMAC"风险;archived ledger replay 兼容路径)
- 7:`key_file_corrupted`

命令模板 `/forgeue:change-apply-{subagent,parallel}` SHALL 在每次 Skill(Task) / Skill(SendMessage) 调用**之后**(post-dispatch capture 真实 agent_id)wrapper append(沿 archived `enhance-workflow-automation-executable-enforcement` F2 round 1 inline writeback 协议 — pre-dispatch 写入 synthetic agent_id 与真实 agent_id 无关,本 change F3-only scope 不 reopen F2)。命令模板**不暴露** ledger 文件路径给 LLM Read / Write / Edit tool(沿 D-DispatchWrapperBoundary 防 LLM 篡改);**不暴露** key 文件路径给 LLM(沿 D-KeyLocation,key 文件在 LLM 不主动 read 的 `~/.claude/` 用户目录)。

evidence frontmatter `pre_dispatch_metadata: advisory` 标注沿 archived 同款保留(post-dispatch capture 模型的 advisory 限制说明:agent_id 在 dispatch 后 capture,F3 cryptographic enforcement 不解决"LLM 在 post-dispatch 后伪造 agent_id"威胁,本边界留 follow-on `enhance-workflow-automation-skill-tool-binding`)。

evidence frontmatter SHALL 含 `dispatch_ledger_path` 字段,值固定为 `dispatch_ledger.jsonl`(相对 `<change>/`)。

#### Scenario: wrapper append 写一行 JSONL(v2 路径,archived 兼容)

- **WHEN** wrapper version `1.0` + 跑 `python tools/forgeue_dispatch_ledger.py append --change <id> --agent-id ad79e93a40414763e --round 1 --role implementer --task-subject-hash sha256:abc...`
- **THEN** 文件 `<change>/dispatch_ledger.jsonl` 末尾 append 一行 JSON
- **AND** JSON 含 7 字段 v2 schema(无 `protocol_version` / `key_id` / `prev_hmac` / `hmac`)

#### Scenario: wrapper append 写一行 JSONL(v3 路径,本 change ship)

- **WHEN** wrapper version `2.0`(本 change ship 后)+ 跑 append
- **THEN** 文件末尾 append 一行 11 字段 v3 schema JSON
- **AND** JSON 含 `protocol_version: "v3"` / `key_id` / `prev_hmac`(首行全 0,后续行链接前一行 hmac)/ `hmac`(HMAC-SHA256 over canonical)

#### Scenario: ledger timestamp 单调性 verify

- **WHEN** 跑 `python tools/forgeue_dispatch_ledger.py verify --change <id>`
- **THEN** 工具校验所有行 `dispatched_at` 字段单调递增
- **AND** 任意行 timestamp 倒流 → exit 5 + 错误指明行号

#### Scenario: ledger 缺失 finish_gate 阻断

- **WHEN** evidence frontmatter `runtime_enforcement_protocol_version: v2` 或 `v3` + `dispatch_ledger_path: dispatch_ledger.jsonl` + `subagent_continuity` 字段 declared dispatch 但实际 `<change>/dispatch_ledger.jsonl` 文件不存在
- **THEN** `forgeue_finish_gate.py::_check_dispatch_ledger` v2/v3 fence exit 非 0
- **AND** 错误信息指明缺失的 ledger 文件

#### Scenario: ledger agent_id 集合 与 evidence subagent_continuity 不一致 finish_gate 阻断

- **WHEN** evidence frontmatter `subagent_continuity.round_1_implementer_id: ad79e93a40414763e` 但 ledger 中**无**此 agent_id 行
- **THEN** `_check_dispatch_ledger` fence exit 非 0
- **AND** 错误信息指明 evidence agent_id 不在 ledger 中

#### Scenario: ledger wrapper_version 字段缺失 finish_gate 阻断

- **WHEN** ledger JSONL 任意行缺 `wrapper_version` 字段(可能 LLM 手工伪造行)
- **THEN** `_check_dispatch_ledger` fence exit 非 0

#### Scenario: v3 ledger 行 hmac 字段缺失 finish_gate 阻断(v3 路径)

- **WHEN** evidence v3 + ledger 行 `protocol_version: "v3"` 但缺 `hmac` 字段
- **THEN** `_check_dispatch_ledger` v3 fence exit 非 0,error message prefix `[hmac_mismatch] line <N>: hmac field missing`

#### Scenario: cmd_verify active v3 默认 key_id mismatch BLOCKER(round 1 codex F2 inline writeback)

- **WHEN** 跑 `python tools/forgeue_dispatch_ledger.py verify --change <id>` + ledger 是 v3 + ledger 内 key_id 与当前 file key_id 不一致 + 命令未指定 `--allow-archived-replay` flag
- **THEN** verify exit 5(`key_id_mismatch`,BLOCKER)
- **AND** stderr 打印 `[ERROR] ledger key_id <X> ≠ current key_id <Y>; HMAC verify cannot proceed; if this is archived replay, set evidence_frontmatter ledger_archived_replay: true OR pass --allow-archived-replay flag`

#### Scenario: cmd_verify archived replay user override 路径 exit 6(round 1 codex F2 inline writeback)

- **WHEN** 跑 `python tools/forgeue_dispatch_ledger.py verify --change <id> --allow-archived-replay` + ledger 是 v3 + ledger 内 key_id 与当前 file key_id 不一致
- **THEN** verify exit 6(`key_rotation_user_override_required`,user opt-in WARN)
- **AND** stderr 打印 `[WARN] ledger key_id <X> ≠ current key_id <Y>; HMAC verify skipped per --allow-archived-replay flag; archived ledger replay accepted`
- **AND** finish_gate 接受 user override 路径(evidence frontmatter `ledger_archived_replay: true` 配套必须;否则 finish_gate 自身不接受 cmd_verify exit 6)

#### Scenario: cmd_verify exit code 7 区分 key_file_corrupted

- **WHEN** 跑 `python tools/forgeue_dispatch_ledger.py verify --change <id>` + key 文件存在但 JSON parse 失败 / key_hex 长度错
- **THEN** verify exit 7(`key_file_corrupted`)
- **AND** stderr 打印 `[ERROR] key file corrupted at <path>: <reason>; backup + remove file to re-init`

### Requirement: Round 2+ fix subagent continuity

`subagent-driven-development` 协议中,round 1 reviewer 找问题后 round 2 fix MUST 通过 `SendMessage` 给 same implementer subagent;round 2 reviewer re-review MUST 给 same reviewer subagent。

evidence frontmatter MUST 含 `subagent_continuity` 字段(对象):

```yaml
subagent_continuity:
  round_1_implementer_id: <agent-id>
  round_2_fix_implementer_id: <agent-id>  # MUST same as round_1
  round_1_reviewer_id: <agent-id>
  round_2_review_reviewer_id: <agent-id>  # MUST same as round_1_reviewer
```

`forgeue_finish_gate.py` SHALL 含 `_check_round_fix_continuity` fence 守门 round 1 / round 2 agent ID 一致性。

**v2 升级**(archived `enhance-workflow-automation-executable-enforcement`):`_check_round_fix_continuity` v2 fence 升级为 ledger cross-check — 校验 evidence frontmatter `subagent_continuity` 中所有 agent_id 都在 `<change>/dispatch_ledger.jsonl` 中**有真实记录**(沿 D-DispatchWrapperBoundary 防 LLM 伪造 agent_id);ledger 缺失 → fail-closed。v1 evidence(无 `dispatch_ledger_path` 字段)沿 v1 fence 行为(仅校验 frontmatter 字段 round_1 == round_2 字符串相等)。

**v3 升级**(本 change `enhance-workflow-automation-ledger-binding`):`_check_round_fix_continuity` v3 fence 在 v2 cross-check 基础上加 HMAC chain 整链 verify — 校验 ledger 全行 `_forgeue_ledger_crypto.verify_chain_v3(key_bytes, lines)` 整链通过(任何 hand-edit / 删除 / reorder → break chain → fence exit 非 0);v2 evidence(`runtime_enforcement_protocol_version: v2`)仍走 v2 schema-only 路径,不触 v3 chain verify。

**ADR-013 update**:本 change 调整 default cwd 为 main repo(沿 D-AllChangeApplyMainRepoDefault),W3 dispatch ledger 仍 active(与 worktree 解耦)— ledger 路径 `<change>/dispatch_ledger.jsonl` 在 main repo cwd(`worktree_mode: in_place`)或 worktree(`worktree_mode ∈ {skill_worktree, wrapper_worktree}`)内创建;v2/v3 fence cross-check 行为不变(沿 archived `enhance-workflow-automation-executable-enforcement` 同款)。**注**:parallel + decline 路径下 W3 仍跑但 sequential dispatch(沿 D-ParallelDeclineFallback 自动降级)。

#### Scenario: round 2 fix 用 same implementer agent ID(v1 + v2 + v3)

- **WHEN** evidence frontmatter 含 `subagent_continuity` + `round_2_fix_implementer_id`
- **THEN** `round_2_fix_implementer_id` MUST 等于 `round_1_implementer_id`,否则 `_check_round_fix_continuity` exit 非 0

#### Scenario: round 2 reviewer 用 same reviewer agent ID(v1 + v2 + v3)

- **WHEN** evidence frontmatter 含 `round_2_review_reviewer_id`
- **THEN** `round_2_review_reviewer_id` MUST 等于 `round_1_reviewer_id`,否则 fence exit 非 0

#### Scenario: v2 evidence ledger cross-check 通过

- **WHEN** v2 evidence `subagent_continuity.round_1_implementer_id: ad79e93a40414763e` + `<change>/dispatch_ledger.jsonl` 中含此 agent_id 行(round=1, role=implementer)
- **THEN** fence pass

#### Scenario: v2 evidence ledger 缺失 agent_id 阻断

- **WHEN** v2 evidence `subagent_continuity.round_1_implementer_id` 在 ledger 中**无对应行**
- **THEN** `_check_round_fix_continuity` v2 fence exit 非 0
- **AND** 错误信息指明 evidence agent_id 不在 ledger 中

#### Scenario: v2 evidence dispatch_ledger.jsonl 文件缺失阻断

- **WHEN** v2 evidence `dispatch_ledger_path: dispatch_ledger.jsonl` 但 `<change>/dispatch_ledger.jsonl` 文件不存在
- **THEN** `_check_round_fix_continuity` v2 fence + `_check_dispatch_ledger` v2 fence 都 exit 非 0(双重守门)

#### Scenario: ADR-013 main repo cwd ledger 路径不变

- **WHEN** controller default 在 main repo cwd 跑 `/forgeue:change-apply-subagent` + W3 ledger append
- **THEN** ledger 路径 `<repo>/openspec/changes/<id>/dispatch_ledger.jsonl`(沿 archived ADR-012 同款 main repo path)
- **AND** v2/v3 fence cross-check 行为不变

#### Scenario: v3 evidence ledger HMAC chain 整链 verify 通过

- **WHEN** v3 evidence `runtime_enforcement_protocol_version: v3` + ledger 含 N 行 v3 schema 合法行(整链 HMAC + key_id 一致)
- **THEN** `_check_round_fix_continuity` v3 fence + `_check_dispatch_ledger` v3 fence pass
- **AND** evidence frontmatter `ledger_forgery_resistance: cryptographic`

#### Scenario: v3 evidence ledger 行被 hand-edit 触发 BLOCKER(double fence)

- **WHEN** v3 evidence + ledger 任意一行 `agent_id` 被 hand-edit
- **THEN** `_check_dispatch_ledger` v3 fence exit 非 0(hmac_mismatch)
- **AND** `_check_round_fix_continuity` v3 fence 也 exit 非 0(双重守门)

#### Scenario: v2 evidence 不触 v3 chain verify(self-dogfood gap)

- **WHEN** evidence frontmatter `runtime_enforcement_protocol_version: v2`(本 change 自身 evidence 沿 self-dogfood gap)
- **THEN** v3 fence 分支 pass-through(不 inspect ledger 的 hmac 字段)
- **AND** v2 advisory schema-only 校验仍生效
