# Follow-on Backlog Registry

集中 follow-on backlog 记录(自 `centralize-followon-backlog-registry` change 起,2026-05-07;2026-05-19 自 `forge/backlog/` 迁出至本目录)。

> **与 forge 原生 backlog 的关系**:`forge/backlog/` 由 forge 插件原生占用 —— `/forge:archive` 自动从各 change 的 `forge-scope-entries` YAML 块生成,不可手编。本目录(`docs/followon_backlog/`)是 ForgeUE 项目自有的**手工维护** follow-on registry,两套是独立机制。自 `retire-forgeue-protocol-layer-fully` 起本 registry 的 fence 守门已 retire,由 user 自由维护,git history 替代 audit trail。

## 文件结构

- [`active.md`](active.md) — 当前 active follow-on entries(workflow-protocol + capability-boundary + requirements-tbd-pointer 三类)
- [`archived.md`](archived.md) — 已归档 tombstone(append-only by convention;cancelled-superseded / cancelled-not-applicable / cancelled-completed)

## Schema(active.md entry)

每条 entry 由 H3 标题 + 8 字段块组成:

```markdown
### `<followon-id>`

- **source**: <forge/changes/archive/<change-id>/tasks.md § P12.X | docs/requirements/SRS.md § 7.3 TBD-XXX | docs/design/LLD.md § <section>>
- **description**: <1-2 句 description>
- **trigger**: <触发条件,何时启动 follow-on change>
- **category**: workflow-protocol | capability-boundary | requirements-tbd-pointer
- **retire-impact-status**: unaffected | scope-narrowed | partial-superseded
- **priority**: high | medium | low | (空)
- **status**: active
```

## Schema(archived.md tombstone entry)

每条 tombstone 由 H3 标题 + 4 字段块组成(append-only by convention;不删 / 不改既有 entry):

```markdown
### `<followon-id>`

- **archived_at_commit**: <40-char lower-case hex git sha>
- **archived_in_change**: <change-id;触发归档的 change>
- **cancellation_reason**: <cancelled-superseded by <ref> | cancelled-not-applicable: <enum>+free-form | cancelled-completed: <commit-ref> | inherited-then-completed>
- **registry_entry_snapshot**: <原 active.md entry 8 字段拷贝,JSON 单行>
```

## 双源 + 互链:与 SRS §7.3 TBD 表关系

- **registry**(本目录)收 archive-tracking 类(workflow-protocol + capability-boundary)+ pointer entries 至 SRS §7.3 active TBD
- **SRS §7.3 TBD 表**(`docs/requirements/SRS.md`)仍是需求层 backlog;active TBD(`status ∈ {❌, ⚠️ baseline, ⏳}`)在 registry 有对应 `requirements-tbd-pointer` entry
- 两边 cross-link 不重复:registry pointer 不复制 SRS TBD 详细描述,只 1 行 pointer;两边集合一致性由 user 维护(fence 守门已 retire)

## Cancel 协议

cancel 4 类合规出口:

| 类型 | tag 格式 | 说明 |
|---|---|---|
| `cancelled-superseded` | `[cancelled-superseded by <new-change-id>]` | 被后续 change 取代 |
| `cancelled-not-applicable` | `[cancelled-not-applicable: <reason>]` | reason 第一 token ∈ 5 类 enum:`retire-superseded` / `out-of-scope` / `scope-changed` / `obsolete` / `infeasible`(允许冒号后补 free-form 文字) |
| `cancelled-completed` | `[cancelled-completed: <commit-ref>]` 或 `[cancelled-completed: <commit-ref> evidence: <path>]` | follow-on 已实现完成 |
| `inherited` | `(沿前一 change 继承)` 文字 | 被后续 change 继承 |

## 协议引用

- `forge/changes/archive/2026-05-07-centralize-followon-backlog-registry/design.md` — D-RegistrySchema / D-RegistryDualSource / D-TombstoneProtocol / D-CrossLinkSync 等设计决策
- `forge/specs/examples-and-acceptance/spec.md` — Centralized follow-on backlog registry 行为契约 + tombstone schema requirements
