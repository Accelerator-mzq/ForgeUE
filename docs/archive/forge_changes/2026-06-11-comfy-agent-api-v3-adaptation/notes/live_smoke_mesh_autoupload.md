# L2 live smoke — mesh 路径切 v3 input_image auto-upload(退役 FORGEUE_COMFY_INPUT_DIR)

> change: `comfy-agent-api-v3-adaptation` Task 7 · 日期: 2026-06-11
> 全程 **FORGEUE_COMFY_INPUT_DIR 未设置**,代码已无直写 ComfyUI input/ 路径。

## 机制变更

- 旧(round 5 D10):executor 直写 `$FORGEUE_COMFY_INPUT_DIR/forgeue_<sha1>.png`,传裸文件名
- 新:executor 写 in-tree staging `<run_dir>/comfy/forgeue_<sha1>.png`,**resolve() 绝对路径**
  传给 CLI;上游 v3 `_auto_upload_input_images` 自动 POST /upload/image 落 ComfyUI input/

## 排查记录(systematic-debugging,首跑失败)

1. 首跑 `mesh_worker_error`(mesh step 秒级 fail,image step 成功)
2. 证据:staging 文件正确落 in-tree;ComfyUI input/ **无新上传**;直调 worker(手工
   resolve 绝对路径)成功生成 GLB 76s
3. 假说验证:用相对路径直调 CLI →
   `{"ok": false, "error": "HTTPError: HTTP Error 400: Bad Request", "error_code": "unknown"}`
4. **根因**:framework.run 默认 `--artifact-root artifacts/<today>` 是相对路径 →
   `ctx.run_dir` 相对 → CLI 子进程 cwd=scripts_dir,`os.path.isfile(相对路径)` 判 False
   → auto-upload 不触发 → 相对路径原值透传 LoadImage → ComfyUI prompt 校验 HTTP 400
   → error_code=unknown → generic WorkerError → mesh_worker_error(与观察 mode 吻合)
5. 修复:`staging_dir = (ctx.run_dir / "comfy").resolve()`(generate_mesh.py);
   回归 fence `test_generate_via_comfy_worker_resolves_relative_run_dir_to_absolute_path`
   (相对 run_dir + chdir,断言传 worker 的路径 is_absolute)

## 执行记录(修复后,resume 同 run-id,image step checkpoint 恢复)

```
FORGEUE_COMFY_SCRIPTS_DIR=D:/AI/ComfyUI/scripts PYTHONPATH=src \
python -m framework.run --task examples/comfy_local_smoke_mesh.json \
    --live-llm --run-id mesh_autoupload_smoke_20260611
-> status: "succeeded", visited: [step_image, step_mesh], last_failure_mode: null
real    1m55.208s
```

## 产物验证

```
artifacts/2026-06-11/mesh_autoupload_smoke_20260611/
  mesh_autoupload_smoke_20260611_step_mesh_mesh_237518e5_0.glb   3,598,040 bytes, magic b'glTF'
  comfy/forgeue_d15e35778174d5da.png                              in-tree staging(随 run 产物管理)

D:/AI/ComfyUI/apps/official-main-git-v092/input/
  forgeue_d15e35778174d5da.png   2026-06-11 14:57  <- 上游 /upload/image 放入(非 ForgeUE 直写)
  forgeue_7ebf44bcb578e16c.png   2026-05-03        <- 旧机制遗留(对照组)
```

## 结论

- mesh auto-upload 全链路 PASS;`FORGEUE_COMFY_INPUT_DIR` 配置链(env / models.yaml /
  ComfyAgentConfig / registry dataclass)全部退役,旧 yaml 残留键容忍并忽略
- 上游次生改进点(未做,记录):`runner.submit()` 对 HTTP 400 HTTPError 未读 response body
  转成 `ComfyUI rejected: value_not_in_list` 友好错误,error_code 落 unknown 而非
  value_not_in_list;可作 follow-on 提升错误分类精度
