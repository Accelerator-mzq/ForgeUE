---
purpose: P5 阶段 onboarding,新会话用此文件快速对齐到 P5 起点状态
created_at: 2026-04-27
target_session: new Claude Code session(本 change P0+P1+P2+P3+P4 已完成,准备进 P5 Validation)
note: |
  本文件不是 evidence,是 onboarding helper。新会话 Claude 读完即知道 P5 任务全貌(只 3 项,~10 min)+ forgeue_verify Level 0/1/2 行为契约 + 自动生成的 verify_report 12-key frontmatter 形态 + 后续 P6-P9 路径。
  archive 时随 change 走但仅作历史 reference,不影响 finish gate(notes/ 子目录允许 helper,无 12-key 强制)。
---

# P5 Onboarding: fuse-openspec-superpowers-workflow

## 你现在的状态(新会话 Claude 必读)

你被开启在 ForgeUE 项目(`D:\ClaudeProject\ForgeUE_claude`)的新会话里,**继续推进 active OpenSpec change `fuse-openspec-superpowers-workflow` 的 P5 阶段(Validation)**。

P5 工作量小:**3 项任务,~10 min**(几乎全是跑 tool + 看输出 + 标 [x])。

### 项目环境

- Windows 11 + Git-Bash + D: 盘
- Python 3.13
- pytest baseline:**1123 tests**(P4 milestone 实测 — 848 P3 + 262 P4 + 13 P4-codex-review-fence)
- codex CLI 已装(`codex-cli 0.125.0`,ChatGPT 已登录)
- codex 插件已装在 `~/.claude-max/plugins/cache/openai-codex/codex/1.0.4/`
- Superpowers plugin 已装(全局,12 skills + 7 agents + 4 hooks)
- `/codex:review` / `/codex:adversarial-review` / `/codex:status` / `/codex:result` / `/codex:cancel` 5 个 slash 命令**已 unlock 给 Claude 调** + **broker discovery 已修**(P3 commit 5dd870c 的 `${CLAUDE_PLUGIN_ROOT}` 失效 bug 在 commit 37288fe 修好,改成 `printf '%s\n' "${USERPROFILE:-$HOME}"/.claude*/plugins/cache/openai-codex/codex/*/scripts/codex-companion.mjs | sort -V | tail -1`)

### P0+P1+P2+P3+P4 已完成

milestone commit 链:

```
2aceee3  docs: backfill writeback_commit in P4 review evidence
37288fe  chore: P4 tests + codex slash override broker fix + post-review F1-F4 resolution landed
cf4a6f9  docs: P4 onboarding helper for fresh session entry
5dd870c  chore: unlock /codex:review + adversarial-review + status + result + cancel for Claude model invocation
d0a47f3  docs: codify codex review verbatim-first exposure protocol in design.md sec3
5b564c3  chore: track OpenSpec v1.3 product upgrade
1c0da37  docs: backfill writeback_commit in P3 tools review evidence
d5630a1  chore: P3 tools + C1+C1' review fix landed
9c1be42  docs: P3 onboarding helper for fresh session entry
e8067f3  chore: P2 commands + skills landed
7d0c730  docs: backfill writeback_commit in P1 round-1 evidence
a705754  chore: P1 docs landed
73f18e6  chore: bootstrap fuse-openspec-superpowers-workflow (P0)
```

P4 详情(P5 起步前必懂):

- **regular `/codex:review --base main` review**(broker session `019dce26-...`,8m 53s):4 finding(1 P1 + 3 P2),全 verified TRUE
  - F1 P1 fix-in-tool:`src/framework/comparison/diff_engine.py` 加 `_stable_aid_key` + `_compute_artifact_diffs` / `_compute_verdict_diffs` stable-key 配对 + `_diff_one_artifact` per-side aid kw → 跨 run_id 比较从全 missing 修到正常 unchanged/content_changed
  - F2 written-back-to-design + fix-in-tool:`tools/forgeue_finish_gate.py` `check_malformed_evidence` 从 2-key 扩到 8 always-required,加 `_frontmatter_key_present` helper 处理 bool/list/null edge case;design.md §3 "Helper vs formal evidence subdir" 表写回 + 8/4 split 段
  - F3 P2 fix-in-tool:`tools/_common.py` `_CLAUDE_CODE_ENV_VARS` 加 `CLAUDE_CODE_SSE_PORT`(对齐 env_detect 4-var)
  - F4 P2 fix-in-tool:`tools/forgeue_doc_sync_check.py` `framework_changed` 改成 non-core-detect-independently-of-core
- 4 fix 各加 fence test:diff_engine +6 / finish_gate +3 / env_detect +2 / doc_sync_check +2 = 13 新 fence
- evidence:`review/p4_tests_review_codex.md`(`drift_decision: written-back-to-design`,`writeback_commit: 37288fe...`,`aligned_with_contract: true`)

### P5 阶段任务全貌(tasks.md §6)

