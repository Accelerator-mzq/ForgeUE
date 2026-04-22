# TBD-006 视觉 review 图像压缩

> 计划文档(2026-04-22)。源:`C:\Users\mzq\.claude-max\plans\tbd-006-hidden-hejlsberg.md`(plan-mode 自动生成),归档至此供项目内审阅。
>
> **状态:已实施(2026-04-22)。** 本文档反映 v1 计划(只压图);v2 修订(Codex 独立 review 后扩到双修复:摘要化 + 压缩)的最终落地见 `docs/acceptance/acceptance_report.md` §6.5 + §7 TBD-006 + `CHANGELOG.md` Unreleased / Fixed 段。代码:`src/framework/review_engine/image_prep.py` + `src/framework/runtime/executors/review.py`(`_summarize_image_payload` / `_candidate_payload` / `_attach_image_bytes` 4 个 kw)。Fence:`tests/unit/test_visual_review_image_compress.py`(8) + `tests/unit/test_review_payload_summarization.py`(2)。
>
> 下方 v1 文本保留作历史记录,**与最终实装有出入**(尤其 §6 描述的"只做图像压缩"不闭环 —— Codex 发现 `_build_candidates` 还把 raw bytes 塞进 payload,需要双修复)。

## Context

A2 阶段 `a2_mesh` 验证撞 bug:`review_judge_visual` alias 在收到 3 张 1024×1024 Qwen 生成 PNG 后,GLM/DashScope 三家 vision provider 全返"输入过长"(base64 总 1,262,246 字符 > DashScope 1M 硬限、GLM 更严)。

根因已定位到 `src/framework/review_engine/judge.py:100-114` 的 `_build_prompt()` visual path:把 `c.image_bytes` 原封 `base64.b64encode` 拼进 `image_url` content block,无体积控制。现有 router 修复(2f57df9)已让错误链不再吞栈,但不治根 —— payload 本身需要预处理。

**目标**:在 `_attach_image_bytes()` 读字节之后、返回之前,按需 resize + JPEG recompress,使单张 base64 ≤ 200KB,保障 3–4 张合一条 message 不撞任何 vision provider 输入上限。同时守:a2_image / a2_review 走 Anthropic 路径的小占位图不被无谓 JPEG 劣化(阈值短路)。

修好后 `--resume a2_mesh` 能复用已生成的 3 张图(不再烧 $0.08 重跑 image_fast),直接验证 step_review_image → step_mesh 全链。

## 设计决策

1. **Q1 插入点 — `_attach_image_bytes()` 内,helper 抽到新文件**
   `src/framework/review_engine/image_prep.py`(新)放 `compress_for_vision()`。`review.py` 只 import helper,不直接碰 Pillow。judge 保持纯编码器。理由:review.py 已是"image bytes 注入点"的自然层,和 `artifact_type.modality=="image"` 判定同层。

2. **Q2 Pillow 依赖 — `optional-dependencies.llm` 分组**
   和 `litellm`、`instructor` 同组。`review_judge_visual` 本质依赖 LLM extras,一次安装到位。延迟 import + 清晰 install hint(复制 `src/framework/providers/litellm_adapter.py:30-55` 的 `_import_litellm()` 模式)。

3. **Q3 默认行为 — visual_mode=True 时默认开启 + 阈值短路**
   `compress_images` 默认 True,但 raw bytes < `compress_threshold_bytes`(256KB)时直接透传不转码。好处:a2_image / a2_review 的 FakeComfy 小占位图(< 10KB)照走原 PNG,Anthropic 结论不漂移;a2_mesh 的 ~320KB Qwen 真图自动压。

4. **Q4 测试图 — Pillow 合成 + `pytest.importorskip`**
   合成图精确控尺寸/mode,覆盖 alpha 扁平化 / 尺寸缩放 / magic bytes 全路径。单独一条 fence 用 `monkeypatch sys.modules["PIL"]=None` 模拟 Pillow 缺失,守 install hint 消息。

## 实施步骤

### 1. 新建 `src/framework/review_engine/image_prep.py`

提供 `compress_for_vision(data: bytes, *, max_dim: int, quality: int) -> tuple[bytes, str]`,返回 `(压缩后 bytes, "image/jpeg")`。

