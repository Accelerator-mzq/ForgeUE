# Design — env-template-hunyuan-key-alignment

## 1. Context

历史:Hunyuan 3D mesh provider 接入早期走腾讯云 TC3-HMAC-SHA256 签名(SECRET_ID +
SECRET_KEY + REGION 三段)。某次重构改为 hunyuan-tokenhub Bearer `sk-xxx` 单 key
认证,但 `.env.example` 模板未同步,残留三段 placeholder。

## 2. Decisions

**D1**:模板换为 Bearer 单 key 形式(运行时唯一支持模式),三段 SECRET 从模板里删除。

**D2**:加注释 cross-reference runtime 实读位置(`config/models.yaml:95` +
`src/framework/run.py:100`),后续若再发生 env var 改名,审计能直接 grep。

**D3**:不写 migration warning(用户照旧模板 `HUNYUAN_3D_SECRET_ID/KEY/REGION` 配的
env var 在 `.env` 里仍可保留,只是不被读 — 不会引发任何错误,只是空配)。

## 3. Risk

无。模板仅影响新 user 首次 setup;现有 production 无影响。

## 4. Migration

旧 `.env`(列 SECRET_ID/KEY/REGION 三段)继续工作 = 空配 = Hunyuan 3D fall back
Fake / Tripo。用户需手动加 `HUNYUAN_3D_KEY=sk-...` 才能用真实 Hunyuan 3D。这与本
change **无关**(本 change 只改 `.env.example` 模板,不动 runtime)。

## 5. Scope discipline

本 change 只动 `.env.example`。**不**改 `config/models.yaml` / `framework/run.py` /
`mesh_worker.py`(这些已经是正确的 source-of-truth)。
