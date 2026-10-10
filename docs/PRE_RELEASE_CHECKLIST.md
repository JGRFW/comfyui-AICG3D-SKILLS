# GitHub 发布前检查清单

## 版本与元数据

- [ ] `pyproject.toml` 版本号已更新。
- [ ] `routes.py` 版本号已更新。
- [ ] 如仓库提供 `llms.txt`，其当前版本和 Release Notes 链接已更新。
- [ ] README 顶部更新摘要已更新。
- [ ] Release Notes 已包含本次用户可见变更。
- [ ] 旧版本号和错误链接已清理。

## 法律与第三方

- [ ] `LICENSE` 保留。
- [ ] `THIRD_PARTY_NOTICES.md` 保留。
- [ ] `ACKNOWLEDGEMENTS.md` 保留。
- [ ] `DISCLAIMER.md`、`PRIVACY.md`、`SECURITY.md` 和合规文档保留。
- [ ] `AI_CONTENT_POLICY.md` 和 `docs/SKILL_LICENSES.md` 已随仓库保留。
- [ ] T8 的 MIT / CC BY 4.0 文件随 Skill 分发。
- [ ] `character-refs` 的 Apache-2.0 LICENSE 保留。
- [ ] 默认导演 Skill 的 MIT LICENSE 保留。
- [ ] Goohai 许可证文件保留。
- [ ] 发布包中的每个 Skill 均有作者和许可证记录；不得重新加入作者或许可不明的 Skill。
- [ ] 预览媒体仍以远程链接为主，没有把权利不明的 GIF/MP4 当成自有素材重新许可。

## 安全与隐私

- [ ] 未提交 `optimizer_settings.json`、`.env`、`config.local.json`、API Key、Token、Cookie、私钥或客户资料。
- [ ] 未提交 `__pycache__`、`.pyc`、临时日志和备份文件。
- [ ] 远程预览 URL 不包含本地绝对路径或私有凭据。
- [ ] 文档已说明线上 API、CDN、本地模型和日志的数据流。
- [ ] 安全问题可通过 GitHub private vulnerability reporting 报告。

## 功能验证

- [ ] Python 编译通过。
- [ ] 前端 JavaScript 语法检查通过。
- [ ] ComfyUI 节点映射数量符合预期。
- [ ] 技能列表、中文名称、预览、导入/删除逻辑通过基本测试。
- [ ] 本地模型扫描能识别预期模型。
- [ ] 参考素材插入测试通过。
- [ ] 工作流 JSON 未出现无效路径或无权限依赖。

## 发布前最终确认

- [ ] 目标 GitHub 仓库、分支和标签已确认。
- [ ] `pyproject.toml` 的 `Repository` 和 `.github/ISSUE_TEMPLATE/config.yml` 中的仓库 URL 已与实际目标仓库一致。
- [ ] 已拉取远程最新 `main` 并解决冲突。
- [ ] 提交内容只包含本插件文件，不包含 ComfyUI 本体或本地配置。
- [ ] 推送后验证 GitHub 页面、Release Notes、LICENSE 和第三方声明可访问。
- [ ] 发布说明明确写出兼容性、升级步骤和已知限制。
