## 1. Phase A — F-C 框架侧 schema + drop loop(round 1 codex F1+F2+F4 修订后)

- [ ] 1.1 `src/framework/core/ue.py`:`Evidence` 加 `skip_reason: Literal["permission_denied", "no_handler"] | None = None` 字段(向后兼容,default None)
- [ ] 1.2 `src/framework/ue_bridge/manifest_builder.py`:加 public 函数 `is_manifest_importable(art) -> bool`(`payload.kind==file AND _KIND_MAP.get((modality, shape)) is not None` — round 1 codex F1 D10 单源)
- [ ] 1.3 `src/framework/runtime/executors/export.py::ExportExecutor._is_importable`:收敛为 `return is_manifest_importable(art)`(沿 D10;round 1 codex F1 修订)
- [ ] 1.4 `src/framework/ue_bridge/manifest_builder.py`:加 public 函数 `derive_drop_target(art, *, target: UEOutputTarget, run_id: str) -> tuple[Path, str]`(round 1 codex F4 签名加 target),内部复用 `_KIND_MAP` + `_PREFIX_BY_KIND` + `_derive_ue_name(art, kind=..., policy=target.asset_naming_policy)`:
  - video + `_KIND_MAP[(modality, shape)] == "file_media_source"` → `(target.project_root/Content/Movies/<run_id>, MS_<base>.mp4)`
  - 其他 importable modality(image / audio / mesh / material)→ `(target.project_root/Content/Generated/<run_id>, raw_basename)` 其中 `raw_basename = Path(art.payload_ref.file_path).name`(round 1 codex F2 修订:**非 video 保 raw filename**,不引入 NG1 超范围 silent change)
  - `_KIND_MAP` miss(defensive,正常调用前 caller 应已 `is_manifest_importable` filter)→ fall through 到非 video 分支返 `(Generated/<run_id>, raw_basename)`,**不 raise**(round 1 codex F1 修订)
- [ ] 1.5 `src/framework/ue_bridge/manifest_builder.py::build_manifest`:
  - L98-104 silent skip 改为 `if not is_manifest_importable(art): continue`(沿 D10 单源)
  - `UEAssetEntry.source_uri` 计算改用 `derive_drop_target` 返回 path 相对 project_root 的 POSIX 形式:video → `Content/Movies/<run_id>/MS_<base>.mp4`;非 video → `Content/Generated/<run_id>/<raw_basename>`
- [ ] 1.6 `src/framework/runtime/executors/export.py::ExportExecutor.execute` drop loop(L102-125):用 `derive_drop_target(art, target=ctx.task.ue_target, run_id=ctx.run.run_id)` 获 `(drop_dir, target_filename)`,`drop_dir.mkdir(parents=True, exist_ok=True)` + `target_fs = drop_dir / target_filename` + `shutil.copy2(src_fs, target_fs)`;Evidence `target_object_path` 用 `str(target_fs.relative_to(Path(target.project_root)))`(POSIX-style)
- [ ] 1.7 `src/framework/runtime/executors/export.py::ExportExecutor.execute` permission mask emit(L149-158):denied evidence 加 `skip_reason="permission_denied"`(沿 spec L93 修订)
- [ ] 1.8 `src/framework/runtime/executors/export.py::_rebase_artifact_source`:审视该 helper 是否仍需要(D2 框架 drop 改 derive_drop_target 后,manifest entry source_uri 已经在 build_manifest 时直接对齐;rebase helper 可能成 dead code);若仍调用,确保不冲突
- [ ] 1.9 加 unit fence `tests/unit/test_export_video_path_split.py`:
  - `test_export_drops_video_to_content_movies_and_image_preserves_raw_filename`(D12 video 分流 + round 1 codex F2 非 video 保 raw)
  - `test_derive_drop_target_preserves_raw_filename_for_non_video`(round 1 codex F2 fence)
  - `test_derive_drop_target_falls_through_for_unmapped_shape`(round 1 codex F1 defensive 不 raise)
  - `test_export_unsupported_shape_does_not_crash_drop_loop`(round 1 codex F1 video.webm 路径,_KIND_MAP miss 静默 skip 不 crash)
  - `test_is_manifest_importable_requires_file_payload_kind`(D10 helper)
  - `test_manifest_entry_source_uri_matches_framework_drop_path`(单源契约 — manifest source_uri == 实际物理 drop path 相对 project_root)
