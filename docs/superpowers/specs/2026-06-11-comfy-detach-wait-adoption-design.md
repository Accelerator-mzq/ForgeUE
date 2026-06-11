# comfy-detach-wait-adoption — 设计 spec

> 日期:2026-06-11 · 状态:已与用户确认 · 来源 backlog:`docs/backlog/active.md` 的
> `2026-06-11-comfy-agent-api-v3-adaptation::comfy-detach-wait-adoption`
> 动机(用户确认):清 backlog + 与上游推荐的 submit-then-poll 模式架构对齐;
> 无迫切多租户 / 并发场景 → **最小爆炸半径优先**。

## 0. 一句话

`ComfyAgentWorker` 4 条 `_run_once_*_async` 先收敛到共享 subprocess helper(纯重构),
再把阻塞 `run` 协议换成 `run --detach` + `wait --prompt-id` 两段式;cancel 升级
`cancel --prompt-id`,并新增「超时后先 cancel 再 raise」关掉僵尸 GPU prompt 边界。

## 1. 上游契约(2026-06-11 已逐条核验实装,非 doc claim)

来源:`D:/AI/ComfyUI/docs/workflows/COMFYUI_AGENT_API.md` v3.3 §1.6/§1.8 +
`scripts/comfyui_api/cli.py` / `runner.py` 实码。

| 命令 | 已核验行为 | 出处 |
|---|---|---|
| `run --detach` | submit 前同步完成 manifest 校验 + `input_image*` auto-upload;返回 `{ok, prompt_id, detached:true, timeout_hint_s, params_used, project, date, lifecycle}`;仅支持 lifecycle `none`/`ensure_running`(ForgeUE 固定传 `none` ✓);与 `--render-views` 互斥(ForgeUE 不用 ✓) | `cli.py:182-216`, `runner.py:405-457` |
| `wait --prompt-id X --timeout N` | 内部 `runner.poll` 轮询 `/history`;成功返 `{ok, prompt_id, wait_duration_s, outputs}`;失败 `{ok:false, error, error_code}` exit 2(`timeout`/`prompt_errored`/`comfy_unreachable`/`prompt_lost`);**可重复调用**(poll 只读 history,已完成立即返回);poll fail-fast(~60s 判 server 死)对阻塞 run 与 wait 同源生效 | `cli.py:379-389`, `runner.py:222-252` |
| `cancel --prompt-id X` | **无条件全局 `POST /interrupt`** + 针对性 `POST /queue {"delete":[X]}`。"精确"只体现在 queue 删除;interrupt 部分仍是全局的 | `cli.py:329-358` |
| `status --prompt-id X` | 返回该 prompt 的 history entry(本 change 不消费,记录备查) | `cli.py:302-315` |

**两个修正 backlog 原始假设的发现**:

1. backlog 写的「精确取消」偏乐观:多租户下若我方 prompt 在排队、别家在跑,
   `cancel --prompt-id` 仍会 interrupt 别家。但它是对现状的**严格改进**:今天裸
   `cancel` 不仅打断别家,我方排队 prompt 还会继续跑掉白烧 GPU;升级后至少我方的
   会从 queue 删掉。残留边界在 LLD 文档化(见 §7)。
2. backlog 写的「长任务期间更快感知 server 崩溃」收益已不存在:poll fail-fast
   在上游 `runner.poll` 实现,v3 起阻塞 run 与 wait 走同一函数。

detach 化的**真实差异收益**:① 拿到 `prompt_id` → 可追溯 + cancel 时 queue 删除;
② CLI 子进程挂死 / 被杀后 prompt 不失联(可凭 id 善后);③ 超时路径可精确 cancel
自己的 prompt(关僵尸 GPU 边界,见 §4)。

## 2. 已确认的设计决策

| # | 决策 | 选择 | 理由 |
|---|---|---|---|
| D1 | 实施路径 | **方案 A:先提共享 helper(纯重构)再 detach 化一次实现** | 4 条 `_run_once_*_async` 同构 ~120 行;detach 逻辑只写一份;重构与行为变更分两个可独立验证的 commit |
| D2 | 锁语义 | **全程串行:`_comfy_submit_lock` 包 submit→wait 整段** | GPU 单任务现实下只锁 submit 段 wall-clock 收益≈0;全程串行保留 cancel 归因不变量,fence 改造量最小。只锁 submit 留 follow-on |
| D3 | wait 策略 | **单次长 wait(`--timeout` = per-call timeout)** | chunked 短轮询多付 interpreter spawn 开销(~1-2s/次)无对应收益;`CancelledError` 在 `communicate()` await 点照常可达 |
| D4 | 超时后 cancel 归属 | **ForgeUE 侧**(不动上游) | wall-clock 挂死 / CancelledError 路径反正需要 ForgeUE 自己发 cancel,超时路径复用只多 1 行;不扩 must-preserve 清单;兼容原版 v3.3。上游 `--cancel-on-timeout` flag 留作独立上游改进,不进本 change 验收(双 cancel 幂等无害:空转 `/interrupt` 与删除不存在 queue id 均 no-op) |
| D5 | L2 验收范围 | **image smoke + video teacache smoke + cancel 探针** | 覆盖快/慢两极 roundtrip + cancel 真机行为实证 |

