> ## Documentation Index
> Fetch the complete documentation index at: https://platform.minimaxi.com/docs/llms.txt
> Use this file to discover all available pages before exploring further.

# 音乐生成

> 通过 prompt 参数定义音乐的风格、情绪和场景，通过 lyrics 参数提供演唱的歌词内容。该功能可用于为视频、游戏或应用快速生成独特的背景音乐和主题曲。

## Music 2.6：以声传情：翻唱入心，器乐入魂

以声传情：翻唱入心，器乐入魂

## 音乐生成示例

下面以生成一首欢快的新年歌曲为例，演示如何通过两步完成从灵感到成品的全流程：先用歌词生成接口，根据主题自动写词；再用音乐生成接口创作，轻松产出一首完整歌曲。

<Steps>
  <Step title="调用歌词生成接口，根据主题生成歌词（可选）">
    只需告诉模型你想要什么主题——比如"一首欢乐的新年歌曲"，歌词生成接口就会自动为你写出包含段落结构（Verse、Chorus、Bridge 等）的完整歌词。如果你已经有了歌词，可以跳过这一步。另外即使没有歌词也可以直接进入第二步，调用音乐生成接口，谱曲并生成完整歌曲。

    <CodeGroup>
      ```python 歌词生成 theme={null}
      import requests
      import os

      url = "https://api.minimaxi.com/v1/lyrics_generation"
      api_key = os.environ.get("MINIMAX_API_KEY")

      payload = {
          "mode": "write_full_song",
          "prompt": "一首欢乐的新年歌曲"
      }
      headers = {
          "Content-Type": "application/json",
          "Authorization": f"Bearer {api_key}"
      }

      response = requests.post(url, json=payload, headers=headers)

      print(response.text)
      ```
    </CodeGroup>
  </Step>

  <Step title="调用音乐生成接口，谱曲并生成完整歌曲">
    拿到歌词后，通过 `prompt` 设定音乐风格（如 "Mandopop, Festive, Upbeat"），将歌词传入 `lyrics` 参数，音乐生成接口会为你编曲、演唱，输出一首完整的歌曲。如果没有歌词，可将 [lyrics\_optimizer](https://platform.minimaxi.com/docs/api-reference/music-generation#body-lyrics-optimizer) 参数设置为 true，则可直接生成歌曲。而且 Music 2.6 支持了纯音乐生成，请参考 [is\_instrumental](https://platform.minimaxi.com/docs/api-reference/music-generation#body-is-instrumental) 参数。

    <CodeGroup>
      ```python 音乐生成 theme={null}
      import requests
      import json
      import os

      url = "https://api.minimaxi.com/v1/music_generation"
      api_key = os.environ.get("MINIMAX_API_KEY")

      headers = {
          "Content-Type": "application/json",
          "Authorization": f"Bearer {api_key}"
      }

      payload = {
          "model": "music-2.6",
          "prompt": "Mandopop, Festive, Upbeat, Celebration, New Year",
          "lyrics": "[Intro]\n嘿！新年到！\n(新年快乐！)\n大家一起笑！\n(哈哈！)\n鞭炮声声响，锣鼓敲起来！\n一，二，三，四，一起嗨！\n\n[Verse 1]\n旧的一年已经过去，烟花点亮夜空\n(点亮夜空)\n新的一年已经来临，充满希望和感动\n家家户户贴春联，红红火火多喜庆\n(多喜庆)\n孩子们换上新衣裳，脸上洋溢着笑容\n街头巷尾人潮涌，热闹非凡真开心\n(真开心)\n暖暖的祝福在传递，温暖了我的心\n空气中弥漫着年味，饺子和汤圆香\n(香喷喷)\n这个时刻属于我们，一起尽情地歌唱\n\n[Pre-Chorus]\n锣鼓敲起来 鞭炮响起来\n(噼里啪啦！)\n笑声传过来 祝福送过来\n(新年好！)\n心儿跳起来 身体摆起来\n\n[Chorus]\n新年到！新年到！乐翻天！\n(乐翻天！)\n大家笑！大家跳！乐翻天！\n(乐翻天！)\n烦恼都忘掉，快乐最重要\n新的一年，好运一定会来到！\n新年到！新年到！乐翻天！\n(乐翻天！)\n舞步跳！歌声飘！乐翻天！\n(乐翻天！)\n祝福送给你，幸福永相依\n我们一起迎接这美好的新年！\n\n[Verse 2]\n亲朋好友齐聚一堂，举杯共饮美酒\n(共饮美酒)\n回忆过去的美好时光，畅谈未来的追求\n长辈的关怀和叮咛，晚辈的问候和拜年\n(和拜年)\n这份亲情的力量，让我们更加坚强\n电视里播放着春晚，节目精彩又好看\n(又好看)\n一家人围坐在一起，温馨又充满温暖\n窗外的雪花轻轻飘，大地一片银装素裹\n(银装素裹)\n愿这美好的时刻，永远铭刻在心窝\n\n[Bridge]\n（唱起来！）\n（跳起来！）\n（笑起来！）\n（嗨起来！）\n所有的梦想，在新的一年里实现！\n所有的烦恼，在新的一年里不见！\n（大声喊！）\n新年！新年！新年快乐！\n\n[Chorus]\n新年到！新年到！乐翻天！\n(乐翻天！)\n大家笑！大家跳！乐翻天！\n(乐翻天！)\n烦恼都忘掉，快乐最重要\n新的一年，好运一定会来到！\n新年到！新年到！乐翻天！\n(乐翻天！)\n舞步跳！歌声飘！乐翻天！\n(乐翻天！)\n祝福送给你，幸福永相依\n我们一起迎接这美好的新年！\n\n[Outro]\n新年好！\n(新年好！)\n乐翻天！\n(再一年！)\n（新年快乐！哈哈！）\n（耶！）",
          "audio_setting": {
              "sample_rate": 44100,
              "bitrate": 256000,
              "format": "mp3"
          },
          "output_format": "url"
      }

      response = requests.post(url, headers=headers, json=payload)
      result = response.json()

      print(json.dumps(result, ensure_ascii=False, indent=2))
      ```
    </CodeGroup>
  </Step>

  <Step title="试听生成结果">
    完成上述两步后，你将得到一首完整的歌曲！点击播放即可试听效果：

    <video controls className="w-full aspect-video rounded-xl audio-container" src="https://filecdn.minimax.chat/public/de53bb96-10e6-428f-9036-9e3ce74cca3a.mp3" />
  </Step>
</Steps>

## 翻唱生成

Music Cover 可以基于已有歌曲生成不同风格的翻唱版本。支持两种模式：

* **一步翻唱**：直接传入参考音频，系统自动通过 ASR 提取歌词。
* **两步翻唱**：先对音频进行前处理，提取并修改歌词后再生成翻唱。

### 一步翻唱（快捷模式）

将参考音频 URL 和风格描述直接传入音乐生成接口，歌词将从音频中自动提取。

<CodeGroup>
  ```python 一步翻唱 theme={null}
  import requests
  import json
  import os

  url = "https://api.minimaxi.com/v1/music_generation"
  api_key = os.environ.get("MINIMAX_API_KEY")

  headers = {
      "Content-Type": "application/json",
      "Authorization": f"Bearer {api_key}"
  }

  payload = {
      "model": "music-cover",
      "audio_url": "https://example.com/original-song.mp3",
      "prompt": "爵士风格，慵懒深夜酒吧，萨克斯",
      "audio_setting": {
          "sample_rate": 44100,
          "bitrate": 256000,
          "format": "mp3"
      },
      "output_format": "url"
  }

  response = requests.post(url, headers=headers, json=payload)
  result = response.json()

  print(json.dumps(result, ensure_ascii=False, indent=2))
  ```
</CodeGroup>

### 两步翻唱（进阶模式 — 支持歌词修改）

如需修改歌词，可使用两步流程：先调用前处理接口提取音频特征和歌词，修改歌词后再生成翻唱。

<Steps>
  <Step title="步骤 1：预处理参考音频">
    调用[翻唱前处理接口](/api-reference/music-cover-preprocess)提取音频特征和结构化歌词。此步骤**免费**（不计费）。

    返回内容包括：

    * `cover_feature_id`：音频特征唯一标识（有效期 24 小时）
    * `formatted_lyrics`：带段落标签（`[Verse]`、`[Chorus]` 等）的结构化歌词，可自由编辑
    * `structure_result`：JSON 字符串，包含段落类型和时间戳
    * `audio_duration`：参考音频时长（秒）

    <CodeGroup>
      ```python 前处理 theme={null}
      import requests
      import json
      import os

      url = "https://api.minimaxi.com/v1/music_cover_preprocess"
      api_key = os.environ.get("MINIMAX_API_KEY")

      headers = {
          "Content-Type": "application/json",
          "Authorization": f"Bearer {api_key}"
      }

      payload = {
          "model": "music-cover",
          "audio_url": "https://example.com/original-song.mp3"
      }

      response = requests.post(url, headers=headers, json=payload)
      result = response.json()

      # 保存 cover_feature_id 并查看提取的歌词
      cover_feature_id = result["cover_feature_id"]
      formatted_lyrics = result["formatted_lyrics"]

      print(f"特征 ID: {cover_feature_id}")
      print(f"提取的歌词:\n{formatted_lyrics}")
      ```
    </CodeGroup>
  </Step>

  <Step title="步骤 2：修改歌词并生成翻唱">
    查看并编辑上一步返回的 `formatted_lyrics`，然后将 `cover_feature_id` 和修改后的歌词传入[音乐生成接口](/api-reference/music-generation)。

    <Note>
      使用 `cover_feature_id` 时，不要传入 `audio_url` 或 `audio_base64`（三者互斥）。`lyrics` 参数为必填（10–1000 字符）。
    </Note>

    <CodeGroup>
      ```python 生成翻唱 theme={null}
      import requests
      import json
      import os

      url = "https://api.minimaxi.com/v1/music_generation"
      api_key = os.environ.get("MINIMAX_API_KEY")

      headers = {
          "Content-Type": "application/json",
          "Authorization": f"Bearer {api_key}"
      }

      # 使用上一步返回的 cover_feature_id
      # 根据需要修改提取的歌词
      modified_lyrics = "[Verse 1]\n这里是修改后的第一段歌词\n用新的文字讲述你的故事\n\n[Chorus]\n全新的副歌部分\n用不同的感觉演唱"

      payload = {
          "model": "music-cover",
          "cover_feature_id": cover_feature_id,
          "lyrics": modified_lyrics,
          "prompt": "爵士风格，慵懒深夜酒吧，萨克斯",
          "audio_setting": {
              "sample_rate": 44100,
              "bitrate": 256000,
              "format": "mp3"
          },
          "output_format": "url"
      }

      response = requests.post(url, headers=headers, json=payload)
      result = response.json()

      print(json.dumps(result, ensure_ascii=False, indent=2))
      ```
    </CodeGroup>
  </Step>
</Steps>

## 推荐阅读

<Columns cols={2}>
  <Card title="音乐生成接口" icon="book-open" href="/api-reference/music-generation" arrow="true" cta="点击查看">
    使用 API 接口，输入歌词和歌曲描述，进行歌曲生成。
  </Card>

  <Card title="翻唱前处理接口" icon="book-open" href="/api-reference/music-cover-preprocess" arrow="true" cta="点击查看">
    对参考音频进行预处理，提取特征和歌词，用于两步翻唱生成。
  </Card>

  <Card title="歌词生成接口" icon="book-open" href="/api-reference/lyrics-generation" arrow="true" cta="点击查看">
    使用 API 接口，输入歌曲描述，进行歌词生成或编辑。
  </Card>

  <Card title="产品定价" icon="book-open" href="/guides/pricing-paygo#音乐" arrow="true" cta="点击查看">
    各模型的定价说明、计费方式及使用限制。
  </Card>

  <Card title="速率限制" icon="book-open" href="/guides/rate-limits#3、我们的-api-的限速具体数值" arrow="true" cta="点击查看">
    为保证资源的高效使用，引入速率限制，以确保服务的可用性、稳定性。
  </Card>
</Columns>
