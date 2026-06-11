# comfy-detach-wait-adoption Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `ComfyAgentWorker` 4 条 `_run_once_*_async` 从阻塞 `run` 切换为 `run --detach` + `wait --prompt-id` 两段式协议,cancel 升级 `cancel --prompt-id`,并新增超时后先 cancel 再 raise 的僵尸 GPU prompt 防护。

**Architecture:** 先把 4 条同构 subprocess 块提取为共享 helper `_invoke_comfy_cli_once`(纯重构,commit 1),再在新 orchestration 方法 `_run_comfy_prompt` 内一次性实现 detach+wait 协议(锁全程串行包 submit→wait)。cancel/timeout 归因全部集中在 `_run_comfy_prompt` 的 except 层,低层 helper 只负责子进程卫生(terminate/kill)。

**Tech Stack:** stdlib asyncio(`create_subprocess_exec` / `wait_for`)、pytest + pytest-asyncio(`asyncio_mode = "auto"`)、上游 `comfyui_api` CLI v3.3 契约。

**Spec:** `docs/superpowers/specs/2026-06-11-comfy-detach-wait-adoption-design.md`(已 user 批准,commit d9401f9)

**关键背景(给零上下文工程师):**

- 生产文件只有一个:`src/framework/providers/workers/comfy_worker.py`(~2000 行)。4 条
  `_run_once_*_async`(image `:894` / mesh `:1256` / audio `:1486` / video `:1735`)各含
  ~120 行同构 subprocess 块。
- 上游契约(已实证,见 spec §1):`run --detach` 返回
  `{"ok":true,"prompt_id":"...","detached":true,"timeout_hint_s":N,...}`;
  `wait --prompt-id X --timeout N` 返回 `{"ok":true,"outputs":{...},"wait_duration_s":...}`,
  失败 `{"ok":false,"error":"...","error_code":"..."}` exit 2;`cancel --prompt-id X` =
  全局 `/interrupt` + 针对性 queue 删除。
- 测试在 `tests/unit/test_comfy_subprocess{,_audio,_video}.py`(74+21+30 条),三个文件**各自
  复制了一份** `_AsyncFakeProcess` / `_patch_create_subprocess_exec` helper(image 版在
  `test_comfy_subprocess.py:103-186`)。mock 方式 = 替换模块级 `asyncio.create_subprocess_exec`。
- 跑测试用 `python -m pytest -q`(全量)或 `python -m pytest tests/unit/test_comfy_subprocess.py -q`
  (单文件)。当前基数 1363 passed;**测试总数不硬编码,以实测为准**。
- 禁令:`artifacts/` / `demo_artifacts/` / `.env` / 本机绝对路径不提交;probe 输出用 ASCII
  标记不用 emoji(Windows GBK stdout);commit message 中文。

---

## File Structure

| 文件 | 动作 | 职责 |
|---|---|---|
| `src/framework/providers/workers/comfy_worker.py` | Modify | 唯一生产文件:新增 `_SUBMIT_TIMEOUT_S` 常量、`_invoke_comfy_cli_once` 低层 helper、`_run_comfy_prompt` orchestration、`_abort_comfy_prompt(prompt_id)` 参数化、`_last_prompt_id` 钩子;4 条 `_run_once_*_async` 改薄 |
| `tests/unit/test_comfy_subprocess.py` | Modify | image+mesh fence;`_patch_create_subprocess_exec` dispatch 升级 + 新 fence |
| `tests/unit/test_comfy_subprocess_audio.py` | Modify | audio fence;同款 dispatch 升级 |
| `tests/unit/test_comfy_subprocess_video.py` | Modify | video fence;同款 dispatch 升级 |
| `tests/unit/test_probe_framework.py` | Modify | cancel 探针的 opt-in / 零副作用 fence |
| `probes/provider/probe_comfy_cancel.py` | Create | L2 cancel 真机探针 |
| `docs/archive/forge_changes/2026-06-11-comfy-detach-wait-adoption/notes/` | Create | L2 evidence notes ×3 |
| `docs/design/LLD.md` / `CLAUDE.md` / `CHANGELOG.md` / `docs/backlog/{active,archived}.md` / `docs/testing/test_spec.md` | Modify | Task 7 document-release 阶段统一处理 |

---

### Task 1: 防 drift fence + 提取 `_invoke_comfy_cli_once`(纯重构,commit 1)

**Files:**
- Modify: `src/framework/providers/workers/comfy_worker.py`
- Test: `tests/unit/test_comfy_subprocess.py`

- [ ] **Step 1.1: 写防 drift fence(RED)**

在 `tests/unit/test_comfy_subprocess.py` 文件尾部追加(`_make_worker` / `_make_mesh_worker` 已在同文件,audio/video worker 在此 fence 内就地构造):

```python
# ---------------------------------------------------------------------------
# detach-wait change Task 1: 共享 CLI helper 防 drift fence
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_all_four_run_once_methods_route_through_shared_cli_helper(
    tmp_path, monkeypatch,
):
    """防 drift fence(detach-wait change):4 条 _run_once_*_async 的 subprocess
    块必须共走 _invoke_comfy_cli_once,防止 4 份重复 diff 复发。
    spy 替换 helper 并短路 raise;每个 capability 调用后断言 helper 被调用。"""
    contexts: list[str] = []

    async def _spy(self, *, cmd, wall_timeout_s, cli_timeout_s, context, **kw):
        contexts.append(context)
        raise WorkerError("spy short-circuit")

    monkeypatch.setattr(ComfyAgentWorker, "_invoke_comfy_cli_once", _spy)

    def _mk(model_id: str) -> ComfyAgentWorker:
        scripts_dir = tmp_path / f"scripts_{model_id.replace('/', '_')}"
        (scripts_dir / "comfyui_api").mkdir(parents=True)
        art = tmp_path / f"art_{model_id.replace('/', '_')}"
        art.mkdir()
        return ComfyAgentWorker(
            scripts_dir=scripts_dir, model_id=model_id, run_id="r",
            project_id="p", artifacts_dir=art,
        )

    with pytest.raises(WorkerError):
        await _mk("comfy/local").agenerate(
            spec={"comfy_workflow": "GameAssets/x"}, num_candidates=1)
    with pytest.raises(WorkerError):
        await _mk("comfy/local-mesh").agenerate_mesh(
            spec={"comfy_workflow": "GameAssets/x"},
            source_image_filename="stub.png")
    with pytest.raises(WorkerError):
        await _mk("comfy/local-audio").agenerate_audio(
            spec={"comfy_workflow": "Audio_Workflows/x"})
    with pytest.raises(WorkerError):
        await _mk("comfy/local-video").agenerate_video(
            spec={"comfy_workflow": "Vedio/x"})
    assert len(contexts) == 4, f"4 条 _run_once 应各调 helper 1 次,实际 {contexts!r}"
```

- [ ] **Step 1.2: 跑 fence 确认 RED**

