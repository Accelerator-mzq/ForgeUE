---
change_id: comfy-agent-cli-video-adoption
stage: S3
evidence_type: codex_plan_review
contract_refs:
  - execution/execution_plan.md
  - execution/micro_tasks.md
  - design.md
  - tasks.md
  - specs/provider-routing/spec.md
  - specs/runtime-core/spec.md
  - specs/artifact-contract/spec.md
  - specs/examples-and-acceptance/spec.md
  - specs/probe-and-validation/spec.md
  - specs/ue-export-bridge/spec.md
detected_env: claude-code
triggered_by: "/forgeue:change-apply (S3→S4-S5 transition;Superpowers executing-plans + TDD pending) → /codex:adversarial-review --background"
codex_plugin_available: true
plugin_task_id: bsdglo1b3
verdict: needs-attention
findings_count: 4
findings_severity_breakdown: "high=1, medium=3"
created_at: 2026-05-04T12:30:00+08:00
codex_completed_at: 2026-05-04T12:50:00+08:00
aligned_with_contract: false
drift_decision: written-back-to-design+specs+tasks+proposal+runner.py (4 findings 全 accepted-codex;PF1 用户拍板路径 (a) → ComfyUI runner.py user-authored extension 已实施;commit 1185377 含全部 round-3 修订)
writeback_commit: 11853772fcc909ddc17f945a7c41596e94fa935b
drift_reason: "PF1 (high) requires user-level decision on whether to extend D:/AI/ComfyUI/scripts/comfyui_api/runner.py (user-authored ComfyUI shared dir, 沿 round 5 D10 mini-LoadImage 模式) or implement ForgeUE-side fallback parsing outputs.raw"
reasoning_notes_anchor: "design.md `## Reasoning Notes — round-3 codex plan review (2026-05-04)` (待 PF1 决策后写)"
note: |
  本文件是 codex /codex:adversarial-review --background 的 verbatim 输出 (codex thread 019df...),
  落盘以备 finish gate / cross-check 引用。Claude resolution / 独立验证 / writeback 详情见
  `review/plan_cross_check.md` `## B / C / D` 段。
  
  PF1 (high) 是 critical blocker:实测 D:/AI/ComfyUI/scripts/comfyui_api/runner.py
  `extract_outputs` 只返回 {images, audio, glb, raw} — 无 video key。Wan T2V 7-min
  跑会被 `_validate_outputs` 判 missing outputs.video,后续 executor + UE import
  全部断链。两条修复路径:(a) 扩 runner.py 加 video 收集(user-authored ComfyUI
  shared dir 修改,沿 round 5 D10 mini-LoadImage 模式必须用户授权);(b) ForgeUE
  worker 端走 outputs.raw 提取 video paths(脆弱 — 需要假设 VHS_VideoCombine 节点
  输出 shape;若 ComfyUI 升级 VHS 节点,worker 端可能挂)。
  
  PF2 / PF3 / PF4 (medium) 不阻断设计层,可在 writeback round 修。
---

# Codex Plan Adversarial Review (verbatim)

## Codex output

Target: working tree diff
Verdict: needs-attention

不建议进入 S4/S5:计划仍把当前 CLI 不会产出的 `outputs.video` 当成已确认事实,且 mp4-only 与 BMFF 严格校验合同还有会误导实现的硬漏洞。

Findings:

- [high] `outputs.video` 被当成已确认,但当前 CLI 不会产出这个 key (openspec/changes/comfy-agent-cli-video-adoption/tasks.md:29-30)
  `tasks.md` 把 OQ-1/OQ-2 写成 S2→S3 阻塞项,但同一段又说真实 `comfyui_api run` 样例留到 implementation 且"不阻断 S3"。我打开了该行引用的 `D:/AI/ComfyUI/scripts/comfyui_api/runner.py::extract_outputs`,当前实现只收集并返回 `images` / `audio` / `glb` / `raw`,没有 `video` key。按计划在 commit 4 加 `_REQUIRED_OUTPUT_KEY["video"] = "video"` 后,真实 Wan 运行会在约 7 分钟生成后被 `_validate_outputs` 判定为 missing `outputs.video`,后续 executor 和 UE import 全部无法走通;只靠 mock fence 会漏掉这个 live 断点。
  Recommendation: 把 OQ-1 改回真正的 S4 前阻塞项:先补/验证 `comfyui_api.runner.extract_outputs` 的 video 提取,或让 worker 从 `outputs.raw`/manifest `outputs.primary` 派生 video 路径;增加一个基于真实 runner stdout shape 的 fence 后再实施 commit 4。

- [medium] BMFF `box_size == 1` 分支会放过伪造的短 mp4 (openspec/changes/comfy-agent-cli-video-adoption/design.md:273-306)
  计划中的 BMFF 校验允许 `box_size == 1`,但没有解析 64-bit `largesize`。在 ISO BMFF 中 size=1 时 bytes 8-15 是 largesize,brand 数据应从 byte 16 开始;当前伪代码仍用 `data[8:12]` 当 `major_brand`,且只要求 `len(data) >= 16`。因此一个 16-byte 伪 header(size=1、ftyp、非零 largesize 字节、没有真实 major_brand)会通过"strict"校验,直到 UE FileMediaSource import 才失败。`test_generate_video_bmff_box_size_largesize_1_accepted` 还会把这个漏洞固化成通过条件。
  Recommendation: 本 change 最简单做法是拒绝 `box_size == 1` 并登记 follow-on;若要支持 largesize,必须要求 `len(data) >= 24`,解析 `largesize = int.from_bytes(data[8:16], 'big')` 并校验范围,然后用 `data[16:20]` 检查 `major_brand`,同步改 fence 名和 L2 evidence 规则。

