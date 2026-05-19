---
purpose: P3 §4.7 self-test 结果记录(5 tool 手 --json --dry-run 自检)
created_at: 2026-04-27
note: |
  helper-style 记录(无 12-key 正规 evidence schema);archive 时随 change 走作 reference。
  不是 evidence,不进 finish_gate 的 frontmatter 全检。
---

# P3 §4.7 Self-test: 5 tool --json --dry-run

self-test 在 `chore/openspec-superpowers` 分支上对 self-host change `fuse-openspec-superpowers-workflow` 跑通,产物落 `./demo_artifacts/p3_selftest/`。

## 测试矩阵

| # | 命令 | exit | JSON 有效 | 副作用 | 备注 |
|---|---|---|---|---|---|
| 1 | `python tools/forgeue_env_detect.py --json --dry-run` | 0 | [OK] | 无 | claude-code 检出;superpowers plugin 在 `~/.claude-max/plugins/cache/.../superpowers`;codex-plugin-cc 未装(降级 path B) |
| 2 | `python tools/forgeue_change_state.py --change <self> --json --dry-run` | 0 | [OK] | 无 | state=S4,无 --writeback-check 时不跑 4 类 DRIFT;basic mode |
| 3 | `python tools/forgeue_verify.py --change <self> --level 0 --json --dry-run` | 0 | [OK] | 无 | dry-run = 仅 emit plan 不 spawn pytest |
| 4 | `python tools/forgeue_doc_sync_check.py --change <self> --json --dry-run` | **2** | [OK] | 无 | 检出 4 份 REQUIRED docs 未编辑(README/CHANGELOG/CLAUDE/AGENTS;P6 阶段才会改) |
| 5 | `python tools/forgeue_finish_gate.py --change <self> --no-validate --json --dry-run` | **2** | [OK] | 无 | 59 blockers:3 evidence_missing(P5-P7 待生成)+ 1 aligned_false_no_drift(codex_design_review.md frontmatter)+ 55 tasks_unchecked(P3-P9 残留 [ ]) |

## 关键观察

- **exit 2 不是 tool 失败**:doc_sync_check 与 finish_gate 检出的是 self-host change 当前阶段(P3 收尾,P5-P9 未启)的真实状态,这是工具按设计工作。两者都正确实现:
  - doc_sync_check 的 4 个 DRIFT 对应 tasks.md §7.5.7-§7.5.10(P6 工作);
  - finish_gate 的 evidence_missing 对应 tasks.md §6 / §7 / §8(P5/P6/P7 工作),tasks_unchecked 对应 §4.x 之后所有未做项。
- **--dry-run 无副作用**:5 tool 在 --dry-run 下都不写 verification/ 目录,不 spawn 关键 subprocess(verify --dry-run 仅 emit plan;finish_gate --dry-run 计算报告但不落盘;change_state / doc_sync_check / env_detect 本就是 read-only)。git rev-parse / git show --name-only 是 read-only,不属"关键 spawn"。
- **stdlib only**:5 tool 共享 `tools/_common.py`(setup_utf8_stdout / parse_frontmatter / git_rev_parse / git_show_files / find_repo_root / list_active_changes / iter_evidence_files / env_truthy / console_safe / change_path 共 11 个 helper)— 无 third-party dep,不进 `pyproject.toml [project.scripts]`(沿决议 D-NoConsoleScripts)。
- **Windows GBK 兼容**:setup_utf8_stdout 在每个 tool 的 `main()` 第一行调用;`console_safe` 把 stderr error 信息 ASCII 化避免 Git-Bash GBK 崩。tools 自身 stdout JSON 是 utf-8(消费者读时需 `encoding='utf-8'`)。
- **frontmatter 解析**:_common.parse_frontmatter 经实测能解 991 字符 `drift_reason` 块标量(p1_docs_review_codex.md 真实 evidence)+ list 形式 contract_refs + bool/null/int/string 标量,完整覆盖 12-key schema。

## 已知行为(留 P4 决定)

- **DRIFT 1 detection**(`evidence_introduces_decision_not_in_contract`):跳过 `evidence_type` ∈ {design_cross_check, plan_cross_check} 的文件,因为 cross-check 协议本身用 `D-XXX:` 作 intra-review tracking ID(per design.md §3 模板),不是 contract 决策。其他 evidence 类型仍扫。
- **DRIFT 3 / 4 detection**:启发式 — DRIFT 3 看 evidence 中 `def`/`class` 声明是否在 design.md fenced 代码 + 反引号标识符里;DRIFT 4 扫已知 failure-mode 关键字(BudgetExceeded / WorkerTimeout 等 10 个)是否 design.md 未写。stdlib only 不做 semantic 分析;P4 fixture 设计需匹配这套 heuristic。
- **doc_sync diff base**:默认用 change 的 bootstrap commit(`git log --reverse -- openspec/changes/<id>/` 取首)的 parent 作 base,不是 main(避免分支上其他已 archive 工作干扰 scope)。`--base <ref>` 显式覆盖。

## 产物清单

5 个 tool + 1 个 helper + 1 个 __init__:

```
tools/
├── __init__.py                     (空,0 行)
├── _common.py                      (220 行,11 helper)
├── forgeue_env_detect.py           (244 行,5 层检测)
├── forgeue_change_state.py         (450 行,回写检测主力)
├── forgeue_verify.py               (350 行,Level 0/1/2 编排)
├── forgeue_doc_sync_check.py       (390 行,10 文档启发式)
└── forgeue_finish_gate.py          (450 行,中心化最后防线)
```

行数为参考量级,实测以 `wc -l` 为准。

## 下一阶段(P4)

P4 写 tests/fixtures/forgeue_workflow/ + tests/unit/test_forgeue_*.py,fence 守门各 tool 的契约面;详 tasks.md §5。
