# 原图保存与复用

解析过程中实际用于说明/论证的图，不论最终是 Markdown 还是 HTML，都保存为独立 PNG/JPEG，并建立索引。不是全篇每个装饰图都导出；优先方法图、主结果、关键消融或用户指定图。先查已有同版本索引，校验后直接复用。

本技能自带 `scripts/paper_workspace.py`。所有命令从技能根目录执行或使用脚本绝对路径；示例路径需替换为实际任务路径。

```bash
# 从已有下载结果开始，metadata 为 PDF 旁的同名 .json
python3 scripts/paper_workspace.py init --pdf input.pdf --metadata input.pdf.json --output-dir paper-v1
# 独立解析/写作：没有下载元数据也可以，不编造公开网址
python3 scripts/paper_workspace.py init --pdf input.pdf --title "已核对的论文标题" --output-dir paper-local
python3 scripts/paper_workspace.py check paper-v1
# 查看实际 PDF 页，先导出完整页供视觉定位，页序从 1 起
python3 scripts/paper_workspace.py capture paper-v1 --id page-3 --page 3 --label "Figure 1 整页参考" --caption "原文图注"
# 视觉确定边界后，用相对渲染页的 x0 y0 x1 y1 坐标导出；以下数值只是示例
python3 scripts/paper_workspace.py capture paper-v1 --id figure-1 --page 3 --box 0.1 0.1 0.9 0.6 --label "Figure 1" --caption "原文图注"
# 没有 pdftoppm：用宿主已经可靠导出的图登记保存；不是随便找张图库图片
python3 scripts/paper_workspace.py import-figure paper-v1 --image host-export.png --id figure-1 --page 3 --label "Figure 1" --caption "原文图注"
```

`init` 要求新目录，已有资料用 check，不能反复初始化来覆盖。目录名建议带论文 ID/短标题与明确版本；本地无版本论文由哈希区分。metadata 与选文版本冲突会停止，不“自动修正”成另一篇。

`capture` 仅依赖已存在的 Poppler `pdftoppm`，可用 `--renderer` 指定已验证的可执行路径；核心检查/导入功能只需 Python 标准库，不自动安装。它渲染完整页面再根据已确认坐标取区域，不按嵌入位图对象顺序猜图号，因此能保留矢量图中文字和线条。默认长边 2400 像素（--scale 可选 600–6000），每次只处理指定一页，每次子进程最多 45 秒。

输出后实际看图：核对图号、坐标、图例、子图标签和完整图注，裁剪不能改变实验含义。不清楚边界时保留整页；需新裁剪时使用新图 ID。相同 ID、参数和已校验文件会返回 cached，不重复渲染；不同内容不会覆盖原图。

索引初始 `checked:false`、`rights_status:unknown`，表示提取成功不等于编辑审核。助手视觉检查后才设 checked:true，填写中文 alt、credit 和已知使用依据；未知许可仍保持 unknown。未索引的半成品/写入锁意味着上次失败，需要检查后恢复，不直接删整个资料目录。

保存 reading.md 后，将 `notes_path` 设为 `reading.md`；每个用于文章的结论写入 claims，包含状态、原文定位与推断说明。不把整个精读结论自动标为 verified。

公众号技能可直接把 paper-workspace.json 当作 prepare 的输入，不要求重复导图。--draft-images 可在内部草稿中显示待核验图片并附醒目警示；最终 --require-ready 不允许未就绪图，也不把研究用途的本地留存当成已获转载许可。
