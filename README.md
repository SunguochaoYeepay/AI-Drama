# AI Drama

把多角色故事脚本转换为可用于短视频制作的剧情音频和基础视频镜头。MiniMax Speech 2.8 负责角色语音，ElevenLabs Sound Effects 负责环境音和拟音，Qwen Image 负责人物与关键帧，MiniMax H3 负责短视频镜头。

## AI Skill

仓库内置四个可复用 Skill，按下面顺序使用：

1. [`generate-ai-drama-screenplay`](SKILL/generate-ai-drama-screenplay/SKILL.md)：把故事拆成完整剧本、对白 ID、镜头和 DramaClaw 制作包。
2. [`generate-ai-drama-audio`](SKILL/generate-ai-drama-audio/SKILL.md)：用 MiniMax Speech 2.8 生成人声，用 ElevenLabs 生成环境音和拟音，输出混音与字幕。
3. [`generate-ai-drama-visuals`](SKILL/generate-ai-drama-visuals/SKILL.md)：为 Qwen、Flux 和 ComfyUI 生成真实、连续、可审核的人物、场景和关键帧提示词。
4. [`generate-ai-drama-video`](SKILL/generate-ai-drama-video/SKILL.md)：使用已确认的关键帧和音频，分段生成 MiniMax H3 视频，并用尾帧接力保持连续。

每个有对白的镜头都必须在提示词中明确写出“谁在说话”和“说什么”。`dialogue_ids` 只是程序引用，不能代替给 Qwen/Flux/H3 的自然语言指令。每个场景还要先生成并审核场景参考图，以及餐桌、手机、账本、作业本、餐具等连续性关键道具的参考图。

支持 Skills 的 AI 可以直接使用：

```text
使用 $generate-ai-drama-audio，把这个故事制作成多角色剧情音频：……

使用 $generate-ai-drama-screenplay，把这个故事拆成完整短剧剧本和 DramaClaw 制作包：……

使用 $generate-ai-drama-video，按已确认的故事和音频生成角色关键帧，并跑一个 H3 4 步测试镜头。
```

如果当前 AI 不会自动发现仓库中的 Skill，请先让它完整读取 `SKILL/generate-ai-drama-audio/SKILL.md`，再提供故事。Skill 不包含 API Key；密钥仍只保存在本地 `.env`。

## 推荐工作流

```text
故事
  -> 剧本与制作包
  -> MiniMax Speech 2.8 对白 + ElevenLabs 环境音
  -> 人物参考图 / 场景图 / 连续关键帧
  -> 单图生视频，上一段尾帧接下一段首图
  -> H3 分段视频 + 独立对白/环境音后期混音
```

DramaClaw 自由画布负责资源管理、人工审图、ComfyUI 和 H3 调用。故事拆解和提示词由这些 Skill 负责；不要使用 DramaClaw 原生剧本分析去重新改写剧情。

## 当前能力

- 支持 `speech-2.8-hd` 和 `speech-2.8-turbo`
- 每个角色独立配置音色、语速、音量、音高和默认情绪
- 每句台词可以覆盖情绪和演绎参数
- 支持 `<#1.2#>` 停顿标签与 `(laughs)`、`(sighs)` 等 Speech 2.8 语气标签
- 分句生成并缓存，修改一句时不必重新生成整段故事
- 使用 ElevenLabs `eleven_text_to_sound_v2` 生成环境音和定点音效
- 环境音可以按绝对时间或指定台词开始，支持循环、音量和淡入淡出
- 对白可以在 MiniMax Speech 2.8 与 ElevenLabs `eleven_v3` 之间切换比较
- 两种对白方案共享环境音缓存，不会因为对比重复生成相同音效
- 自动合并完整音频并根据实际时长生成 SRT 字幕
- 保存请求计划、接口追踪编号和生成清单，方便排查失败请求
- 使用官方 Qwen Image Lightning 4 步工作流生成 1344×768 关键帧
- 使用 MiniMax H3 官方提示词结构和 4 步 768p Turbo 工作流生成约 5 秒测试镜头
- 调用 ComfyUI `/object_info` 检查节点，通过 `/prompt` 排队并自动下载图片或 MP4
- 可将剧本、最终音频、关键帧、H3 镜头和视频提示词一键发布到 DramaClaw 自由画布

## 视频阶段

视频配置示例位于 [`examples/family_money_argument_video.json`](examples/family_money_argument_video.json)。生成媒体仍放在已忽略的 `outputs/`，仓库只提交可复用配置、工作流和代码。

家里机器如果前端运行在 `8080`，原始 ComfyUI API 通常仍是 `8188`。先生成并检查人物定妆图和场景首帧：

```bash
python3 -m ai_drama video-keyframe \
  examples/family_money_argument_video.json character_lineup \
  --comfyui-url http://100.82.50.123:8188

python3 -m ai_drama video-keyframe \
  examples/family_money_argument_video.json opening_conflict \
  --comfyui-url http://100.82.50.123:8188
```

关键帧确认后，用它跑首个 H3 I2VA 测试镜头：

```bash
python3 -m ai_drama video-h3 \
  examples/family_money_argument_video.json opening_conflict_test \
  --image outputs/family_money_argument_video/video/keyframes/opening_conflict.png \
  --comfyui-url http://100.82.50.123:8188
```

当前 4 步模板使用 H3 Turbo 官方推荐值：1344×768、124 帧、24fps、视频 shift 6、音频 shift 3。完整视频制作应先确认人物与代表性关键帧，再按字幕时间拆分镜头，不要直接批量生成整条故事。