逻辑(严格顺序):
- `_import_pillow()` 延迟 import,缺失时 raise `ProviderError` 带 `"pip install 'forgeue[llm]'"` hint
- Magic bytes 预检:PNG(`\x89PNG`) / JPEG(`\xFF\xD8\xFF`) / WebP(`RIFF...WEBP`),不认识直接原样返回
- `with Image.open(BytesIO(data)) as img:` — 上下文管理器及时释放
- `ImageOps.exif_transpose(img)` — 防旋转错乱(Qwen 无 EXIF 但未来兼容)
- 若 `max(img.width, img.height) > max_dim` → `img.thumbnail((max_dim, max_dim), Image.LANCZOS)`
- 若 mode 是 RGBA / LA / P(有 alpha)→ `Image.new("RGB", size, (255, 255, 255))` + `paste(mask=img.split()[-1])` 扁平化到白底
- `img.save(buf, "JPEG", quality=quality, optimize=True)` → 返回 `(buf.getvalue(), "image/jpeg")`

### 2. 修改 `src/framework/runtime/executors/review.py`

- **line 51-60 附近**:config 读取区追加 4 行
  ```python
  compress_images = bool(cfg.get("compress_images", visual_mode))
  compress_max_dim = int(cfg.get("compress_max_dim", 768))
  compress_quality = int(cfg.get("compress_quality", 80))
  compress_threshold_bytes = int(cfg.get("compress_threshold_bytes", 256 * 1024))
  ```
- **line 64 调用处**:`_attach_image_bytes(ctx, candidates, compress=compress_images, max_dim=compress_max_dim, quality=compress_quality, threshold_bytes=compress_threshold_bytes)`
- **line 252-269 `_attach_image_bytes` 函数签名扩展**:4 个 kw-only 参数,默认值和 cfg 同。读完 `c.image_bytes` 后,若 `compress and len(c.image_bytes) > threshold_bytes`,调 `compress_for_vision` 更新 `c.image_bytes` 和 `c.image_mime`。

### 3. 修改 `pyproject.toml`

`[project.optional-dependencies].llm` 追加 `"Pillow>=10.0,<12"`。

### 4. 新建 `tests/unit/test_visual_review_image_compress.py`

**fence 清单(8 条)**:

1. `test_compress_thumbnails_oversized_image` — 合成 1024×1024 RGB PNG,调 `compress_for_vision`,断言 max(w,h)==768 且宽高比误差 ≤1px
2. `test_compress_target_under_size_budget` — 同输入,断言压缩后 bytes < 150KB(q=80)
3. `test_compress_flattens_alpha_to_white` — 合成 RGBA(半透明红),断言输出 mode=RGB + JPEG magic(`\xFF\xD8\xFF`)
4. `test_compress_returns_jpeg_mime` — 返回 mime 严格 `"image/jpeg"`
5. `test_attach_skips_compression_when_disabled` — `compress=False`,字节恒等通过,mime 保留原值
6. `test_attach_short_circuits_under_threshold` — 构造 raw bytes < 256KB 的图,`compress=True` 下字节仍恒等通过(Q3 阈值短路守门)
7. `test_compress_raises_with_install_hint_when_pillow_missing` — `monkeypatch sys.modules["PIL"]=None`,断言 `ProviderError` 且 message 含 `"pip install"` 和 `"[llm]"`
8. `test_attach_visual_payload_under_provider_limit_for_three_candidates` — 合成 3 张 1024×1024 PNG 跑完整 `_attach_image_bytes`,断言 `sum(len(base64.b64encode(c.image_bytes)) for c in out) < 900_000`(DashScope 1M 硬限留 10% 余量)

### 5. 文档同步

- `docs/acceptance/acceptance_report.md` §7 TBD-006 状态 ⚠️ → ✅;§6.4 顺序 4 解锁;§6.5 根因章节追加"修复确认"小段
- `docs/design/LLD.md` review_engine 章节追加 image_prep 说明(一段)
- `docs/testing/test_spec.md` §5 fence 清单追加 8 条 + 测试基数 526 → 534;§2.2 pyramid 合计表同步
- `CLAUDE.md` / `AGENTS.md` / `README.md` / `docs/INDEX.md` 测试基数 526 → 534
- `CHANGELOG.md` 追加 TBD-006 条目
- `docs/requirements/SRS.md` NFR-PERF-005 (526+ → 534+);ADR-001 的 526 同步

### 6. 验证