- [ ] 1.10 加 unit fence `tests/unit/test_evidence_skip_reason.py`:
  - `test_evidence_load_legacy_no_skip_reason_field_defaults_to_none`(后向兼容)
  - `test_export_permission_denied_evidence_carries_skip_reason`(framework emit 路径)
  - `test_evidence_dump_excludes_none_skip_reason`(serialization 校验,沿 Pydantic exclude_none 约定;若用 model_dump_json 不 exclude 则改为校验 `null`)

## 2. Phase B — F-D UE 端 filter + simplify(round 1 codex F3 修订后)

- [ ] 2.1 `ue_scripts/evidence_writer.py::make_record`:加可选 kwarg `skip_reason: str | None = None`,序列化时若不为 None 则写入 JSON
- [ ] 2.2 `ue_scripts/run_import.py` L67-73 pre-scan filter:改为 `if status=="skipped" and skip_reason=="permission_denied" and op_id` 三 AND 条件
- [ ] 2.3 `ue_scripts/run_import.py` L89-92 no-handler skipped append 时显式带 `skip_reason="no_handler"`
- [ ] 2.4 `ue_scripts/domain_video.py::import_video_entry`(round 1 codex F3 修订;file_path 派生协议改写):
  - 删除 `shutil.copy2` 调用 + `movies_dir.mkdir(parents=True, exist_ok=True)`(framework 已 drop)
  - 保留 `if not source_fs.is_file()` 防御
  - **新增 source_uri 验证**:`relative_to_content = entry["source_uri"]` 去 `Content/` 前缀(若不以 `Content/` 起首 → return failed);校验 `relative_to_content.startswith("Movies/")` AND path part count == 3 → 否则 return failed("source_uri does not match D12 Movies/<run_id>/<filename>.mp4 layout")
  - **新增 mismatch fence**:从 source_uri 派生 `(run_id_from_source, ue_name_from_source)` vs target_object_path 反推 `(run_id_from_target, ue_name_from_target)` 必须相等;不等 return failed
  - `relative_file_path = relative_to_content`(直接用 source_uri 派生路径,**NOT** target_object_path 反推 — 沿 D6 修订单源契约)
  - 保留 FileMediaSource asset 创建 + `set_editor_property("file_path", relative_file_path)`
- [ ] 2.5 加 unit fence `tests/unit/test_run_import_skipped_filter.py`(stub-unreal):
  - `test_pre_skipped_only_includes_permission_denied`(双 skipped entry 区分)
  - `test_no_handler_skipped_does_not_pre_filter`(UE 端写的 skipped 不被吞)
- [ ] 2.6 加 unit fence `tests/unit/test_evidence_writer_skip_reason.py`:
  - `test_make_record_with_skip_reason_appears_in_json`
  - `test_make_record_without_skip_reason_yields_null_or_omitted_field`
- [ ] 2.7 加 unit fence `tests/unit/test_domain_video_no_copy.py`(stub-unreal):
  - `test_domain_video_does_not_invoke_shutil_copy2`(monkeypatch shutil.copy2 → fail-on-call;实际通过统计 stub 调用次数)
  - `test_domain_video_file_path_derived_from_source_uri`(round 1 codex F3 fence:set_editor_property("file_path") value 等于 source_uri 去 Content/ 前缀)
  - `test_domain_video_rejects_non_d12_source_uri`(round 1 codex F3:source_uri 不以 Content/Movies/ 起首返 failed)
  - `test_domain_video_returns_failed_on_source_target_mismatch`(round 1 codex F3:source_uri 与 target_object_path 反推 (run_id, ue_name) 不等返 failed)
  - `test_domain_video_returns_failed_when_source_mp4_missing`(防御路径)

## 3. Phase C — Integration + L2 evidence

- [ ] 3.1 修改 `tests/integration/test_p4_ue_manifest_only.py`:
  - 既有 `test_p4_domain_video_copies_mp4_to_content_movies_subdir` 重构为 `test_p4_domain_video_creates_file_media_source_uasset_without_copying_mp4`(reflect new contract)
  - 加 `test_p4_export_drops_video_mp4_to_content_movies_directly`(framework drop 后 mp4 已在 Movies/<run_id>/,domain_video 不再 copy)
  - 加 `test_p4_domain_video_returns_failed_when_mp4_missing`(D2 修订 spec scenario)