- [medium] round-2 mp4-only writeback 未完成,spec/proposal 仍允许 webm (openspec/changes/comfy-agent-cli-video-adoption/specs/provider-routing/spec.md:7)
  `provider-routing` 的顶层 Requirement 仍声明 `VideoCandidate.format: Literal["mp4", "webm"]`,而后面的 Scenario 又要求 mp4-only 并拒绝 webm;`proposal.md` 同样还保留 `format: Literal["mp4", "webm"]`、`{mp4, webm}` whitelist 和 webm magic bytes 文案。实现者按顶层 Requirement 写会让 webm candidate 进入 executor,但 UE bridge 只映射 `("video", "mp4")`,最终要么被错误标成 mp4,要么在 manifest/UE 阶段失败;按后续任务写则 archive 后留下自相矛盾的行为契约。
  Recommendation: 在进入 implementation 前,把 provider-routing spec 和 proposal 中所有 webm 接受路径改成 `Literal["mp4"]` / mp4-only;webm 只能以 follow-on 名称出现,不能出现在当前 change 的 accepted formats、magic 校验或 worker whitelist 中。

- [medium] TDD 计划假设 dataclass 会校验 `Literal`,commit 2 按原样无法变绿 (openspec/changes/comfy-agent-cli-video-adoption/tasks.md:56-104)
  `tasks.md` 要求 `VideoCandidate` 是普通 `@dataclass`,但 `test_video_candidate_format_whitelist_mp4_only` 又要求 `format="webm"` / `"mov"` 触发 dataclass `Literal["mp4"]` 校验失败。Python dataclass 不会运行时校验 `Literal`;仓库现有 `tests/unit/test_audio_worker.py` 已明确写明 audio 的 `Literal` 不做 runtime enforcement,实际守门在 worker 层。因此 commit 2 的 fence 要么无法通过,要么实现者必须临时引入未写入计划的 `__post_init__`/Pydantic 行为;若放松测试,非 Comfy worker 仍可构造 webm candidate,破坏 mp4-only invariant。
  Recommendation: 明确选择 enforcement 层:若要 candidate 构造即拒绝,任务和 spec 应要求 `VideoCandidate.__post_init__` 对 `format != "mp4"` raise `ValueError` 并把 fence 断言改成该错误;若沿 audio 模式,则删除 dataclass 构造拒绝要求,只在 `_run_once_video` 扩展名/BMFF 边界拒绝。

Next steps:
- 先修正 OQ-1 blocking probe、BMFF largesize 规则、mp4-only 合同和 dataclass enforcement 语义,再进入 S4/S5 implementation。
- 补一个基于当前 `comfyui_api.runner.extract_outputs` 真实输出 shape 的回归 fence,避免只用 mock 验证 `outputs.video`。

---

## Codex tool calls trace (excerpt)

```
[codex] Starting Codex task thread (codex 实际跑了 ~30 个 PowerShell rg / Get-Content 命令).
[codex] Critical verifications:
  - Get-Content -Raw D:/AI/ComfyUI/scripts/comfyui_api/runner.py (PF1 verify extract_outputs shape)
  - rg -n "VideoCandidate|format.*Literal" tests/unit/test_audio_worker.py (PF4 verify audio dataclass behavior)
  - rg -n "Literal\\[\"mp4\", \"webm\"\\]" openspec/changes/comfy-agent-cli-video-adoption/specs/provider-routing/spec.md (PF3 verify webm leak in spec line 7)
  - rg -n "box_size == 1" openspec/changes/comfy-agent-cli-video-adoption/design.md (PF2 verify largesize handling)
[codex] Assistant message: verdict=needs-attention, 4 findings (1 high + 3 medium).
```

Codex thread id 019df... — codex 调用了 ~30 个 PowerShell rg / Get-Content 命令交叉验证 plan / spec / design / 真实 runner.py 源码,所有 finding location claim 都给了具体 file:line + 实际 source 引用。

---

## Claude post-codex action summary

Verdict-driven:`needs-attention`(1 high + 3 medium)。

- **PF1 (high)** — critical blocker,需要用户决策修复路径(扩 ComfyUI runner.py vs ForgeUE-side workaround);Claude **STOP** implementation pending user direction
- **PF2 (medium)** — accepted-codex,简化为「拒绝 box_size==1 + follow-on `video-bmff-largesize-support`」(largesize 极少在 standard mp4 出现,Wan T2V 标准输出不会用)
- **PF3 (medium)** — accepted-codex,sweep spec/provider-routing line 7 + proposal.md 全部 webm 残留改为 mp4-only
- **PF4 (medium)** — accepted-codex,沿 audio Phase 2 模式选 (b) — 删除 dataclass 构造拒绝 fence,改测「dataclass accept mp4 + 异常路径在 worker 层 _run_once_video 扩展名 / BMFF 边界拒绝」

详细 cross-check 在 `review/plan_cross_check.md` `## B/C/D` 段。Claude 完成 PF2-PF4 writeback 后等用户回 PF1 修复路径。`disputed_open: 0`(全 accepted-codex,无 disputed)。
