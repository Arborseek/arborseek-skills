# Arborseek Skills

论文研究、内容创作与网站设计，六个可独立使用的 AI 技能。由 Arborseek（天树探界）整理维护，显示名称以功能关键词为主。

**唯一维护仓库：[Arborseek/arborseek-skills](https://github.com/Arborseek/arborseek-skills)。** 公众号技能已并入这里，旧 `wechat-article-skill` 仓库保留历史、不再作为新版本维护源。各平台的本地安装目录只是部署副本；后续修复、版本、打包和文档均在本仓库更新。

## 技能目录

| 显示名称 | 功能 | 技能标识（Slug） |
| --- | --- | --- |
| [arXiv 论文检索与筛选](skills/tianshu-tanjie-paper-search/SKILL.md) | 按主题、日期和分类检索，依据摘要筛选候选 | `tianshu-tanjie-paper-search` |
| [arXiv 论文下载](skills/tianshu-tanjie-arxiv/SKILL.md) | 下载明确版本的 PDF，按需获取源码，校验文件与元数据 | `tianshu-tanjie-arxiv` |
| [论文精读与解析](skills/tianshu-tanjie-paper-reading/SKILL.md) | 解释方法、核对实验、标注证据，支持对比和复现准备 | `tianshu-tanjie-paper-reading` |
| [小红书图文创作](skills/xiaohongshu-illustrated-post/SKILL.md) | 标题正文、主题与版式、无字底图提示词及中文排字；默认 6 张、最多 9 张 | `xiaohongshu-illustrated-post` |
| [微信公众号智能创作与排版](skills/wechat-article-skill/SKILL.md) | 文章研究、写作配图、完整 HTML 排版与质量校验 | `wechat-article-skill` |
| [科技风网站与落地页设计](skills/build-bright-tech-landing-page/SKILL.md) | 明亮科技风网站、响应式落地页、配图与交互设计规范 | `build-bright-tech-landing-page` |

合集版本：**1.3.0**。三个论文技能保持 **1.2.1**，小红书 **3.2.1**，公众号 **1.1.2**，网站 **1.0.1**；技能独立版本以各自 `SKILL.md` 为准，目录与打包入口由 [catalog.json](catalog.json) 管理。保留既有 Slug，避免打断调用和交接。

## 安装

面向 **OpenClaw、Codex、Claude Code、Hermes Agent、WorkBuddy**，共用标准 `SKILL.md` 入口与独立资源目录。选择一种方式：

1. 克隆/下载仓库，将 `skills/` 下需要的完整技能目录放进宿主技能目录。
2. 运行 `python3 scripts/package.py`，在 `dist/` 中获取合集包、六个普通独立 ZIP 和六个 `-workbuddy.zip` 根目录直接导入包。WorkBuddy 优先使用对应的直接导入包。

具体安装目录、调用方式及环境限制见 [安装与兼容指南](docs/installation.md)。不要只复制 `SKILL.md`，也不要把整个仓库当成第七个技能导入。

## 使用示例

> 使用论文检索、下载和精读三个技能，找最近一个月关于长上下文评测的论文，按相关性选出 3 篇，下载对应版本 PDF，再各写一份中文速读。不要配置定时任务。

也可以只说：

- “用 arXiv 论文检索与筛选找 10 篇 RAG 评测文献，只给清单与选文理由。”
- “用 arXiv 论文下载保存 1706.03762v1，不下载源码。”
- “用论文精读与解析解释这份 PDF，重点看实验设置和结论依据。”
- “用小红书图文创作，把这个主题写成正文并规划 6 张配图。”
- “用微信公众号智能创作与排版，把这篇稿件做成完整 HTML。”
- “用科技风网站与落地页设计，为这个产品做一个响应式介绍页。”

检索结果不是自动下载授权；只提供摘要时不宣称完成全文精读。下载交接保留带版本 ID、元数据与文件路径，阅读结论标明实际取得的材料范围。

## 运行与验证

| 技能 | 运行依赖 |
| --- | --- |
| 论文检索 / 下载 | Python 3.9+ 标准库；联网任务需要 arXiv 官方 HTTPS 访问权限，无 API 密钥要求 |
| 论文解析 | 宿主正文/图片读取能力；不内置 PDF/OCR 引擎 |
| 小红书图文 | Python 3.9+；排字/图片检查需 Pillow、可用中文字体；实际底图需宿主图像生成工具 |
| 微信公众号 | Python 3.9+ 与 Beautiful Soup；完整视觉验收需浏览器预览 |
| 网站设计 | 当前项目已有框架与工具链；视觉验收需浏览器，不绑定指定框架 |

依赖按各技能的 `requirements.txt` 安装到获准的环境；打包不自动安装依赖、不上传内容、不创建定时任务或部署网站。

准备好对应测试依赖后，在仓库根目录运行：

```bash
python3 scripts/check.py
python3 scripts/package.py
```

Windows 可根据已有解释器使用 `py -3` 或 `python` 替代 `python3`。打包脚本只打包技能目录与安装说明，排除缓存、私人论文、环境文件和测试下载结果。

检查入口覆盖论文脚本回归、公众号原有测试、小红书计划边界测试、六技能结构/引用及目录搬迁检查。**未逐个完成五个客户端的原生导入与模型端到端测试**；Windows/Linux 原生运行也未实测。网络限流、图像生成、调度、OCR 与附件展示取决于实际环境，不能由技能格式兼容推断全部可用。

## 来源说明

各技能保留独立的 `SOURCES.md`，说明输入材料、重写或迁移范围与方法背景。原始输入 ZIP、参考图片、私人评审历史和论文下载文件不随仓库发布。来源说明不是第三方授权的替代，也不表示 arXiv 或其他原作者对本项目的背书；本次不替原始材料新增许可证声明。没有并入第三方 `xiaohongshu-write` 技能。

版本变化见 [更新记录](CHANGELOG.md)。