Run: `python -m pytest tests/unit/test_comfy_subprocess.py::test_all_four_run_once_methods_route_through_shared_cli_helper -v`
Expected: FAIL — `AttributeError: ... has no attribute '_invoke_comfy_cli_once'`(monkeypatch 找不到原属性)

- [ ] **Step 1.3: 实现 `_invoke_comfy_cli_once`**

在 `comfy_worker.py` 的 `_abort_comfy_prompt` 方法之后插入(类内方法):

```python
    async def _invoke_comfy_cli_once(
        self,
        *,
        cmd: list[str],
        wall_timeout_s: float,
        cli_timeout_s: float,
        context: str,
        abort_on_cleanup: bool = True,
    ) -> tuple[dict, int]:
        """一次 comfyui_api CLI 子进程调用的共享低层封装(detach-wait change)。

        收敛原 4 条 _run_once_*_async 的同构块:spawn → communicate(wall-clock
        守门)→ cleanup(abort/terminate/kill)→ decode → stdout JSON 解析 →
        ok=false 走 _raise_comfy_failure 分类。调用方负责持有 _comfy_submit_lock
        与 outputs 字段校验(detach submit 响应没有 outputs 字段)。
        abort_on_cleanup:cleanup 时是否先发 server-side abort(裸 cancel);
        detach 协议下取消归因上移到 _run_comfy_prompt,传 False。
        返回 (stdout JSON dict, returncode)。
        """
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=str(self.scripts_dir),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            # 测试钩子:保存当前 proc 供 cancel 测试断言终态
            self._last_proc = proc
        except FileNotFoundError as exc:
            raise WorkerUnsupportedResponse(
                f"{context}: failed to spawn subprocess "
                f"(python_exe={self.python_exe!r}, scripts_dir={self.scripts_dir!r}): "
                f"{exc}; verify FORGEUE_COMFY_SCRIPTS_DIR env var"
            ) from exc
        try:
            raw_out, raw_err = await asyncio.wait_for(
                proc.communicate(), timeout=wall_timeout_s,
            )
        except asyncio.TimeoutError as exc:
            raise WorkerTimeout(
                f"{context} subprocess wall-clock exceeded "
                f"{wall_timeout_s}s (CLI internal timeout was {cli_timeout_s}s)"
            ) from exc
        finally:
            if proc.returncode is None:
                if abort_on_cleanup:
                    await self._abort_comfy_prompt()
                proc.terminate()
                try:
                    await asyncio.wait_for(proc.wait(), timeout=_PROC_GRACE_S)
                except asyncio.TimeoutError:
                    proc.kill()
                await proc.wait()

        stdout_text = raw_out.decode("utf-8", errors="replace").strip() if raw_out else ""
        stderr_text = raw_err.decode("utf-8", errors="replace").strip() if raw_err else ""
        returncode = proc.returncode

        if not stdout_text:
            raise WorkerUnsupportedResponse(
                f"{context}: empty stdout (exit code {returncode}; "
                f"stderr first 500 chars: {stderr_text[:500]!r})"
            )
        try:
            data = json.loads(stdout_text)
        except json.JSONDecodeError as exc:
            raise WorkerUnsupportedResponse(
                f"{context}: stdout is not valid JSON "
                f"(exit code {returncode}; first 500 chars: {stdout_text[:500]!r})"
            ) from exc
        if not isinstance(data, dict):
            raise WorkerUnsupportedResponse(
                f"{context}: stdout JSON is not a dict (got {type(data).__name__})"
            )
        if not data.get("ok"):
            _raise_comfy_failure(data, returncode, context)
        return data, returncode
```

**消息 parity 注意**:image 路径原错误消息前缀是 `"ComfyAgentWorker"`,mesh/audio/video 是
`"ComfyAgentWorker.agenerate_mesh"` 等 — `context` 参数原样传这些字符串,模板展开后与
现消息**逐字符一致**(空 stdout / 非 JSON / 非 dict / wall-clock / spawn 失败 5 类全部核对过)。
唯一例外:image 原文 `"ComfyAgentWorker: stdout is not valid JSON"` 与 mesh 等
`"ComfyAgentWorker.agenerate_mesh: stdout is not valid JSON"` 本就同模板,无 drift。

- [ ] **Step 1.4: 改写 4 条 `_run_once_*_async` 调 helper**

以 image 版为例(`_run_once_async`),原 `cmd = [...]` 到 `_raise_comfy_failure(...)` 段替换为:

```python
        cmd = [
            str(self.python_exe), "-m", "comfyui_api", "run",
            "--workflow", comfy_workflow,
            "--params", json.dumps(params, ensure_ascii=False),
            "--project", self.project_id,
            "--lifecycle", "none",
            "--timeout", str(int(timeout_s)),
        ]
        async with _comfy_submit_lock():
            data, returncode = await self._invoke_comfy_cli_once(
                cmd=cmd,
                wall_timeout_s=timeout_s + _SUBPROC_BUFFER_S,
                cli_timeout_s=timeout_s,
                context="ComfyAgentWorker",
            )

        if "outputs" not in data or not isinstance(data["outputs"], dict):
            raise WorkerUnsupportedResponse(
                f"ComfyAgentWorker: stdout JSON missing 'outputs' field or "
                f"not a dict (got {data.get('outputs')!r})"
            )
        outputs = data["outputs"]
```

之后的 `_validate_outputs` 调用与 candidate 构造**保持不动**。mesh / audio / video 三条做
同样替换,`context` 分别传 `"ComfyAgentWorker.agenerate_mesh"` /
`"ComfyAgentWorker.agenerate_audio"` / `"ComfyAgentWorker.agenerate_video"`,outputs 守门
消息保留各自原前缀。audio/video 的 `comfy_subprocess_run_metadata.exit_code` 用 helper 返回
的 `returncode`(原变量名一致,candidate 构造代码无需动)。

注意:JSON 解析从锁外移到锁内(helper 在锁内执行)— 无 fence 断言锁范围细节,
行为等价;锁仍只在 4 条方法里出现一次。

- [ ] **Step 1.5: 跑 fence 确认 GREEN + 全量回归**

Run: `python -m pytest tests/unit/test_comfy_subprocess.py tests/unit/test_comfy_subprocess_audio.py tests/unit/test_comfy_subprocess_video.py -q`
Expected: 全 PASS(纯重构,零行为变化)
Run: `python -m pytest -q`
Expected: 全 PASS(基数 1363+1,以实测为准)

- [ ] **Step 1.6: Commit**

```bash
git add src/framework/providers/workers/comfy_worker.py tests/unit/test_comfy_subprocess.py
git commit -m "refactor: comfy worker 4 条 _run_once 同构 subprocess 块收敛 _invoke_comfy_cli_once 共享 helper"
```

---

### Task 2: `_abort_comfy_prompt(prompt_id)` 参数化(commit 2)

**Files:**
- Modify: `src/framework/providers/workers/comfy_worker.py:1127-1154`
- Test: `tests/unit/test_comfy_subprocess.py`

