# 安装与复用

完整解压 `wechat-ai-autopilot` 到工作目录的 `.agents/skills/`（Codex）或用户 `~/.codex/skills/`。Claude Code 可放 `~/.claude/skills/`，其他宿主放其声明的 skill 目录。保持整个文件夹，不只复制 SKILL.md。安装位置仅说明发现方式；各宿主实际验证范围见[发布准备](release-readiness.md)。首次执行[能力检查与配置](onboarding.md)，不复制开发者账号。在下一轮/新会话中调用。

核心 Python 3.10+，不安装 pip 包。配置可复制 assets/profile.example.json 到用户工作目录并修改作者、受众、篇幅、图数、主题，不填任何密钥。凭证仅使用环境变量。doctor 支持 profile.skills 指向自定义目录。

新文章额外执行research.py plan，由宿主做全网和相关平台实际检索，记录原始案例及逐节价值，再research.py check。标题生成12—18个不同候选后展示3个，明确承诺和正文兑现；见titles.md、research-depth.md。公开搜索可直接用，X等站内搜索可能需要用户登录，不把公共索引称全平台接口接通。AIhot匿名接口无须Key，网络受限时按aihot-troubleshooting.md使用宿主获准网络；脚本不自动提权。

新文章默认正文无引用编号/来源附录，图片无「AI生成」图注；证据和图片来源仍保留内部审稿记录。旧运行续作需用 `configure --run RUN --citations internal --image-captions none` 显式迁移，并按新契约重写正文/claims、导出和验收；不靠删来源文件绕过核验。

新文章先读完整正文，逐节判断文字已足够、需要真实证据截图，还是需要概念图；默认body_images="auto"，不固定截图/生图张数。每张图必须有明确的信息收益，只有Logo、标题和日期不能算有效证据。公告优先截功能、数据和测试条件、案例产出；教程截真实步骤与结果。官方原始PDF图表也可保留原像素局部渲染，不能用生图仿造。来源与裁切只存内部，不添加正文引用或生成来源图注。参考 [真实截图流程](real-screenshots.md) 与 [实测排错和提速](verified-efficiency.md)。

依赖策略：AIhot 客户端和原创写法/标题简版已自带；有安装版则优先读 skill。周行排版为必要依赖，来自 https://github.com/Kianzzz/zhouxing-paiban-wx 。可按宿主的 skill-installer 流程安装仓库内 zhouxing-paiban-wx 目录。通过网络安装只在当前授权和宿主权限下进行，不自动下载未知代码运行。AIhot 最新安装方式以 https://aihot.virxact.com/aihot-skill/ 为准；不猜 GitHub 仓库地址。khazix-writer 与 baokuan-title-generator 可以使用本机版本，缺失时明确采用本包的简版，不声称调用不存在的 skill。

自然语言例子

> 使用 $wechat-ai-autopilot，找最近7天最值得普通用户关注的AI消息，写资讯型文章，自动配图和排版，交付审稿包。

> 使用 $wechat-ai-autopilot，写一篇能照做的AI干货，选题你来定，实测记录要保留，不发布。

> 使用 $wechat-ai-autopilot，写标准篇幅3000—4500字的AI资讯。推荐一套周行排版，也列出其他选项。封面用深色电影感，参考我给的两张封面，不发布。

> 使用 $wechat-ai-autopilot，写5000—7000字深度干货，排版选石墨档案，重点解释失败案例，配图用清晰图解。

> 使用 $wechat-ai-autopilot，这次写约4000字，排版我选沙金手记，封面用产品摄影风。

篇幅、主题与视觉选择的范围、优先级和命令见 [preferences.md](preferences.md)。用户直接用中文选择即可，Agent 负责设置命令和保存配置。

> 使用 $wechat-ai-autopilot，继续 RUN_PATH，修复 quality.json 中的失败项。

> 这篇标题、内容和排版都确认了。使用 $wechat-ai-autopilot，存到我登录的公众号草稿箱，保留原排版和图片，让我自己发送。

首次扫码登录官方后台即可使用浏览器草稿路径，无需填写 AppSecret。Agent 负责图片上传、真实富文本粘贴、封面两种裁切、保存后重新打开核对；只有账号登录步骤需要用户参与。以后修改同一篇时更新原草稿。浏览器宿主须支持文件上传与 HTML 剪贴板，具体流程和脚本见 [publishing.md](publishing.md)。

命令帮助 `python scripts/workflow.py --help`。init/discover/assemble/layout/accept-html/fingerprint/audit/status 都是可复用命令；每次任务由 Agent 执行步骤，不要求用户手动建 JSON。脚本不是 LLM、搜索引擎或内置生图 API 的替代品。

分享本包无需分享 runs。每个 run 带来源、图片和审阅记录；不要把私有操作输入/测试数据或账号凭证包含进分享包。`python scripts/package_skill.py --output PATH.zip` 打包仅 skill 资源，排除缓存。

没有浏览器导出能力可以先交预览与Markdown，但要说尚未导出。有内置生图时常规正文实际调用，封面不抵扣正文；没有时询问是否配置，再确认具体厂商/模型并验证连接；用户拒绝则只用真实截图。有依据的无增益例外可省去生图，详见 [能力与配置分支](image-capability.md)。截图还可从X、抖音、B站、小红书等原帖和实际作品取有用局部，不能称未访问的平台已连通。浏览器草稿路径使用用户自己的登录；可选官方API需要帐号权限和IP白名单，详见publishing.md。