只 3 项,**全是 tool 自动化**:

```
- [ ] 6.1 `python tools/forgeue_verify.py --level 0 --change fuse-openspec-superpowers-workflow --json` 全绿
- [ ] 6.2 Level 1/2 显式 SKIP(本 change 不需要 LLM/UE/ComfyUI live)+ SKIP reason 写入 verify_report
- [ ] 6.3 `verification/verify_report.md` 落盘 + frontmatter `aligned_with_contract: true`
```

实际执行:**跑 1 条命令** → tool 自动产 verify_report.md → 标 3 个 [x] → commit。

## 必读文件清单(按顺序读)

读完前 4 项再开始 P5;后 2 项作 reference 按需。

```bash
# P5 必读(契约 + 工具)
cat openspec/changes/fuse-openspec-superpowers-workflow/tasks.md       # 重点:§6(P5 三项)+ §5.8(P4 codex review fixups,刚完成)
cat openspec/changes/fuse-openspec-superpowers-workflow/design.md      # 重点:§5 Tool Design 表(forgeue_verify 行 — Level 0 默认 / 1/2 env guard / exit 0/2/3/1)+ §3 (verify_report 在 REQUIRED-at-archive 通用 3 项里)
cat tools/forgeue_verify.py                                            # 工具实装(build_plan / run_step / render_report);verify_report 12-key frontmatter 由 render_report 自动生成
cat docs/ai_workflow/validation_matrix.md                              # forgeue_verify 是这份矩阵的机器版

# P5 fence reference(已绿 50 个 test 守护此工具行为契约)
cat tests/unit/test_forgeue_verify.py                                  # 50 fence test:Level 0 默认 + Level 1/2 env guard + report 12-key frontmatter + ASCII / dry-run / 不硬编码 pytest 总数

# 可选 reference
cat openspec/changes/fuse-openspec-superpowers-workflow/review/p4_tests_review_codex.md  # P4 codex review 全文(verbatim + 4 finding 解决)
```

## P5 启动指引(实操)

读完上下文后,**直接跑这一条命令**:

```bash
python tools/forgeue_verify.py \
    --change fuse-openspec-superpowers-workflow \
    --level 2 \
    --json
```

**为什么 `--level 2`**:让 tool 把 Level 0 + Level 1 + Level 2 全部 step 都列出来,Level 0 真跑(pytest + offline smoke),Level 1/2 因 env guard 未 truthy 全 SKIP 带 reason。这一条命令完整覆盖 §6.1 + §6.2 + §6.3。

**预期产出**:

- exit 0(无 [FAIL])
- stdout JSON:7 个 step
  - L0 `pytest`:[OK] + pytest_summary `"1123 passed in <Ns>"`(数量以实测为准,≥ 1123 即合理)
  - L0 `offline-bundle-smoke`:[OK]
  - L1 `live-llm-character-extract`:[SKIP] reason `"opt-in env FORGEUE_VERIFY_LIVE_LLM not truthy ({1,true,yes,on} required)"`
  - L2 `live-mesh-generation`:[SKIP] 同模式
  - L2 `live-ue-export`:[SKIP] 同模式
  - L2 `live-comfy-pipeline`:[SKIP] 同模式
- 报告落 `openspec/changes/fuse-openspec-superpowers-workflow/verification/verify_report.md`
  - 12-key frontmatter `evidence_type: verify_report` / `stage: S5` / `aligned_with_contract: true` / `drift_decision: null` / `detected_env: claude-code` / `triggered_by: cli-flag` / `codex_plugin_available: true`
  - body 含 7 step + summary("[OK]: 2 / [FAIL]: 0 / [SKIP]: 4")

**耗时**:~45s(pytest 全跑约 35-40s + offline smoke 约 5s + tool 开销 < 5s)。

**注意事项**:

- pytest 子进程 cwd 是 repo 根,会跑 **全部 1123 test**;不会因为本 change 范围窄而仅跑 forgeue 子集
- offline smoke 走 `examples/mock_linear.json`(无 API key),不会触发付费 provider
- 4 个 Level 1/2 step 是 SKIP 不是 FAIL — finish_gate 不会因为 Level 1/2 SKIP 阻 archive
- verify_report.md 自动写入 verification/(no need 手动改)
- `verify_report` evidence_type 是 base REQUIRED 三项之一(per design.md §3 "REQUIRED at archive"),P5 完成意味着这个 slot fulfilled

## P5 完成判定 + 标 [x]

跑完 + 看 stdout / verify_report.md 满足上述预期,即标 tasks.md §6.1-§6.3 全 [x]。

