---
name: minimax-h3-short-drama-director
description: "把漫剧老李短剧导演方法适配为 MiniMax H3 提示词系统。用于把简单创意、图片/视频/音频参考或多段分镜扩展为 H3 三字段或 Ref2VA 六段式提示词，并执行战斗、镜头、语气、连续性、素材引用与 H1~H12 质检。"
metadata:
  short-description: MiniMax H3 短剧提示词导演
---

# MiniMax H3 短剧提示词导演

本 Skill 专门把上游“漫剧老李 AIGC 全流程 Skill”转换成 MiniMax H3 可投喂的提示词。默认模型固定为 MiniMax H3；上游 Seedance 方法只作为导演、镜头、动作、语气和连续性知识来源，不输出种子舞七段式格式。

## 工作流程

1. 判断 H3 任务模式：`T2VA`、`I2VA`、`FL2VA`、`L2VA` 或 `Ref2VA`。
2. 读取 [references/minimax-h3-plugin-context.md](references/minimax-h3-plugin-context.md)，按其中的压缩规程设计字段、素材用途、动作节拍、镜头和声音。
3. 需要完整字段定义、模式路由、参考素材上限或 H1~H12 机检时，读取 [references/h3-adapter.md](references/h3-adapter.md)。
4. 按用户意图追加相关专业规则：
   - 战斗：`combat-direction-engine.md`、`action-previs-15grid.md`
   - 文戏与对白：`dialogue-doctor-7d.md`、`dialogue-speed-check.md`、`wenxi-micro-expression.md`
   - 镜头与分镜：`camera-specs-15rules.md`、`camera-transitions-6types.md`
   - 多段连续性：`segment-splicing.md`、`asset-spatial-ledger.md`
   - 玄幻法术：`xuanhuan-magic-combat.md`、`anime-ultimate-vfx-paradigm.md`
5. 输出最终 H3 提示词，不输出解释、过程笔记或 Markdown 围栏。

## 输出约束

- `T2VA`、`I2VA`、`FL2VA`、`L2VA`：只输出 `integrated_multimodal_description`、`overall_soundscape`、`non_diegetic_music`。
- `Ref2VA`：按固定顺序输出 `subject_definitions`、`summary`、`retention_analysis`、`detailed_description`、`overall_soundscape`、`non_diegetic_music`。
- 输入很简单时也要主动补足合理、可见、可执行的镜头动作；不得只把原句改写得更好看。
- 用户明确给出的主体、对白、事件和参考素材关系不得改变。
- 正文只写实际存在的画面和声音，不写否定式指令、七段式栏名、`@` 资产锚点、坐标表或工作流术语。
- 素材必须先用 `<Picture N>`、`<Video N>`、`<Audio N>` 或 `<Subject N>` 定义，再在正文引用；未引用就不要定义。
- 对白保留原语言和原标点，语气、音色和语速写在 `<d>[Language]...</d>` 外面；画外声紧跟闭口证据。
- 生成后按 H1~H12 检查字段、镜号、时长、语言标签、保留度标记、说话人编号、画外声、声音分层、语气继承和首镜锚定。

## 参考文件

- `references/minimax-h3-plugin-context.md`：插件使用的压缩入口，默认先读。
- `references/h3-adapter.md`：H3 格式转换正文，权威规则。
- `DIRECTOR_SYSTEM_FULL.md`：保留的完整漫剧老李导演系统，需要深入查阅时使用。
- 其他 `references/*.md`：按任务类型按需读取，不要一次加载全部。
