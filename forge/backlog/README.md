# Follow-on Backlog Registry

集中 follow-on backlog 记录位置(自 `centralize-followon-backlog-registry` change 起,2026-05-07)。

## 文件结构

- [`active.md`](active.md) — 当前 active follow-on entries(workflow-protocol + capability-boundary + requirements-tbd-pointer 三类)
- [`archived.md`](archived.md) — 已归档 tombstone(append-only;cancelled-superseded / cancelled-not-applicable / cancelled-completed)

## Schema(active.md entry)

每条 entry 由 H3 标题 + 8 字段块组成:

```markdown
### `<followon-id>`

- **source**: <archived/<change-id>/tasks.md § P12.X | docs/requirements/SRS.md § 7.3 TBD-XXX | docs/design/LLD.md § <section>>
- **description**: <1-2 句 description>
- **trigger**: <触发条件,何时启动 follow-on change>
- **category**: workflow-protocol | capability-boundary | requirements-tbd-pointer
- **retire-impact-status**: unaffected | scope-narrowed | partial-superseded
- **priority**: high | medium | low | (空)
- **status**: active
```

## Schema(archived.md tombstone entry)

每条 tombstone 由 H3 标题 + 4 字段块组成(append-only;不允许删 / 改既有 entry,沿 `_check_followon_continuity` fence git diff 守门):

```markdown
### `<followon-id>`

- **archived_at_commit**: <40-char lower-case hex git sha>
- **archived_in_change**: <change-id;触发归档的 active change>
- **cancellation_reason**: <cancelled-superseded by <ref> | cancelled-not-applicable: <enum>+free-form | cancelled-completed: <commit-ref> | inherited-then-completed>
- **registry_entry_snapshot**: <原 active.md entry 8 字段拷贝,JSON 单行>
```

## 双源 + 互链:与 SRS §7.3 TBD 表关系

- **registry**(本目录)收 archive-tracking 类(workflow-protocol + capability-boundary)+ pointer entries 至 SRS §7.3 active TBD
- **SRS §7.3 TBD 表**(`docs/requirements/SRS.md`)仍是需求层 backlog;active TBD(`status ∈ {❌, ⚠️ baseline, ⏳}`)在 registry 有对应 `requirements-tbd-pointer` entry
- 两边 cross-link 不重复:registry pointer 不复制 SRS TBD 详细描述,只 1 行 pointer
- **Fence enforcement**:`tools/forgeue_finish_gate.py::_check_srs_registry_consistency` archive 阶段校验 registry `requirements-tbd-pointer` 集合 == SRS §7.3 active TBD 集合(set equality)

## Cancel 协议(沿 design.md D-FenceStrictness)

cancel 4 类合规出口,fence strict ref validation:

| 类型 | tasks.md tag 格式 | fence 校验 |
|---|---|---|
| `cancelled-superseded` | `[cancelled-superseded by <new-change-id>]` | `Path("openspec/changes/<id>").exists() OR Path("openspec/changes/archive").glob("*-<id>")` 任一为真 |
| `cancelled-not-applicable` | `[cancelled-not-applicable: <reason>]` | reason 第一 token 必须 ∈ 5 类 enum:`retire-superseded` / `out-of-scope` / `scope-changed` / `obsolete` / `infeasible`(允许冒号后补充 free-form 文字) |
| `cancelled-completed` | `[cancelled-completed: <commit-ref>]` 或 `[cancelled-completed: <commit-ref> evidence: <path>]` | `git rev-parse --verify` exit 0 + `git diff-tree --name-only` 触达 follow-on `source` / `contract_refs` 集合 OR `evidence: <path>` escape hatch `Path.exists()` |
| `inherited` | `(沿前一 change 继承)` 文字 | checkbox checked + 显式声明继承 |

## Fence 守门(沿 `tools/forgeue_finish_gate.py`)

archive 阶段(`/forgeue:change-finish`)触发 2 fence:

- `_check_followon_continuity`:active.md self-diff(主源) + archived tasks.md 兜底源 + cancel ref strict validation + tombstone 5-point consistency
- `_check_srs_registry_consistency`:SRS §7.3 ↔ active.md `requirements-tbd-pointer` 集合等价 + 状态变化同步

漏 inherit / cancel 声明 / cancel ref 失效 / tombstone snapshot 不一致 / SRS sync 漂移 → BLOCKER exit 2 + 列具体 reason。

## 协议引用

- `openspec/changes/archive/2026-05-07-centralize-followon-backlog-registry/design.md` — D-RegistrySchema / D-RegistryDualSource / D-FenceStrictness / D-FenceLocation / D-FenceParseStrategy / D-TombstoneProtocol / D-CrossLinkSync / D-EvidenceFrontmatterField / D-BackfillScope
- `openspec/specs/examples-and-acceptance/spec.md` — Centralized follow-on backlog registry + `_check_followon_continuity` fence + `_check_srs_registry_consistency` fence + tombstone schema requirements
- `docs/ai_workflow/forgeue_integrated_ai_workflow.md` §B.4 / §E — `followon_continuity` evidence frontmatter 字段