- [ ] **Step 2.1: 写 fence(RED)**

追加到 `tests/unit/test_comfy_subprocess.py`:

```python
@pytest.mark.asyncio
async def test_abort_comfy_prompt_with_prompt_id_appends_cli_flag(tmp_path):
    """detach-wait change:有 prompt_id 时 cancel cmd 必须带 --prompt-id <id>
    (interrupt + 从 queue 删除;上游 AGENT_API.md §1.6)。"""
    worker = _make_worker(tmp_path)
    with _patch_create_subprocess_exec(_make_async_completed("{}")) as mock:
        await worker._abort_comfy_prompt("abc-123")
    cmd = list(mock.call_args)
    assert "cancel" in cmd
    assert "--prompt-id" in cmd
    assert "abc-123" in cmd
    # --prompt-id 紧跟 id 值(argparse 位置约定)
    assert cmd[cmd.index("--prompt-id") + 1] == "abc-123"


@pytest.mark.asyncio
async def test_abort_comfy_prompt_without_prompt_id_uses_bare_cancel(tmp_path):
    """无 prompt_id(submit 段被取消的窄窗口)退回裸 cancel(全局 /interrupt;
    残留边界见 LLD cancel 小节)。"""
    worker = _make_worker(tmp_path)
    with _patch_create_subprocess_exec(_make_async_completed("{}")) as mock:
        await worker._abort_comfy_prompt()
    cmd = list(mock.call_args)
    assert "cancel" in cmd
    assert "--prompt-id" not in cmd
```

- [ ] **Step 2.2: 跑 fence 确认 RED**

Run: `python -m pytest tests/unit/test_comfy_subprocess.py::test_abort_comfy_prompt_with_prompt_id_appends_cli_flag -v`
Expected: FAIL — `TypeError: _abort_comfy_prompt() takes 1 positional argument but 2 were given`

- [ ] **Step 2.3: 实现参数化**

`_abort_comfy_prompt` 签名与 cmd 构造改为(docstring 同步更新,方法其余部分不动):

```python
    async def _abort_comfy_prompt(self, prompt_id: str | None = None) -> None:
        """cancel 路径 best-effort:有 prompt_id 时 `cancel --prompt-id <id>`
        (interrupt + 从 queue 删除;注意上游 interrupt 部分仍是全局 /interrupt,
        "精确"只体现在 queue 删除 — detach-wait change 核验结论,LLD 已标注),
        无 id 退回裸 cancel(submit 段被取消的窄窗口 fallback)。
        失败只 warning,不抛;_ABORT_TIMEOUT_S 守门 + kill 清理。
        """
        ap = None
        cancel_cmd = [str(self.python_exe), "-m", "comfyui_api", "cancel"]
        if prompt_id:
            cancel_cmd += ["--prompt-id", prompt_id]
        try:
            ap = await asyncio.create_subprocess_exec(
                *cancel_cmd,
                cwd=str(self.scripts_dir),
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await asyncio.wait_for(ap.wait(), timeout=_ABORT_TIMEOUT_S)
        except Exception as exc:  # noqa: BLE001 — best-effort,失败只 warning
            _COMFY_LOGGER.warning("comfy prompt abort failed: %s", exc)
        finally:
            if ap is not None and ap.returncode is None:
                try:
                    ap.kill()
                    await ap.wait()
                except Exception:  # noqa: BLE001 — cleanup best-effort
                    pass
```

- [ ] **Step 2.4: 跑 fence GREEN + 全量**

Run: `python -m pytest tests/unit/test_comfy_subprocess.py -q` → 全 PASS
Run: `python -m pytest -q` → 全 PASS

- [ ] **Step 2.5: Commit**

```bash
git add src/framework/providers/workers/comfy_worker.py tests/unit/test_comfy_subprocess.py
git commit -m "feat: _abort_comfy_prompt 支持 cancel --prompt-id 精确取消(queue 删除)"
```

---

### Task 3: 测试脚手架 dispatch 升级 + detach+wait 协议切换(commit 3)

**Files:**
- Modify: `src/framework/providers/workers/comfy_worker.py`
- Modify: `tests/unit/test_comfy_subprocess.py`(scaffolding `:134-186` + 断言 sweep)
- Modify: `tests/unit/test_comfy_subprocess_audio.py`(scaffolding `:95-148` + sweep)
- Modify: `tests/unit/test_comfy_subprocess_video.py`(scaffolding `:99-152` + sweep)

- [ ] **Step 3.1: 三个测试文件的 `_patch_create_subprocess_exec` 升级为协议 dispatch**

每个文件:在 `_patch_create_subprocess_exec` 函数前加 helper:

```python
def _detach_ok_stdout(prompt_id: str = "fake-prompt-1") -> str:
    """detach submit 段的成功响应(上游 AGENT_API.md §1.8 实测 shape)。"""
    return json.dumps({
        "ok": True, "prompt_id": prompt_id, "detached": True, "timeout_hint_s": 300,
    })
```

并把 `_patch_create_subprocess_exec` 的无 side_effect 分支(image 版 `:159-162`)替换为:

```python
    else:
        async def _factory(*a, **kw):
            calls.append(a)
            # detach-wait 协议 dispatch:submit 段返回 canned ok+prompt_id,
            # cancel 段返回 canned ok;fake_proc 语义 = wait 段响应
            # (既有测试的失败注入 stdout 因此落在 wait 段,分类共享
            # _raise_comfy_failure,语义不变)
            if "--detach" in a:
                return _AsyncFakeProcess(_detach_ok_stdout())
            if "cancel" in a:
                return _AsyncFakeProcess(json.dumps({"ok": True, "interrupted": True}))
            return fake_proc
```

- [ ] **Step 3.2: 写协议 fence(RED)**

追加到 `tests/unit/test_comfy_subprocess.py`:

