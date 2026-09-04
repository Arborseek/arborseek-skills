# 运行与转换约定

标准 SKILL.md 面向 OpenClaw、Codex、Claude Code、Hermes Agent、WorkBuddy、DeepSeek Harness 等技能宿主；实际可用性取决于终端、文件和依赖权限，不宣称各客户端均已原生测试。

依赖：Python 3.9+、lxml、Pillow、python-docx；转换需 Pandoc 3+，PDF 需 LibreOffice/soffice 与 pypdf。Python 依赖见 requirements.txt，Pandoc、LibreOffice、字体须由现有环境提供，技能不自动安装。仅查看 --help 不需第三方 Python 包。

Windows 使用实际安装的 python/py -3 和工具 PATH；可通过 --pandoc、--soffice 指定工具绝对路径。字体通过 --font 指定字体族，默认 Noto Sans CJK SC。检查字体实际存在且渲染器可见；例如 macOS 的 Arial Unicode MS、Windows 的 Microsoft YaHei。字体不随技能分发。

文档纸张默认 Letter 纵向，可显式指定 --paper a4、--landscape。Word 的段落、表格和图片按可打印宽度调整；超长代码或超宽表格仍需人工复核。源 CSS 的 @page 不自动覆盖命令行纸张，避免未核验的原样式影响交付。

## 文件与资源

- 支持 UTF-8（含 BOM），其他编码用 --encoding。输入最大 20 MiB、单图片原始/规范化数据最大 15 MiB、单张最大 2500 万像素；每张取原始/规范化数据较大值，累计最大 80 MiB。超限应缩小任务，不隐式跳过资源。
- 本地图片只从 HTML 所在目录及子目录读取，拒绝路径越界和符号链接逃逸；支持 PNG/JPEG/GIF/WebP，嵌入前重编码 PNG。GIF/WebP 动画须先由用户确认选帧，脚本默认拒绝动画。
- 支持上述格式的 base64 data URI。不自动抓远程图片、CSS、字体或 iframe；图片缺失时给准确错误，先由获准工具取得需要的资源到任务目录。
- 只保留安全超链接，不访问目标。相对链接没有已知 --base-url 时默认阻止，以免交付不可跳转的链接；锚点 #id 单独保留。危险协议移除为普通文字并记录。
- Pandoc 读取经过白名单处理的静态 HTML，启用 --sandbox、不接受输入中的过滤器或命令；图片转为内嵌 data URI。LibreOffice 只读取本工具生成且通过外部关系检查的 DOCX，不直接打开未处理的原 HTML。

## 输出

新目录包含每个输入的编号子目录，内有 public/converted.docx 和/或 public/converted.pdf，以及独立 report.json。PDF-only 模式的临时 Word 在私有临时目录中使用，不作为额外交付文件。BATCH.json 汇总各文件成功/失败与结果，批量有任何失败时退出码非零。文件生成未经过人工视觉验收前不称“可直接发布”。

脚本只在自建临时目录内进行中间转换，退出时清理临时文件；不覆盖或清理用户输入。输出部分失败时保留报告方便诊断，不自动上传，也不把内部报告发给外部收件人。

SkillHub 上架需另行授权；显示名称“HTML 转 Word 与 PDF”，Slug `html-to-office`，版本 1.0.0。选择转换/文档图标并确认保存，不把打包等同于上架。

## 快速试用

自带 [模拟 HTML](../examples/office-sample.html)，包含中文、纵向/横向合并单元格、内嵌配图、内外链接和显式分页。不含真实业务数据。将以下相对路径替换为技能实际绝对路径，输出使用新目录：

```bash
python3 scripts/convert.py inspect examples/office-sample.html
python3 scripts/convert.py convert examples/office-sample.html --format both --font "实际可用中文字体" --output-dir /新的示例目录
python3 -m unittest discover -s tests -v
```

真实业务稿需重新验收；示例通过不等于任意网页保真。字体存在但渲染缺字时，先检查渲染器字体发现配置，不以文字可提取代替视觉确认。
