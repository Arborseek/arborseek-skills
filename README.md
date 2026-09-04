# Arborseek Skills

论文检索、下载与精读，三个可独立使用、也可串联的 AI 技能。由 Arborseek（天树探界）整理维护，显示名称以功能关键词为主。

## 技能目录

| 显示名称 | 功能 | 技能标识（Slug） |
| --- | --- | --- |
| [arXiv 论文检索与筛选](skills/tianshu-tanjie-paper-search/SKILL.md) | 按主题、日期和分类检索，依据摘要筛选候选 | `tianshu-tanjie-paper-search` |
| [arXiv 论文下载](skills/tianshu-tanjie-arxiv/SKILL.md) | 下载明确版本的 PDF，按需获取源码，校验文件与元数据 | `tianshu-tanjie-arxiv` |
| [论文精读与解析](skills/tianshu-tanjie-paper-reading/SKILL.md) | 解释方法、核对实验、标注证据，支持对比和复现准备 | `tianshu-tanjie-paper-reading` |

当前版本：**1.2.1**。保留既有 Slug，升级不会因显示名称变化而打断技能间引用。

## 安装

面向 **OpenClaw、Codex、Claude Code、Hermes Agent、WorkBuddy**，共用标准 `SKILL.md` 入口与独立资源目录。选择一种方式：

1. 克隆/下载仓库，将 `skills/` 下需要的完整技能目录放进宿主技能目录。
2. 运行 `python3 scripts/package.py`，在 `dist/` 中获取整套包和三个独立 ZIP，再按宿主的上传入口导入。

具体安装目录、调用方式及环境限制见 [安装与兼容指南](docs/installation.md)。不要只复制 `SKILL.md`，也不要把整个仓库当成第四个技能导入。

## 使用示例

> 使用论文检索、下载和精读三个技能，找最近一个月关于长上下文评测的论文，按相关性选出 3 篇，下载对应版本 PDF，再各写一份中文速读。不要配置定时任务。

也可以只说：

- “用 arXiv 论文检索与筛选找 10 篇 RAG 评测文献，只给清单与选文理由。”
- “用 arXiv 论文下载保存 1706.03762v1，不下载源码。”
- “用论文精读与解析解释这份 PDF，重点看实验设置和结论依据。”

检索结果不是自动下载授权；只提供摘要时不宣称完成全文精读。下载交接保留带版本 ID、元数据与文件路径，阅读结论标明实际取得的材料范围。

## 运行与验证

检索/下载脚本仅使用 Python 3.9+ 标准库，无 API 密钥和第三方 Python 包依赖。联网任务需要 arXiv 官方 HTTPS 访问权限；论文解析需要宿主提供正文/图片读取能力，本仓库不附带 PDF 或 OCR 引擎。

在仓库根目录运行：

```bash
python3 scripts/check.py
python3 scripts/package.py
```

Windows 可根据已有解释器使用 `py -3` 或 `python` 替代 `python3`。打包脚本只打包技能目录与安装说明，排除缓存、私人论文、环境文件和测试下载结果。

已在 macOS 上通过 59 项离线回归、技能结构/本地引用校验和中文空格目录搬迁检查。**未逐个完成五个客户端的原生导入与模型端到端测试**；Windows/Linux 原生运行也未实测。网络限流、调度、OCR 与附件展示取决于实际环境，不能由技能格式兼容推断全部可用。

## 来源说明

各技能保留独立的 `SOURCES.md`，说明输入材料、重写范围与方法背景。原始输入 ZIP、私人评审历史和论文下载文件不随仓库发布。来源说明不是第三方授权的替代，也不表示 arXiv 或其他原作者对本项目的背书；本次不替原始材料新增许可证声明。

版本变化见 [更新记录](CHANGELOG.md)。