```python
# ---------------------------------------------------------------------------
# detach-wait change Task 3: submit-then-poll 协议 fence
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_uses_detach_submit_then_wait_protocol(tmp_path):
    """协议 fence:第 1 个子进程 = run --detach,第 2 个 = wait --prompt-id --timeout。"""
    out_png = tmp_path / "out_a.png"
    _make_png_file(out_png)
    worker = _make_worker(tmp_path)
    with _patch_create_subprocess_exec(
        _make_async_completed(_ok_stdout([str(out_png)]))
    ) as mock:
        cands = await worker.agenerate(
            spec={"comfy_workflow": "GameAssets/x"}, num_candidates=1, timeout_s=120.0)
    assert mock.call_count == 2, f"应 submit+wait 两个子进程,实际 {mock.call_count}"
    submit_cmd = list(mock.call_args_list[0])
    wait_cmd = list(mock.call_args_list[1])
    assert "run" in submit_cmd and "--detach" in submit_cmd
    assert "--workflow" in submit_cmd and "GameAssets/x" in submit_cmd
    assert "wait" in wait_cmd and "--prompt-id" in wait_cmd
    assert wait_cmd[wait_cmd.index("--prompt-id") + 1] == "fake-prompt-1"
    assert "--timeout" in wait_cmd
    assert wait_cmd[wait_cmd.index("--timeout") + 1] == "120"
    assert len(cands) == 1


@pytest.mark.asyncio
async def test_prompt_id_recorded_in_candidate_metadata(tmp_path):
    """metadata fence:comfy_prompt_id 透传(spec §6,可追溯性是本 change 核心收益)。"""
    out_png = tmp_path / "out_b.png"
    _make_png_file(out_png)
    worker = _make_worker(tmp_path)
    with _patch_create_subprocess_exec(
        _make_async_completed(_ok_stdout([str(out_png)]))
    ):
        cands = await worker.agenerate(
            spec={"comfy_workflow": "GameAssets/x"}, num_candidates=1)
    assert cands[0].metadata["comfy_prompt_id"] == "fake-prompt-1"


@pytest.mark.asyncio
async def test_detach_response_missing_prompt_id_raises_unsupported(tmp_path):
    """契约破坏 fence:submit 成功响应缺 prompt_id → WorkerUnsupportedResponse。"""
    worker = _make_worker(tmp_path)
    bad_submit = _make_async_completed(json.dumps({"ok": True, "detached": True}))
    with _patch_create_subprocess_exec(side_effect=[bad_submit]):
        with pytest.raises(WorkerUnsupportedResponse, match="prompt_id"):
            await worker.agenerate(
                spec={"comfy_workflow": "GameAssets/x"}, num_candidates=1)


@pytest.mark.asyncio
async def test_submit_stage_deterministic_error_maps_to_unsupported(tmp_path):
    """submit 段失败分类 fence:workflow_not_found 在 submit 段就近报
    WorkerUnsupportedResponse,不 spawn wait 子进程。"""
    worker = _make_worker(tmp_path)
    fail_submit = _make_async_completed(
        json.dumps({"ok": False, "error": "FileNotFoundError: API workflow not found",
                    "error_code": "workflow_not_found"}),
        returncode=2,
    )
    with _patch_create_subprocess_exec(side_effect=[fail_submit]) as mock:
        with pytest.raises(WorkerUnsupportedResponse, match="workflow_not_found"):
            await worker.agenerate(
                spec={"comfy_workflow": "GameAssets/nope"}, num_candidates=1)
    assert mock.call_count == 1, "submit 失败不应再 spawn wait"
```

mesh / audio / video 的 `comfy_prompt_id` metadata fence 各加一条到对应文件
(`test_comfy_subprocess.py` mesh 区 / `_audio.py` / `_video.py`),模式同
`test_prompt_id_recorded_in_candidate_metadata`,改用各自的 worker factory 与
`_ok_mesh_stdout` / `_ok_audio_stdout` / `_ok_video_stdout` + 对应文件构造器
(`_make_glb_file` / `_make_flac_file` / `_make_minimal_mp4`),断言
`cands[0].metadata["comfy_prompt_id"] == "fake-prompt-1"`。

- [ ] **Step 3.3: 跑新 fence 确认 RED**

Run: `python -m pytest tests/unit/test_comfy_subprocess.py::test_run_uses_detach_submit_then_wait_protocol -v`
Expected: FAIL — `mock.call_count == 1`(还是单子进程阻塞 run)

- [ ] **Step 3.4: 实现 `_run_comfy_prompt` + 4 条方法接线**

(a) 常量区(`_ABORT_TIMEOUT_S` 之后)加:

```python
# detach submit 段(run --detach)的 wall-clock 上限(秒):
# 覆盖 manifest 校验 + mesh staging PNG 的 input_image auto-upload,无 GPU 等待
_SUBMIT_TIMEOUT_S: float = 60.0
```

(b) `__init__` 中 `self._last_proc = None` 之后加:

```python
        # detach-wait change 测试/探针钩子:最近一次 submit 解析出的 prompt_id
        self._last_prompt_id: str | None = None
```

(c) `_invoke_comfy_cli_once` 之后加 orchestration 方法:

```python
    async def _run_comfy_prompt(
        self,
        *,
        comfy_workflow: str,
        params: dict[str, Any],
        timeout_s: float,
        context: str,
    ) -> tuple[dict, int, str]:
        """detach+wait 两段式协议(detach-wait change,spec §3.2)。

        整段在 _comfy_submit_lock() 内(D2 全程串行,与原阻塞 run 等价):
        1. submit: run --detach → 立即返回 prompt_id(上游在返回前同步完成
           manifest 校验 + input_image* auto-upload)
        2. wait:   wait --prompt-id <id> --timeout N → 收割 outputs
        cancel 归因集中在本层 except:wait 段异常带 prompt_id 精确取消,
        submit 段异常退回裸 cancel(窄窗口 fallback)。
        返回 (outputs dict, wait 段 returncode, prompt_id)。
        """
        base = [str(self.python_exe), "-m", "comfyui_api"]
        submit_cmd = base + [
            "run",
            "--workflow", comfy_workflow,
            "--params", json.dumps(params, ensure_ascii=False),
            "--project", self.project_id,
            "--lifecycle", "none",
            "--timeout", str(int(timeout_s)),
            "--detach",
        ]
        async with _comfy_submit_lock():
            try:
                sdata, _submit_rc = await self._invoke_comfy_cli_once(
                    cmd=submit_cmd,
                    wall_timeout_s=_SUBMIT_TIMEOUT_S,
                    cli_timeout_s=timeout_s,
                    context=context,
                    abort_on_cleanup=False,
                )
            except asyncio.CancelledError:
                # submit 段被取消:prompt 可能已 queue 也可能没有 → 裸 cancel
                # best-effort(残留边界见 LLD cancel 小节)
                await self._abort_comfy_prompt(None)
                raise
            prompt_id = sdata.get("prompt_id")
            if not isinstance(prompt_id, str) or not prompt_id:
                raise WorkerUnsupportedResponse(
                    f"{context}: run --detach response missing prompt_id "
                    f"(got {sdata.get('prompt_id')!r}); upstream AGENT_API.md "
                    f"§1.8 contract requires it — check comfyui_api version"
                )
            self._last_prompt_id = prompt_id
            wait_cmd = base + [
                "wait",
                "--prompt-id", prompt_id,
                "--timeout", str(int(timeout_s)),
            ]
            try:
                wdata, wait_rc = await self._invoke_comfy_cli_once(
                    cmd=wait_cmd,
                    wall_timeout_s=timeout_s + _SUBPROC_BUFFER_S,
                    cli_timeout_s=timeout_s,
                    context=context,
                    abort_on_cleanup=False,
                )
            except asyncio.CancelledError:
                # wait 段被取消:精确取消自己的 prompt(interrupt + queue 删除)
                await self._abort_comfy_prompt(prompt_id)
                raise
            if "outputs" not in wdata or not isinstance(wdata["outputs"], dict):
                raise WorkerUnsupportedResponse(
                    f"{context}: stdout JSON missing 'outputs' field or "
                    f"not a dict (got {wdata.get('outputs')!r})"
                )
            return wdata["outputs"], wait_rc, prompt_id
```

