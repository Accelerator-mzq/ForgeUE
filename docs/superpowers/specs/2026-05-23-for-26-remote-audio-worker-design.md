# FOR-26 Remote Audio Worker 设计

日期:2026-05-23

Issue:Linear FOR-26 `LR-0127 remote-audio-worker-integration`

状态:用户已确认采用通用 HTTP remote audio worker,不绑定 ElevenLabs / AudioCraft

更新:用户随后指定 MiniMax music API key 作为真实远端音频用例。FOR-26 在通用
HTTP worker 之外补一个 MiniMax 原生薄 worker,仍不绑定 ElevenLabs / AudioCraft。

## 问题

ForgeUE 已有本地 audio baseline:`AudioWorker` / `AudioCandidate` /
`GenerateAudioExecutor` / `audio.t2a`。本地 ComfyUI 通过 `audio_local`
alias 跑通,但远端音乐生成还不能只靠 URL + API key 接入。

缺口不是 audio artifact 契约,而是远端 worker adapter:

- `framework.run` 当前注册 `GenerateAudioExecutor()` 时没有注入远端 worker。
- `config/models.yaml` 没有远端 audio alias。
- 没有一个最小通用 HTTP 协议把第三方服务返回值转成 `AudioCandidate`。

## 决策

新增 `RemoteHttpAudioWorker`,作为 `AudioWorker` 的第二个真实客户。

运行时通过环境变量启用:

- `FORGEUE_REMOTE_AUDIO_URL`:必填,远端生成接口 URL。
- `FORGEUE_REMOTE_AUDIO_API_KEY`:可选,Bearer token。
- `FORGEUE_REMOTE_AUDIO_MODEL`:可选,透传给远端服务。

没有 `FORGEUE_REMOTE_AUDIO_URL` 时,`framework.run` 仍保持当前行为,不启用远端
worker。本地 `audio_local` / `comfy/local-audio` 路径不受影响。

新增 alias:

- `audio_remote` -> `remote/audio`
- `audio_minimax` -> `minimax/music-2.6`

bundle 仍使用现有 `StepType.generate` + `capability_ref="audio.t2a"`。也就是说,
FOR-26 不新增 step type,不改 Artifact 契约,不改 UE audio import。

## MiniMax 原生 worker

`MiniMaxMusicWorker` 直连 MiniMax `music_generation`:

- 默认 endpoint:`https://api.minimaxi.com/v1/music_generation`
- API key:`MINIMAX_KEY`
- 可选覆盖:`FORGEUE_MINIMAX_MUSIC_URL` / `FORGEUE_MINIMAX_MUSIC_MODEL`
- 启用顺序:`FORGEUE_REMOTE_AUDIO_URL` 优先;没有通用 URL 且有 `MINIMAX_KEY`
  时注入 MiniMax worker

请求体使用 MiniMax 原生字段:`model` / `prompt` / `lyrics` /
`audio_setting` / `output_format`。默认 `output_format="url"`,worker 下载
返回 URL 的音频 bytes 后再落 ForgeUE artifact,避免下游依赖短期 CDN 链接。
同时支持 `output_format="hex"` 的 `data.audio` hex bytes 响应。

## HTTP 契约

请求为 `POST <FORGEUE_REMOTE_AUDIO_URL>`:

```json
{
  "model": "music-model",
  "prompt": "short music cue",
  "num_candidates": 1,
  "seed": 42,
  "spec": {
    "prompt": "short music cue"
  }
}
```

`prompt` 从 `spec.prompt` / `spec.text` / `spec.input` 中取第一个字符串值。
完整 `spec` 会原样透传,让用户自建服务可以读取更多厂商参数。

响应支持两种最小形态:

```json
{
  "candidates": [
    {
      "format": "mp3",
      "bytes_base64": "...",
      "metadata": {"provider": "custom"}
    }
  ]
}
```

或:

```json
{
  "format": "wav",
  "url": "https://example.test/audio.wav"
}
```

`format` 仅接受 `flac` / `mp3` / `wav`。payload 需要通过 magic bytes
二次校验,避免扩展名和内容不一致。

## 错误处理

- URL 未配置:不构造远端 worker,由现有 `GenerateAudioExecutor` 报无可用 worker。
- HTTP 超时 / 连接失败:`AudioWorkerTimeout`。
- 4xx / 5xx / 非 JSON / schema 不可识别:`AudioWorkerUnsupportedResponse` 或
  `AudioWorkerError`。
- 格式不在 whitelist、base64 无法解码、magic bytes 不匹配:
  `AudioWorkerUnsupportedResponse`。

错误不记录 API key。远端返回的 `job_id` 若存在,写入异常字段或 candidate metadata。

## 方案比较

推荐方案:通用 HTTP worker。

优点:最小、可测试、不绑定厂商;用户自建 AudioCraft server 或任何商业 API proxy
都能接。缺点:需要用户提供 URL,只有 API key 不够。

备选 A:ElevenLabs 专用 worker。

优点:开箱更具体。缺点:马上绑定一个厂商响应格式,后续 AudioCraft / Suno / 自建服务
仍要再拆一次。

备选 B:只扩 registry,不写 worker。

优点:改动最小。缺点:运行时仍不知道如何发请求和解析音频,不能关闭 FOR-26。

## 测试

新增离线单测,全部用 `httpx.MockTransport`:

- 请求 body 包含 `model` / `prompt` / `num_candidates` / `seed` / `spec`。
- Bearer token header 仅在 key 存在时发送。
- `bytes_base64` 响应转成 `AudioCandidate`。
- `url` 响应会下载音频 bytes。
- 不支持格式 / magic mismatch / 超时走 audio worker 异常。
- `framework.run` 在 env URL 存在时注入 `RemoteHttpAudioWorker`。
- `framework.run` 在仅有 `MINIMAX_KEY` 时注入 `MiniMaxMusicWorker`。
- `audio_remote` alias 能解析为 kind=`audio`。
- `audio_minimax` alias 能解析为 kind=`audio`。

## 验收

完成标准:

- `examples/remote_audio_smoke.json` 可被 loader + dry-run 接受。
- `examples/minimax_music_smoke.json` 可被 loader + dry-run 接受。
- `audio_remote` alias 可解析。
- `audio_minimax` alias 可解析。
- 设置 `FORGEUE_REMOTE_AUDIO_URL` 后,`framework.run` 注入远端 worker。
- 设置 `MINIMAX_KEY` 且未设置 `FORGEUE_REMOTE_AUDIO_URL` 后,`framework.run`
  注入 MiniMax worker。
- 不设置 URL 时,现有本地 ComfyUI audio 路径保持不变。
- FOR-26 从 backlog active 归档到 archived,并同步 SRS / testing spec /
  acceptance report / CHANGELOG。