```bash
# 本地 Python 3.13 环境装 Pillow(和 llm extras 一次到位)
python -m pip install "Pillow>=10.0,<12"

# Unit 回归
python -m pytest tests/unit/test_visual_review_image_compress.py -v
python -m pytest -q   # 预期 534 绿

# Pillow 缺失路径单独验(fence 7 覆盖,但手工跑一遍确认 hint)
# 不需要真卸 Pillow — fence 用 monkeypatch 模拟

# resume a2_mesh 端到端(复用已生成的 3 张真 Qwen 图,不再烧 $0.08)
PYTHONPATH=src python -m framework.run \
    --task examples/image_to_3d_pipeline.json \
    --live-llm --run-id a2_mesh --artifact-root ./artifacts \
    --resume --trace-console 2>&1 | tee artifacts/a2_mesh/resume_v3.log
```

**预期**:
- step_review_image 通过(之前撞 payload 的 1.26M 现在降到 ~250KB base64)
- step_mesh_spec(text cheap)通过
- **step_mesh** 触达 → 真实烧 ~$0.5-1 Hunyuan 3D 生成 mesh(首次测 mesh_from_image live 链)
- step_export 按预期 raise `UE project_root does not exist`(占位路径,和 A1 绑定)
- run_summary.status=failed(因 step_export),但 visited_steps 含 step_mesh,mesh artifact 落盘,A2 顺序 4 ✅

若 mesh 步也真能通,acceptance_report §6.4 顺序 4 升格 ✅,A2 彻底收官(只剩顺序 5 A1 UE 真机)。

## Critical Files

**修改**:
- `src/framework/runtime/executors/review.py` —— `_attach_image_bytes` 扩 4 kw,execute() 读 cfg 传参
- `pyproject.toml` —— llm extras 加 Pillow
- `docs/acceptance/acceptance_report.md` + `docs/design/LLD.md` + `docs/testing/test_spec.md` + `CLAUDE.md` / `AGENTS.md` / `README.md` / `docs/INDEX.md` / `CHANGELOG.md` / `docs/requirements/SRS.md` —— 测试基数 + TBD-006 状态

**新建**:
- `src/framework/review_engine/image_prep.py` —— `compress_for_vision()` + `_import_pillow()`
- `tests/unit/test_visual_review_image_compress.py` —— 8 条 fence

**参考但不改(复用其 pattern)**:
- `src/framework/providers/litellm_adapter.py:30-55` —— `_import_litellm()` 延迟导入模板
- `src/framework/providers/workers/mesh_worker.py:819-825` —— magic bytes 校验模板
- `tests/unit/test_router_fallback_errors.py` —— 最近一条 fence 的组织模板(头注释 + 一组针对一个 fix 的断言)

## 风险与注意

1. **JudgeBatchReport 不记图像 hash**(已核实 judge.py:27-40):原 plan agent 警告的"provenance 对齐"风险不适用。review 输出只记 scores/issues/notes,不记图字节。
2. **阈值短路用 raw bytes 而非 base64 长度**:避免多算一次 encode,也对 Anthropic 路径(小图)最友好 —— 256KB raw ≈ 345KB base64,单张 Anthropic 可吃。
3. **EXIF orientation 默认修**:Qwen 无 EXIF 但未来接手机拍摄图 / 扫描件会踩,`ImageOps.exif_transpose` 默认做,零代价防御。
4. **Pillow 缺失时的失败姿态**:必须 raise(不能静默跳过压缩),否则和本 bug 同模式再炸;fence 7 守门。
5. **Python 3.13 + Pillow wheel**:确认 `Pillow>=10.0` 有 cp313 官方 wheel(Pillow 10.4+ 支持)。若本地装失败,pin `>=11.0` 更稳(2024-2025 版本跟 3.13 适配好)。实装前 `pip install Pillow` 一次验证即可。
6. **a2_image 不走 visual path**:`examples/image_pipeline.json` 未带 `visual_mode`,其 review 走 text-only 路径,完全不 import `image_prep`,本修复波及不到。真正触发压缩的是 `image_to_3d_pipeline.json` 和 `image_edit_pipeline.json`(两处都写了 `visual_mode: true`)。fence 6(阈值短路)更多是守未来扩展 —— 若将来某 visual review bundle 接入小占位图(如 512×512 以下),确保不被无谓 JPEG 劣化。
7. **Mesh live 烧钱**:TBD-006 修完后的 resume a2_mesh 真的跑 mesh 会 burn ~$0.5-1。若此时不想烧,可在 fix commit 后先停,让用户决定何时跑。合理做法:修完 TBD-006 + 全 unit 回归绿后,commit + push,再单独一条消息问用户"现在 resume a2_mesh 烧 mesh 费用?"。
