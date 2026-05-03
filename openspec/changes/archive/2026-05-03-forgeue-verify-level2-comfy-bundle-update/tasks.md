# Tasks — forgeue-verify-level2-comfy-bundle-update

## 1. Code fix

- [x] 1.1 `tools/forgeue_verify.py:174-189` 替换 `live-comfy-pipeline` 步骤为三个 capability-specific 步骤(image / mesh / audio)
- [x] 1.2 `tools/forgeue_verify.py` 顶部 docstring Level 2 env var 说明扩展(加 `_COMFY_MESH` / `_COMFY_AUDIO` + `FORGEUE_COMFY_SCRIPTS_DIR` / `FORGEUE_COMFY_INPUT_DIR` 环境依赖)

## 2. Verify

- [x] 2.1 `python -m pytest -q` baseline 不退化
- [x] 2.2 `python tools/forgeue_verify.py --level 0 --json --dry-run` smoke run 不崩(本 change 加 step 不影响 Level 0)

## 3. Commit

- [x] 3.1 commit:`fix(forgeue_verify): split Level 2 Comfy step into image+mesh+audio (G6-F1)`

## 4. Archive

- [x] 4.1 finish gate exit 0
- [x] 4.2 `openspec validate --strict` PASS
- [x] 4.3 `openspec archive --yes`
