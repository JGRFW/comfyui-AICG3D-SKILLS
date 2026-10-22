# comfyui-AICG3D-SKILLS v1.3.1

本次更新把原来的音频反推能力正式升级为“数字人提示词生成”，目标是让 10 号提示词工作流生成的内容可以直接粘贴到 11 号 MiniMax H3 数字人工作流。

## 数字人提示词生成

- 快捷任务新增并显示 `数字人提示词生成`。
- 自动加载 `audio-prompt-reverse` 数字人专用 Skill。
- 支持人物演唱参考图、歌曲音频和人工校正的歌词时间线。
- 使用本地 Whisper 识别真实歌词、起始时间和结束时间。
- 输出固定六段式：
  - `subject_definitions`
  - `summary`
  - `retention_analysis`
  - `detailed_description`
  - `overall_soundscape`
  - `non_diegetic_music`
- 保留 `<Picture 1>` 作为数字人主体。
- 在 `retention_analysis` 写入 `<Picture 1>: fully_preserved` 和 `锁定歌曲音轨: fully_copy`。
- 在 `detailed_description` 中按真实时间码逐段写入 `<d>` 歌词，例如：

```text
00:00.000-00:05.000, <Subject 1> (S1) sings:
<d>[Mandarin singing] 真实歌词</d>
```

## 与 11 号数字人工作流兼容

- 不输出 `<Audio N>` 标签，避免数字人节点运行时删除标签后留下 `: fully_copy` 等残缺字段。
- 输出保持 H3 六段式结构；模型漏字段时会自动补齐。
- 清除模型自行编造的歌词，只使用 Whisper 识别或用户提供的真实歌词。
- 口型、下颌、呼吸、眼神和头肩动作会绑定到对应歌词时间段。
- `overall_soundscape` 和 `non_diegetic_music` 使用 `N/A`，完整歌曲音轨由数字人模式锁定。

## 歌词识别优化

- 默认优先显示已安装的可用 Whisper 模型。
- 支持 `medium.pt`、`large-v3-turbo.pt` 和 `large-v3.pt`。
- 增加纯音乐、间奏和自动字幕类幻听过滤。
- 无法确认的内容不会凭空补写。
- 可通过“台词时间线”输入人工校正歌词。

## 快捷任务兼容修复

- 界面显示新名称 `数字人提示词生成`。
- 前后端自动兼容旧值 `音频反推提示词`。
- 前端会根据当前运行中的 ComfyUI 后端实际支持的值写入隐藏字段，修复“无效输入”错误。
- 旧工作流无需手动重建节点。

## 使用要求

- 图片反推、视频反推和数字人提示词生成需要配置线上视觉模型或本地视觉模型。
- 歌词识别需要 ComfyUI Python 环境安装 `whisper`，并把 `.pt` 模型放在 `ComfyUI/models/audio_encoders`。
- 建议先生成提示词，再运行 H3 数字人视频工作流，避免提示词模型与 H3 模型同时争用显存。
- 如果只追求数字人提示词生成速度，建议使用 `Qwen3VL-4B-Instruct-Q4_K_M.gguf`；复杂理解任务可继续使用更大的模型。

## 验证

- Python 编译检查通过。
- JavaScript 语法检查通过。
- 使用实际音频 `10月22日.mp3` 和 `large-v3.pt` 完成歌词与时间码识别测试。
- 验证数字人最终提示词不包含 `<Audio N>` 标签。
- 验证输出包含六段式字段、`fully_preserved`、`fully_copy`、真实时间码和逐字 `<d>` 歌词。
- 验证新值和旧快捷任务值均可被后端接受。
