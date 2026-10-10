# 第三方声明与许可证清单

本文件是项目级第三方声明。具体组件的原始许可证文件优先于本摘要。本文件不构成法律意见。

## 许可证矩阵

| 组件 | 用途 | 许可证/状态 | 文件或来源 |
|---|---|---|---|
| 本插件自有代码 | ComfyUI 节点、路由、前端逻辑 | GPL-3.0-or-later | `LICENSE` |
| 默认短剧导演 Skill | `minimax-h3-short-drama-director` | MIT | `skills/minimax-h3-short-drama-director/LICENSE` |
| T8 Creative DNA Skill | 284 个 Skill 与参考资料 | 代码 MIT；原创摘要/Creative DNA/模板 CC BY 4.0 | `skills/T8-LICENSE.txt`、`skills/T8-LICENSE-CONTENT.txt`、`skills/T8-PROMPT-LIBRARY-SOURCE.md` |
| T8 案例预览 | 仅保存远程 URL 映射 | 不复制媒体；原视频、GIF、作者信息按 T8 原仓库声明 | `preview_manifest.json` |
| Goohai 提示词优化相关代码 | 部分上游实现与适配 | GPL-3.0-or-later | `third_party/LICENSE-Goohai-MiniMax-H3_Integration-GPL-3.0-or-later.txt` |
| 角色参考图 Skill | `character-refs`，作者标识 X：`@eternityspring` | Apache-2.0 | `skills/character-refs/SKILL.md`、`skills/character-refs/LICENSE` |
| Python 运行依赖 | 例如 aiohttp、Pillow、numpy、Transformers、llama-cpp-python | 各自项目许可证 | 不随本仓库打包，由用户环境安装 |
| 本地模型权重 | Qwen、Gemma 等模型 | 各自模型许可证 | 不由本插件分发；用户自行下载并接受相应条款 |

## 权利边界

- 本插件不会因为整合、索引或生成提示词而取得第三方作品、角色、商标、声音、肖像或模型的知识产权。
- 第三方 Skill 的文本、案例摘要和参考链接不代表本插件重新许可其底层权利。
- 预览图的加载由浏览器向外部 CDN/仓库发起；预览的展示不等于对原作品授予商业使用权。
- “可访问”“可在 GitHub 查看”“可在模型中生成”都不等于“可商用”“可再分发”或“已获得肖像权、著作权或商标权授权”。

## 发布前待办

当前没有已知的待确认 Skill。`cinematic-gunfight-director`、`h3-video-remake-复刻skill` 已于 2026-10-10 从发布目录移除；在重新加入任何 Skill 前，必须补充作者、来源和许可证记录。逐项核验记录见 `docs/SKILL_LICENSES.md`。