(d) 4 条 `_run_once_*_async` 接线 — Task 1 改出来的「cmd 构造 + 锁 + helper 调用 +
outputs 守门」段整体替换为(image 版):

```python
        outputs, returncode, prompt_id = await self._run_comfy_prompt(
            comfy_workflow=comfy_workflow,
            params=params,
            timeout_s=timeout_s,
            context="ComfyAgentWorker",
        )
```

mesh / audio / video 同样替换,context 传各自原字符串。candidate 构造 metadata 各加一行:
- image:`metadata={...}` dict 加 `"comfy_prompt_id": prompt_id,`
- mesh:`metadata={...}` dict 加 `"comfy_prompt_id": prompt_id,`
- audio / video:顶层 metadata dict 加 `"comfy_prompt_id": prompt_id,`(与
  `comfy_manifest` 平级,不放进 `comfy_subprocess_run_metadata` 嵌套)

(e) 模块 docstring「生产流程」段同步:`run` 行改为
`run --detach → prompt_id → wait --prompt-id`(两行);「Cancel 语义」段补
`cancel --prompt-id` 精确取消。

(f) 既有 Task-4 cancel spy fence(`test_comfy_subprocess.py:1960` 附近)签名修正:

```python
    async def _spy_abort(self, prompt_id=None):
        aborted["n"] += 1
```

- [ ] **Step 3.5: 跑三个 comfy 测试文件,按转换规则 sweep 既有断言**

Run: `python -m pytest tests/unit/test_comfy_subprocess.py tests/unit/test_comfy_subprocess_audio.py tests/unit/test_comfy_subprocess_video.py -q`

对每个失败应用下列规则(机械转换,不改断言语义):

| 规则 | 旧模式 | 新模式 |
|---|---|---|
| R1 cmd 形状 | `cmd = list(run_mock.call_args)` 断言 run 参数(已知:`test_comfy_subprocess.py:476,497,660,745`、`_audio.py` / `_video.py` 各自的 invocation 测试) | `cmd = list(run_mock.call_args_list[0])`(submit cmd)+ 顺手加 `assert "--detach" in cmd` |
| R2 call_count | `call_count == N`(N 个 candidate) | `call_count == 2 * N`(每 candidate submit+wait;若该测试触发 cancel 再 +1) |
| R3 side_effect 列表 | `side_effect=[proc_a, proc_b]` | 每个 wait 段 proc 前插 `_make_async_completed(_detach_ok_stdout())`:`side_effect=[_make_async_completed(_detach_ok_stdout()), proc_a, _make_async_completed(_detach_ok_stdout()), proc_b]` |
| R4 side_effect callable | `def _route(*a, **kw): return proc` | 函数体顶部插 dispatch:`if "--detach" in a: return _make_async_completed(_detach_ok_stdout())` + `if "cancel" in a: return _make_async_completed('{"ok": true}')` |
| R5 串行锁 fence(`:1666`) | side_effect callable 计数并发 | 应用 R4;断言「最大并发 1」不变(submit/wait 均在锁内顺序执行) |
| R6 错误注入语义 | 单 proc 注入失败 JSON(原到达 run 段) | 不动 — dispatch 后失败 JSON 到达 wait 段,分类共享 `_raise_comfy_failure`,断言不变 |

Expected sweep 后: 三文件全 PASS

- [ ] **Step 3.6: 全量回归**

Run: `python -m pytest -q`
Expected: 全 PASS。若 `tests/unit/test_generate_*_comfy.py` / integration 出现失败,按 R1-R4
同款规则处理(它们大多 mock worker 层非 subprocess 层,预期不受影响)。

- [ ] **Step 3.7: Commit**

```bash
git add src/framework/providers/workers/comfy_worker.py tests/unit/test_comfy_subprocess.py tests/unit/test_comfy_subprocess_audio.py tests/unit/test_comfy_subprocess_video.py
git commit -m "feat: comfy worker 切 run --detach + wait --prompt-id 两段式协议,prompt_id 透传 metadata"
```

---

### Task 4: cancel-on-timeout + 取消归因 fence(commit 4)

**Files:**
- Modify: `src/framework/providers/workers/comfy_worker.py`(`_run_comfy_prompt` 两处 except)
- Test: `tests/unit/test_comfy_subprocess.py`

- [ ] **Step 4.1: 加 hanging fake proc 测试工具**

`tests/unit/test_comfy_subprocess.py` 的 `_AsyncFakeProcess` 之后加:

```python
class _HangingFakeProcess:
    """communicate() 挂起的 fake proc:模拟 CLI 子进程挂死 / 长任务执行中。
    terminate()/kill() 后 communicate()/wait() 返回(模拟真进程被杀)。"""

    def __init__(self) -> None:
        self.returncode: int | None = None
        self._dead = None  # lazy:在首个 await 点创建,绑定当前 loop

    def _ensure_event(self):
        import asyncio as _aio
        if self._dead is None:
            self._dead = _aio.Event()
        return self._dead

    async def communicate(self):
        await self._ensure_event().wait()
        return (b"", b"")

    async def wait(self):
        await self._ensure_event().wait()
        return self.returncode

    def terminate(self):
        self.returncode = -15
        self._ensure_event().set()

    def kill(self):
        self.returncode = -9
        self._ensure_event().set()
```

- [ ] **Step 4.2: 写 4 条 cancel/timeout fence(RED)**

