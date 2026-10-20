---
name: h3-six-segment-standard
description: 按 MiniMax H3 Ref2VA 标准生成严格六段式提示词，固定输出 subject_definitions、summary、retention_analysis、detailed_description、overall_soundscape、non_diegetic_music，并在需要时补充镜头时间。用户选择“H3 六段式标准提示词”时使用。
---

# H3 六段式标准提示词

无论参考素材数量多少，都必须输出完整的六段式结构。

## 固定结构

1. `subject_definitions:`
2. `summary:`
3. `retention_analysis:`
4. `detailed_description:`
5. `overall_soundscape:`
6. `non_diegetic_music:`

每个标题单独一行，冒号后换行写正文，段与段之间留一个空行。

## 规则

- 主体使用 `<Subject N>`；图片、视频、音频使用 `<Picture N>`、`<Video N>`、`<Audio N>`。
- `retention_analysis` 每项使用 `标签: 关系 - 具体说明`。
- `detailed_description` 以 `[Shot 1]` 开头；有真实切镜时再使用 `[Shot 2]` 和时间码。
- 没有参考音频时不要虚构原音频；没有台词时不要编造 `<d>` 对白。
- 音乐不确定时写 `N/A`。
- 不复制原片人物、品牌、台词、音乐和标志性镜头。

## 质量要求

六段必须全部存在、顺序正确、内容互相一致，不能合并标题，不能只输出三字段。
