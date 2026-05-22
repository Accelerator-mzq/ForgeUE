# Design — comfy-agent-cli-path-containment-hardening

## 1. Context

Phase 1 mesh + Phase 2 audio adoption 共建立了 ComfyAgentWorker 三 capability 路径
(image / mesh / audio),三处都从 ComfyUI subprocess 的 stdout JSON 读 output paths
然后 read_bytes。Codex G11-F2(2026-05-03 audio adoption mixed-scope adversarial
review)指出现有 trust boundary(`is_file()` + `is_symlink()` + extension whitelist
+ magic bytes)不足以挡住 ComfyUI 返回 install tree 外路径的场景。

R7-C `disputed-permanent-drift / accepted-claude` 立场承诺 follow-on 三 capability
同步加 containment。本 change 兑现该承诺。

## 2. Decisions

**D1**:`comfy_output_root` resolution 两层:
- env var `FORGEUE_COMFY_OUTPUT_ROOT` 显式 override(production 推荐配置项 — user
  ComfyUI install 在非默认位置时必填)
- heuristic fallback `scripts_dir.parent` —
  - 真实 ComfyUI:`scripts_dir = D:/AI/ComfyUI/scripts`,parent = `D:/AI/ComfyUI`,
    outputs 在 `D:/AI/ComfyUI/outputs/main/...` 都被覆盖 ✓
  - tests:`scripts_dir = tmp_path/scripts`,parent = `tmp_path`,fake outputs 直接
    放 `tmp_path/out_*.png/.glb/.flac` 都被覆盖 ✓
- **决策不用** `scripts_dir.parent / "outputs"`(更紧的 boundary)因为 tests fake
  outputs 不在 outputs/ 子目录,会失败;且 scripts_dir.parent 是 ComfyUI install
  根,custom_nodes 也在该树下,production 实际威胁面**已经**是 install root 内
  路径任何位置(即使 outputs/ 子目录限制无意义,因为 ComfyUI 自己可以写 anywhere
  under install root)

**D2**:helper `_assert_path_within_comfy_output_root(src, output_kind)` 集中
containment logic:
- `Path.resolve()` 先 normalise symlinks / relative segments
- `is_relative_to()`(Python 3.9+)check
- raise `WorkerUnsupportedResponse` with explicit error message + hint to
  `FORGEUE_COMFY_OUTPUT_ROOT` env

**D3**:三 capability 同步加(symmetry argument 关键):
- 加在 magic bytes 之前(read_bytes 之前)
- 错误消息引用 `output_kind="images"` / `"glb"` / `"audio"` 区分

**D4**:**不**改 audio executor / generate_image executor / generate_mesh executor
— containment 在 worker 层,executor 层无需改。

**D5**:不引入新 env var 默认值(用 heuristic fallback);user 可选配置
`FORGEUE_COMFY_OUTPUT_ROOT` 收紧 boundary。

## 3. Risk

**Mild breaking risk**:
- 用户的 ComfyUI 在非默认位置(scripts_dir 与 outputs 不在同一 parent)时,
  heuristic fail → containment block valid output → step fail。Mitigation:
  user 显式设 `FORGEUE_COMFY_OUTPUT_ROOT` env。
- Tests 用 `tmp_path/scripts` + fake outputs 直接放 `tmp_path/...` 时 fall back
  正确(已 verified 1310 → 1313 fence pass)。

**No risk on real ComfyUI**:已 L2 PASS verified(`audio_smoke_path_containment_l2`
真实 1.17 MB FLAC 落地)。

## 4. Migration

- 用户:无须做事;heuristic fallback 覆盖默认 ComfyUI install 布局
- 异常布局:加 `FORGEUE_COMFY_OUTPUT_ROOT=<path>` 到 `.env`
- 旧 Artifact records:不受影响(只影响新 run 的写入路径校验)

## 5. Scope discipline

本 change 只动 `comfy_worker.py`(~30 行 + 1 helper)+ 2 test files(3 fence + 3 helper
docstring update)。**不**动 executor / examples / probes / docs(.env.example
follow-on 可独立加 env var 模板,scope 不必扩在此)。

## 6. References

- 起源:`archive/2026-05-03-comfy-agent-cli-audio-adoption` G11-F2(plan_task `b86swn4sj`)
- 已修代码 verified:[src/framework/providers/workers/comfy_worker.py](src/framework/providers/workers/comfy_worker.py)
  三处 `_assert_path_within_comfy_output_root` 调用