### 调度九宫格与尾帧接力

单图生视频按镜头分段时，先用 [`examples/family_money_storyboard.json`](examples/family_money_storyboard.json) 固定人物站位和镜头方向，再生成写实关键帧。两张可直接预览的简笔调度图位于 [`examples/storyboards/`](examples/storyboards/)：

- `family-money-grid-a.svg`：1-1 到 1-3，陈浩进门、夫妻争执、小宇害怕。
- `family-money-grid-b.svg`：1-4 到 1-5，婆婆从右侧卧室出场、说明检查费、四人围桌。

九宫格只作为构图参考，不作为写实风格参考。生成下一镜头时，优先把上一段视频的尾帧作为首图，同时继续挂人物定妆图和客餐厅场景图。需要换角度时，在动作或台词停顿处硬切，并按 `continuity_chain` 继承人物位置、视线、手部状态和桌面道具。

当前家庭故事制作包中的 `assets` 已定义客餐厅场景板、木质餐桌、家庭账本、黑色手机、作业本与铅笔、陶瓷碗六类参考资产，状态为 `pending_generation`，需要在 ComfyUI 中分别生成后再挂到对应镜头。没有可访问的真实文件地址时，不要填写虚构的 `url`。

注意：`family_money_visual_quality_test.json` 才是 DramaClaw 的制作包；`family_money_storyboard.json` 是调度说明，格式为 `ai-drama.storyboard.v1`，不能通过制作包入口导入。两张 SVG 只作为画布中的位置参考图。

## 发布到 DramaClaw 自由画布

DramaClaw 前端通常使用 `8080`，而 ComfyUI API 通常使用 `8188`。生成媒体后，可以把当前故事的可用结果上传到一个独立画布：

```bash
python3 -m ai_drama publish-canvas \
  examples/family_money_argument.json \
  examples/family_money_argument_video.json \
  --project family_money_argument \
  --canvas ai_drama_assets \
  --dramaclaws-url http://100.82.50.123:8080
```

`--project` 可以填写 DramaClaw 项目名或项目 ID。项目不存在时会自动创建；同名画布会按当前结果更新，不会重复堆叠节点。默认读取 `outputs/<脚本文件名>/` 和对应的 `<脚本文件名>_video/video/`，缺少的媒体会跳过，但说明、剧本和视频计划仍会保存。

打开命令输出的正式路由即可查看：`/projects/<项目ID>/freezone?canvas=<画布ID>`。该命令只上传 `outputs/` 中的生成结果，不会读取或提交 `.env`。

## 开始使用

运行环境需要 Python 3.11 及 FFmpeg。Python 部分没有第三方运行依赖。

1. 在项目根目录创建 `.env`，填入两个平台的 API Key：

   ```dotenv
   MINIMAX_API_KEY=your_api_key
   ELEVENLABS_API_KEY=your_api_key
   ```

2. 复制并修改 [`examples/demo_story.json`](examples/demo_story.json)，为每个角色设置 MiniMax `voice_id` 和 ElevenLabs `elevenlabs_voice_id`，再按顺序填写台词。

3. 先检查脚本，不调用接口、不产生费用：

   ```bash
   python3 -m ai_drama generate examples/demo_story.json --dry-run
   ```

4. 生成逐句语音、环境音、最终混音和字幕：

   ```bash
   python3 -m ai_drama generate examples/demo_story.json
   ```

5. 使用 ElevenLabs `eleven_v3` 生成同一故事的多角色对话版：

   ```bash
   python3 -m ai_drama generate examples/demo_story.json --speech-provider elevenlabs
   ```

MiniMax 结果默认位于 `outputs/demo_story/`，ElevenLabs 结果位于 `outputs/demo_story_elevenlabs/`。也可以使用 `--output` 指定目录。`--no-merge` 仅适用于 MiniMax 逐句生成模式。

## 故事脚本

```json
{
  "title": "故事标题",
  "model": "speech-2.8-hd",
  "characters": {
    "narrator": {
      "name": "旁白",
      "voice_id": "Chinese (Mandarin)_Lyrical_Voice",
      "elevenlabs_voice_id": "JBFqnCBsd6RMkjVDRZzb",
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

ElevenLabs 使用带时间戳的 Text to Dialogue 接口，一次生成整段多角色表演。免费 API 方案可以使用账号自带的预设音色；Voice Library 中的共享中文音色通常需要付费方案才能通过 API 调用。

环境音的 `duration_seconds` 必须在 0.5–30 秒之间。`start_ms` 表示从成片第几毫秒开始；`start_at_line` 表示从第几句台词开始，二者只填一个。持续环境音可设置 `loop: true` 和 `until_end: true`，系统会循环到对白结束。建议用英文描述音效，并加入 `no music, no voices`，减少模型生成音乐或人声的概率。

## 输出内容

- `segments/`：每句角色音频及对应接口信息
- `sound_effects/`：ElevenLabs 生成的环境音及缓存信息
- `outputs/.sound_effect_cache/`：跨对白供应商共享的环境音缓存
- `dialogue.mp3`：合并后的完整对话
- `final_mix.mp3`：对白与全部环境音混合后的最终音频
- `dialogue.srt`：按实际音频时长生成的字幕
- `plan.json`：正式请求前的完整生成计划
- `manifest.json`：本次生成结果和 MiniMax `trace_id`

生成内容默认不会提交到 GitHub。真实人物、网络热点和第三方故事在发布前仍需检查事实、隐私和版权风险。
