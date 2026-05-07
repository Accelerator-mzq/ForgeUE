## Context

`tools/forgeue_finish_gate.py` 是 ForgeUE Integrated AI Workflow 的中心化最后防线(沿 `docs/ai_workflow/forgeue_integrated_ai_workflow.md` + `examples-and-acceptance` capability spec §1163+),负责 evidence frontmatter audit + cross-check + writeback 真实性 + tasks unchecked + `openspec validate --strict` 等多 fence。其中两类 fence 在对 archived 历史 change 做 `D-ArchivedReplayCompat` 二次 replay 时产生 spurious blocker:

- **`_check_tasks_unchecked`** 用 `_SECTION_HEADING_RE = re.compile(r"^##\s+(\d+)\.\s+", re.MULTILINE)` 识别 section heading 抽 section number 用于 `_SELF_STAGE_SECTION_THRESHOLD = 9` 阈值 filter(P8 finish-gate / P9 archive / footer 的 self-stage `[ ]` 行不应阻断 finish_gate 自身)。但 archived 历史 change 的 tasks.md 用 `## P<N> — <text>` 格式(P-prefix + em-dash U+2014),regex 不命中 → `current_section` 滞留前个匹配值 → §P10 / §P11 内 unchecked 行被误报为 blocker(实测 archived 4 change 共 25 个 spurious `tasks_unchecked`)。
- **`openspec validate <id> --strict`** 调用对 archived change(`openspec/changes/archive/<dated-id>/`)报 `Unknown item` — openspec CLI 仅识别 active `openspec/changes/<id>/` + active `openspec/specs/<id>/`,archive/ 路径是 finish_gate 自己的物理布局,upstream openspec CLI 不感知。每个 archived change replay 触发 1 个 `openspec_validate_failed` blocker(实测 4 个)。

两类 bug 都是 pre-existing(regex 自 commit `a4334db` 起 baseline,openspec CLI 是上游 tool design),`retire-parallel-and-worktree-fully` archive P0 baseline 实测被迫修正 `D-ArchivedReplayCompat` criterion 为"31 → 29 unchanged"而非"全 PASS"(沿 archived `retire-parallel-and-worktree-fully/verification/baseline.md:74-98`)。Active workflow 路径不受影响(active changes 用 `## 1. P0 Setup` / `## 9. P8 Finish Gate` 数字+点格式,regex 命中;active changes 在 active 目录,openspec validate OK)。

## Goals / Non-Goals

**Goals:**

- 扩展 `_SECTION_HEADING_RE` regex 支持双格式 — `## <int>. <text>`(active 现行)+ `## P<int> — <text>`(archived 历史 em-dash U+2014),两种格式均抽出整数 section number 用于阈值 filter,**backward-compat 不破现有行为**。
- `forgeue_finish_gate.py` 的 `openspec validate` 调用在 archive/ 路径下自动 skip 并写 rationale 注释(短期 mitigation),avoid 噪声 blocker;active change 路径行为 unchanged。
- `D-ArchivedReplayCompat` 噪声 baseline 从 29 → 0(2 v2 fence 已在 retire 中消失;本 change 再去掉 25 + 4),让"archived 4 change replay 全 PASS" criterion 真正 hold。

**Non-Goals:**

- **不**给 upstream openspec CLI 提 PR 或本地 patch 让 CLI 识别 `openspec/changes/archive/<dated-id>/` 路径。这是更长期的工作(可能需要双向沟通 + 上游 release 节奏 + 跨 repo coordination),留单独 follow-on backlog `enhance-openspec-cli-archived-change-support` 若决定推上游。
- **不**改 active `## <int>. <text>` 格式的 `_SELF_STAGE_SECTION_THRESHOLD = 9` 数值或语义(P8 finish gate = section 9,backward-compat 守门)。但 **per-format threshold 拆分**(沿 codex round 1 F2 inline writeback + 新 D-PerFormatThreshold):active 格式 ≥9 / archived `## P<int>` 格式 ≥10(因 archived P-num 与 active section-num 跨 change 不严格对齐,实测 archived P9 既有 `Documentation Sync Gate` workflow prerequisite 也有 `MEMORY.md update(后置可选)` self-stage,统一 ≥9 会把 prerequisite stage 静默 skip)。
- **不**支持其他 dash 字符变体(`–` U+2013 en-dash / `--` 半角双连字符)— 实测 archived 4 change tasks.md 仅用 em-dash U+2014;YAGNI 不引入 over-eager regex。
- **不**改其他 finish_gate fence(`_check_skill_cascade` / `_check_round_fix_continuity` / `_check_task_granularity` / `_check_autonomy_boundary` 等);本 change scope 严控两 fence。
- **不**做 evidence frontmatter audit 改动 / 不引入新 evidence_type / 不动 12-key audit frontmatter contract。
- **不**触动 docs/ 五件套(SRS / HLD / LLD / test_spec / acceptance_report)— finish_gate tooling 行为在 `openspec/specs/examples-and-acceptance/spec.md` capability spec 内 specified,不在 docs/ contract 内。

