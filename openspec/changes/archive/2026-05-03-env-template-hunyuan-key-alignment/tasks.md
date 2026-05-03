# Tasks — env-template-hunyuan-key-alignment

## 1. Code fix

- [x] 1.1 `.env.example:81-83` 删除 `HUNYUAN_3D_SECRET_ID/SECRET_KEY/REGION` 三段 placeholder + 加 `HUNYUAN_3D_KEY=sk-your-hunyuan-tokenhub-bearer-token` placeholder + cross-ref 注释

## 2. Verify

- [x] 2.1 `python -m pytest -q` baseline 1299 不退化

## 3. Commit

- [x] 3.1 commit:`docs(.env.example): align HUNYUAN_3D_* template with runtime Bearer auth`

## 4. Archive

- [x] 4.1 finish gate exit 0
- [x] 4.2 `openspec validate --strict` PASS
- [x] 4.3 `openspec archive --yes`
