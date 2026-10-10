# comfyui-AICG3D-SKILLS

![license](https://img.shields.io/badge/license-GPL--3.0--or--later-blue)
![ComfyUI](https://img.shields.io/badge/ComfyUI-custom%20node-1E90FF)

独立的 ComfyUI 提示词插件。它把“漫剧老李 AIGC 创作全流程 Skill”适配为 MiniMax H3 版本，用一个主节点把简单创意扩展成 H3 可投喂提示词。

## v1.2.1 更新摘要

- 将 9 个 Skill 的用户可见名称、短说明和演示提示词从 Seedance 统一改为 MiniMax H3。
- 保留原来的稳定目录 ID，旧工作流、API 调用和序列化数据继续兼容。
- 同步更新 T8 来源记录和 Skill 许可证台账，明确标注本次界面元数据修改。

## 项目定位与作用

本插件用于把一句创意、参考素材和 Skill 规则组合成可执行的 MiniMax H3 提示词。它负责提示词工程、素材整理、Skill 管理和质检，不生成或托管视频模型权重，也不授予第三方素材、角色、声音、商标或模型的权利。

完整说明见 [docs/PURPOSE.md](docs/PURPOSE.md)。

## 功能

- 支持线上 API 和本地视觉模型：OpenAI 兼容接口、Gemini、RunningHub，以及 `ComfyUI/models/llm` 下的 Transformers / GGUF 模型。
- 内置 MiniMax H3 导演 Skill，生成时自动加载 H3 格式、战斗、分镜、语气、连续性和质检规则。
- 额外打包 T8 Creative DNA 的 284 个 Skill，覆盖产品广告、连续追逐、品牌宣传、微表情、材质变身、角色登场等短视频机制。
- 技能包下拉支持 T8 案例预览：鼠标移上去先显示海报，停留后切换到对应的 GIF 动画。
- 可输入类似“图1和图2在图3场景打斗”的一句话，自动映射 `<Picture 1>`、`<Picture 2>`、`<Picture 3>` 并补全六段式提示词。
- 没有配置模型时仍可输出结构完整的离线草稿，方便继续修改。
- 提供 H3 提示词检查节点，覆盖字段、镜号、素材引用、对白、声音和首镜锚定。

## 节点

| 节点 | 用途 |
|---|---|
| `AICG3D SKILLS · 模型设置` | 设置 API 或本地模型，保存后全插件共用。 |
| `AICG3D SKILLS · 技能选择器` | 选择战斗、文戏、镜头、段缝连续性等导演重点。 |
| `AICG3D SKILLS · Skill 管理器` | 浏览、搜索、套用、导入或删除 Skill；T8 Skill 使用中文名称和中文用途说明。 |
| `AICG3D SKILLS · 参考素材整理` | 把图片、视频、音频整理成 H3 标签和用途说明。 |
| `AICG3D SKILLS · H3 提示词推理` | 主节点，调用模型并生成 H3 提示词。 |
| `AICG3D SKILLS · H3 提示词检查` | 运行 H1~H12 质量检查。 |

## 安装

把当前目录放入：

```text
ComfyUI/custom_nodes/comfyui-AICG3D-SKILLS
```

然后重启 ComfyUI。插件和 `ComfyUI-AICG3D-Integrated` 可以同时安装，节点 ID、接口和设置文件互不冲突。

## 现成工作流

插件自带两套可直接打开的工作流：

- `AICG3D-SKILLS 多参考提示词工作流.json`：资源库 → H3提示词推理 → 质检，适合先生成和检查提示词。
- `AICG3D-SKILLS 多参考无限视频工作流.json`：在完整无限视频工作流上增加多参考提示词生成、质检和运行状态预览。

这两个文件也会复制到 ComfyUI 的用户工作流目录，打开工作流列表即可看到。

## 使用顺序

1. 添加“模型设置”节点，点击“模型设置”按钮选择线上 API 或本地模型。
2. 添加“H3 提示词推理”节点，输入一句创意。
3. 点击主节点的“选择 / 管理技能”，搜索中文用途并点“使用”；普通任务也可保留默认导演 Skill。
4. 如有参考图片，把它们接到“参考素材整理”，再把 JSON 接到主节点。
5. 运行工作流，读取 `H3提示词` 输出。
6. 可选：把提示词接到检查节点，先看问题和警告。

## 主节点字段说明

点击主节点上的“使用说明”可以打开同样的内置帮助。截图中常见的五个字段用途如下：

| 字段 | 用途 | 普通使用是否要填 |
|---|---|---|
| `参考素材JSON` | 从“参考素材整理”接入图片、视频、音频标签和用途。 | 否；有素材节点时再连接 |
| `技能重点输入` | 从“技能选择器”接入并覆盖节点上的“技能重点”。 | 否 |
| `技能包输入` | 从上游节点接入并覆盖节点上的“技能包”。 | 否；推荐直接用技能库弹窗 |
| `额外要求` | 输入必须遵守的自然语言限制，例如“不要添加新人物”。 | 可选 |
| `模型设置JSON` | 从“模型设置”节点接入本次工作流专用配置。 | 否；不接就用全局设置 |

从插件 1.1.0 起，这四项在画布上优先显示为连线接口，不再需要手动填写 JSON。

## Skill 目录

所有可选择的 Skill 都放在插件目录下的：

```text
skills/
```

每个技能包可以有两种结构：

```text
skills/my-skill/SKILL.md
```

或：

```text
skills/my-skill/package-name/SKILL.md
```

默认内置 `minimax-h3-short-drama-director`，并已加入 T8 Creative DNA 的 284 个 Skill。点击主节点或“技能选择器”的“选择 / 管理技能”，可以按中文名称、中文用途和英文 ID 搜索，再点“使用”套到当前节点。

Skill 管理器仍支持导入 ZIP、刷新列表和删除非内置 Skill。也可以在文件资源管理器里直接增删文件夹，然后刷新列表。内置的 `minimax-h3-short-drama-director` 不允许误删。

## 本地模型目录

本地模型扫描：

```text
ComfyUI/models/llm/
```

- Transformers 视觉模型需要 `config.json` 和处理器文件。
- GGUF 主模型会自动查找同名 mmproj，也可在设置面板手动选择；当前支持 Qwen3.5 / 3.8、Qwen3-VL 和 Gemma3 / Gemma4 的 GGUF 视觉处理器。
- 本地 GGUF 依赖 `llama-cpp-python`；缺少时，设置面板会显示依赖状态。

## 数据与密钥

API Key 和本地模型设置保存在插件目录的 `optimizer_settings.json`。该文件已加入 `.gitignore` 和 `.comfyignore`，不会提交到仓库。

## 合规与发布资料

- [项目定位与作用](docs/PURPOSE.md)
- [致谢与来源](ACKNOWLEDGEMENTS.md)
- [第三方声明与许可证](THIRD_PARTY_NOTICES.md)
- [免责声明](DISCLAIMER.md)
- [隐私说明](PRIVACY.md)
- [安全政策](SECURITY.md)
- [AI 内容使用政策](AI_CONTENT_POLICY.md)
- [Skill 来源与许可证台账](docs/SKILL_LICENSES.md)
- [法律法规与合规说明](docs/LEGAL_AND_COMPLIANCE.md)
- [侵权规避与内容审查](docs/INFRINGEMENT_AVOIDANCE.md)
- [版权与下架请求](docs/COPYRIGHT_AND_TAKEDOWN.md)
- [GitHub 发布前检查](docs/PRE_RELEASE_CHECKLIST.md)


## 许可

插件代码使用 GPL-3.0-or-later。上游 Goohai-MiniMax-H3_Integration 的许可证见 `third_party/`。默认短剧导演 Skill 使用 MIT。T8 Creative DNA Skill 来自 `T8mars/minimax-h3-prompt-skill-T8`，代码许可为 MIT，原创摘要、Creative DNA 与提示词模板许可为 CC BY 4.0；来源和固定版本记录见 `skills/T8-PROMPT-LIBRARY-SOURCE.md`。

`character-refs` 在 `SKILL.md` 中声明 Apache-2.0，项目已补充完整许可证正文。原先未确认作者和许可证的 `cinematic-gunfight-director`、`h3-video-remake-复刻skill` 已于 2026-10-10 从发布目录移除，不再随插件分发。逐项状态见 [Skill 来源与许可证台账](docs/SKILL_LICENSES.md)，完整声明见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。

本 README 和相关合规文档不构成法律意见。发布、商用或处理真人、未成年人、品牌、音乐和敏感数据前，请咨询有资质的法律或合规专业人士。
