# 项目定位与作用

> English summary: This plugin expands short creative ideas into MiniMax H3-ready prompt text, with optional local or remote vision models, reusable Skills, reference-media cataloguing, previews, and prompt validation. It does not generate video by itself and does not grant rights to third-party content.

## 1. 这是什么

`comfyui-AICG3D-SKILLS` 是面向 ComfyUI 的提示词工作流插件。它把创意描述、参考素材和 Skill 规则组合起来，生成可交给 MiniMax H3 使用的结构提示词。

插件的主要目标是让非专业提示词作者也能完成以下工作：

- 把一句话创意扩展成可执行的画面、动作、镜头、声音和连续性描述；
- 管理并复用不同导演、题材和创意 DNA Skill；
- 整理图片、视频和音频参考素材，并明确每项素材的用途；
- 在本地模型或用户自选的线上 API 之间切换；
- 在生成后检查字段、镜号、素材引用、对白、声音和首帧锚定。

## 2. 主要组件

- `AICG3D SKILLS · 模型设置`：配置线上 API 或本地视觉模型。
- `AICG3D SKILLS · 技能选择器`：选择导演重点和 Skill。
- `AICG3D SKILLS · Skill 管理器`：浏览、搜索、预览、导入和删除 Skill。
- `AICG3D SKILLS · 参考素材整理`：把图片、视频和音频整理为 H3 标签。
- `AICG3D SKILLS · H3 提示词推理`：核心提示词生成节点。
- `AICG3D SKILLS · H3 提示词检查`：执行结构性质检。

## 3. 它不做什么

- 不生成或托管视频模型权重；
- 不授予任何第三方图片、视频、音频、音乐、角色、商标、字体或模型的权利；
- 不替代版权审查、肖像权审查、隐私影响评估或法律意见；
- 不保证模型输出准确、原创、适合商用或符合特定平台规则；
- 不会因为用户选择某个 Skill 就自动获得该 Skill、角色或参考素材的授权。

## 4. 使用者责任

使用者应自行确认输入素材、提示词、模型、生成结果和发布行为符合适用法律、模型许可证、API 服务条款及发布平台规则。涉及真人、未成年人、个人数据、商业品牌、音乐、影视角色或敏感内容时，应先取得必要授权并完成合规审查。