```python
# ---------------------------------------------------------------------------
# detach-wait change Task 4: cancel-on-timeout + 取消归因
# ---------------------------------------------------------------------------


def _route_with_cancel_capture(wait_proc_factory, cancel_cmds: list):
    """side_effect callable 工厂:submit → canned ok;cancel → 记录 cmd;
    其余(wait 段)→ wait_proc_factory()。"""
    def _route(*a, **kw):
        if "--detach" in a:
            return _make_async_completed(_detach_ok_stdout())
        if "cancel" in a:
            cancel_cmds.append(a)
            return _make_async_completed(json.dumps({"ok": True}))
        return wait_proc_factory()
    return _route


@pytest.mark.asyncio
async def test_wait_timeout_error_code_cancels_prompt_then_raises_worker_timeout(tmp_path):
    """spec §4 新行为:wait 返回 error_code=timeout → 先 cancel --prompt-id
    再 raise WorkerTimeout(关僵尸 GPU prompt 边界 — 原阻塞模式下 CLI 超时
    退出后 prompt 继续烧 GPU,retry 再叠一个)。"""
    worker = _make_worker(tmp_path)
    cancel_cmds: list = []
    timeout_json = json.dumps({
        "ok": False, "error": "TimeoutError: Prompt 'x' did not complete within 120s",
        "error_code": "timeout",
    })
    route = _route_with_cancel_capture(
        lambda: _make_async_completed(timeout_json, returncode=2), cancel_cmds)
    with _patch_create_subprocess_exec(side_effect=route):
        with pytest.raises(WorkerTimeout):
            await worker.agenerate(
                spec={"comfy_workflow": "GameAssets/x"}, num_candidates=1)
    assert len(cancel_cmds) == 1, "wait timeout 后应恰好 cancel 1 次"
    assert "--prompt-id" in cancel_cmds[0] and "fake-prompt-1" in cancel_cmds[0]


@pytest.mark.asyncio
async def test_wait_wallclock_timeout_cancels_prompt_then_raises_worker_timeout(
    tmp_path, monkeypatch,
):
    """wall-clock 超时(wait 子进程挂死)→ terminate 子进程 + cancel --prompt-id
    + raise WorkerTimeout。"""
    import framework.providers.workers.comfy_worker as cw
    monkeypatch.setattr(cw, "_SUBPROC_BUFFER_S", 0.05)
    worker = _make_worker(tmp_path)
    cancel_cmds: list = []
    route = _route_with_cancel_capture(lambda: _HangingFakeProcess(), cancel_cmds)
    with _patch_create_subprocess_exec(side_effect=route):
        with pytest.raises(WorkerTimeout):
            await worker.agenerate(
                spec={"comfy_workflow": "GameAssets/x"}, num_candidates=1,
                timeout_s=0.05)
    assert len(cancel_cmds) == 1
    assert "--prompt-id" in cancel_cmds[0] and "fake-prompt-1" in cancel_cmds[0]


@pytest.mark.asyncio
async def test_cancel_during_wait_stage_aborts_with_prompt_id(tmp_path):
    """CancelledError 落在 wait 段 → cancel --prompt-id(归因升级:原裸 cancel)。"""
    worker = _make_worker(tmp_path)
    cancel_cmds: list = []
    route = _route_with_cancel_capture(lambda: _HangingFakeProcess(), cancel_cmds)
    with _patch_create_subprocess_exec(side_effect=route):
        task = asyncio.ensure_future(worker.agenerate(
            spec={"comfy_workflow": "GameAssets/x"}, num_candidates=1))
        # 等 task 推进到 wait 段挂起点:_last_prompt_id 出现 = submit 已完成
        for _ in range(50):
            await asyncio.sleep(0.01)
            if worker._last_prompt_id is not None:
                break
        assert worker._last_prompt_id == "fake-prompt-1", "task 未推进到 wait 段"
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    assert len(cancel_cmds) == 1
    assert "--prompt-id" in cancel_cmds[0] and "fake-prompt-1" in cancel_cmds[0]


@pytest.mark.asyncio
async def test_cancel_during_submit_stage_falls_back_to_bare_cancel(tmp_path):
    """CancelledError 落在 submit 段(还没拿到 prompt_id)→ 裸 cancel fallback。"""
    worker = _make_worker(tmp_path)
    cancel_cmds: list = []

    def _route(*a, **kw):
        if "cancel" in a:
            cancel_cmds.append(a)
            return _make_async_completed(json.dumps({"ok": True}))
        # submit 段直接挂死(--detach cmd 也走这里)
        return _HangingFakeProcess()

    with _patch_create_subprocess_exec(side_effect=_route):
        task = asyncio.ensure_future(worker.agenerate(
            spec={"comfy_workflow": "GameAssets/x"}, num_candidates=1))
        await asyncio.sleep(0.05)   # 让 task 推进到 submit communicate await
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    assert len(cancel_cmds) == 1
    assert "--prompt-id" not in cancel_cmds[0]
```

- [ ] **Step 4.3: 跑 fence 确认 RED**

Run: `python -m pytest tests/unit/test_comfy_subprocess.py -k "cancels_prompt or aborts_with_prompt_id or falls_back_to_bare" -v`
Expected: 前两条 FAIL(cancel 未发生 / 无 --prompt-id);后两条:wait 段 fence FAIL
(Task 3 已实现 CancelledError→prompt_id,此条应已 PASS — 若 PASS 属预期,RED
验证以前两条 timeout fence 为准)

- [ ] **Step 4.4: 实现 — `_run_comfy_prompt` 两处 except 扩为 (WorkerTimeout, CancelledError)**

submit 段:

```python
            except (WorkerTimeout, asyncio.CancelledError):
                # submit 段超时 / 被取消:prompt 可能已 queue 也可能没有 →
                # 裸 cancel best-effort(残留边界见 LLD cancel 小节)
                await self._abort_comfy_prompt(None)
                raise
```

wait 段:

```python
            except (WorkerTimeout, asyncio.CancelledError):
                # wait 段超时(CLI 内部 error_code=timeout 或 wall-clock 挂死)
                # / 被取消:精确取消自己的 prompt(interrupt + queue 删除),
                # 防僵尸 GPU prompt 继续烧卡 + retry 叠加(spec §4)
                await self._abort_comfy_prompt(prompt_id)
                raise
```

- [ ] **Step 4.5: 跑 fence GREEN + 全量**

Run: `python -m pytest tests/unit/test_comfy_subprocess.py -q` → 全 PASS
Run: `python -m pytest -q` → 全 PASS

- [ ] **Step 4.6: Commit**

```bash
git add src/framework/providers/workers/comfy_worker.py tests/unit/test_comfy_subprocess.py
git commit -m "feat: comfy wait 超时/取消先 cancel --prompt-id 再抛,关僵尸 GPU prompt 边界"
```

---

### Task 5: probe_comfy_cancel 真机探针 + probe fence(commit 5)

**Files:**
- Create: `probes/provider/probe_comfy_cancel.py`
- Test: `tests/unit/test_probe_framework.py`

- [ ] **Step 5.1: 写 probe fence(RED)**

`tests/unit/test_probe_framework.py` 文件尾部追加(沿 `:526-563` video probe 同款两条):

```python
# ============================================================================
# probe_comfy_cancel (detach-wait change Task 5)
# ============================================================================


def test_probe_comfy_cancel_default_skip_without_optin(monkeypatch, capsys):
    """probe_comfy_cancel.main() returns 0 + skip message when
    FORGEUE_PROBE_COMFY_CANCEL is not set. 沿 video / audio probe opt-in
    convention(probes/README.md:付费/GPU 调用默认 skip,显式 opt-in 才跑)。"""
    monkeypatch.delenv("FORGEUE_PROBE_COMFY_CANCEL", raising=False)
    from probes.provider import probe_comfy_cancel
    rc = probe_comfy_cancel.main()
    out = capsys.readouterr().out
    assert rc == 0, f"unset FORGEUE_PROBE_COMFY_CANCEL must skip with rc=0, got rc={rc}"
    assert "[SKIP]" in out
    assert "FORGEUE_PROBE_COMFY_CANCEL" in out


def test_probe_comfy_cancel_no_import_side_effects():
    """probe_comfy_cancel.py module-level body must not call hydrate_env() /
    _out_dir() / os.environ[...] at import time(沿 video probe 同款守门)。"""
    import re
    probe_path = _REPO_ROOT / "probes" / "provider" / "probe_comfy_cancel.py"
    src = probe_path.read_text(encoding="utf-8")

    module_body = re.split(r"\ndef\s+\w+|\nasync\s+def\s+\w+", src)[0]
    active_lines = [
        line for line in module_body.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    active = "\n".join(active_lines)

    forbidden_patterns = [
        (r"^\s*_hydrate_env\s*\(\s*\)", "_hydrate_env() at import time"),
        (r"^\s*_out_dir\s*\(\s*\)", "_out_dir() at import time"),
        (r"^\s*hydrate_env\s*\(\s*\)", "hydrate_env() at import time"),
        (r'^\s*API_KEY\s*=\s*os\.environ\[', "API_KEY = os.environ[...] at import"),
    ]
    for pattern, desc in forbidden_patterns:
        assert not re.search(pattern, active, flags=re.MULTILINE), (
            f"probe_comfy_cancel.py: {desc}. Match pattern: {pattern!r}"
        )
```

