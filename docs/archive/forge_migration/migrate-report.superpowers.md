# Migration Verification — superpowers @ 2026-05-19

> **本文件性质**:人工核验记录,非 `forge migrate` CLI 自动生成。
>
> `forge migrate` 的报告固定写 `forge/migrate-report.md`(第二个 source 会覆盖第一个,
> 见 forge `docs/migration/from-openspec.md §7.1`)。本项目第一遍 openspec 的报告已备份为
> `forge/migrate-report.openspec.md`;superpowers 这一遍当时未保留独立报告。本文件为补录,
> 经人工逐文件核验源目录得出,作为 superpowers 迁移环节的证据留痕。

## Summary

- Source: superpowers(探测目录 `docs/superpowers/{specs,plans}/`)
- 可迁移 active 工作:**0**
- 结论:superpowers 源无 active 工作可迁,无需在 `forge/changes/` 产生新 change

## 源目录核验

`forge migrate superpowers` 探测 `docs/superpowers/specs/` 与 `docs/superpowers/plans/`。
实际内容(`find docs/superpowers -type f`):

| 文件 | 性质 | 处置 |
| ---- | ---- | ---- |
| `docs/superpowers/plans/2026-05-10-retire-forgeue-protocol-layer-fully.md`(957 行) | 已完成 change `retire-forgeue-protocol-layer-fully` 的实施计划史料 | 见下「处置」 |

- `docs/superpowers/specs/` 目录不存在 —— 无 spec 产物。
- 唯一的 plan 文件对应的 change `2026-05-10-retire-forgeue-protocol-layer-fully` **已归档**,
  位于 `forge/changes/archive/2026-05-10-retire-forgeue-protocol-layer-fully/`(随 openspec 迁移落地)。
  该 plan 是已完成 change 的史料,不是待实施的 active 工作 —— 故无可迁的 active change。

## 处置:plan 史料抢救

`forge migrate` 不会把已完成 change 的 superpowers plan 搬进 `forge/`。为避免后续
`git rm -r docs/superpowers/` cleanup 丢失这份 957 行实施计划,已人工拷入对应已归档 change 的
notes 目录:

```
docs/superpowers/plans/2026-05-10-retire-forgeue-protocol-layer-fully.md
  → forge/changes/archive/2026-05-10-retire-forgeue-protocol-layer-fully/notes/superpowers-implementation-plan.md
```

逐字节一致,已核验。

## Cleanup

superpowers 源目录可随 openspec cleanup 一并清理(plan 史料已抢救):

```bash
git rm -r docs/superpowers/
```
