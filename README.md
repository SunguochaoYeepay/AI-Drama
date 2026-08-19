# AI Drama

把多角色故事脚本转换为可用于短视频制作的剧情音频。MiniMax Speech 2.8 负责角色语音，ElevenLabs Sound Effects 负责环境音和拟音，最后通过 FFmpeg 完成时间轴混音并输出字幕。

## 当前能力

- 支持 `speech-2.8-hd` 和 `speech-2.8-turbo`
- 每个角色独立配置音色、语速、音量、音高和默认情绪
- 每句台词可以覆盖情绪和演绎参数
- 支持 `<#1.2#>` 停顿标签与 `(laughs)`、`(sighs)` 等 Speech 2.8 语气标签
- 分句生成并缓存，修改一句时不必重新生成整段故事
- 使用 ElevenLabs `eleven_text_to_sound_v2` 生成环境音和定点音效
- 环境音可以按绝对时间或指定台词开始，支持循环、音量和淡入淡出
- 自动合并完整音频并根据实际时长生成 SRT 字幕
- 保存请求计划、接口追踪编号和生成清单，方便排查失败请求

## 开始使用

运行环境需要 Python 3.11 及 FFmpeg。Python 部分没有第三方运行依赖。

1. 在项目根目录创建 `.env`，填入两个平台的 API Key：

   ```dotenv
   MINIMAX_API_KEY=your_api_key
   ELEVENLABS_API_KEY=your_api_key
   ```

2. 复制并修改 [`examples/demo_story.json`](examples/demo_story.json)，为每个角色设置 MiniMax 音色 ID，并按顺序填写台词。

3. 先检查脚本，不调用接口、不产生费用：

   ```bash
   python3 -m ai_drama generate examples/demo_story.json --dry-run
   ```

4. 生成逐句语音、环境音、最终混音和字幕：

   ```bash
   python3 -m ai_drama generate examples/demo_story.json
   ```

默认结果位于 `outputs/demo_story/`。也可以使用 `--output` 指定目录，或使用 `--no-merge` 只生成分句音频。

## 故事脚本

```json
{
  "title": "故事标题",
  "model": "speech-2.8-hd",
  "characters": {
    "narrator": {
      "name": "旁白",
      "voice_id": "Chinese (Mandarin)_Lyrical_Voice",
      "speed": 0.95,
      "vol": 1,
      "pitch": 0,
      "emotion": "calm"
    }
  },
  "sound_effects": [
    {
      "id": "rainy_night",
      "prompt": "Steady nighttime rain, no music, no voices, seamless loop",
      "start_at_line": 1,
      "duration_seconds": 10,
      "prompt_influence": 0.65,
      "loop": true,
      "until_end": true,
      "volume_db": -23,
      "fade_in_ms": 500,
      "fade_out_ms": 800
    }
  ],
  "lines": [
    {
      "speaker": "narrator",
      "text": "故事开始了。(sighs)",
      "pause_after_ms": 400
    }
  ]
}
```

Speech 2.8 可用情绪：`happy`、`sad`、`angry`、`fearful`、`disgusted`、`surprised`、`calm`。未填写时由模型根据台词自动判断。

环境音的 `duration_seconds` 必须在 0.5–30 秒之间。`start_ms` 表示从成片第几毫秒开始；`start_at_line` 表示从第几句台词开始，二者只填一个。持续环境音可设置 `loop: true` 和 `until_end: true`，系统会循环到对白结束。建议用英文描述音效，并加入 `no music, no voices`，减少模型生成音乐或人声的概率。

## 输出内容

- `segments/`：每句角色音频及对应接口信息
- `sound_effects/`：ElevenLabs 生成的环境音及缓存信息
- `dialogue.mp3`：合并后的完整对话
- `final_mix.mp3`：对白与全部环境音混合后的最终音频
- `dialogue.srt`：按实际音频时长生成的字幕
- `plan.json`：正式请求前的完整生成计划
- `manifest.json`：本次生成结果和 MiniMax `trace_id`

生成内容默认不会提交到 GitHub。真实人物、网络热点和第三方故事在发布前仍需检查事实、隐私和版权风险。