Run: `python -m pytest tests/unit/test_probe_framework.py -k comfy_cancel -v`
Expected: FAIL — `ModuleNotFoundError: probes.provider.probe_comfy_cancel`

- [ ] **Step 5.2: 写探针**

Create `probes/provider/probe_comfy_cancel.py`(完整文件):

```python
"""Direct probe of ComfyAgentWorker cancel --prompt-id path(opt-in,not paid)。

detach-wait change(2026-06-11)L2 真机验收第 3 项:实证 asyncio task 取消 →
`_abort_comfy_prompt(prompt_id)` 发出 `cancel --prompt-id` → ComfyUI 侧
interrupt + queue 删除生效。

流程(走 ForgeUE worker 生产路径,不裸调 CLI):
1. 构造 video-capability ComfyAgentWorker(长任务给 cancel 留窗口)
2. asyncio task 起 agenerate_video(Wan teacache manifest,~2min GPU)
3. 等 submit 完成(worker._last_prompt_id 出现)+ 数秒 GPU 启动
4. task.cancel() → 期待 CancelledError + worker 内部发 cancel --prompt-id
5. `comfyui_api status --prompt-id <id>` 查 history entry 留证

**不是 paid call** — 本地 GPU subprocess;但仍 opt-in 因需要 ComfyUI server
running + Wan 模型权重已缓存,且会真实占用 GPU 数十秒。

Run:
    FORGEUE_PROBE_COMFY_CANCEL=1 python -m probes.provider.probe_comfy_cancel

Module 顶层零副作用(L3 fence `test_probe_comfy_cancel_no_import_side_effects`
守门):所有 init 推迟到 main()。
"""
from __future__ import annotations

import os
import sys
from pathlib import Path


def _hydrate_env() -> None:
    """Lazy-init only;沿 ForgeUE probe convention(模块顶层零副作用)。"""
    env_path = Path(__file__).resolve().parents[2] / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        os.environ.setdefault(k.strip(), v.strip())


def _out_dir() -> Path:
    """Per probes/README.md §5:
    `demo_artifacts/<date>/probes/provider/probe_comfy_cancel/<HHMMSS>/`。"""
    from datetime import datetime
    root = Path(__file__).resolve().parents[2]
    today = datetime.now().strftime("%Y-%m-%d")
    hms = datetime.now().strftime("%H%M%S")
    p = root / "demo_artifacts" / today / "probes" / "provider" / "probe_comfy_cancel" / hms
    p.mkdir(parents=True, exist_ok=True)
    return p


async def _run_and_cancel(worker, spec) -> tuple[str | None, str]:
    """起 agenerate_video task → 等 submit 完成 → cancel。
    返回 (prompt_id, outcome):outcome ∈ {cancelled, completed, failed:<exc>}。"""
    import asyncio

    task = asyncio.ensure_future(worker.agenerate_video(
        spec=spec, num_candidates=1, seed=42, timeout_s=900.0,
    ))
    # 等 submit 完成(最多 90s:冷启动 + manifest 校验)
    for _ in range(900):
        await asyncio.sleep(0.1)
        if worker._last_prompt_id is not None or task.done():
            break
    prompt_id = worker._last_prompt_id
    if task.done():
        # 没等到 cancel 窗口就终态了(失败或秒完成)
        try:
            task.result()
            return prompt_id, "completed"
        except Exception as exc:  # noqa: BLE001 — probe 留证用
            return prompt_id, f"failed:{type(exc).__name__}:{exc}"
    if prompt_id is None:
        task.cancel()
        return None, "failed:no_prompt_id_after_90s"
    # 给 GPU 任务几秒真正跑起来,再取消
    await asyncio.sleep(8.0)
    task.cancel()
    try:
        await task
        return prompt_id, "completed"  # cancel 竞态:已完成
    except asyncio.CancelledError:
        return prompt_id, "cancelled"


def main() -> int:
    if os.environ.get("FORGEUE_PROBE_COMFY_CANCEL") != "1":
        print(
            "[SKIP] probe opt-in: set FORGEUE_PROBE_COMFY_CANCEL=1 to run "
            "(will submit a real Wan T2V prompt to ComfyUI then cancel it;"
            " needs ComfyUI server running + Wan weights cached)"
        )
        return 0

    import asyncio
    import json
    import subprocess

    _hydrate_env()
    scripts_dir = os.environ.get("FORGEUE_COMFY_SCRIPTS_DIR")
    if not scripts_dir:
        print("[FAIL] FORGEUE_COMFY_SCRIPTS_DIR not set (typical: D:/AI/ComfyUI/scripts)")
        return 1
    if not Path(scripts_dir).is_dir():
        print(f"[FAIL] FORGEUE_COMFY_SCRIPTS_DIR is not a directory: {scripts_dir}")
        return 1

    out_dir = _out_dir()
    print(f"[OK ] output dir: {out_dir}")

    from framework.providers.workers.comfy_worker import (
        ComfyAgentWorker, WorkerUnsupportedResponse,
    )

    artifacts_dir = out_dir / "comfy_artifacts"
    artifacts_dir.mkdir(exist_ok=True)
    try:
        worker = ComfyAgentWorker(
            scripts_dir=Path(scripts_dir),
            model_id="comfy/local-video",
            run_id="probe_cancel",
            project_id="probe_comfy_cancel",
            artifacts_dir=artifacts_dir,
            default_lifecycle="none",
        )
    except WorkerUnsupportedResponse as e:
        print(f"[FAIL] ComfyAgentWorker construct failed: {e}")
        return 1

    spec = {
        "comfy_workflow": "Vedio/Wan2.1-T2V-1.3B_native_teacache",
        "comfy_params": {
            "positive_prompt": "cancel probe abstract scene, slow camera motion",
            "negative_prompt": "blurry, low quality",
            "seed": 42,
        },
        "comfy_lifecycle": "none",
    }

    print("[OK ] submitting Wan teacache prompt then cancelling after ~8s GPU ...")
    prompt_id, outcome = asyncio.run(_run_and_cancel(worker, spec))
    print(f"[OK ] prompt_id: {prompt_id}")
    print(f"[OK ] outcome: {outcome}")

    if outcome != "cancelled":
        print(f"[FAIL] expected outcome=cancelled, got {outcome!r}")
        return 1
    if not prompt_id:
        print("[FAIL] no prompt_id captured")
        return 1

    # 留证:status --prompt-id 查 history entry(被 interrupt 的 prompt 的
    # entry 形态由 ComfyUI 决定 — 可能为空 dict 或带 error/interrupted 状态;
    # probe 只断言「不是正常完成态」,完整 entry 落盘人工对照)
    res = subprocess.run(
        [sys.executable, "-m", "comfyui_api", "status", "--prompt-id", prompt_id],
        cwd=scripts_dir, capture_output=True, text=True, timeout=30,
    )
    evidence = out_dir / "status_after_cancel.json"
    evidence.write_text(res.stdout or "", encoding="utf-8")
    print(f"[OK ] status stdout saved: {evidence}")
    try:
        entry = json.loads(res.stdout).get("entry", {})
    except (json.JSONDecodeError, AttributeError):
        print("[FAIL] status --prompt-id stdout not parseable JSON")
        return 1
    outputs = entry.get("outputs") if isinstance(entry, dict) else None
    if outputs:
        print(f"[FAIL] cancelled prompt has non-empty history outputs: {list(outputs)[:3]}")
        return 1
    print("[OK ] cancelled prompt has no completed outputs in history")
    print("[OK ] probe complete")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 5.3: 跑 probe fence GREEN(离线,只验 skip + 零副作用)**

Run: `python -m pytest tests/unit/test_probe_framework.py -k comfy_cancel -v`
Expected: 2 PASS

- [ ] **Step 5.4: 全量回归 + Commit**

Run: `python -m pytest -q` → 全 PASS

```bash
git add probes/provider/probe_comfy_cancel.py tests/unit/test_probe_framework.py
git commit -m "feat: probe_comfy_cancel 真机 cancel --prompt-id 探针(opt-in)"
```

---

### Task 6: L2 真机验收(手工,需 ComfyUI server + user 在场)

**Files:**
- Create: `docs/archive/forge_changes/2026-06-11-comfy-detach-wait-adoption/notes/live_smoke_image_detach.md`
- Create: `docs/archive/forge_changes/2026-06-11-comfy-detach-wait-adoption/notes/live_smoke_video_detach.md`
- Create: `docs/archive/forge_changes/2026-06-11-comfy-detach-wait-adoption/notes/live_probe_cancel.md`

前置:ComfyUI server running(`python -m comfyui_api status` 显示 online,
不在线先 `python -m comfyui_api serve`,冷启动 ~30-90s);`.env` 或终端 export
`FORGEUE_COMFY_SCRIPTS_DIR=D:/AI/ComfyUI/scripts`。`framework.run` 需 `PYTHONPATH=src`。

- [ ] **Step 6.1: image detach roundtrip(~30s)**

```bash
PYTHONPATH=src python -m framework.run --task examples/comfy_local_smoke.json \
    --live-llm --run-id detachwait-img
