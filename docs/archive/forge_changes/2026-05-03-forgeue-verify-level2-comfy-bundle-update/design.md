# Design — forgeue-verify-level2-comfy-bundle-update

## 1. Context

`forgeue_verify.py` 是 ForgeUE Integrated AI Workflow 的 verification 工具
(Level 0 / 1 / 2 编排,产 verify_report.md)。Level 2 是 opt-in live-call 验证,
原本设计为各 paid / live API 跑一次真实 bundle。其中 `live-comfy-pipeline` 步骤在
v1.5(HTTP `/prompt` + `/history`)时代写,v1.6 改 agent CLI subprocess 后未同步,
持续假阳性了几个月。

## 2. Decisions

**D1**:把单个 Comfy Level 2 步骤拆成 3 个 capability-specific 步骤(image / mesh /
audio),理由:
- 三 capability 的运行依赖不同(mesh 需 `FORGEUE_COMFY_INPUT_DIR`,audio / image 不需要)
- 用户可能只想验某一个(如装了 audio 模型权重但没下 mesh 主模型)
- 与现有的 mesh / UE 步骤的"每个 paid API 一个 env var"一致

**D2**:env var 命名沿用 `FORGEUE_VERIFY_LIVE_*` 前缀:
- `FORGEUE_VERIFY_LIVE_COMFY` 复用(image,本来就指 ComfyUI;不破 backward compat
  spirit — 行为从假阳性改成真验证 = bug fix 而非破坏)
- `FORGEUE_VERIFY_LIVE_COMFY_MESH` 新增
- `FORGEUE_VERIFY_LIVE_COMFY_AUDIO` 新增

**D3**:不删 `--comfy-url` 命令行参数(`framework.run` 内已处理 deprecated 静默
忽略;本 change 不动 framework.run)。verify 工具不再传 `--comfy-url` 即足够。

## 3. Risk

**Mild breaking**:用户旧 CI 跑 `FORGEUE_VERIFY_LIVE_COMFY=1` 不带 ComfyUI server
/ `FORGEUE_COMFY_SCRIPTS_DIR` env 时,现在 step fail 而非假 PASS。这是预期的
"不再说谎"行为,但需要 CHANGELOG.md / CLAUDE.md 提醒(本 change 仅修工具,不改文档;
follow-on 提醒可走 CHANGELOG Unreleased 但本 change scope 不必)。

实际影响面窄:`FORGEUE_VERIFY_LIVE_COMFY` opt-in env var,默认不开。

## 4. Migration

- 用户继续用 `FORGEUE_VERIFY_LIVE_COMFY=1`:必须 ComfyUI server up + `FORGEUE_COMFY_SCRIPTS_DIR`
  env(per CLAUDE.md 双终端 setup),否则 step fail
- 想验 mesh / audio:set 对应新 env var

## 5. Scope discipline

本 change 只动 `tools/forgeue_verify.py`(~40 行)。**不**动 framework.run /
ComfyAgentWorker / examples/* / docs。
