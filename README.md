<img width="1890" height="958" alt="image" src="https://github.com/user-attachments/assets/768ad1a7-8c5b-41cb-953c-d829536cc41a" />

# comfyui-AICG3D-SKILLS

![license](https://img.shields.io/badge/license-GPL--3.0--or--later-blue)
![ComfyUI](https://img.shields.io/badge/ComfyUI-custom%20node-1E90FF)

独立的 ComfyUI 提示词插件。它把"漫剧老李 AIGC 创作全流程 Skill"适配为 **MiniMax H3** 版本：用一个主节点把一句创意、参考素材和 Skill 规则，扩展成可直接投喂给 MiniMax H3 的六段式提示词。

**核心用途一句话**：你给一句创意、几张图/一段视频/一首歌，它帮你产出可直接复制粘贴给 MiniMax H3 的 `subject_definitions / summary / retention_analysis / detailed_description / overall_soundscape / non_diegetic_music` 六段式提示词。

---

## 这是什么

本插件负责提示词工程、素材整理、Skill 管理和质检，**不生成或托管视频模型权重**，也不授予第三方素材、角色、声音、商标或模型的权利。

完整定位说明见 [docs/PURPOSE.md](docs/PURPOSE.md)。

## 核心能力

- **多模型后端**：支持线上 API（OpenAI 兼容接口、Gemini、RunningHub）和本地视觉模型（`ComfyUI/models/llm` 下的 Transformers / GGUF）。
- **快捷任务**：普通创作、图片反推提示词、视频反推提示词、数字人提示词生成。选择后自动加载对应 Skill 并隐藏无关参数。
- **数字人提示词生成**：从歌曲音频识别**真实歌词和逐段时间码**，产出让 MiniMax H3 数字人跟随原唱逐字演唱、口型与歌词同步的提示词；男女对唱使用交替单人镜头，每个时间段画面中只有对应歌手，另一人完全在画外，避免两人同时张嘴。
- **一句话多素材映射**：输入"图1和图2在图3场景打斗"，自动映射 `<Picture 1>`、`<Picture 2>`、`<Picture 3>` 并补全六段式。
- **内置 MiniMax H3 导演 Skill**：自动加载 H3 格式、战斗、分镜、语气、连续性和质检规则。
- **额外打包 T8 Creative DNA 的 284 个 Skill**：覆盖产品广告、连续追逐、品牌宣传、微表情、材质变身、角色登场等短视频机制。
- **技能包 T8 案例预览**：下拉悬停先显示海报，停留后切换为对应 GIF 动画。
- **无模型也能出草稿**：未配置模型时输出结构完整的离线草稿，方便继续修改。
- **H3 提示词检查节点**：覆盖字段、镜号、素材引用、对白、声音和首镜锚定。

## 内置 Skill

| Skill | 用途 |
|---|---|
| `minimax-h3-short-drama-director` | 默认导演 Skill，自动加载 H3 格式、分镜、语气、连续性与质检规则。 |
| `image-prompt-reverse` | 图片反推：输出一段可直接复制的图片生成提示词。 |
| `video-prompt-reverse` | 视频反推：输出 Ref2VA 六段式，不附加时间线或分析。 |
| `audio-prompt-reverse` | 数字人提示词生成：识别歌词+时间码，产出数字人演唱提示词。 |
| `h3-video-remake` | H3 视频复刻：把参考视频用指定 IP 角色重新演绎，输出 Ref2VA 提示词+分镜关键帧+上传顺序。 |
| `white-model-person-scene-replacement` | 3D 白模人物/场景替换：原视频动作母版，按颜色 ID 锁身份，输出 Ref2VA 六段式。 |
| T8 Creative DNA ×284 | 由 T8mars 提供，覆盖各类短视频创作机制。 |

前三个专用反推 Skill 会由"快捷任务"自动选择，一般无需在技能库手动搜索。

## 节点一览

| 节点 | 用途 |
|---|---|
| `AICG3D SKILLS · 模型设置` | 设置 API 或本地模型，保存后全插件共用。 |
| `AICG3D SKILLS · 技能选择器` | 选择战斗、文戏、镜头、段缝连续性等导演重点。 |
| `AICG3D SKILLS · Skill 管理器` | 浏览、搜索、套用、导入或删除 Skill；T8 Skill 用中文名称和中文用途。 |
| `AICG3D SKILLS · 参考素材整理` | 把图片、视频、音频整理成 H3 标签和用途说明。 |
| `AICG3D SKILLS · H3 提示词推理` | 主节点，调用模型并生成 H3 提示词。 |
| `AICG3D SKILLS · 视频台词识别` | 从 AUDIO 识别真实台词、时间码和 S1/S2 说话人，输出可接入主节点的台词时间线。 |
| `AICG3D SKILLS · H3 提示词检查` | 运行 H1~H12 质量检查。 |

## 安装

把当前目录放入：

```text
ComfyUI/custom_nodes/comfyui-AICG3D-SKILLS
```

然后重启 ComfyUI。本插件与 `ComfyUI-AICG3D-Integrated` 可同时安装，节点 ID、接口和设置文件互不冲突。

## 现成工作流

- `AICG3D-SKILLS 多参考提示词工作流.json`：资源库 → H3提示词推理 → 质检，适合先生成和检查提示词。
- `AICG3D-SKILLS 多参考无限视频工作流.json`：在完整无限视频工作流上增加多参考提示词生成、质检和运行状态预览。

这两个文件也会复制到 ComfyUI 的用户工作流目录。

## 快速上手

### 普通创作

1. 添加"模型设置"节点，点击"模型设置"按钮选择线上 API 或本地模型。
2. 添加"H3 提示词推理"节点，输入一句创意。
3. 点击主节点的"选择 / 管理技能"，搜索中文用途并点"使用"；普通任务也可保留默认导演 Skill。
4. 如有参考图片，接到"参考素材整理"，再把 JSON 接到主节点。
5. 运行工作流，读取 `H3提示词` 输出。
6. 可选：把提示词接到检查节点，先看问题和警告。
7. 需要口型或原对白复用时：视频原音轨 → `视频台词识别` → `台词时间线` 接到主节点。

### 图片 / 视频反推

1. "快捷任务"选 `图片反推提示词` 或 `视频反推提示词`。
2. 图片接到"参考图片"或 AICG3D 资源库；视频接到 AICG3D 资源库。
3. 配置支持视觉的线上或本地模型（反推模式不会用离线模板代替真实分析）。
4. 可在"创意描述"补充重点分析内容，然后运行。

### 数字人提示词生成（音频反推 → H3 数字人）

1. "快捷任务"选 `数字人提示词生成`。
2. 人物演唱图接到"参考图片"或 AICG3D 资源库；歌曲音频接到"音频"输入或同一资源库；`输出画幅` 与目标数字人工作流保持一致。歌词识别始终分析完整上传音频，不受 `视频时长` 限制。
3. 在"音频反推模型"选择歌词识别模型（默认 `large-v3-turbo.pt`），运行。
4. 插件自动识别每段歌词和真实时间码，并做**幻听过滤**（丢弃"作曲 作曲…"这类纯音乐段同词重复），输出带逐句时间码的 `<d>[Mandarin singing] 歌词。</d>`。
5. 男女对唱时在创意描述中明确写出图片角色，例如：`<Picture 2>` 女子唱女声部分、`<Picture 1>` 男子唱男声部分、两人都在 `<Picture 3>` 场景。插件会先做人声分离，再用 wav2vec2 男女声分类模型和音色聚类交叉判断 S1/S2。若模型文件不可用，才回退音高算法；状态栏会显示实际使用的声部来源和每句置信度。
6. 插件会按歌词段自动编排不同的 MV 单人镜头，并把切点放在起唱、换气或重音处；当前演唱者始终保留完整嘴部，另一位歌手完全在画外，避免男女同时张嘴。
7. 把结果粘贴到 MiniMax H3 数字人工作流的提示词框，模式选"数字人"，资源库保持两张人物图、场景图和同一首歌曲。

**推荐的歌词识别模型**（`ComfyUI/models/audio_encoders`）：

| 模型 | 体积 | 特点 | 建议 |
|---|---|---|---|
| `large-v3-turbo.pt` | ~1.6GB | 快 + 准，中文平衡 | 默认，日常用 |
| `large-v3.pt` | ~3GB | 中文演唱最准 | 追求歌词精确度 |
| `medium.pt` | ~1.5GB | 轻量均衡 | 显存小或图快 |

> 说明：whisper 本质是语音识别模型，对带旋律/伴奏的歌曲仍有个别字识别不准的固有局限，但已过滤纯音乐段幻听；输出始终保证每句歌词带精确到毫秒的时间码。

**男女声识别模型**：默认使用 Apache-2.0 的 `7wolf/wav2vec2-base-gender-classification`，并与音色聚类交叉确认。首次运行时自动下载约 378 MB 到 `ComfyUI/models/audio_classifiers/gender_wav2vec2_7wolf`；也可通过 `AICG3D_GENDER_MODEL_DIR` 指向手动放置的模型目录。模型不可用时才回退到音高/音色算法。完整目录、手动下载方法和排错说明见 [docs/MODEL_INSTALL.md](docs/MODEL_INSTALL.md)，选型与实测记录见 [docs/MALE_FEMALE_VOICE_MODELS.md](docs/MALE_FEMALE_VOICE_MODELS.md)。

## 主节点字段说明

点击主节点上的"使用说明"可打开同样的内置帮助。常见字段：

| 字段 | 用途 | 普通使用是否要填 |
|---|---|---|
| `参考素材JSON` | 从"参考素材整理"接入图片、视频、音频标签和用途。 | 否；有素材节点时再连接 |
| `技能重点输入` | 从"技能选择器"接入并覆盖节点上的"技能重点"。 | 否 |
| `技能包输入` | 从上游节点接入并覆盖节点上的"技能包"。 | 否；推荐直接用技能库弹窗 |
| `额外要求` | 输入必须遵守的自然语言限制，例如"不要添加新人物"。 | 可选 |
| `模型设置JSON` | 从"模型设置"节点接入本次工作流专用配置。 | 否；不接就用全局设置 |

## Skill 目录结构

所有可选 Skill 放在插件目录下：

```text
skills/
```

每个技能包可有两种结构：

```text
skills/my-skill/SKILL.md
skills/my-skill/package-name/SKILL.md
```

Skill 管理器支持导入 ZIP、刷新列表和删除非内置 Skill。内置导演 Skill 和三个专用反推 Skill 不允许误删。

## 依赖

### 歌词识别（whisper）

`视频台词识别` 和 `数字人提示词生成` 需要 ComfyUI Python 环境能 `import whisper`，并把 `.pt` 模型放到 `ComfyUI/models/audio_encoders`（也可手动填写模型绝对路径）。节点默认不联网下载模型；打开"允许自动下载模型"后才会按所选名称下载。

节点会扫描 `ComfyUI/models/audio_encoders` 和 `ComfyUI/models/whisper`；其他位置的 `.pt` 模型可把完整路径填到"本地模型路径"。若本机已有 `pyvideotrans` 等语音工具，可复用其中的 `large-v3.pt`，无需重复下载。

### 本地视觉模型

本地模型扫描目录：

```text
ComfyUI/models/llm/
```

- Transformers 视觉模型需要 `config.json` 和处理器文件。
- GGUF 主模型自动查找同名 mmproj，也可在设置面板手动选择；当前支持 Qwen3.5 / 3.8、Qwen3-VL 和 Gemma3 / Gemma4 的 GGUF 视觉处理器。
- 本地 GGUF 依赖 `llama-cpp-python`；缺少时设置面板会显示依赖状态。

## 配置与密钥

API Key 和本地模型设置保存在插件目录的 `optimizer_settings.json`。该文件已加入 `.gitignore` 和 `.comfyignore`，不会提交到仓库。

## 更新记录

- **v1.4.0**：数字人提示词生成改为完整音频转写；新增 wav2vec2 男女声分类模型，并与音色聚类交叉识别 S1/S2；男女对唱使用交替单人镜头，另一人完全在画外；新增模型自动下载与详细放置说明；补齐第三方许可证声明。
- **v1.3.1**：新增"数字人提示词生成"，从歌曲音频识别真实歌词和逐段时间码；输出可粘贴到 MiniMax H3 数字人工作流的六段式提示词，包含 `<Picture 1>`、`fully_copy` 音轨关系和逐段 `<d>` 歌词；为歌词识别增加音乐幻听过滤；修复与旧版快捷任务值不一致导致的无效输入错误。
- **v1.3.0**：新增"快捷任务"：普通创作、图片反推提示词、视频反推提示词；任务模式新增 `H3 六段式标准提示词`、`文生图（T2I）`、`首尾帧生图（FL2I）`；所有 Skill 输出统一清理为可直接复制粘贴的提示词。
- **v1.2.2**：新增"视频台词识别"，从原视频音轨识别真实台词、时间码和说话人映射；运行时清除模型自行编造的 `<d>` 对白。
- **v1.2.1**：将 9 个 Skill 的用户可见名称、短说明和演示提示词统一改为 MiniMax H3。

## 合规与发布资料

- [项目定位与作用](docs/PURPOSE.md)
- [致谢与来源](ACKNOWLEDGEMENTS.md)
- [第三方声明与许可证](THIRD_PARTY_NOTICES.md)
- [免责声明](DISCLAIMER.md)
- [隐私说明](PRIVACY.md)
- [安全政策](SECURITY.md)
- [AI 内容使用政策](AI_CONTENT_POLICY.md)
- [模型下载与放置说明](docs/MODEL_INSTALL.md)
- [男女声模型选型与实测](docs/MALE_FEMALE_VOICE_MODELS.md)
- [Skill 来源与许可证台账](docs/SKILL_LICENSES.md)
- [法律法规与合规说明](docs/LEGAL_AND_COMPLIANCE.md)
- [侵权规避与内容审查](docs/INFRINGEMENT_AVOIDANCE.md)
- [版权与下架请求](docs/COPYRIGHT_AND_TAKEDOWN.md)
- [GitHub 发布前检查](docs/PRE_RELEASE_CHECKLIST.md)

## 许可

插件代码使用 GPL-3.0-or-later。上游 Goohai-MiniMax-H3_Integration 的许可证见 `third_party/`。默认短剧导演 Skill 使用 MIT。T8 Creative DNA Skill 来自 `T8mars/minimax-h3-prompt-skill-T8`，代码许可为 MIT，原创摘要、Creative DNA 与提示词模板许可为 CC BY 4.0；来源和固定版本记录见 `skills/T8-PROMPT-LIBRARY-SOURCE.md`。

`character-refs` 在 `SKILL.md` 中声明 Apache-2.0，项目已补充完整许可证正文。逐项状态见 [Skill 来源与许可证台账](docs/SKILL_LICENSES.md)，完整声明见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。

本 README 和相关合规文档不构成法律意见。发布、商用或处理真人、未成年人、品牌、音乐和敏感数据前，请咨询有资质的法律或合规专业人士。
