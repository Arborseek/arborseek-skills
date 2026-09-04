# 教程数据与导出

JSON 由助手整理；格式示例由 [模拟样例生成器](../examples/make_demo.py) 在用户任务目录中生成。无需在技能安装目录写素材。

```bash
python3 examples/make_demo.py /新的模拟任务目录
python3 scripts/guide.py build /新的模拟任务目录/guide.json /新的预览目录 --draft --docx --font "实际安装的中文字体名称"
```

样例是合成界面状态视频，不包含真人操作或真实点击，核对标志默认 false。演示预览使用 --draft，不应为了展示而把样例全部改为已通过业务验收。

顶层字段：

- schema：`screen-guide/1`。
- title、purpose、audience、scope：非空字符串，用读者语言写任务和适用范围。
- prerequisites、completion：字符串数组，分别为有依据的准备条件、完成检查，允许为空。
- sources：别名到提取索引相对路径的映射，基于 guide.json 所在目录解析；多个索引必须属于同一视频哈希。
- coverage_reviewed：布尔值；确认操作流程覆盖完整、有疑问片段已补看后才设 true。
- questions：内部待确认字符串数组；正常 build 要求为空。
- steps：按操作顺序排列的非空数组，每项包含唯一 id、title、instruction、expected、verified（动作及结果已核对）、privacy_reviewed（图片和文字隐私已核对）、evidence 数组。
- evidence 每项有 source（索引别名）、frame（索引中的帧 ID）、role（before/after/detail）。每一步至少一项，时间由索引导入，不能手填伪造。
- 每个 evidence 可指定 `redactions`（矩形数组）、`boxes`（矩形数组，自动编号）、`arrows`（起止点数组）、`crop`（矩形）。矩形是原尺寸像素 `[x,y,width,height]`，箭头是 `[x1,y1,x2,y2]`。先遮盖，再框选/箭头，最后裁剪。越界、零面积、裁掉标注会拒绝。中文说明放正文，图内只放数字，避免缺字体。

```bash
python3 scripts/guide.py check /任务目录/guide.json
python3 scripts/guide.py build /任务目录/guide.json /新的输出目录
python3 scripts/guide.py build /任务目录/guide.json /新的输出目录 --docx
python3 scripts/guide.py build /任务目录/guide.json /内部预览目录 --draft
```

check 输出 errors（结构/文件损坏）与 blockers（核对未完成）；退出码非零即不可作为正常教程导出。`--draft` 仅容许 blockers，不绕过格式、越界、文件哈希检查。check 不访问业务系统，不验证用户是否真的点击。

build 输出：

- public/tutorial.html：内嵌样式、相对图片、目录锚点、图下注明原视频时间，支持浏览器打印。没有外部脚本、跟踪或在线字体。
- public/tutorial.md：可编辑文字与相对图片。
- public/images/：扁平化处理后的 PNG，去掉源元数据；不复制原图或原视频。
- public/tutorial.docx：仅指定 --docx 且依赖可用时生成，正文可编辑；截图及标注为嵌入图片，不是 Word 可编辑形状。
- review.md：独立内部核对单和交付检查提醒。
- provenance.json：索引、截图哈希、变换参数和原输入记录，仅内部保留。

输出目录必须不存在，已有版本不覆盖。导出前完整检查；处理中失败可能保留部分目录，未写入 `COMPLETE.json` 时视为未完成，修复后换新目录重试，不直接外发。确认门槛只用于组织人工/模型核对，不构成自动证明。

Word 字体默认 Noto Sans CJK SC；通过 `--font "实际安装的中文字体名称"` 覆盖，例如 Windows 的 Microsoft YaHei、macOS 可用的 Arial Unicode MS。字体不随技能分发，生成 DOCX 不等于渲染环境能找到字体。出现方框/空白字时先确认渲染器字体可见性并重渲染，不用图片替代全部可编辑文字。标题样式会去除默认段落边框。

完整性不仅是“所有现有步骤都打勾”：还要回看录屏前后衔接、有无剪切和缺失前提。未经确认的步骤不能通过删除疑问字段变成成稿。必要步骤缺失时请用户补录或补充说明；如果用户只需已确认片段，先缩小 scope 并明确该范围。
