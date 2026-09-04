# 分镜数据与导出

结构化 JSON 由助手整理，不让员工手填。只写脚本时可直接用 Markdown；需要秒数核对、CSV 或 SRT 才用下列结构。完整可运行的例子在 [合成示例](../examples/work-feedback.json)。

- title、audience、objective：标题、受众与本条视频目标。
- type：types.md 的英文 ID；platform 为目标渠道文本，不将其当平台功能保证。
- aspect_ratio：9:16、16:9、1:1、4:5 之一；duration_seconds 是成片计划总秒数。
- shots：成片顺序数组。每镜含 duration_seconds、framing（景别/机位）、movement（固定或运动）、visual（可执行画面）、voiceover（口播/旁白，允许空）、subtitle（屏幕文字，允许空）、audio（同期声/音乐/静音说明）、assets（素材 ID 数组）。镜号与连续起止时间由工具生成，不手写冲突时间码。
- assets：素材数组，每项含唯一 id、description、status（existing / to-shoot / to-create）、source（文件定位/待拍场景/制作要求）。existing 只是清单标记，不表示脚本已打开或审查过文件；真正核验仍由助手完成。
- production_notes：制作待办/拍摄安排的字符串数组，可为空。未知事实、版权检查或缺素材放这里，不混入 voiceover/subtitle。

校验时总时长容差为 0.01 秒；拒绝负数、NaN、重复素材 ID、无效引用和缺字段。估计口播超过每秒四个中文字/英文单词时给警告，需试读，不自动修改文稿或把估计当真实音频时长。

```bash
python3 scripts/storyboard.py check /实际任务目录/storyboard.json
python3 scripts/storyboard.py export /实际任务目录/storyboard.json /实际交付目录
```

输出目录必须不存在，防止覆盖旧脚本。CSV 是 UTF-8 BOM，可用于常见表格工具；以公式字符开头的文本会加单引号防止被表格软件执行。Markdown 分镜表对竖线/换行进行转义。SRT 以镜头时段展示字幕，每镜一条、无字幕镜头跳过，不宣称逐字对齐。素材源定位可能含内部信息，交付外部制作方前检查范围。

script.md 是脚本和分镜，production.md 是员工执行单，manifest.json 是原始结构化记录。输入事实没有自动认证：导出成功仅表示结构和时间检查通过。
