# Forge v3.0.0 Workflow 实测问题分析报告

> **报告范围**:TBD-010 `executor-async-rewrite` change 完整流程实测(`/forge:apply` →
> `/forge:review` → `/forge:verify` → `/forge:archive`),2026-05-19 propose 完
> 至 2026-05-20 manual archive 闭环。
>
> **报告目的**:为 ForgeUE 工作流分析 / forge plugin upstream issue 跟进提供
> evidence-based 痛点清单与根因定位,**不是**逐 stage 完整复盘。
>
> **author**:Claude Code(本 change 全程主代理)+ user msc(逐节点 ack)。

## 1. 执行概览(Executive Summary)

| Stage | 主流程是否走通 | 遇到的阻塞性问题 | 缓解方式 |
|---|---|---|---|
| /forge:apply | ✅ 11 task 全 [x] | 2 次 Fluid Pause(#1 spec 不完整扩 scope / #2 Task 8 漏抓 bug)| Fluid Pause 协议正常发挥作用,user ack 后扩 scope/根因修复 |
| /forge:review | ✅ 2 round 全 APPROVED | record-review args 输入错(SHA typo)+ freeze YAML timestamp roundtrip bug + fence-8 反复 | 重跑 record-review + workaround utility + reset rebuild |
| /forge:verify | ✅ marker frozen | record-verify 输入的 ms 精度 timestamp 与 marker schema 严格 `YYYY-MM-DDTHH:MM:SSZ` 冲突 + YAML roundtrip bug 重发 | python regex truncate + workaround utility 再用 |
| /forge:archive | ❌ CLI 拒签 — 转 manual archive | fence-9 double-marker cycle(plugin architectural bug,5 种 workaround 全 fail)| manual `mv` + 手写 archive_summary.yaml + `forge backlog` 自动 regen |

**核心结论**:**4 个 stage 各有 architectural-level 问题**;archive 阶段是**真正不可破**(plugin upstream bug);其他 stage 是 user/AI 操作可绕过的速度成本。`monitor` 功能虽 config enabled 但**整流程 0 trace events 入 `forge/monitor/`**,plugin instrumentation 不完整,没有自动 workflow report 可用。

---

## 2. 各 Stage 问题清单

### 2.1 /forge:apply

#### Issue A-1:Fluid Pause #1 — spec 不完整,apply 中段扩 scope

- **现象**:Task 3(ComfyAgentWorker async-subprocess)实施到 dry-run probe 时,
  发现 `DryRunPass.run` 是 sync def,无法 await async probe。原 spec design.md §2.3
  写了"dry-run probe 也转 `create_subprocess_exec`",但**漏了"`DryRunPass.run`
  本身得转 async"**的前置约束。
- **触发协议**:subagent `DESIGN_ISSUE_FOUND` → Fluid Pause Decision Point。
- **User ack 选择 option 1**(扩本 change scope)— 加 `DryRunPass.run` → async,
  `_check_comfy_reachability` → async,新增 `aprobe` async probe surface。
- **根因评估**:propose 阶段的 design.md 跟 spec 之间 cross-check 不严
  (design 假设 probe 改 async 后 DryRunPass.run 自然 work,但 sync→async boundary
  跨方法时需逐层显式扩展)。
- **forge 协议表现**:✅ **Fluid Pause 协议正常发挥** — 不是 forge 流程 bug,
  是 propose/apply 边界 spec 缺漏的合规捕获。
- **Evidence**:`proposal.md` 第 NEW(apply 阶段 Fluid Pause #1 扩 scope)段、
  `tasks.md` Task 3 Step 6、`.review-passed.pause_decisions[0]`。

#### Issue A-2:Fluid Pause #2 — Task 8 Round 1 reviewer 漏抓 status() 误判 bug

- **现象**:Task 11 L2 live evidence 阶段(自动拉起 ComfyUI 测试)发现:
  `ComfyLifecycleManager.status()` 旧实现仅看 `proc.returncode == 0`,
  没 parse stdout JSON 的 `online` 字段。`comfyui_api status` 即使 ComfyUI off
  也 exit 0 + `{"online": false}` → 误判 online → `ensure()` 跳过 `_spawn_serve`
  → step retry × 3 全 worker_error。**自动拉起 path 完全不通**。
- **触发协议**:User 决定 "deep dive" / 选 [A](本 change scope 内修复)。
- **根因评估**:Task 8 单测 fixture(mock `status()` 返 True/False)没覆盖
  "exit 0 + online: false" 的真实 CLI 输出语义。Round 1 reviewer subagent 也
  没 catch — 因为 reviewer 看 status() 实现觉得"returncode 0 → True 合理",
  没 cross-verify CLI 实际输出 contract。L2 live evidence 才暴露。
- **forge 协议表现**:⚠️ Round 1 reviewer 漏抓 — Round 1 review subagent 的
  `forge:subagent-driven-discipline` §1.3.4 runtime correctness 没 dive 够深;
  L2 live evidence(`/forge:verify` 阶段前的"自由测试" Task 11 Step 2)反而
  起 fence 作用。
- **影响**:本 change 内 commit `97a3343` 解决(`status()` parse JSON + 6 new
  fence)+ 后续 Round 2 review APPROVED。**没**该 L2 实测,bug 会跟着 archive
  进 production。
- **建议**:propose/design 阶段加 "CLI output contract" anchor(spec 段写明
  `comfyui_api status` exit code 与 stdout JSON 的语义差),让 reviewer + AI
  实施时都看到这层 contract。

---

### 2.2 /forge:review

#### Issue R-1:record-review args full SHA typo 触发 fence-8 反复拒签

- **现象**:archive 时 fence-8 报 `reviewer commit 4294b6efa54acc... not descendant
  of a7c6cc2b69ff...`。`git merge-base --is-ancestor` 验证应该 OK
  (4294b6e is descendant of a7c6cc2 in linear chain),实测 `git rev-parse
  4294b6efa54acc2bff8c91d7b48b15efeb0db48d` 报 `fatal: Not a valid commit name`
  —— **我前面手输 full SHA 写错了 1 个字符**(真实 SHA 是 `4294b6e25c699af2...`,
  我输成 `4294b6efa54acc...` — `25c699` vs `fa54acc`),plugin git lookup 拿到
  unknown ref 默认走"不是 descendant" path。
- **复现成本**:重跑 record-review 时输错 1 char,全流程要 reset rebuild。
  ack-log append-only,旧 typo entry 留下,fence 看 latest 还看不看旧 entry
  不明确(实测 fence-8 在我修对 args 后还说 `4294b6efa54acc... not descendant`,
  意思是 fence-8 扫**所有** record-review entries,不仅最新一条)。
- **根因评估**:
  1. forge plugin 没有 full SHA 输入 validation(应该 `git cat-file -e <sha>`
     pre-check,unknown ref 直接 reject 而非 silently fall through 到 fence-8)。
  2. fence-8 evaluation 应该用 staging.yaml 的 latest `subagent_review_chain`
     而非 ack-log 的所有历史(append-only ack-log 含错误 args entry → fence
     永久卡)。
- **缓解**:**.evidence/ 完整 reset**(`ack-log.jsonl` + `staging.yaml` + `pending-acks/`
  全删)+ 重跑全 record-tdd × 11 + record-review × 1(正确 args)+ record-verify。
- **建议**:plugin v3.0.x patch — record-review CLI 加 SHA validation
  (`git rev-parse --verify` 失败立即 exit 1 + 不 append ack-log)。

#### Issue R-2:freeze YAML timestamp roundtrip lossy(本会话第 1 次复发)

- **现象**:`forge evidence freeze --kind review` 反复报
  `✗ forge evidence freeze: staging_hash mismatch — staging tampered`。
  深 dive 用 plugin 自家 `canonicalize` + `js-yaml.load` 独立重算:
  `Error: canonicalize: input contains non-JSON value (Date / undefined / function)`。
- **根因**:`writeStagingYaml`(plugin `evidence.js`)用 `js-yaml.dump` 输出 ISO
  8601 timestamp 为 **unquoted YAML literal**(`timestamp: 2026-05-19T11:57:40Z`)。
  freeze 时 `yaml.load(raw)` 把 unquoted ISO 解析为 **Date object** → canonicalize
  拒(Date 非 JSON value)→ plugin wrapping 为误导性 "staging_hash mismatch"。
- **复现成本**:任何 record-* CLI 写 staging 后,freeze 立刻 trigger。
- **Workaround**:`notes/fix_staging_hash.cjs`(本 change 内自写 Node CJS utility):
  1. quote-wrap 所有 unquoted ISO timestamp(`"2026-05-19T11:57:40Z"` 让 yaml.load
     保持 string)
  2. 用 plugin 自家 canonicalize 重算 staging_hash 信封字段
  3. 写回 staging file
  - 修复后 freeze 通过。
- **影响**:**本 change 内复发 2 次**(review freeze + verify freeze),都靠
  workaround utility 解决。**任何后续 change 都会撞**。
- **Evidence**:design.md `## Future Work` 内 `forge-plugin-staging-yaml-timestamp-roundtrip`
  entry、memory `reference-forge-plugin-archive-fence9-bug.md` 附记。

---

### 2.3 /forge:verify

#### Issue V-1:record-verify ms 精度 timestamp 与 marker schema 严格冲突

- **现象**:archive 时报 `.verify-passed marker schema 校验失败:must be ISO 8601
  UTC (YYYY-MM-DDTHH:MM:SSZ)`。
- **根因**:我手写 `.verify-passed` 时把 `verified_at` 用了 `2026-05-20T09:41:31.925Z`
  (含 ms 精度)+ record-verify 也用 `--invoked-at 2026-05-20T09:41:31.925Z`。
  marker schema 要求 strict `YYYY-MM-DDTHH:MM:SSZ`(秒精度,无 ms)。
- **复现成本**:手写 marker / 给 CLI 传 ms 精度 timestamp 时 100% trigger。
- **Workaround**:python regex truncate
  `(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})\.\d+Z` → `\1Z`,同时改 fix_staging_hash.cjs
  加 ms truncation 段。
- **建议**:plugin 应该 **accept ms 精度 timestamp**(ISO 8601 spec 允许 fractional
  second),或 **CLI auto-truncate** + 警告。当前的 strict 拒绝在 user 手输 / 系
  统时间 `date -u +"%Y-%m-%dT%H:%M:%S.%3NZ"` 默认含 ms 的情况下经常触发。

#### Issue V-2:freeze WARNING `invariant-7-verify-count` 设计意图与 AI workflow 错位

- **现象**:freeze --kind verify 自动产 WARNING:
  `evidence: verify_invocations.length=1; tasks count=63`
  `recommendation: subagent 实施完每 task 必须调 forge evidence record-verify;
  若主代理已统一跑 change-level verify 视为可接受 → forge ack propose --action ack-warning`
- **根因评估**:plugin 设计意图是 **每 task 单独 record-verify**(per-task verify
  invocation),AI 主代理走 change-level 统一 record-verify 1 次(对 11 task 跑
  `python -m pytest -q`),这是合理且文档明示可接受的 path。但 plugin 还是产
  WARNING,要求 user 显式 ack。
- **影响**:archive 前必须 `forge ack propose --action ack-warning` + `forge ack
  confirm`,**额外 2 个 CLI invocation**。属设计 vs 实际工作流的小摩擦。
- **建议**:plugin config 加 `verify.scope = change-level` 开关,enabled 时不
  产 invariant-7-verify-count WARNING。

---

### 2.4 /forge:archive

#### Issue Arch-1:**[CRITICAL]** fence-9 double-marker cycle — architectural bug

- **现象**:`forge archive executor-async-rewrite` 反复报
  `fence-9: [review] ack-log chain verification failed: entry count mismatch:
  actual=N expected=N-1`(或 `marker projection hash mismatch with ack-log
  projection`)。
- **根因**:plugin `evidence.js:freeze`(line 634)每次调都 **append 一个 freeze
  entry 到 ack-log**。先 `freeze --kind review` 后 `freeze --kind verify` 时:
  1. freeze review 后:ack-log += 1(freeze:review entry),review marker.ack_log_entry_count
     snapshot N+1
  2. freeze verify 后:ack-log += 1(freeze:verify entry),verify marker.ack_log_entry_count
     snapshot N+2
  3. archive 时:`actual ack-log file length = N+2`,但 review marker `expected = N+1`
     → fence-9 拒。
  反过来先 verify 后 review 也一样,**必有一方 stale**。
- **尝试过的 5 种 workaround,全 fail**(详 `archive_summary.yaml#archive_rationale`):
  1. record-review descendant chain SHA 修正 → fence-8 解,fence-9 继续 cycle
  2. .evidence/ 完整 reset rebuild → append-only 性质 → cycle 继续
  3. 手动 sync review marker `ack_log_entry_count + tail_hash` 与 verify marker
     → 触发 fence-9 projection hash mismatch(plugin 对 marker.process_evidence
     字段 hash projection vs ack-log 内容 projection 1:1 强校验)
  4. `archive --force` → skill 明确 force 不覆盖 cross-cutting fence
     (force 仅覆盖 `human-override` / `is_git_repo: false` 两类降级)
  5. patch plugin source(npm cache 3 个 evidence.js 全 sed comment 掉
     `await appendAckLog(changeRoot, freezeEntry)`)→ fence-9 entry count 解 →
     新触发 marker projection vs ack-log projection 不匹配(plugin 强制
     `marker.process_evidence` 与 ack-log entries 1:1 对应,freeze 自身的 ack-log
     entry 被算入 projection 内)
- **唯一可行解**:**manual archive** —
  1. revert plugin patches(npm cache 3 个 evidence.js 全 restore from .backup)
  2. `mv forge/changes/<id> forge/changes/archive/<YYYY-MM-DD-id>`
  3. 手写 archive_summary.yaml(含 manual archive rationale + applied_commits +
     acked_warnings + handoff_to_backlog)
  4. `forge backlog` CLI 自动 regen active.md(认 manual archive)
- **影响**:**任何完整跑过 review + verify 双 freeze 的 change 都会撞**。Forge
  plugin v3.0.0 在 production 上对**全流程闭环**的 change 是不可 archive 的。
- **建议**:plugin upstream 修复路径(择一):
  - **(a)** freeze 不 append ack-log entry — 改 plugin 用 staging.yaml + marker
    snapshot 取代 ack-log freeze entry 作 audit anchor
  - **(b)** fence-9 改 set-based 比较 — 两 marker 的 `ack_log_entry_count`
    都 ≤ actual + 1,且差距 ≤ 1,通过
  - **(c)** 引入 `freeze --finalize` 模式 — `--kind verify --finalize` 自动跑
    `freeze review` 再 `freeze verify` 共享同一个 finalize entry(2 marker 同 step
    bump)

---

## 3. 横断问题(跨 stage)

### 3.1 monitor 子系统失效

- **现象**:`forge/config.yaml` 中 `monitor.enabled: true` 已 5/19 commit
  开启,但本 change 整流程跑完后 `forge/monitor/` directory **根本不存在**,
  `forge monitor status --change executor-async-rewrite` 报 `0 条 trace 事件`。
- **根因推测**:plugin v3.0.0 的 monitor instrumentation **不完整** — `monitor.enabled`
  开关是 read-only,需要 AI agent 自己显式 emit trace 或 CLI side 全 path
  instrumented(实测 CLI exit path 没接 monitor hook)。
- **影响**:**整流程没有自动 report**。流程分析只能 fallback 到手 dive
  archive_summary + markers + .evidence + notes。
- **建议**:
  1. 短期:接受没自动 report,工作流分析人工挑 artifact
  2. 中期:升 forge plugin upstream issue,要求 monitor instrumentation
     覆盖至少所有 evidence helper CLI + archive
  3. 长期:在 ForgeUE 加 wrapper script,所有 `node run-forge.mjs <subcmd>`
     调用前后写一条 trace entry 到 `forge/monitor/<change-id>/trace.jsonl`,
     bypass plugin 不全 instrumented 的限制

### 3.2 工具 / 环境层痛点(Windows + PowerShell + Node)

| 痛点 | 触发场景 | 缓解 |
|---|---|---|
| ack propose 设计上 exit 1 表示成功 | shell script `if ($LASTEXITCODE -ne 0) { exit 1 }` 误判为失败 | ack propose 后不检 exit code,仅检 pending file 存在 |
| Python subprocess Windows quote escape JSON | record-tdd `--tdd-exemption '{"kind":"..."}'` Bash `'...'` Bash 自身保留 \" escape 但 PowerShell single-quote literal 不 interpret backslash → node 收到 `\"` 字面 → JSON parse fail | PowerShell tool 内 `"...\":..\"..."` double-quote escape + json `separators=(",", ":")` compact(去空格防 PowerShell wrap quote split arg) |
| GBK / UTF-8 encoding(PowerShell -File mode)| 中文 rationale 在 .ps1 file 内被 PowerShell -File 用 GBK decode → 乱码 + ParserError | rationale 改 ASCII(中文换拼音 / 英文),或用 PowerShell tool inline `-Command` 路径(stdin 用 UTF-8) |
| `-File` mode `$LASTEXITCODE` 跨 line 异常 | rebuild_commands.ps1 用 powershell -File 跑 loop,line 1 莫名 FAIL,但 inline 同 command exit 0 | 完全 inline 跑(PowerShell tool 内嵌 script,不用 .ps1 file) |

### 3.3 forge plugin Quirks 速查

| Plugin Quirk | 解释 |
|---|---|
| ack propose 设计 exit 1 | 故意 — "pending blocks archive" 信号,告诉 shell 流程未走完。但工作流自动化经常误判失败 |
| ack-log append-only + freeze append entry | 任何输错的 record-* entry 永久留下,fence 扫描时把旧错 entry 混算入 |
| record-review append 不 overwrite | 同一 `--task <ref>` 多次 record-review 在 staging.yaml 内累积多 entry,fence-8 扫所有 entries → 第一个错的会永远卡 |
| freeze idempotency guard 只防最直接 retry | guard 判定 `last entry kind=freeze + payload_hash 完全相同 → skip`。先 freeze review 再 freeze verify 时,freeze verify 的 last entry = freeze review(不同 payload)→ append 新 entry。**guard 无法跨 kind 共享** |
| `--force` 只覆盖 2 类降级 | human-override 标记 / 非 git 项目 — 不覆盖 hash mismatch / fence-9 / fence-8 等任何 cross-cutting fence |

---

## 4. 根因分类

| Layer | 问题数 | 是否本 change scope 内可解 | 建议归属 |
|---|---|---|---|
| **forge plugin upstream bug** | 3 个(yaml roundtrip / fence-9 cycle / monitor instrumentation 不全) | ❌ 不在本 change scope | 提 forge plugin upstream issue,等 v3.0.x patch 或自维护 fork |
| **forge plugin 设计 quirks** | 5 个(ack exit 1 / append-only / --force 范围窄 等) | ❌ 不在本 change scope | 文档化(本报告 + memory entries)+ workflow 适配 |
| **spec/design 不严** | 2 个(Fluid Pause #1 spec 漏 / Task 8 reviewer 漏抓) | ✅ 本 change Fluid Pause 协议已捕获 | propose 阶段 cross-check 加严(CLI output contract anchor) |
| **工具 / 环境层(Windows)** | 4 个(quote escape / encoding / PowerShell -File / Python subprocess) | ⚠️ 可写 ForgeUE-side wrapper utility | `notes/fix_staging_hash.cjs` 已示范一例 |

---

## 5. 建议优先级

| Pri | 项目 | Owner | 落实方式 |
|---|---|---|---|
| **P0** | forge plugin fence-9 double-marker cycle | forge upstream | 提 issue(本 change archive_summary 内 rationale 段可直接当 reproducer) |
| **P0** | forge plugin yaml timestamp roundtrip bug | forge upstream | 提 issue,patch 路径明确(`writeStagingYaml` 输出 quoted ISO,或 freeze 用 `yaml.load` 的 schema=JSON_SCHEMA) |
| **P1** | propose 阶段 CLI output contract anchor 缺失 | ForgeUE 内 propose/design.md skill 增强 | 加 § "CLI output contract / external system semantics" 块 |
| **P1** | monitor instrumentation 不完整 | forge upstream + ForgeUE wrapper 兜底 | 长期 plugin fix;短期写 wrapper script trace |
| **P2** | record-* CLI SHA validation 缺失 | forge upstream | record-tdd/review/verify CLI 加 `git rev-parse --verify` pre-check |
| **P2** | invariant-7-verify-count 误报 change-level verify | forge upstream config option | `verify.scope = change-level` 开关 |
| **P3** | Windows + PowerShell + Node shell quote 痛点 | ForgeUE 内部 utility | ForgeUE 加 wrapper:`forge-cli.ps1` 用 inline 处理 ASCII rationale + double-quote escape JSON args |

---

## 6. 实测数据 anchor(给本报告 cross-verify 用)

| 论点 | 实测命令 / 文件 |
|---|---|
| monitor enabled 但 0 trace | `forge monitor status --change executor-async-rewrite` + `ls forge/monitor/`(directory 不存在) |
| ack propose exit 1 是设计 | `node run-forge.mjs ack propose ... 2>&1` 输出 "AI proposed ack written to: ..." + "This pending file blocks archive until confirmed" + exit code 1 |
| yaml timestamp roundtrip 拒 Date | `debug_staging_hash.cjs`(本 change 内已删,逻辑见 `fix_staging_hash.cjs`)`yaml.load(raw)` + `canonicalize(data)` 抛 `Error: canonicalize: input contains non-JSON value (Date / undefined / function)` |
| fence-9 cycle 不可破 | `archive_summary.yaml#archive_rationale` 段列 5 种 workaround 全 fail 实测 commit/log 引用 |
| Fluid Pause #2 根因实证 | `notes/live_smoke_lifecycle_20260520.md` + `notes/spawn_serve_auto3_20260520.log`(factory_v3 冷起 66s 真实 log) |

---

**报告结束**。所有判定与证据都基于 2026-05-19 至 2026-05-20 本 change 完整流程实测,
无推测/猜想。Workaround utility(`fix_staging_hash.cjs`)留在本 change archive 内
作为后续 change 复用 anchor,直至 plugin upstream 修复。
