# 项目网站资料归档

论文中的项目网址可能提供方法演示、视频、更多图片、补充材料和代码。先核对该页确由论文/作者链接、标题和研究内容一致，记录 relation_note；不能仅凭同名网站判定。网站可以更新，关联到某论文版本不代表网页内容与该版本完全一致，默认 website_version 为 unverified。

## 范围与优先级

只保存与当前解析/写作有关、公开且允许下载的素材，不整站镜像，不遍历所有链接。用户已要求归档相关资料时可以继续，不逐个重复问小文件；但单文件超过 50 MiB 或预计总量很大时先确认范围/大小。只有普通解读、尚未要求素材归档时，可列出重要项目链接，按任务需要保存少量关键素材，不扩大为全量视频下载。

论文原图优先，其次项目网站补充图片/演示，最后才考虑明确标注的重绘或生成概念图。不要把官网演示当作论文正式评测，不用项目视频替代对论文实验设置的核验。

## 本地结构

归档文件位于同一论文资料目录 `project-assets/`，索引放 `paper-workspace.json` 的可选 `project_assets` 数组；旧目录没有该字段仍可用。`figures/` 继续只收论文原图。

每项保留：源页面、原始直链、最终下载地址、取得时间、文件大小/哈希、媒体类型、用途标题、项目与论文的关联依据、所关联的 PDF 哈希/版本、使用依据和审核状态。视频截图额外保留源视频 ID/哈希与秒数。不要存登录 Cookie、授权头、密钥或签名链接；用公开页面代替凭证链接。

状态分为 saved / link-only / failed。缓存只有在文件和哈希正常时复用；失败或新网站版本重试使用新 ID，不覆盖已有素材。无法下载的留链接与原因，不伪称已保存视频。

## 命令

本技能自带 scripts/project_assets.py，Python 3.9+ 标准库；无需安装另一个技能。以下域名/文件都是示例，执行时换成已核实的实际页面与路径。

```bash
# 只检查一页静态 HTML 的图片、视频/附件候选链接，不下载媒体、不执行页面脚本
python3 scripts/project_assets.py discover --page https://example.org/project/ --output candidates.json
# 核实关联、选定必要素材、确认允许下载后，单独归档直链
python3 scripts/project_assets.py fetch paper-folder --id demo-video --url https://example.org/project/demo.mp4 --page https://example.org/project/ --title "方法演示视频" --relation-note "论文首页链接到该项目页，作者与研究内容一致" --kind video --basis "已检查项目页提供公开下载，供本次研究留存"
# 宿主已经下载/导出的合法素材也可导入；记录真实来源，不把本地文件冒称自动抓取
python3 scripts/project_assets.py import paper-folder --id demo-image --file image.png --url https://example.org/project/image.png --page https://example.org/project/ --title "项目补充示意" --relation-note "已核对论文关联" --kind image --basis "用户提供的获准研究素材"
# 嵌入式播放器、受限链接、代码仓库等只留公共页及未保存原因
python3 scripts/project_assets.py link paper-folder --id video-page --url https://example.org/watch --page https://example.org/project/ --title "演示播放页" --relation-note "已核对论文关联" --reason "未获得可公开下载直链，仅保存页面链接"
python3 scripts/paper_workspace.py check paper-folder
```

下载支持 PNG/JPEG/GIF/WebP 图片、常见 MP4/WebM 文件和补充 PDF，按内容签名判断，不依赖 URL 后缀；签名检查不证明媒体完整可播放或文件安全。保存后用宿主实际查看/播放/读文核验，才把 checked 改为 true。SVG、HTML、源码归档、播放列表及需要登录/DRM 的内容只留链接，不执行/编译或绕过保护。网页动态渲染、iframe/第三方播放器、懒加载不一定能被静态候选扫描发现，使用宿主浏览器补查；不能说“一页扫描已覆盖全部资料”。

仅接受不含凭证的 HTTPS，访问前拒绝私有/本地地址，连接到已核验的公网 IP，保持 TLS 证书校验。重定向默认只到源文件/项目页的主机；额外 CDN 主机先检查，确有需要再用 --allow-host。不发送 Cookie、不读取浏览器账号、不换代理规避限制。401/403/429、超时或过大文件会停止，无自动重试。

默认每文件 50 MiB；用户明确批准较大文件后可用 --max-mb N --large-file-approved（上限 250 MiB），更大文件只记录链接并说明需单独安排。缺少长度头时仍按流量上限截停，半成品不冒充已保存。程序读取预算 60 秒、单次 socket 超时 15 秒；网络不可达时可导入宿主获准取得的文件。

## 视频与截图

先保存可下载视频，并实际播放核对相关内容；本工具不解码视频、不自动提帧。需要截图时，用宿主已有视频工具从该已存文件导出，核对实际帧与时间，再用 import 保存图片，增加 `--parent-id 视频ID --timestamp 秒数`，--url 使用源视频 URL。不存在/已变化的父视频不允许关联；不能把 AI 生成画面登记为视频截图。显示时写“项目演示视频截图，时间 00:12.3”，不能写“论文 Figure 3”。

下载依据与对外转载权分开：保存后 rights_status 仍为 unknown，知道具体授权才填写 rights_note 并设置 cleared。后续文章只在使用和核验条件满足时采用，不能以“公网可访问”代替转载许可。

## 给公众号使用

prepare 自动保留 project_assets 索引，但不会把所有图片/视频自动塞进文章。明确选择某张已存图片时：

```bash
python3 scripts/paper_article.py prepare paper-folder/paper-workspace.json draft.html article.json --title "文章标题" --project-image demo-image "补充原论文未展示的演示场景"
```

该命令由论文公众号技能提供；只有解析技能时仍可完成归档并交出整个目录。项目图片会标“项目网站素材，非论文原图”，截图保留时间定位，继承候选状态而不自动审核。视频/PDF 默认作为资料或正文来源链接使用，不插成假图片；公众号后台的视频上传与播放兼容需用户另行授权和验收，不自动上传。