## Decisions

### D-RegexExtension:`_SECTION_HEADING_RE` 双格式支持的 regex 形态(round 1 codex F2 修订)

**决定**(round 1 codex F2 inline writeback 修订):`_SECTION_HEADING_RE = re.compile(r"^##\s+(P)?(\d+)(?:\.|\s+—)\s+", re.MULTILINE)` —— 单 regex 同时匹配两格式;**双 capture group**:group(1) = `"P"` or `None`(P-prefix 标识),group(2) = section integer。`(?:\.|\s+—)` non-capturing alternation 匹配 `.`(active)或 `\s+—`(archived em-dash)。group(1) 决定走 active threshold(≥9)或 archived threshold(≥10,沿新 `D-PerFormatThreshold`)。

**Why**:

- 单 regex 简洁,parse 路径单一,无 case-by-case regex try-loop
- group(1) `(P)?` 暴露 P-prefix 标识 → `_check_tasks_unchecked` 选 per-format threshold(沿 D-PerFormatThreshold);避免硬编码 threshold 让 archived P9 prereq 静默 skip
- group(2) 永远是 section integer,`int(match.group(2))` parse 不变
- `(?:\.|\s+—)` 显式两选一,避免 over-permissive 命中无关 heading(如 `## 1.5 sub-section` 不命中)
- em-dash U+2014 字面写在 source code 是 unicode 安全的(Python 3 source default UTF-8;本工具 stdlib-only 沿 ForgeUE tooling 约定)

**Alternatives considered**:

- (A) 两个独立 regex `_SECTION_HEADING_RE_ACTIVE` + `_SECTION_HEADING_RE_ARCHIVED`,parse 路径分别 try:**拒绝**,代码复杂度无收益;single regex 的 双 capture group 已足够区分格式 + 选 threshold。
- (B) `r"^##\s+P?(\d+)\W+\s*"` 用 `\W+` 通吃所有非字母数字分隔符:**拒绝**,过度宽松会命中错误格式(如 `## 1: subtitle`),YAGNI 边界扩散。
- (C) 在 parse loop 里 string startswith / split 手工解析,不用 regex:**拒绝**,失去 `re.MULTILINE` 与 `\s+` 容错,实现冗长。
- (D) 单 regex 单 capture group(原版 `r"^##\s+P?(\d+)(?:\.|\s+—)\s+"`):**拒绝(round 1 codex F2 inline writeback)**,无 P-prefix 标识 → threshold 必须共用一值 → archived P9 ambiguous 静默 skip prereq stage。

### D-PerFormatThreshold:per-format self-stage threshold(round 1 codex F2 新增)

**决定**(round 1 codex F2 inline writeback 新增):`_check_tasks_unchecked` 内 self-stage 阈值按 regex group(1) 区分:

- **Active 格式**(`group(1) is None`,即 `## <int>. <text>`):threshold ≥9(沿原 baseline,P8 finish gate = section 9 / P9 archive = section 10 / footer = section 11)
- **Archived 格式**(`group(1) == "P"`,即 `## P<int> — <text>`):threshold **≥10**(archived P0-P9 全 workflow prerequisite 应 block;P10+ self-stage 应 skip)

**Why**:

- 实测 archived 4 change tasks.md `## P9 — ` 标题 ambiguous:
  - `## P9 — Documentation Sync Gate`(workflow prerequisite,doc sync gate 在 finish gate **之前**)
  - `## P9 — MEMORY.md update + follow-on tracking(后置可选)`(self-stage post-finish-gate)
- 共用 ≥9 阈值会把 `Documentation Sync Gate` 内 unchecked 项静默 skip(false PASS / archived prereq 漏报)— codex F2 实证
- 阈值 archived ≥10 是 conservative 选择 — 即使某 archived change 把 finish gate 放在 P9 而非 P10,unchecked P9 项被 block 是 false-positive(噪声 +1 而非漏报);实测 archived 4 change finish gate 全在 P10+
- Active 阈值 ≥9 不变(active P8 finish gate 等价 section 9,backward-compat 守门)

**Alternatives considered**:

