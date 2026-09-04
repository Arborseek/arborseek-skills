# 安装与兼容指南

九个技能独立打包，均以 `SKILL.md` 为入口；`agents/openai.yaml` 是 Codex 的可选展示信息，其他平台的核心运行不依赖它。统一从 Arborseek/arborseek-skills 获取更新，公众号旧仓库只保留历史。

普通独立 ZIP 包含一个技能文件夹；`-workbuddy.zip` 的根目录直接放 `SKILL.md` 与资源，并补充平台展示字段。合集 ZIP 用于整体下载和维护，不作为单个技能导入。

## 安装位置

将 `skills/` 下的完整目录复制到目标位置，而非复制仓库最外层目录。已存在同名技能时，先备份并检查自定义改动，再升级；避免在同一平台多个扫描目录重复安装。

| 平台 | 默认位置 / 入口 | 使用方式 |
| --- | --- | --- |
| OpenClaw | 实际工作区 `skills/`，或默认状态目录 `~/.openclaw/skills/`；自定义状态目录使用其 `skills/` 子目录 | 自然语言点名，或使用当前技能菜单提供的命令 |
| Codex | 用户 `~/.agents/skills/` 或项目 `.agents/skills/`；旧环境若已从 `~/.codex/skills/` 发现技能，可原位更新 | 自然语言或 `$tianshu-tanjie-paper-search` 等标识 |
| Claude Code | 用户 `~/.claude/skills/` 或项目 `.claude/skills/` | 自然语言或 `/tianshu-tanjie-paper-search` 等命令 |
| Hermes Agent | 默认 `~/.hermes/skills/`；profile/远程环境需确认实际根目录 | 自然语言或已注册的 `/技能标识` |
| WorkBuddy | “技能 → 添加技能 → 上传技能”，逐个上传 `-workbuddy.zip` 并启用；此包根目录即 `SKILL.md`，避免多一层目录被导入器拒绝 | 在对话中点名功能名称 |

此处 Claude 指 Claude Code，Hermes 指 Nous Research Hermes Agent；不把本地安装自动等同于 Claude 网页版、Desktop/Cowork 或云端运行环境可见。安装后按宿主方式刷新技能或新开会话。

目录与入口依据：[OpenClaw](https://docs.openclaw.ai/tools/skills)、[Codex](https://learn.chatgpt.com/docs/build-skills)、[Claude Code](https://code.claude.com/docs/en/skills)、[Hermes Agent](https://hermes-agent.nousresearch.com/docs/guides/work-with-skills)、[WorkBuddy](https://www.codebuddy.cn/docs/workbuddy/From-Beginner-to-Expert-Guide/Function-Description/Skills-Market)。文档核验日期：2026-09-04；版本差异以宿主当前说明为准。

## 填写技能发布表单

| Slug | 显示名称 |
| --- | --- |
| `tianshu-tanjie-paper-search` | arXiv 论文检索与筛选 |
| `tianshu-tanjie-arxiv` | arXiv 论文下载 |
| `tianshu-tanjie-paper-reading` | 论文精读与解析 |
| `xiaohongshu-illustrated-post` | 小红书图文创作 |
| `wechat-article-skill` | 微信公众号智能创作与排版 |
| `paper-wechat-article` | 论文解读公众号写作 |
| `build-bright-tech-landing-page` | 科技风网站与落地页设计 |
| `short-video-storyboard` | 短视频脚本与分镜助手 |
| `screen-recording-to-guide` | 录屏转操作教程 |

Slug 与技能 `name` 相同，展示名称不带品牌前缀。简介可直接参考各技能 frontmatter 的 `description`。维护者信息可使用 Arborseek（天树探界），不冒称其他作者参与或背书。

## 环境与能力

- Python 脚本需要 Python 3.9+、终端执行权限；小红书排字需要 Pillow 与中文字体，公众号脚本需要 Beautiful Soup（见各技能 requirements.txt）。论文检索/下载需要官方 arXiv HTTPS 访问能力。
- 在 macOS/Linux 通常用 `python3`；Windows 用已安装的 `py -3` 或 `python`。保留 `-X utf8`，路径加引号；复杂查询按实际 shell 传参。
- 相对 `scripts/`、`references/` 都以当前技能目录为起点，不是终端工作目录。不要直接执行示例里的 `SKILL_DIR` 占位路径。
- 容器或远程终端必须能访问技能与论文。远程路径不表示文件已到用户电脑。
- 保存文件需要可写目录，当前安全发布依赖文件系统硬链接支持；不支持的网络盘改用获准的本地目录。
- PDF/OCR、图表查看、附件发送、HTML 预览依赖宿主现有能力；没有全文就标明摘要级分析。
- 定时任务只在用户明确要求且宿主原生调度工具可用时配置；安装不会自动创建定时任务。
- 多个客户端共享同一服务端限流，arXiv 请求仍须串行，不能并发调用以规避限制。

论文运行路由见各自 `references/platform-compatibility.md`；其余技能见各自 `references/runtime.md`。不要求使用所有九个技能，只安装需要的完整目录即可。检索/下载 1.3.1、解析 1.4.0 与论文公众号 1.2.0 共享 paper-workspace/1 交接约定，也接受旧版 Markdown 笔记、PDF 与下载元数据。解析和论文公众号各自携带独立的资料/取图/网站归档脚本，只有其中一个也可运行。

录屏教程另需本地 FFmpeg/ffprobe、Pillow，Word 导出需 python-docx。抽帧脚本不含语义识别、OCR 或 ASR；需要宿主实际查看画面后编写步骤。不自动安装软件、上传录屏或记录桌面。只有 public/ 是对外交付目录，原视频、提取帧和内部核对单不自动外发。

PDF 区域导出需已有 Poppler pdftoppm；没有时用宿主现有工具渲染后 import-figure，不能宣称未执行的提取已经成功。不随 ZIP 安装外部渲染器。使用过的原图与 notes/索引属于用户任务资料，不保存到技能安装目录，也不随技能上传仓库。

解析 1.4.0 与论文公众号 1.2.0 另带 Python 标准库项目素材归档工具，使用已授权的公网 HTTPS；图片/视频播放与视频截图仍依赖宿主工具，不包含流媒体破解或自动转码器。旧资料目录没有 project_assets 字段也可继续使用。

## 验收

1. 确认宿主能发现已安装的技能，名称与版本正确。
2. 运行检索脚本 `--keywords transformer --dry-run` 和下载脚本 `--help`，确认路径/解释器可用。这两项不联网。
3. 指定一篇论文执行实际下载与速读，核对版本、文件保存位置、原文页码与未读取部分。
4. 内容技能另需真实主题验收：小红书核对页数、中文排字和实际底图；公众号检查 HTML 手机预览；网站检查响应式与交互。目录合并不代表这些端到端环节已经通过。

本仓库的离线测试与目录搬迁检查不能替代第 3 步；不会将单机检查标成五平台原生端到端通过。
