# AI Drama

把多角色故事脚本转换为可用于短视频制作的剧情音频。基础版使用 MiniMax Speech 2.8 逐句生成角色语音，再通过 FFmpeg 合并完整对话并输出字幕。

## 当前能力

- 支持 `speech-2.8-hd` 和 `speech-2.8-turbo`
- 每个角色独立配置音色、语速、音量、音高和默认情绪
- 每句台词可以覆盖情绪和演绎参数
- 支持 `<#1.2#>` 停顿标签与 `(laughs)`、`(sighs)` 等 Speech 2.8 语气标签
- 分句生成并缓存，修改一句时不必重新生成整段故事
- 自动合并完整音频并根据实际时长生成 SRT 字幕
- 保存请求计划、接口追踪编号和生成清单，方便排查失败请求

## 开始使用

运行环境需要 Python 3.11 及 FFmpeg。Python 部分没有第三方运行依赖。

1. 在项目根目录创建 `.env`，填入 MiniMax API Key：

   ```dotenv
   MINIMAX_API_KEY=your_api_key
   ```

2. 复制并修改 [`examples/demo_story.json`](examples/demo_story.json)，为每个角色设置 MiniMax 音色 ID，并按顺序填写台词。

3. 先检查脚本，不调用接口、不产生费用：

   ```bash
   python3 -m ai_drama generate examples/demo_story.json --dry-run
   ```

4. 生成逐句音频、完整对话和字幕：

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

## 输出内容

- `segments/`：每句角色音频及对应接口信息
- `dialogue.mp3`：合并后的完整对话
- `dialogue.srt`：按实际音频时长生成的字幕
- `plan.json`：正式请求前的完整生成计划
- `manifest.json`：本次生成结果和 MiniMax `trace_id`

生成内容默认不会提交到 GitHub。真实人物、网络热点和第三方故事在发布前仍需检查事实、隐私和版权风险。
