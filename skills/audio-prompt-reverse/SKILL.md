---
name: audio-prompt-reverse
description: 数字人提示词生成。根据一张人物演唱图和一段歌曲音频，使用带时间码的真实歌词，生成可直接粘贴到 11 号 MiniMax H3 数字人工作流的六段式提示词。输出保持 <Picture 1>，不输出会被数字人节点删除的 <Audio N> 标签，并在 detailed_description 中逐段写明演唱时间、歌词和口型同步。
---

# 数字人提示词生成

把「人物演唱图 + 歌曲音频 + 带时间码歌词」转换成可直接用于 MiniMax H3 数字人模式的六段式提示词。

## 输入

- `<Picture 1>`：人物演唱图，决定数字人的身份、脸型、发型、服装、配饰、体态、背景和构图。
- 歌曲音频：由 11 号工作流的 AICG3D 资源库接入，作为数字人模式全局锁定的最终音轨。
- 歌词时间线：由插件使用 Whisper 识别，或由用户通过“台词时间线”输入校正。歌词和时间码是最终定稿。

## 输出规则

1. 只输出以下六个字段，顺序固定：

```text
subject_definitions:
summary:
retention_analysis:
detailed_description:
overall_soundscape:
non_diegetic_music:
```

2. `subject_definitions` 必须把人物写成 `<Subject 1>`，并标明人物是歌手 `(S1)`。
3. 不要在最终提示词中使用 `<Audio N>` 标签。11 号数字人节点会自动删除这类标签；音频关系改用“锁定歌曲音轨”说明。
4. `retention_analysis` 必须同时包含：
   - `<Picture 1>: fully_preserved - ...`
   - `锁定歌曲音轨: fully_copy - ...`
5. `detailed_description` 必须从 `[Shot 1]` 开始，并在同一字段中写入真实演唱时间表。每个时间段使用：

```text
00:03.560-00:07.120, <Subject 1> (S1) sings:
<d>[Mandarin singing] 真实歌词原文</d>
```

6. 歌词必须逐字使用识别结果，保留原语言、标点和顺序；不得翻译、改写、补词、拆句或合并。
7. 每个歌词时间段前写清数字人的口型、下颌、嘴唇、呼吸、眼神、头部和肩颈如何跟随原歌曲同步。
8. 镜头、人物身份、服装、背景、光线和构图保持稳定；只允许自然小幅律动。
9. `overall_soundscape` 和 `non_diegetic_music` 写 `N/A`，因为完整歌曲音轨已由数字人模式锁定。
10. 不输出分析、摘要、Markdown 围栏、操作说明或第六段之后的任何文字。

结果必须可以直接复制粘贴到 11 号工作流的 MiniMax H3 节点，节点模式选择“数字人”。