- (A) 共用 threshold ≥9 跨两格式(原 design):**拒绝(F2 实证不安全)**,archived P9 ambiguous 项静默 skip。
- (B) Active threshold + 1 = ≥10 共用(让 archived "对齐"):**拒绝**,active backward-compat 破坏(`test_finish_gate_skips_p8_p9_self_stage_unchecked` 既有 case fail,`## 9. P8 Finish Gate` 应 skip)。
- (C) Archived threshold 不固定,从 tasks.md 自动推断 finish gate stage:**拒绝**,tasks.md 没标"哪个 stage 是 finish gate"的元数据,推断脆弱;hard-code 值更明确审计。
- (D) Archived threshold ≥9 但加白名单 stage 名("Documentation Sync Gate" 等)不 skip:**拒绝**,白名单脆弱跨 change 不同名;阈值方案更稳定。

### D-OpenSpecValidateArchiveSkip:archive/ 路径下 openspec validate 调用 skip 策略

**决定**:`forgeue_finish_gate.py` 在 invoke `openspec validate <id> --strict` 前检测 `change_dir` 是否在 archived 物理布局下(沿新 `D-DispatchPathDetection` round 1 修订:`change_dir.is_relative_to(_common.archive_dir(repo))`);若是则 skip subprocess invocation 并写 rationale 注释 evidence 到 finish_gate report(标 `openspec_validate_skipped: archive_path_unsupported_by_upstream_cli`),**不**生成 `openspec_validate_failed` blocker。Active change 路径行为 unchanged(继续 invoke + 失败时 BLOCKER)。

**Why**:

- archive/ 路径是 ForgeUE 自家物理布局(`openspec/changes/archive/<YYYY-MM-DD-id>/`),upstream openspec CLI 不感知 — 强制 invoke 必 fail,blocker 是噪声不是真实违规
- skip + rationale 评论保留 audit trail(finish_gate report 可见原因);若 user 想验 archived change validity 可手工 cd 到 archive 目录跑 `openspec` CLI(短期解决方案)
- 长期方案是给 upstream openspec CLI 提 PR(留 follow-on),本 change 先解封 archived replay 路径

**Alternatives considered**:

- (A) 给 upstream openspec CLI 提 PR 让其识别 `openspec/changes/archive/<dated-id>/`:**拒绝(本 change scope 外)**,跨 repo + release 节奏不可控;留 `enhance-openspec-cli-archived-change-support` follow-on 若决定推上游。
- (B) finish_gate 自己实现 archived spec validation(读 spec.md + 解析 markdown structure):**拒绝**,重 implement 上游 CLI 行为是大 scope;archive 是 frozen 状态,validation 价值低。
- (C) 把 archive/ 路径下 openspec validate failure 降级为 WARN 不 BLOCKER:**拒绝**,WARN 仍是噪声;skip + rationale 更干净,且与 D-V1ProtocolBoundary `_runtime_enforcement_active: v1` 设计一致(有些 fence 在某些 evidence 上下文不适用就 explicit skip,不降级)。
- (D) `_runtime_enforcement_active = False`(对所有 archived 路径 skip 全部 fence):**拒绝**,scope 过大;本 change 仅修两 fence,其他 fence 在 archived replay 时仍应跑(评估 evidence frontmatter / cross-check / writeback truthiness 等)。

### D-OpenSpecValidateArchiveSkip:archive/ 路径下 openspec validate 调用 skip 策略

**决定**:`forgeue_finish_gate.py` 在 invoke `openspec validate <id> --strict` 前检测 `change_dir` 是否含 `archive/` segment(沿 `Path.parts` contains `"archive"`);若是则 skip subprocess invocation 并写 rationale 注释 evidence 到 finish_gate report(标 `openspec_validate_skipped: archive_path_unsupported_by_upstream_cli`),**不**生成 `openspec_validate_failed` blocker。Active change 路径行为 unchanged(继续 invoke + 失败时 BLOCKER)。

**Why**:

- archive/ 路径是 ForgeUE 自家物理布局(`openspec/changes/archive/<YYYY-MM-DD-id>/`),upstream openspec CLI 不感知 — 强制 invoke 必 fail,blocker 是噪声不是真实违规
- skip + rationale 评论保留 audit trail(finish_gate report 可见原因);若 user 想验 archived change validity 可手工 cd 到 archive 目录跑 `openspec` CLI(短期解决方案)
- 长期方案是给 upstream openspec CLI 提 PR(留 follow-on),本 change 先解封 archived replay 路径

**Alternatives considered**:

