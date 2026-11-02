# X 推文快速读取与截图分工

本包嵌入 [x-tweet-fetcher 原版 skill](vendor/x-tweet-fetcher/SKILL.md) 和 MIT 源码，固定版本及哈希在其 provenance.json。需要 X 原始案例、厂商消息、操作展示或讨论时读取本文件。默认用本包适配层执行公开 HTTP：不读取浏览器 Cookie、不自动开启上游浏览器驱动、监控、账号操作或定时任务。浏览器步骤仍遵从宿主工具限制。

## 按任务选择通道

- 已有推文 URL：优先 x_fetch.py fetch。通过 FxTwitter 公开代理获取正文、作者、原日期、引用内容和媒体 URL；附带 X Article 有返回正文时一并保留。固定版本仅需 Python3.10+ 标准库，无需额外 pip 安装或 X API Key。
- 还没有 URL：有已配置且实际可用的 Nitter 时用 search；否则宿主网页搜索或已授权 X 浏览器站内检索。定位具体推文再 fetch。无 Nitter 配置立即返回 unconfigured，不能当成“没有相关推文”。不把装好 skill 等同于搜索平台已连通。
- 用户时间线、评论：Nitter 条件相同。timeline 使用 from:用户名查询，避免上游 --user 自动逐条补阅读量而增加请求。结果是代理线索，选择需要的原帖再补读取；评论的日期/完整上下文不充分时回原页面。
- 独立 /i/article 长文、登录后才能显示的部分：使用宿主允许的浏览器；不把标题/预览认作全文。适配层返回 article_partial 时必须保留这个范围。
- 真实截图：项目无截图导出功能，“snapshot”是文本。fetch 只写 screenshot-candidates.json，capture_state=not_captured。实际截图交给宿主浏览器，不能把 JSON 重排成推文卡片当真实截图。

```text
python SKILL_ROOT/scripts/x_fetch.py doctor --workspace WORKSPACE
python SKILL_ROOT/scripts/x_fetch.py fetch --run RUN --workspace WORKSPACE --url https://x.com/USERNAME/status/ID --url https://x.com/OTHER/status/ID
python SKILL_ROOT/scripts/x_fetch.py search --run RUN --query "from:COMPANY feature since:YYYY-MM-DD" --nitter https://USER_CONFIGURED_NITTER --limit 10
python SKILL_ROOT/scripts/x_fetch.py timeline --run RUN --user USERNAME --nitter https://USER_CONFIGURED_NITTER --limit 10
python SKILL_ROOT/scripts/x_fetch.py replies --run RUN --url https://x.com/USERNAME/status/ID --nitter https://USER_CONFIGURED_NITTER
```

以上用户名、日期和实例地址均按实际任务填写。需要连接或部署Nitter时读 [实例配置与验收](nitter-configuration.md)。使用 `nitter_setup.py --workspace WORKSPACE --nitter URL` 实际验证关键词搜索和时间线；两项都有可读推文才保存到工作目录 `.wechat-tools/x-nitter.json`。以后search/timeline/replies带同一--workspace自动读取；临时--nitter优先于环境变量，再优先于本地配置。配置记录是当时的验证，doctor不假装实时连通。

不自动部署 Nitter：上游 README 的 Docker 一行不是完整可用性证明；会有实例、会话及网络条件。用户希望配置时再核实当前上游部署要求，凭证不发到聊天、不进 skill 分享包。返回空列表时适配层标记empty_unverified，不据此宣布“全网没有相关材料”；可能是无结果、上游故障或验证页，回原页面或宿主检索确认。

## 收集与核验

每批最多12条去重推文，最多3个并发公开请求；每条15秒请求超时、不盲重试。Nitter 单次子进程25秒截止，最多两个已配置实例，失败转宿主检索。限制是可恢复执行边界，不是文章素材或图片的数量配额。

产物在 RUN/readings/x：每帖 raw.json 保留代理原响应、reading.txt 保留可读原文、record.json 保留哈希/发布时间/采集时间/媒体及范围；fetch-results.json 保存成功和失败；source-candidates.json 的 verified=false。Agent 通读并核实后，将实际用到的候选纳入既有 sources.json、claims.json、cases.json；需要的话把 X-编号映射到该 run 的 S-编号。不得自动把全部推文作为已核验事实。

正文观点和截图内容仍要分清厂商声明、第三方自报、转载与实际结果。保留原作者和原推文链接；FxTwitter、Nitter 和原 X 页面是同一条信息的不同读取通道，不能算多条独立来源。引用帖是不同作者，不能把它的结论归给当前作者；社区注释和反例保留在内部材料，有关键影响时继续核实。视频地址不等于已看过视频，只据所见片段或可核验作品下结论。

--workspace 启用工作目录 .wechat-tools/x-cache，默认30分钟，按 tweet ID 去重。复用时 fetched_at 仍是原采集时间，reused_at 单独记录。--refresh 或 --max-age 0 用于需要当前内容的读取；不要为了追热点每次重抓已经足够的背景材料。互动数可能来自代理缓存，缺失值保留 null；需要发布具体热度数字时回真实页面核对，并记观测时间。代理读取不能证明编辑/删除前的历史状态。

## 有用截图的采集

先通读 reading.txt，明确文章需要展示哪一个结果、案例或操作；从 screenshot-candidates 选择原页面。等页面正文与媒体真正显示再截图。按[场景截图规则](screenshot-strategy.md)决定范围。整帖交付保留作者、全部正文、附件、绝对日期与互动数据；用户要求中文时使用原平台翻译，不能用英文截图或重新排版的中文卡片顶替。按真实截图流程留未标注原图与采集记录，长帖必要时用保留重叠与媒体完整性的真实滚动拼接。

框选应该指向案例产出、操作步骤、对照结果或有条件的结论；只圈头像、昵称、标题和浏览数不能替代证据。复杂英文案例在紧邻正文讲清任务、结果和限制，390px 下看不清就换更直观原帖、作者作品页或分成不同问题。无法打开时先用可靠原始案例/作品页面，仍缺就说明具体缺哪张图，按现有人工缺图分支处理。文字读取成功不会把截图状态改成完成。

## 2026-10-06 实测范围

固定版本3.1.0读取两条公开推文，无登录或 Key：OpenAI 官方历史公告约1.4秒，244字符并有视频信息；另一条长推文约1.3秒，1325字符，附引用正文和原图 URL。历史公告用于通道验证，不是最新热点。未配置 Nitter 的上游搜索约11.4秒报 all_backends_failed，因此适配层提前检查配置。

同一长推文在本机宿主浏览器实际打开并保存了一屏截图；浏览器沿用用户现有登录。这个结果证明本机浏览器采集可用，不证明抓取器内置截图、匿名截图、视频内容理解或所有用户都能访问 X。后续适配器缓存、去重、失败及来源记录另有实际组件测试；不要将本次少量成功外推成全平台稳定性或固定提速倍数。

无账号研究与原生中文截图不是同一种能力。没有X或Nitter不阻断文章其他来源的研究；特定原帖不可访问时逐张报告缺项。完整性与有限尝试见screenshot-strategy.md；此次新经验仅代表实际采集范围。