## 新版默认交互

请求学习公众号文章时直接进入 [文章学习模式](content-learning.md)，不启动下面的写作问答。可以给链接、指定账号和数量、聚焦某类选题，或继续已有批次。实际阅读全文后交付逐篇记录及总结，默认确认后合并经验；学习进度工具只有标准库，支持去重、哈希和锚点检查，不自动抓取或推断“读完”。

> 使用 $wechat-ai-autopilot，读取这些公众号文章，学习不同选题怎样安排内容、标题怎样兑现。只看内容，先给总结，确认后加入skill。

> 使用 $wechat-ai-autopilot，读账号甲和账号乙各20篇，重点比较测评与教程，记下案例、失败和读者收益。

> 使用 $wechat-ai-autopilot，继续上一批文章学习，跳过已读且记录有效的文章，补齐还缺的篇数。

> 使用 $wechat-ai-autopilot，再找10篇尚未读过的评测文章，检查我们现有规则哪里需要修正。

正式写作前先问选题、篇幅、字体和当前风格库里的文风；已有信息直接用。没有选题先搜五个最近7天候选供选。篇幅支持根据内容自由发挥，字体支持楷体、宋体、微软雅黑、苹方、系统无衬线及自定义。成稿后默认带内容适合的动效，先打开简洁文章预览，可进入工坊从十套真实周行排版中切换、修改正文和设计。没有修改直接向Agent发确认；修改后点“保存当前文章”再确认，Agent采用这个保存版上传已连接账号草稿箱，由用户审核发表。

> 使用 $wechat-ai-autopilot。没有选题，先推荐五个最新AI热点；篇幅自由发挥，字体宋体，文风卡兹克。写完让我对比十套排版，选定无修改后存到我的公众号草稿箱。

首次用户扫码自己的号，Agent从账号详情读取名称与公众号ID；读不到再请用户提供。`intake.py bind-account`记在当前workspace/.wechat-ai/account.json，下次不重复问ID，登录过期仍扫码。只存公开账号标识和操作约定，包内无用户账号，密钥仅环境变量。不同工作目录需显式迁移配置；其他用户必须连接自己的号。

旧稿保持原字体与已选主题，继续已确认稿件不重新发问。详细问答JSON、候选与排版选择命令见 [intake.md](intake.md)。核心新命令：intake.py questions/apply/candidates/select-layout/bind-account/account，以及workflow.py layout-previews。

文章工坊的生成、后台启动、保存与采用命令见 [studio-motion.md](studio-motion.md)。工坊不是一个全局固定网址：Agent为当前文章启动`studio.py serve --run RUN --port 0`，打开实际URL。正文和工坊修改留在本机，可恢复未保存的调整和历史保存版；“另存排版模板”只存设计参数，供后续文章使用。默认有二十种可选动效，按文章内容组合，不固定每篇的数量。预览时关闭动效可以保存并上传静态版。微信端是否保留动效必须传稿后实际核验。

> 这篇先给我预览。我会在工坊里把字号调大、换排版，保存以后发确认；请上传我保存的版本，不重新排版。

> 这篇不用调整，确认当前预览版，存入我已连接公众号的草稿箱。

已确认新增主题：月白笺书、朱砂文藏、天青格物、松烟行旅、胭脂生活。完整解压后即有这五套主题JSON；安装周行依赖即可生成十套预览，无需先将JSON手工复制到周行全局目录。adapter在内存合并，仍使用实际周行渲染，保留宿主其他自定义风格。


## 学习并新增写作风格

可以直接说：“读取我提供的30篇文章，提炼这个作者的文风并加入选项，以后写稿让我选择。”Agent按[文风学习流程](style-distillation.md)实际读全文、统计语言、提炼五份规则、写原创样稿验证，合格后自动注册。少于20篇先做初步学习，不冒充正式文风。以后写前自动列出新风格与卡兹克。用户要求先确认时先交样稿。

引擎已经嵌入本包，新安装不需要另外全局安装writing-dna。首次安装后的下一轮会话可被宿主发现；学习到的个人风格保存在工作目录.wechat-ai/writing-styles，公共ZIP不会带走你的原文或账号。更换电脑需要显式迁移自己的风格库和工作资料。


## 快速传稿连接

新增官方API和独立浏览器DOM通道。首次使用按[连接说明](fast-publishing.md)做本地凭证/权限诊断或专用浏览器扫码标定，后续复用；plan在上传之前决定通道。API和浏览器都只入草稿，不自动发表。分享包不含账号、浏览器资料目录、密钥、素材缓存或个人文章。Python标准库之外，浏览器验收需要宿主Node、Playwright、pngjs和Chrome/Chromium；先发现现有运行时再考虑安装。


写作后自动执行本包[Humanizer审稿](humanizer-review.md)，无需另外安装原仓库。先保留所选风格再改套话，教程按普通人的操作过程讲清楚；审稿说明不进入正文。十套排版的一般正文统一黑色，标题与标志性文字保留原主题颜色。

## 新版首次使用

先onboard.py doctor，再按当前目标setup，setup合并偏好并启用题材验收。现有工作目录profile实际参与新稿init，显式profile覆盖它；旧批准文章不重新初始化。截图、读者所得、效率与发行验收分别见[screenshot-strategy.md](screenshot-strategy.md)、[reader-value.md](reader-value.md)、[performance.md](performance.md)、[release-readiness.md](release-readiness.md)。