## 3. 架构与数据流

### 3.1 共享 helper(commit 1,纯重构)

新增模块级 / 类内 helper(沿 `_raise_comfy_failure` 提取先例),签名意向:

```python
async def _run_comfy_prompt(
    self, *, comfy_workflow: str, params: dict, timeout_s: float, context: str,
) -> tuple[dict, int]:
    """整段在 _comfy_submit_lock() 内。返回 (outputs dict, 末段子进程 returncode)。"""
```

收敛内容:拼 cmd → `create_subprocess_exec` → `communicate()` + wall-clock 守门 →
finally abort/terminate/kill 清理 → decode(`errors="replace"`)→ 空 stdout / 非 JSON
/ 非 dict 守门 → `ok=false` 走 `_raise_comfy_failure` → `outputs` 字段存在性守门。

4 条 `_run_once_*_async` 保留各自的:参数拼装、`_validate_outputs` 三段表调用、
capability 特有 candidate 构造(PNG/GLB/audio magic bytes、BMFF 5-tuple 等校验逻辑
**零变化**)。`_last_proc` 测试钩子由 helper 维护:每次 spawn 即更新,detach 化后
先后指向 submit / wait 子进程(终态指 wait;cancel fence 据此断言)。

commit 1 验收:阻塞 `run` 协议不变,全量 fence 绿(基数以 `python -m pytest -q` 实测)。

### 3.2 detach+wait 协议(commit 2)

helper 内部替换为两段式,整段仍在锁内:

```
1. submit: run --detach --workflow X --params J --project P --lifecycle none --timeout N
   - 子进程 wall-clock 上限 = 新常量 _SUBMIT_TIMEOUT_S(60s;覆盖 manifest 校验
     + mesh staging PNG auto-upload)
   - stdout JSON ok=false → _raise_comfy_failure(deterministic 错在 submit 段就近报)
   - prompt_id 缺失/非 str → WorkerUnsupportedResponse(契约破坏)
2. wait: wait --prompt-id <id> --timeout N
   - 子进程 wall-clock 上限 = N + _SUBPROC_BUFFER_S(沿现状 30s buffer)
   - ok=false → 先按 §4 处理 timeout,再 _raise_comfy_failure
3. 返回 (outputs, wait_returncode)
```

## 4. 取消与超时语义(本 change 核心收益)

- `_abort_comfy_prompt(prompt_id: str | None)`:有 id → `cancel --prompt-id <id>`;
  无 id(submit 段就被取消的窄窗口)→ 退回裸 `cancel`。仍 best-effort、失败只
  warning、`_ABORT_TIMEOUT_S` 守门 + 子进程 kill 清理(全部沿现状)。
- **新行为(关僵尸 GPU 边界)**:wait 返回 `error_code=timeout` **或** wall-clock
  `asyncio.TimeoutError` → 先 `cancel --prompt-id` 再 raise `WorkerTimeout`。
  现状 bug:CLI 内部超时退出后 `finally` 看到进程已退不 abort,GPU prompt 继续跑,
  retry 再叠一个。
- `CancelledError` 落在 wait 段 `communicate()` await 点 → finally 里
  `cancel --prompt-id` + terminate wait 子进程,与现状同构但归因升级。
- `CancelledError` 落在 submit 段 → 裸 cancel fallback(此时可能已 queue 也可能没有;
  残留边界文档化)。

## 5. 失败分类(零新增分类逻辑)

`_raise_comfy_failure` 直接复用,code 优先 + marker fallback 不变:

| 阶段 | error_code | 映射 |
|---|---|---|
| submit | `missing_required_param` / `param_out_of_range` / `value_not_in_list` / `workflow_not_found` / `input_image_not_found` / `invalid_arguments` / `comfy_rejected` | `WorkerUnsupportedResponse`(deterministic,不 retry) |
| submit | `comfy_unreachable` 等其余 | `WorkerError`(本地非 premium retry,`policy.max_attempts`) |
| wait | `timeout` | **先 cancel** → `WorkerTimeout` |
| wait | `prompt_errored` / `comfy_unreachable` / `prompt_lost` | `WorkerError`(retry 重提合理:OOM / server 重启场景) |

## 6. metadata 增量

- 4 capability 的 candidate metadata 新增 `comfy_prompt_id`(可追溯性即本 change 收益)。
- `exit_code`(mesh/audio/video 的 `comfy_subprocess_run_metadata`)记 **wait** 子进程
  returncode(产物来自 wait 段)。

不动:bundle spec 面、executor 调用面、DryRunPass(仍 `status` 探活)、
`ComfyLifecycleManager`(serve/stop 路径与本 change 无交集)。

## 7. 测试与验收

### L0/L1 fence

- 既有 ~125 条 subprocess fence(`test_comfy_subprocess{,_audio,_video}.py`):mock
  脚手架从单子进程改为**双子进程序列**(FakeProcess 队列);断言面(异常分类 /
  candidate 构造)大多不动。
- 新 fence 清单:
  1. submit cmd 含 `--detach`(4 capability 经参数化或共 helper fence 覆盖)
  2. wait cmd 形状:`wait --prompt-id <id> --timeout N`
  3. `prompt_id` 透传到 candidate metadata(`comfy_prompt_id`)
  4. cancel 路径断言 `cancel --prompt-id <id>`
  5. wait `error_code=timeout` → 先 cancel 再 raise `WorkerTimeout`
  6. wall-clock `asyncio.TimeoutError` → 同上
  7. submit 段 `CancelledError` → 裸 cancel fallback
  8. submit 响应 `prompt_id` 缺失 → `WorkerUnsupportedResponse`
  9. 重构防 drift:4 条 `_run_once_*_async` 共走同一 helper(防 4 份 diff 复发)
- 测试总数不硬编码,以 `python -m pytest -q` 实测为准(当前基数 1363 passed,2026-06-11)。

### L2 真机(evidence 落 forge change notes)

1. image smoke(`examples/comfy_local_smoke.json`,~30s):验证 detach→wait 短任务
   roundtrip + 产物落 `artifacts/<today>/<run_id>/comfy/`。
2. video teacache smoke(`examples/comfy_local_smoke_video.json`,~2min):验证长任务
   wait 路径。
3. 新探针 `probes/provider/probe_comfy_cancel.py`:opt-in env(如
   `FORGEUE_PROBE_COMFY_CANCEL=1`,不接受 `false`/`0`)、模块顶层零副作用、ASCII
   输出标记、exit code 约定按 `probes/README.md`;流程 = **走 ForgeUE worker 路径**:
   `agenerate_video` 起 asyncio task(video manifest 长任务)→ 短暂等待 → 取消该
   task → 实证 `_abort_comfy_prompt` 发出 `cancel --prompt-id` 且 ComfyUI 侧
   interrupt + queue 删除生效(后续 `status --prompt-id` 显示非成功终态)。涉及
   lazy-init / opt-in 的对应 fence 加到 `tests/unit/test_probe_framework.py`。

## 8. Out of scope(本 change 不做)

- 只锁 submit 段(ComfyUI 侧排队 pipeline)→ 真有并发需求再开 follow-on
- 上游 `cancel` 条件化 interrupt(查 queue_running 再决定是否 interrupt)→ 动上游
  user-authored 目录,残留边界文档化即可
- 上游 `wait --cancel-on-timeout` flag → 独立上游改进,受益方是上游全体消费者,
  与本 change 验收解耦(D4)
- chunked 短 wait 轮询 → YAGNI
- `status --prompt-id` 状态消费 → 本 change 无需

## 9. 文档结账(document-release 阶段)

- LLD `ComfyAgentWorker` 小节:subprocess 协议重写(detach+wait 两段式 + 共享
  helper)+ **cancel 边界标注修正**(interrupt 仍全局,精确部分是 queue 删除;
  2026-06-11 标注的"精确取消需 detach"表述按本次核验更新)
- HLD 若有 comfy worker 时序描述同步
- CLAUDE.md ComfyUI 接入段:run→detach+wait 模式描述 + cancel 语义更新
- `docs/backlog/active.md` 条目移 `archived.md`(tombstone)
- CHANGELOG + forge change archive(含 3 份 L2 evidence notes)
- `docs/testing/test_spec.md` fence 清单同步