```diff
- - [ ] 6.1 `python tools/forgeue_verify.py --level 0 --change fuse-openspec-superpowers-workflow --json` 全绿
- - [ ] 6.2 Level 1/2 显式 SKIP(本 change 不需要 LLM/UE/ComfyUI live)+ SKIP reason 写入 verify_report
- - [ ] 6.3 `verification/verify_report.md` 落盘 + frontmatter `aligned_with_contract: true`
+ - [x] 6.1 `python tools/forgeue_verify.py --level 0 --change fuse-openspec-superpowers-workflow --json` 全绿(2026-04-XX:Level 0 [OK]+[OK],pytest = NNNN passed)
+ - [x] 6.2 Level 1/2 显式 SKIP(本 change 不需要 LLM/UE/ComfyUI live)+ SKIP reason 写入 verify_report(L1 + 3×L2 全 SKIP,reason `opt-in env FORGEUE_VERIFY_LIVE_* not truthy`)
+ - [x] 6.3 `verification/verify_report.md` 落盘 + frontmatter `aligned_with_contract: true`(commit <sha>)
```

## P5 完成后(下阶段 = P6 Documentation Sync)

P6 工作量:中等(~20-30 min):

```
- [ ] 7.1 python tools/forgeue_doc_sync_check.py --change <id> --json 取标签
- [ ] 7.2 调 docs/ai_workflow/README.md §4.3 提示词
- [ ] 7.3 用户确认 [REQUIRED] 项后应用 patch
- [ ] 7.4 verification/doc_sync_report.md 落盘 + DRIFT 0 + REQUIRED 全应用
- [ ] 7.5.1-12 12 项 checklist(README/CHANGELOG/CLAUDE/AGENTS REQUIRED + 其他 SKIP)
```

P6 关键产物:对 README / CHANGELOG / CLAUDE.md / AGENTS.md / openspec/specs/examples-and-acceptance/spec.md 应用 patch(写回 ForgeUE Integrated AI Change Workflow 描述 + 命令清单)。

之后:**P7 Review** → **P8 Finish Gate** → **P9 Archive**。

## P5 起点 git 状态(2026-04-27 末)

```
HEAD: 2aceee3 docs: backfill writeback_commit in P4 review evidence
本地领先 origin/chore/openspec-superpowers: 8 commits(P0-P4 全部 milestone)
working tree:
  ?? openspec/changes/fuse-openspec-superpowers-workflow/verification/(P3 self-test 中间态产物,非 P5 工作必需,可清可留)
```

可选清理:`rm -rf openspec/changes/fuse-openspec-superpowers-workflow/verification/`(注意:这个 dir 即将被 forgeue_verify 写入 verify_report.md;清掉无副作用,tool 会自动重建)。

P5 起步后产物:
- `openspec/changes/fuse-openspec-superpowers-workflow/verification/verify_report.md`(forgeue_verify 自动生成)
- `tasks.md` §6.1-§6.3 全 [x]
- 1 个 commit:`chore: P5 verify_report landed for fuse-openspec-superpowers-workflow`

## ForgeUE memory 精神(P5 必遵守)

- `feedback_no_silent_retry_on_billable_api`:Level 1/2 失败时 surface job_id,不 silent retry(本 change Level 1/2 全 SKIP,这条不会被触发,但工具实装本身已守门 — `forgeue_verify.run_step` 在 mesh 失败时正则提取 job_id)
- `env_windows`:`/tmp/...` 是 C: 系统目录,产物落 `./demo_artifacts/` / `./artifacts/`;forgeue_verify offline smoke 用默认 `--run-id forgeue_verify_smoke` 落 `./artifacts/<today>/forgeue_verify_smoke/`(在 `.gitignore` 中)
- `user_language_chinese`:中文沟通,技术名词保留英文
- `feedback_decisive_approval`:P5 一条命令搞定;若 SKIP reason / report 路径出意料外结果再问用户
- `feedback_verify_external_reviews`:P5 不调 codex review(verify_report 不属 review evidence);此条仅 P7 用

## 禁令(P5 必遵守)

- **禁修区**:
  - `.claude/commands/opsx/*` / `.claude/skills/openspec-*/`(OpenSpec 默认产物)
  - 五件套(SRS/HLD/LLD/test_spec/acceptance_report;P5 不动文档,P6 才走 Documentation Sync Gate)
  - `pyproject.toml` deps(stdlib only)
  - 已 archived changes
  - **本 change 的 design.md / proposal.md / tasks.md(除标 §6 [x])**:P5 不再回写 contract;contract 已在 P4 codex review 写回 stable
- **禁创**:
  - 不创新 evidence_type(verify_report 是 stage S5 the only product)
  - 不创新 review evidence(P5 不调 codex)
- **行为约束**:
  - 不引入 paid provider / live UE / live ComfyUI 默认调用(env guard `{1,true,yes,on}`,本 change 默认 Level 2 一律 SKIP)
  - 不 mock pytest(forgeue_verify spawn 真子进程跑 pytest)
  - 不硬编码 pytest 总数(参考 §5.6.3 fence)
  - 7 ASCII 标记(`[OK] [FAIL] [SKIP] [WARN] [DRIFT] [REQUIRED] [OPTIONAL]`),无 emoji
  - 不调 `/codex:rescue` 在工作流内(违 review-only)
