## REMOVED Requirements

### Requirement: forgeue_verify.py Level 2 ComfyUI steps SHALL exercise the agent CLI subprocess path (NOT the deprecated HTTP path)

**Reason**:`tools/forgeue_verify.py` 工具在本 change 整 retire(B 路径整删 8 个 `tools/forgeue_*.py` 工具),Level 2 ComfyUI subprocess 验证的 wrapper 不再存在。

**Migration**:核心 contract(`comfy/local*` 虚拟模型 id + 禁止 `--comfy-url` flag + 禁止 LiteLLM wildcard fallback)以**工具无关版**保留为新 Requirement(见下方 ADDED 段),由 user 手工跑 `python -m framework.run --task examples/comfy_local_smoke{,_mesh,_audio,_video}.json --live-llm --run-id <id>` 替代。`docs/testing/test_spec.md` Level 2 章节文档化(从原 P9 optional 升 P3.5 必做)。

## ADDED Requirements

> **Round 1 codex P1-5 writeback**:原 `forgeue_verify.py Level 2 ComfyUI steps` Requirement 被 REMOVED + 新增**工具无关版** ADDED Requirement。原 Requirement 守的是 3 个 contract:`comfy/local*` 虚拟模型 id + 禁止 `--comfy-url` flag + 禁止 LiteLLM wildcard fallback(silently 退到 FakeComfyWorker → false-positive PASS)。Codex finding 验证后 confirmed:这是真业务契约不只是 wrapper 存在性。本 change 改 REMOVED + ADDED(MODIFIED 不可用因 header 改了 — OpenSpec MODIFIED 要求 header exact match):contract 保留,验证机制改 user 手工 pytest + framework.run + `docs/testing/test_spec.md` Level 2 章节文档化(从原 P9 optional 升 P3.5 必做)。

### Requirement: Level 2 ComfyUI verification SHALL dispatch via `comfy/local*` virtual model ids to the ComfyAgentWorker subprocess path (NOT the deprecated HTTP path)

The system SHALL ensure that Level 2 ComfyUI verification(image / mesh / audio / video capability)dispatches via bundles whose `provider_policy.models_ref` resolves to `comfy/local*` virtual model ids(`comfy/local` for image / `comfy/local-mesh` for mesh / `comfy/local-audio` for audio / `comfy/local-video` for video),so that the dispatch chain reaches the `ComfyAgentWorker` subprocess CLI path(`python -m comfyui_api ...`)defined in `src/framework/providers/comfy_agent_worker.py`. Level 2 verification commands MUST NOT pass the deprecated `--comfy-url` flag(silently ignored by `framework.run` and falls back to `FakeComfyWorker`),and MUST NOT use bundles whose only ComfyUI route is via the wildcard `LiteLLMAdapter` fallback(silently routed to `FakeComfyWorker` when no `comfy/local*` route is declared,producing false-positive PASS without exercising real ComfyUI subprocess).

The verification mechanism SHALL be **tool-agnostic**(自 `retire-forgeue-protocol-layer-fully` 起,2026-05-10):无 `tools/forgeue_verify.py` wrapper / 无 `_build_plan()` 内部清单。Level 2 验证由 user 手工跑 `python -m pytest` 或 `python -m framework.run` 命令:

- **Image** capability:`python -m framework.run --task examples/comfy_local_smoke.json --live-llm --run-id <id>`(bundle 含 `provider_policy.models_ref: image_local` 解析至 `comfy/local`)
- **Mesh** capability:`python -m framework.run --task examples/comfy_local_smoke_mesh.json --live-llm --run-id <id>`(bundle 解析至 `comfy/local-mesh`,需 `FORGEUE_COMFY_INPUT_DIR` env)
- **Audio** capability:`python -m framework.run --task examples/comfy_local_smoke_audio.json --live-llm --run-id <id>`(bundle 解析至 `comfy/local-audio`)
- **Video** capability:`python -m framework.run --task examples/comfy_local_smoke_video.json --live-llm --run-id <id>`(bundle 解析至 `comfy/local-video`)

User SHALL document the Level 2 verification matrix in `docs/testing/test_spec.md` Level 2 验证章节,包含 4 capability × bundle path × env requirement matrix + 显式提醒"禁止传 `--comfy-url` flag(silently FakeComfyWorker fallback);禁止用走 LiteLLM wildcard 的 bundle"。

#### Scenario: Level 2 image verification dispatches to ComfyAgentWorker

- **GIVEN** `FORGEUE_COMFY_SCRIPTS_DIR` env set + ComfyUI server is running
- **WHEN** user runs `python -m framework.run --task examples/comfy_local_smoke.json --live-llm --run-id <id>`
- **THEN** the bundle SHALL declare `provider_policy.models_ref: image_local` resolving to `comfy/local`
- **AND** framework dispatch SHALL hit `GenerateImageExecutor._should_use_worker_path() == True` and run via `ComfyAgentWorker.generate()` subprocess
- **AND** the command MUST NOT contain `--comfy-url` flag

#### Scenario: Level 2 mesh / audio / video verification dispatches to capability-specific ComfyAgentWorker subprocess

- **GIVEN** the corresponding env(mesh: `FORGEUE_COMFY_SCRIPTS_DIR` + `FORGEUE_COMFY_INPUT_DIR`;audio: `FORGEUE_COMFY_SCRIPTS_DIR`;video: `FORGEUE_COMFY_SCRIPTS_DIR`)
- **WHEN** user runs corresponding `python -m framework.run --task examples/comfy_local_smoke_<cap>.json --live-llm`
- **THEN** dispatch SHALL reach the capability-specific `ComfyAgentWorker.generate_<cap>()` subprocess
- **AND** the bundle SHALL resolve to `comfy/local-<cap>` (mesh / audio / video) virtual model id
- **AND** the command MUST NOT contain `--comfy-url` flag

#### Scenario: Stale bundle and deprecated flag SHALL NOT silently pass via wildcard fallback

- **GIVEN** the Level 2 verification matrix documented in `docs/testing/test_spec.md`
- **WHEN** any developer or audit reads the matrix
- **THEN** the matrix MUST NOT contain any `--comfy-url` flag in command examples
- **AND** the matrix MUST NOT reference `examples/image_pipeline.json` as a Level 2 target(deprecated by `comfy-agent-cli-adoption` v1.6;silently falls back to `FakeComfyWorker`)
- **AND** the matrix SHALL display the warning "禁止传 `--comfy-url` flag;禁止用走 LiteLLM wildcard 的 bundle(否则 silently FakeComfyWorker fallback,verification 变成 false-positive PASS)"