- (A) 给 upstream openspec CLI 提 PR 让其识别 `openspec/changes/archive/<dated-id>/`:**拒绝(本 change scope 外)**,跨 repo + release 节奏不可控;留 `enhance-openspec-cli-archived-change-support` follow-on 若决定推上游。
- (B) finish_gate 自己实现 archived spec validation(读 spec.md + 解析 markdown structure):**拒绝**,重 implement 上游 CLI 行为是大 scope;archive 是 frozen 状态,validation 价值低。
- (C) 把 archive/ 路径下 openspec validate failure 降级为 WARN 不 BLOCKER:**拒绝**,WARN 仍是噪声;skip + rationale 更干净,且与 D-V1ProtocolBoundary `_runtime_enforcement_active: v1` 设计一致(有些 fence 在某些 evidence 上下文不适用就 explicit skip,不降级)。
- (D) `_runtime_enforcement_active = False`(对所有 archived 路径 skip 全部 fence):**拒绝**,scope 过大;本 change 仅修两 fence,其他 fence 在 archived replay 时仍应跑(评估 evidence frontmatter / cross-check / writeback truthiness 等)。

### D-DispatchPathDetection:archive 路径检测方式(round 1 codex F1 修订)

**决定**(round 1 codex F1 inline writeback 修订):用 `change_dir.is_relative_to(_common.archive_dir(repo))` 检测 — repo-relative + segment-precise。**不**用 `"archive" in Path(change_dir).parts`(round 1 F1 实证不安全:repo 父目录路径含 `archive` segment 时 active change 被误判 archived,openspec validate 静默 skip 漏报真 BLOCKER)。

**Why**(round 1 修订后):

- `_common.archive_dir(repo) = repo / "openspec" / "changes" / "archive"` 是 OpenSpec 物理布局的精确 invariant
- `change_dir.is_relative_to(archive_dir)` 是 Python 3.9+ stdlib `pathlib.Path` API,不 false-positive 命中 repo 父目录含 `archive` 的情况(如 `/some/archive/repo/openspec/changes/<active-id>/` 不 relative_to `/some/archive/repo/openspec/changes/archive/`)
- repo-relative 边界与 ForgeUE 项目其他 tooling 一致(沿 `tools/_common.py:466-467` `archive_dir(repo)` helper)

**Alternatives considered**:

- (A)(原 baseline)`"archive" in Path(change_dir).parts`:**拒绝(round 1 codex F1 inline writeback)**,repo 父目录名含 `archive` 时 active change 被误判 archived → openspec validate 静默 skip 漏报真 BLOCKER。
- (B) `re.search(r"\barchive\b", str(change_dir))`:**拒绝**,word boundary 在 path separator 上行为模糊;不解决 F1 root cause。
- (C) `change_dir.parent.name == "archive"`:**拒绝**,过严 — 假设 archive/ 是 change_dir 直系 parent。OpenSpec 当前布局确实如此(`openspec/changes/archive/<id>` 的 parent 是 `archive`),但 stability 低于 `is_relative_to` 模式;后者对 multi-level archived layout(若未来加 `archive/<year>/<id>/`)仍正确。
- (D) `change_dir.is_relative_to(_common.archive_dir(repo))`:**接受(round 1 F1 final)**,repo-relative + segment-precise + 跨 OpenSpec 未来布局变化 robust。

## Risks / Trade-offs