```
Expected: run 成功;`artifacts/<today>/detachwait-img/comfy/*.png` 存在;run 日志/
artifact metadata 含 `comfy_prompt_id`。证据(命令输出 + 产物路径 + metadata 摘录)
写入 `live_smoke_image_detach.md`。

- [ ] **Step 6.2: video teacache detach roundtrip(~2min)**

```bash
PYTHONPATH=src python -m framework.run --task examples/comfy_local_smoke_video.json \
    --live-llm --run-id detachwait-vid
```
Expected: `artifacts/<today>/detachwait-vid/<artifact_id>.mp4` 存在(BMFF 校验通过);
metadata 含 `comfy_prompt_id`。证据写入 `live_smoke_video_detach.md`。

- [ ] **Step 6.3: cancel 探针**

```bash
FORGEUE_PROBE_COMFY_CANCEL=1 PYTHONPATH=src python -m probes.provider.probe_comfy_cancel
```
Expected: exit 0;输出含 `[OK ] outcome: cancelled` + status evidence 路径;
`demo_artifacts/<today>/probes/provider/probe_comfy_cancel/<HHMMSS>/status_after_cancel.json`
留存。证据写入 `live_probe_cancel.md`。

- [ ] **Step 6.4: Commit evidence notes**

```bash
git add docs/archive/forge_changes/2026-06-11-comfy-detach-wait-adoption/
git commit -m "docs: comfy-detach-wait-adoption L2 真机 evidence(image/video/cancel)"
```

---

### Task 7: 发布门(验证 → document-release → 分支收尾)

按 CLAUDE.md 固定发布门顺序执行,不在本计划内重复各 skill 清单:

- [ ] **Step 7.1**: 用 `superpowers:verification-before-completion` 做证据化验证
  (全量 `python -m pytest -q` 实测数字 + Task 6 三份 evidence 链接)
- [ ] **Step 7.2**: 用项目级 skill `document-release` 同步:
  - LLD `ComfyAgentWorker` 小节(subprocess 协议重写为 detach+wait 两段式 + 共享
    helper;**cancel 边界标注修正**:interrupt 仍全局,精确部分是 queue 删除;
    `_abort_comfy_prompt(prompt_id)` 签名同步 LLD `:1086-1088`)
  - CLAUDE.md ComfyUI 接入段(run→detach+wait 模式 + cancel 语义)
  - `docs/backlog/active.md` 的 `comfy-detach-wait-adoption` 条目移
    `docs/backlog/archived.md`(backlog 显式结账,CLAUDE.md 硬性要求)
  - CHANGELOG.md + `docs/testing/test_spec.md` fence 清单 + forge change archive
- [ ] **Step 7.3**: document-release 后按范围再验证一次,然后用
  `superpowers:finishing-a-development-branch` 收尾(dev 分支 → PR → main,
  沿项目惯例)

---

## Self-Review 记录

- Spec 覆盖:spec §2 D1-D5 → Task 1(D1)/ Task 3(D1-D3)/ Task 4(D4)/
  Task 5+6(D5);§3 → Task 1+3;§4 → Task 2+4;§5 → Task 3 R6 + 新 fence;
  §6 → Task 3 Step 3.4(d);§7 → Task 3-6;§9 → Task 7。无缺口。
- `_last_prompt_id` 钩子:spec 未显式列出,系 Task 4 wait 段推进判断 + Task 5 探针
  取 prompt_id 的实现必需(沿 `_last_proc` 测试钩子先例),已在 Step 3.4(b) 定义。
- 类型一致性:`_invoke_comfy_cli_once` 返回 `tuple[dict, int]`、`_run_comfy_prompt`
  返回 `tuple[dict, int, str]`,Task 3/4 引用一致;`_abort_comfy_prompt(prompt_id:
  str | None = None)` Task 2 定义与 Task 3/4 调用一致。
