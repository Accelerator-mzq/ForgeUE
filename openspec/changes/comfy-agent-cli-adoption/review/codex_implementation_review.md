---
change_id: comfy-agent-cli-adoption
stage: S5
evidence_type: codex_implementation_review
contract_refs:
  - design.md
  - tasks.md
  - specs/provider-routing/spec.md
  - specs/runtime-core/spec.md
  - specs/probe-and-validation/spec.md
prev_round_writeback_commit: 6ad798c
plugin_command: "/codex:adversarial-review --background --base 25b0c5c (production code review)"
plugin_task_id: "thread 019de946-6994-7080-8a7a-c8be6281b074 (Claude task id bdliv8u4m)"
detected_env: claude-code
triggered_by: forgeue-change-review
codex_plugin_available: true
created_at: 2026-05-03T01:30:00+08:00
aligned_with_contract: false
drift_decision: written-back-to-multiple-pending
note: |
  G11 stage codex production-code review on full G2-G10 commit chain
  (base 25b0c5c, HEAD 6ad798c). Verdict: needs-attention,
  recommendation: blocker-stop (5 findings: 1 high + 4 medium).
  Apply Lean Apply Mode meant per-commit codex was skipped; this is
  the consolidated review.
---

# Codex Adversarial Review — G11 Implementation (verbatim)

Target: branch diff against 25b0c5c
Verdict: needs-attention
Recommendation: **blocker-stop**

不建议归档:发现 5 个材料性问题,分布为 high=1、medium=4。建议 blocker-stop,先修运行时解码/文件边界问题,再做 OpenSpec 写回。

## R-Findings

### [high] R1 — Windows 非 ASCII stdout 可绕过结构化失败处理
**File**: `src/framework/providers/workers/comfy_worker.py:402-408`

`subprocess.run(..., text=True)` 未指定 `encoding`/`errors`。在 Windows 上会按本机 locale 解码;如果 `comfyui_api` 输出 UTF-8 JSON,且 error/path/workflow 含非 ASCII,`subprocess.run` 可能在返回前抛 `UnicodeDecodeError`。当前只捕获 `TimeoutExpired` 和 `FileNotFoundError`,该异常不会进入 JSON 解析,也不会被 `FailureModeMap` 分类,live run 会以未结构化异常崩掉。`probe_sync` 也有同样模式。

**Recommendation**: 改为 `capture_output=True` 后按 UTF-8 显式解码并捕获 `UnicodeDecodeError`,或在 `subprocess.run` 上指定 `encoding="utf-8", errors="replace"`;异常应映射为 `WorkerUnsupportedResponse`,并补非 ASCII stdout/path fence。

### [medium] R2 — outputs.images 被当作可信文件路径复制
**File**: `src/framework/providers/workers/comfy_worker.py:492-501`

CLI 返回的每个 `src_str` 只经过 `Path(src_str).is_file()` 检查,随后 `shutil.copy2` 会跟随 symlink,并把 `src.name` 复制到 artifact tree,再直接读作 image bytes。一个 buggy 或被 workflow 影响的 agent CLI 可以返回任意可读文件路径或输出目录中的 symlink,导致 ForgeUE 把非图片/敏感文件复制进 artifacts;也没有 basename 冲突处理或 PNG 签名校验。

**Recommendation**: 对 `src.resolve(strict=True)` 做 allow-list 校验(至少限定在 ComfyUI outputs root 或显式配置 root 下),拒绝 symlink/junction,生成唯一目标文件名,并校验图片后缀/PNG 魔数;为 symlink 和非图片路径加 fence。

### [medium] R3 — 缺少 checkpoint root 时会把 run_dir 静默降级到 cwd
**File**: `src/framework/runtime/orchestrator.py:109-112`

`_compute_run_dir` 在 `CheckpointStore._root` 为空时返回 `Path(".")`。这会被 Orchestrator 注入生产 `StepContext`,而 `ComfyAgentWorker` 会接受已有 cwd 并写入 `./comfy`。因此任何直接使用 in-memory `CheckpointStore` 的 live comfy/local 调用都会把产物落到进程 cwd,破坏 `<artifact_root>/<run_id>` 自包含、resume 和 archive 假设。注释说这是 test-mock convenience,但代码没有生产 guard。

**Recommendation**: 让 `_compute_run_dir` 在 `_root is None` 时 fail fast(或要求调用方显式传 artifact root);测试 mock 继续直接构造 `StepContext(run_dir=tmp_path)`,不要通过 Orchestrator 生产路径隐式返回 `Path('.')`。

### [medium] R4 — G4 sync worker drift 未写回 provider-routing spec
**File**: `openspec/changes/comfy-agent-cli-adoption/specs/provider-routing/spec.md:77-83`

Delta spec 仍声明 `_generate_via_worker` 通过 `asyncio.run(...)` 调用 async `worker.submit`。实际代码已改为同步 `ComfyAgentWorker.generate`,`ComfyWorker` ABC 也只暴露 sync `generate`。这会把不存在的 async contract 归档进主 spec,后续实现/测试可能按错误接口补功能。

**Recommendation**: 把 provider-routing spec、tasks 和 execution_plan 中的 `submit`/`asyncio.run` 文字全部改为 sync `generate(...)`;或者反向改代码匹配 async contract。归档前加 grep fence,禁止残留 `worker.submit`/`_aworker_call`。

### [medium] R5 — dry-run warning 决策与场景仍互相矛盾
**File**: `openspec/changes/comfy-agent-cli-adoption/specs/provider-routing/spec.md:91-99`

同一 requirement 的实现说明已经说 probe failure 只写 `warnings` 且不阻塞 `report.passed`,但紧接的场景仍要求 Run 立即 failed,且不进入实际 generation。生产代码在 `DryRunPass._check_comfy_reachability` 中确实 warning-only 返回;归档后 spec 会同时承诺两种相反行为。

**Recommendation**: 按 G8 决策重写场景:dry-run 对缺 env/probe fail 只 warning;另补一个 live-run fence,证明 env unset 或 probe 真失败时 step-time `ComfyAgentWorker` 失败会进入 `unsupported_response`/终止路径。

## Counter
- high: 1 (R1)
- medium: 4 (R2, R3, R4, R5)
- **Total: 5 findings**
- Recommendation: blocker-stop
