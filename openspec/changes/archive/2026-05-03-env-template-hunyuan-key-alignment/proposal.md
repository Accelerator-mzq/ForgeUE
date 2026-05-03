# Proposal — env-template-hunyuan-key-alignment

## Why

`.env.example:81-83` 模板列 TC3-HMAC-SHA256 三段 env var(`HUNYUAN_3D_SECRET_ID` /
`HUNYUAN_3D_SECRET_KEY` / `HUNYUAN_3D_REGION`),但运行时实际读 Bearer `HUNYUAN_3D_KEY`
单 key([config/models.yaml:95](config/models.yaml#L95) `api_key_env: HUNYUAN_3D_KEY`,
[src/framework/run.py:100](src/framework/run.py#L100) `_os.environ.get("HUNYUAN_3D_KEY")`,
[src/framework/providers/workers/mesh_worker.py:335](src/framework/providers/workers/mesh_worker.py#L335)
`Authorization: Bearer <HUNYUAN_3D_KEY>`)。模板与运行时不一致 → 用户照模板配 `.env`
→ Hunyuan 3D 路由拿不到 key → fall back FakeMeshWorker / Tripo / provider auth 失败。

Codex G6-F4 finding(`comfy-agent-cli-audio-adoption` 2026-05-03)catch 此 drift。

## What Changes

- **MODIFIED**:`.env.example:81-83` — 删 TC3-HMAC-SHA256 三段 placeholder + 加 Bearer
  `HUNYUAN_3D_KEY=sk-...` placeholder + 注释说明 runtime 实读字段及 cross-reference

## Impact

- **Breaking**:无(模板只影响新 user 首次 setup;现有 `.env` 已配 `HUNYUAN_3D_KEY`
  的环境完全不受影响)
- **Affected specs**:无 spec 变更(仅文档模板修复)
- **Affected code**:`.env.example` 一文件 4-5 行
- **Affected tests**:无(新加 spec delta 提供 minimum requirement,无新 fence)
- **L0 baseline**:1299 不变

## References

- 起源:[archive/2026-05-03-comfy-agent-cli-audio-adoption/review/codex_verification_review.md](../archive/2026-05-03-comfy-agent-cli-audio-adoption/review/codex_verification_review.md) G6-F4
- 起源 cross-check:[archive/2026-05-03-comfy-agent-cli-audio-adoption/review/cross_check_g6.md](../archive/2026-05-03-comfy-agent-cli-audio-adoption/review/cross_check_g6.md) G6-F4
- 实际 runtime 读法:[src/framework/run.py:100](src/framework/run.py#L100)
- 实际 yaml 配置:[config/models.yaml:95](config/models.yaml#L95)
