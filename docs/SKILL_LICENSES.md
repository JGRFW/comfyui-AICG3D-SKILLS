# Skill 来源与许可证台账

本台账用于公开发布前核对 `skills/` 目录中的每个 Skill。最后核验日期：2026-10-10。本文件是项目记录，不构成法律意见；权利状态以权利人和原始许可证文本为准。

## 汇总

当前 `skills/` 下共有 286 个 Skill 根目录：

| 类别 | 数量 | 来源 | 许可证状态 | 发布结论 |
|---|---:|---|---|---|
| T8 Creative DNA Skill | 284 | `T8mars/minimax-h3-prompt-skill-T8` 固定版本 | 代码 MIT；原创摘要、Creative DNA 和模板 CC BY 4.0 | 许可证和固定来源已记录 |
| 默认短剧导演 Skill | 1 | Short-Drama Director Suite contributors | MIT | 已附完整许可证 |
| 角色参考图 Skill | 1 | `character-refs`，作者 X：`@eternityspring` | `SKILL.md` 声明 Apache-2.0；已补完整许可证正文 | 已记录 |

2026-10-10 已移除两个作者和许可证未确认的本地 Skill；当前没有待确认的 Skill 根目录。

## T8 Creative DNA Skill

- 目录：`skills/` 中除 `character-refs` 和 `minimax-h3-short-drama-director` 外的全部 284 个 Skill。
- 仓库：<https://github.com/T8mars/minimax-h3-prompt-skill-T8>
- 版本：`v1.4.8`
- 固定提交：`5882fc3d72d7cd4e4b3f0ab39f6b48966cb9076d`
- 导入日期：2026-10-10
- 代码许可证：[T8-LICENSE.txt](../skills/T8-LICENSE.txt)
- 内容许可证：[T8-LICENSE-CONTENT.txt](../skills/T8-LICENSE-CONTENT.txt)
- 来源记录：[T8-PROMPT-LIBRARY-SOURCE.md](../skills/T8-PROMPT-LIBRARY-SOURCE.md)
- 使用条件：CC BY 4.0 内容应保留署名、许可证链接，并说明修改；第三方来源视频、可识别角色、商标、平台标志、作者姓名和其他权利归原权利人，CC BY 4.0 不重新许可这些内容。
- 项目修改：2026-10-10 将 9 个用户可见 Skill 名称、短说明和演示提示词中的 “Seedance” 品牌提示改为 “MiniMax H3”；仅改界面元数据，Skill 目录 ID 和底层 Skill 内容保持兼容。

## 默认短剧导演 Skill

- 目录：`skills/minimax-h3-short-drama-director/`
- 上游名称：Short-Drama Director Suite / 漫剧老李 AIGC 创作全流程 Skill
- 许可证：MIT
- 许可证文件：[LICENSE](../skills/minimax-h3-short-drama-director/LICENSE)
- 说明：插件对该 Skill 进行了 MiniMax H3 适配和界面整合；MIT 允许修改和再分发，但必须保留版权与许可声明。

## 角色参考图 Skill

- 目录：`skills/character-refs/`
- 作者标识：X：`@eternityspring`
- 包内声明：`SKILL.md` 元数据 `license: Apache-2.0`
- 许可证文件：[LICENSE](../skills/character-refs/LICENSE)
- 说明：Apache-2.0 允许复制、修改、分发和商业使用，但要求保留版权、许可证和必要声明；如分发修改版本，应保留 NOTICE 文件（若上游提供）并说明修改。当前未发现上游独立 NOTICE 文件。

## 已移除的 Skill

以下两个 Skill 因未在包内找到作者、来源和许可证声明，已于 2026-10-10 从发布目录移除：

- `skills/cinematic-gunfight-director/`
- `skills/h3-video-remake-复刻skill/`

重新加入任何 Skill 前，必须补充作者、来源 URL、许可证、修改说明和证据位置。不得仅因文件位于本地目录、可在网络访问或由 AI 辅助生成，就推定其已经获得公开再分发许可。

## 许可证文件校验

SHA-256 可用于发布前确认许可证文本没有被误改：

| 文件 | SHA-256 |
|---|---|
| `skills/character-refs/LICENSE` | `CFC7749B96F63BD31C3C42B5C471BF756814053E847C10F3EB003417BC523D30` |
| `skills/T8-LICENSE.txt` | `F37104F5D4E19AD11BA1A25FBDB41FAB33B1D6C39D2C62A92C955EB49CD57339` |
| `skills/T8-LICENSE-CONTENT.txt` | `07B518C9CE5FFA6E74F91FC9B11287BB264D60F846A13827A616C1CD9CC69DD5` |
| `skills/minimax-h3-short-drama-director/LICENSE` | `016457FEC8798111FB307C02EF9F035C4CA7923FBCB3A0AA5176FB3EC765B6E4` |
| `third_party/LICENSE-Goohai-MiniMax-H3_Integration-GPL-3.0-or-later.txt` | `D482FC687A9CAD96750C4EFD9F73C6763558DBC574F2820E1C35181B6930BCFA` |

## 发布操作

正式发布时至少执行：

1. 保留本台账、`THIRD_PARTY_NOTICES.md`、T8 两份许可证、默认导演 Skill LICENSE 和 `character-refs` LICENSE。
2. 对 T8 Skill 的修改保留来源、固定提交和 CC BY 4.0 署名；不要删除原许可证或来源记录。
3. 不重新加入作者或许可不明的 Skill；新 Skill 必须先在台账中登记。
4. 再次检查预览清单没有把第三方 GIF/MP4 复制进仓库或重新许可。
5. 如增加新 Skill，先在台账中登记目录、作者、来源 URL、许可证、是否修改和证据位置。

权利人或维护者需要更正本台账时，请按 [版权、商标与下架请求流程](COPYRIGHT_AND_TAKEDOWN.md) 联系项目维护者。
