# 安装与兼容指南

三个技能独立打包，均以 `SKILL.md` 为入口；`agents/openai.yaml` 是 Codex 的可选展示信息，其他平台的核心运行不依赖它。

## 安装位置

将 `skills/` 下的完整目录复制到目标位置，而非复制仓库最外层目录。已存在同名技能时，先备份并检查自定义改动，再升级；避免在同一平台多个扫描目录重复安装。

| 平台 | 默认位置 / 入口 | 使用方式 |
| --- | --- | --- |
| OpenClaw | 实际工作区 `skills/`，或默认状态目录 `~/.openclaw/skills/`；自定义状态目录使用其 `skills/` 子目录 | 自然语言点名，或使用当前技能菜单提供的命令 |
| Codex | 用户 `~/.agents/skills/` 或项目 `.agents/skills/`；旧环境若已从 `~/.codex/skills/` 发现技能，可原位更新 | 自然语言或 `$tianshu-tanjie-paper-search` 等标识 |
| Claude Code | 用户 `~/.claude/skills/` 或项目 `.claude/skills/` | 自然语言或 `/tianshu-tanjie-paper-search` 等命令 |
| Hermes Agent | 默认 `~/.hermes/skills/`；profile/远程环境需确认实际根目录 | 自然语言或已注册的 `/技能标识` |
| WorkBuddy | “技能 → 添加技能 → 上传技能”，逐个上传独立 ZIP 并启用；若当前版本要求文件夹，解压后选择含 `SKILL.md` 的技能目录 | 在对话中点名功能名称 |

此处 Claude 指 Claude Code，Hermes 指 Nous Research Hermes Agent；不把本地安装自动等同于 Claude 网页版、Desktop/Cowork 或云端运行环境可见。安装后按宿主方式刷新技能或新开会话。

目录与入口依据：[OpenClaw](https://docs.openclaw.ai/tools/skills)、[Codex](https://learn.chatgpt.com/docs/build-skills)、[Claude Code](https://code.claude.com/docs/en/skills)、[Hermes Agent](https://hermes-agent.nousresearch.com/docs/guides/work-with-skills)、[WorkBuddy](https://www.codebuddy.cn/docs/workbuddy/From-Beginner-to-Expert-Guide/Function-Description/Skills-Market)。文档核验日期：2026-09-04；版本差异以宿主当前说明为准。

## 填写技能发布表单

| Slug | 显示名称 |
| --- | --- |
| `tianshu-tanjie-paper-search` | arXiv 论文检索与筛选 |
| `tianshu-tanjie-arxiv` | arXiv 论文下载 |
| `tianshu-tanjie-paper-reading` | 论文精读与解析 |

Slug 与技能 `name` 相同，展示名称不带品牌前缀。简介可直接参考各技能 frontmatter 的 `description`。维护者信息可使用 Arborseek（天树探界），不冒称其他作者参与或背书。

## 环境与能力

- 脚本需要 Python 3.9+、终端执行权限；网络操作需要官方 arXiv HTTPS 访问能力。
- 在 macOS/Linux 通常用 `python3`；Windows 用已安装的 `py -3` 或 `python`。保留 `-X utf8`，路径加引号；复杂查询按实际 shell 传参。
- 相对 `scripts/`、`references/` 都以当前技能目录为起点，不是终端工作目录。不要直接执行示例里的 `SKILL_DIR` 占位路径。
- 容器或远程终端必须能访问技能与论文。远程路径不表示文件已到用户电脑。
- 保存文件需要可写目录，当前安全发布依赖文件系统硬链接支持；不支持的网络盘改用获准的本地目录。
- PDF/OCR、图表查看、附件发送、HTML 预览依赖宿主现有能力；没有全文就标明摘要级分析。
- 定时任务只在用户明确要求且宿主原生调度工具可用时配置；安装不会自动创建定时任务。
- 多个客户端共享同一服务端限流，arXiv 请求仍须串行，不能并发调用以规避限制。

详细运行路由由各技能的 `references/platform-compatibility.md` 提供。

## 验收

1. 确认宿主能发现三个技能，名称与版本正确。
2. 运行检索脚本 `--keywords transformer --dry-run` 和下载脚本 `--help`，确认路径/解释器可用。这两项不联网。
3. 指定一篇论文执行实际下载与速读，核对版本、文件保存位置、原文页码与未读取部分。

本仓库的离线测试与目录搬迁检查不能替代第 3 步；不会将单机检查标成五平台原生端到端通过。