- [ ] 3.2 跑 L2 live smoke `examples/comfy_local_smoke_video.json`:用户开 ComfyUI server(终端 1)+ Claude 跑 `python -m framework.run --task examples/comfy_local_smoke_video.json --live-llm --run-id cluster2_l2_<HHMMSS>`,实证 framework 端 mp4 落 `<project_root>/Content/Movies/<run_id>/MS_<base>.mp4` + `Content/Generated/<run_id>/MS_<base>.uasset` 同 run 内 + Generated/ 下不再有 raw mp4 垃圾文件
- [ ] 3.3(选)P4 真机 commandlet evidence(若 user 装了 UE 5.x):走 `exec(open('ue_scripts/run_import.py').read())` 实证 import_video_entry 不 copy + FileMediaSource asset 正确创建

## 4. Phase D — Spec sync + doc-sync gate + active 收敛

- [ ] 4.1 `docs/design/LLD.md` Evidence schema 段:加 `skip_reason` 字段 + 描述用途;对应行号在 commit 时定位
- [ ] 4.2 `docs/design/LLD.md` ExportExecutor + manifest_builder 路径分流段:加 derive_drop_target 函数描述 + D12 路径表格(若 LLD 已有 video 段则修订,否则 follow `comfy-agent-cli-video-adoption` Phase 3 D12 段就近补)
- [ ] 4.3 `docs/design/HLD.md` UE Export Bridge 章节:若有"framework drop physical layout"图或表,更新 Movies/ 分流
- [ ] 4.4 `docs/testing/test_spec.md`:加新增 fence test 索引(test_export_video_path_split / test_evidence_skip_reason / test_run_import_skipped_filter / test_evidence_writer_skip_reason / test_domain_video_no_copy)
- [ ] 4.5 `docs/acceptance/acceptance_report.md`:若 video FR/NFR 矩阵涉及 D12 路径,更新状态(可能不需要 — D12 协议层契约已固定,这是 implementation alignment 而非新 FR)
- [ ] 4.6 `CHANGELOG.md`:新增条目"feat(export+ue-scripts): D12 video drop 路径分流前移到 framework + Evidence skip_reason 字段 + run_import skipped 过滤精确"
- [ ] 4.7 `CLAUDE.md` ComfyUI 接入段:更新 video 路径段说明 framework 端落 Movies/(当前段写"video 落 `artifacts/<today>/<run_id>/<artifact_id>.mp4`"是 framework artifact 落地,不是 export 后 UE project 路径,所以 export 后 UE project 内的 D12 描述需要复核 + 必要时补)
- [ ] 4.8 `AGENTS.md`:若有 mentions of `Content/Generated/` video 路径,扫一遍并更新
- [ ] 4.9 跑 `python tools/forgeue_doc_sync_check.py --change fix-export-d12-and-skipped-evidence-filter`(10 文档静态扫,标记 [REQUIRED] / [OPTIONAL] / [SKIP] / [DRIFT])
- [ ] 4.10 `openspec/backlog/active.md` retire 两条 active follow-on(`fix-video-export-path-split-d12-violation` + `fix-run-import-skipped-filter-permission-only`)→ 移到 `archived.md`,状态 `cancelled-completed: <commit-ref-of-this-change>`
- [ ] 4.11 evidence frontmatter `followon_continuity` 4-list 在 P5/P6 阶段 verify_report.md / cross-check 评审 evidence 中正确填写

## 5. Phase E — Verify + Review + Finish

- [ ] 5.1 跑全套 pytest:`python -m pytest -q` 确认 1576 → 1576 + 新增 5 fence(test_export_video_path_split / test_evidence_skip_reason / test_evidence_writer_skip_reason / test_run_import_skipped_filter / test_domain_video_no_copy 大致 5-10 case 增加)无回归
- [ ] 5.2 Level 0/1/2 verify(走 `/forgeue:change-verify fix-export-d12-and-skipped-evidence-filter`)+ codex `/codex:review --base main` verification hook
- [ ] 5.3 `/forgeue:change-review` finalize:Superpowers `requesting-code-review` + codex `/codex:adversarial-review` mixed scope;blocker 回写
- [ ] 5.4 `/forgeue:change-doc-sync` 走 Documentation Sync Gate(10 文档 + README §4.3 提示词 + 应用 [REQUIRED])
- [ ] 5.5 `/forgeue:change-finish` 跑 finish_gate(中心化最后防线;evidence 完整性 + frontmatter 全检 + cross-check + writeback 真实性 + tasks unchecked + `openspec validate --strict` + 4 类 v1 advisory fence + followon_continuity)
- [ ] 5.6 archive change(squash merge dev → main,**用户授权后**)+ followon registry 推动 active.md 两条 entry 迁 archived.md(P10 archive script 自动迁 + tombstone)
