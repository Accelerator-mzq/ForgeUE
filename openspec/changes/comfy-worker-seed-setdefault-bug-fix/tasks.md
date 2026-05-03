# Tasks — comfy-worker-seed-setdefault-bug-fix

## 1. Code fix

- [x] 1.1 [src/framework/providers/workers/comfy_worker.py:442](src/framework/providers/workers/comfy_worker.py#L442)(image generate loop)`params_for_call.setdefault("seed", call_seed)` → `params_for_call["seed"] = call_seed`(直接覆盖);加注释说明 G11-F3 同模式 fix(audio 已修,本 change 同步 image)
- [x] 1.2 [src/framework/providers/workers/comfy_worker.py:703](src/framework/providers/workers/comfy_worker.py#L703)(mesh generate loop)同样改

## 2. Fences

- [x] 2.1 [tests/unit/test_comfy_subprocess.py](tests/unit/test_comfy_subprocess.py) 加 `test_generate_image_per_candidate_seed_overrides_comfy_params_seed` — PASS
- [x] 2.2 [tests/unit/test_comfy_subprocess.py](tests/unit/test_comfy_subprocess.py) 加 `test_generate_mesh_per_candidate_seed_overrides_comfy_params_seed` — PASS

## 3. Verify

- [x] 3.1 `python -m pytest tests/unit/test_comfy_subprocess.py -v -k "seed_overrides"` 两个新 fence PASS
- [x] 3.2 `python -m pytest -q` 全套实测 1299 passed(+5 over prior 1294 baseline:2 seed override fence + 3 latent fence resolution evidence_type fix)

## 4. Commit

- [x] 4.1 commit 1:`fix(comfy): per-candidate seed override in image+mesh paths (G11-F3 follow-on)`

## 5. Doc sync

- [x] 5.1 不需要(本 change 是行为正确性 fix,不改 contract / spec / docs)
- [x] 5.2 latent doc fix:archive `cross_check_g6.md` / `cross_check_g11.md` `evidence_type: cross_check` → `implementation_cross_check`(满足 `test_real_cross_check_files_have_evidence_type` fence;本 change 跑全套 pytest 时 catch)

## 6. Archive

- [ ] 6.1 `tools/forgeue_finish_gate.py --change comfy-worker-seed-setdefault-bug-fix` exit 0
- [ ] 6.2 `openspec validate comfy-worker-seed-setdefault-bug-fix --strict` PASS
- [ ] 6.3 `openspec archive comfy-worker-seed-setdefault-bug-fix --yes`