| Risk | Mitigation |
|------|-----------|
| Regex 改动可能误报或漏报某些 corner-case heading | 加 unit test 覆盖:active `## 9. P8` / archived `## P10 —` / archived `## P11 — Documentation Sync footer` / 假阴性 `## 1.5 sub-section`(应不命中) / 假阳性 `## P10X —` 缺空格(应不命中);regression 守门两个 existing case `test_finish_gate_skips_p8_p9_self_stage_unchecked` + `test_finish_gate_does_not_skip_pre_p8_unchecked` |
| **archived P9 ambiguous 语义 → 误 skip workflow prerequisite**(round 1 codex F2)| `D-PerFormatThreshold` 拆分阈值:active ≥9 / archived ≥10;archived `## P9 — Documentation Sync Gate` block 守门(P9.1 unchecked → blocker)+ archived `## P10 — Finish Gate` skip 守门(P10.x unchecked → not-blocker) |
| **repo 父目录名含 `archive` segment → active change 被误 skip openspec validate**(round 1 codex F1)| `D-DispatchPathDetection` 改用 `change_dir.is_relative_to(_common.archive_dir(repo))` repo-relative + segment-precise 检测;regression test `repo = tmp_path / "archive" / "repo"` 配 active change → 仍 invoke openspec validate(monkeypatch + count == 1 守门)|
| **archive-skip test invocation 验证强度不足**(round 1 codex F3)| `test_finish_gate_skips_openspec_validate_for_archive_path` 用 monkeypatch + count == 0 + 拒绝任何 validate-related blocker type(`openspec_validate_failed` / `openspec_cli_missing` / `openspec_validate_error`),env 无 openspec CLI 不 false-pass |
| openspec validate skip 在 archive/ 路径下可能掩盖 archived change 的真实 spec 损坏(如 archive 目录被外力 corrupt) | rationale 评论 emit 到 finish_gate report 可见;archived 是 frozen 状态,损坏概率低;长期方案给上游 CLI 提 PR(follow-on) |
| 双 regex 格式让未来若引入第 3 种 section heading 风格(如带 emoji 或 中文 prefix)需扩展 | YAGNI — 本 change 仅修当前实测两格式;未来引入新格式时 regex 已是 single point of change |
| `Path.parts` 检测在 symlink 或 case-insensitive filesystem 上行为? | Windows NTFS 默认 case-insensitive;`archive` literal segment 是 OpenSpec 自家物理布局,user 不会 rename;symlink 在 OpenSpec workflow 不存在(workflow 假定 plain dir tree) |
| 改动 `_check_tasks_unchecked` 行为可能让某些 active change 的 false-positive 消失或新增 | active changes regex 命中行为不变(P-prefix 是 optional);新 regex 是 superset,不会改 active 路径已 PASS 的 case 行为(`## N.` 仍命中) |

## Migration Plan

无 migration 需要 — 本 change 是纯 backward-compat 扩展 + 路径分流 skip:

- Active workflow:行为不变(regex superset + openspec validate 仍 invoke)
- Archived 4 change replay:噪声 baseline 从 29 → 0,自动生效不需 user 手工干预
- evidence frontmatter:无新字段引入

回滚:`git revert <commit>` 即可,无 schema migration / 数据 migration。

## Open Questions

无。所有边界已在 D-decision 内 cover。

## Reasoning Notes

### codex round 1 inline writeback(2026-05-06)

Codex `/codex:adversarial-review` round 1(verdict `needs-attention`,3 finding 全 accepted-codex):

- **F1 (high)** — `D-DispatchPathDetection` `"archive" in Path(change_dir).parts` 在 repo 父目录名含 `archive` 时 false-positive,active change 被误判 archived → openspec validate 静默 skip → 漏报真 BLOCKER。**Fix**:改用 `change_dir.is_relative_to(_common.archive_dir(repo))` repo-relative + segment-precise 检测。详见 `review/codex_design_review.md` F1 + `review/design_cross_check.md` `## D` F1 verify。
- **F2 (medium)** — `_SELF_STAGE_SECTION_THRESHOLD = 9` 跨 active `## <int>.` 与 archived `## P<int>` 不对齐;archived P9 实测 ambiguous(`Documentation Sync Gate` workflow prerequisite + `MEMORY.md update(后置可选)` self-stage)→ 共用 ≥9 把 prereq 静默 skip。**Fix**:加新 `D-PerFormatThreshold`(active ≥9 / archived ≥10)+ `D-RegexExtension` regex 改 `r"^##\s+(P)?(\d+)(?:\.|\s+—)\s+"` 暴露 P-prefix capture group。详见 `review/codex_design_review.md` F2 + `review/design_cross_check.md` `## D` F2 verify。
- **F3 (medium)** — archive-skip test 仅 assert blocker type 不在 + warning prefix 在,env 无 openspec CLI 时 blocker type `openspec_cli_missing` escapes assertion → false-pass。**Fix**:`micro_tasks.md` task_p1 改用 monkeypatch + count == 0 + 拒绝任何 validate-related blocker type。详见 `review/codex_design_review.md` F3 + `review/design_cross_check.md` `## D` F3 verify。

`disputed_open: 0`(全 accepted-codex)。Round 1 inline writeback target:
- `design.md`(本文件)— `D-RegexExtension` 修订 + 新 `D-PerFormatThreshold` + `D-DispatchPathDetection` 修订 + Risks/Trade-offs +3 行
- `specs/examples-and-acceptance/spec.md` — Scenario 7 改造 + 加 Scenario 8/9/10/11(repo-relative invariant + archived P9 prereq + archived P10 self-stage + monkeypatch invocation count)
- `execution/micro_tasks.md` task_p1 — 加 3 test case + 改造 `test_finish_gate_skips_openspec_validate_for_archive_path` 用 monkeypatch
- `execution/execution_plan.md` Phase 总览 + File Structure 实施 sketch 同步
