# comfyui-AICG3D-SKILLS v1.2.2

本次更新增加原视频台词识别与说话人映射，并收紧人物场景替换 Skill 的对白和口型规则。

## 新节点

- `AICG3D SKILLS · 视频台词识别`
- 输入 ComfyUI `AUDIO`，使用本地 `openai-whisper` 模型识别真实台词。
- 输出 `台词JSON`、`台词时间线`、`台词全文`、`运行状态`。
- 多人对白支持：

```text
S1 = Picture 1 | 0.00-1.25
S2 = Picture 2 | 1.25-3.00
```

## 提示词主节点

- 新增可选输入 `台词时间线`。
- 识别文本会逐字写入对应时间段，保留原语言、标点、说话人和 Subject/Picture 映射。
- 原音轨复用时继续使用 `fully_copy`，台词文本用于锁定语言、口型和说话顺序。
- 没有识别结果且用户没有提供逐字台词时，运行时不会保留模型自行编造的 `<d>` 对白。

## 依赖说明

- Python 环境需要能 `import whisper`。
- Whisper `.pt` 模型放在 `ComfyUI/models/audio_encoders`，或手动填写绝对路径。
- 节点默认不联网下载模型；只有打开“允许自动下载模型”后才会下载。
