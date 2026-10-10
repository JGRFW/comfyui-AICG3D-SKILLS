# comfyui-AICG3D-SKILLS v1.2.1

本次更新统一技能库里的用户可见品牌名称。

## 技能名称

以下 9 个 Skill 的显示名称、短说明和演示提示词由 `Seedance` 改为 `MiniMax H3`：

- MiniMax H3 3D 动画短片
- MiniMax H3 品牌宣传短片
- MiniMax H3 双人游戏开场
- MiniMax H3 手绘实拍融合
- MiniMax H3 极简产品广告
- MiniMax H3 音乐动态文字
- MiniMax H3 纸拼贴讲解
- MiniMax H3 纸艺定格科普
- MiniMax H3 提示词编写

## 兼容性

- 只修改用户可见的界面元数据。
- 原始 Skill 目录 ID 保持不变。
- 旧工作流、API 请求和保存的 Skill 选择继续兼容。
- 底层 Skill 正文和模板未因本次名称调整而改变。

## 许可证记录

- 在 `skills/T8-PROMPT-LIBRARY-SOURCE.md` 中增加本地界面修改说明。
- 在 `docs/SKILL_LICENSES.md` 中登记 Seedance 到 MiniMax H3 的名称调整。

## 升级方法

1. 更新插件仓库。
2. 重启 ComfyUI。
3. 打开“技能包”下拉，确认相关名称已显示为 `MiniMax H3`。
