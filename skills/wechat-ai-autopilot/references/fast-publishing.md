# 两条传稿通道、一次连接与有界验收

这是2026-10-05的脚本升级。官方API路径已通过模拟客户端测试，独立浏览器的剪贴板载荷、文件输入与本地动效通过实际Chromium测试；随后GitHub新手教程已经在独立登录资料中通过真实UI存入草稿并重新打开，13张正文图与三处动效在官方阅读预览核验通过。此次过程中发现并修复的选择器、批量映射与粘贴弹窗问题见verified-efficiency.md；修订脚本须按其各自的真实测试范围报告，不将手工恢复结果冒称整条自动命令已经零干预完成。既有文章的四款兼容动效在此前真实微信阅读页已通过鼠标和模拟触屏两次回播。不能把这些不同范围合并成“所有账号、所有动效都实测成功”。

## 默认选择

用户确认保存版、adopt与audit通过后，先prepare，再执行：

```text
python <SKILL_ROOT>/scripts/fast_publish.py plan --run RUN
```

返回route和api_blockers。没有凭证、原生SVG动效、过大的HTML，或本篇已有网页草稿但没有对应API media_id，使用browser_dom。API的20000字符是本项目保守传输阈值，不是已核实的所有账号最新限制；不能静默删CSS、截标题、重排或取消动效以凑阈值。图片替换后的真实长度在写入前再次检查。

已完成连接/标定后，统一执行`fast_publish.py deliver --workspace WORKSPACE --run RUN`：按plan走API或独立浏览器；API明确40164/48001拒绝时可转浏览器，响应丢失绝不跨通道重建。它负责传输，返回saved_needs_review后仍由Agent取新官方阅读页完成验收。素材超过项目API PNG/JPEG及1MB保守门槛也提前分流，不在传稿中临时压缩用户原图。

API和网页编号是两个命名空间：网页appmsgid不能直接用作API media_id。已有同篇网页草稿须继续更新它；不能为了选API而新建重复稿。API条件满足也先做只读探测，40164检查出口IP白名单，48001检查账号接口权限。明确接口拒绝可换浏览器；网络超时且写入结果不明时不能换通道再创建。

## 官方API：完全不用桌面操作

借鉴[baoyu-post-to-wechat](https://github.com/JimLiu/baoyu-skills/tree/main/skills/baoyu-post-to-wechat)与[wenyan-core](https://github.com/caol64/wenyan-core/blob/main/docs/wechat.md)的官方接口路径。新代码独立实现，不引入对方排版器，不复制其默认引用、主题、评论设置。密钥只从宿主环境读取。

首次配置由Agent引导：

1. 在公众号后台实际核对账号名称、原始gh_ID、AppID与接口权限。没有draft/add权限，直接使用扫码浏览器，不要求用户无效地配置密钥。
2. 用户在本机设置WECHAT_APP_ID、WECHAT_APP_SECRET。AppSecret不发聊天、不放skill/ZIP/日志；不要通过命令行明文参数传入。必要时由宿主提供密码输入或环境设置界面，Agent只检查是否存在。
3. 将运行机器的实际出口IP加入后台白名单。固定出口可减少动态IP变化造成的重新配置；本包尚未实测SSH代理，不把它列为现成加速能力。
4. 确实看过AppID和gh_ID对应关系后，`fast_publish.py bind-api --workspace WORKSPACE --account-id <实际gh_ID>`绑定AppID的单向哈希和公开账号ID，不保存密钥。随后doctor。doctor仅证明token/IP及draft/count可用，不能提前声称draft/add权限已通过。

```text
python <SKILL_ROOT>/scripts/fast_publish.py doctor
python <SKILL_ROOT>/scripts/fast_publish.py push --workspace WORKSPACE --run RUN
```

push校验当前批准指纹与账号绑定，最多三个图片上传任务并发，SHA去重、正文图及封面分别缓存。缓存按API账号隔离，纯公开素材URL/media_id，正文图和封面内容变化会重新上传。当前API图像实现仅接收批准PNG/JPEG，不把GIF压成静态JPEG。任何图片失败都不写草稿；不沿用其他账号的素材。

正文使用确认过的HTML，标题、摘要、作者来自当前meta；不调用Markdown重排，不改原创/评论/发布设置。保存前写journal并用run锁防并发；已有API稿update，无则add。响应丢失保留write_in_flight；`fast_publish.py recover --run RUN`只读查找最近最多60条，唯一标题、摘要、封面及全文样式匹配才接回原稿，零条或多条时交给实际后台核查，不自动重发。崩溃残留锁先检查进程与journal再清理，不猜测成功。

返回api_readback_status，对API读取的全文、CSS、图片顺序、标题摘要和封面media_id检查。状态仍为saved_needs_review：API读回不是图片加载、实际封面裁切和阅读效果验收。全部真实验收后由draft_bridge verify记saved_verified；流程止于草稿，没有发表接口。

## 独立浏览器：不抢占桌面鼠标和焦点

使用自己的Playwright持久化资料目录WORKSPACE/.wechat-ai/browser-profile，不读取或导入用户其他浏览器Cookie。不打平台私有HTTP接口。初次扫码需要用户操作；登录有效时后续无头运行。资料目录含本机登录状态，必须留在用户工作目录并排除分享和Git提交；不同公众号用独立目录，不混账号。

依赖Node与Playwright、可启动的Chromium/Chrome。发现宿主已有运行时，不重复安装。通过PLAYWRIGHT_MODULE_PATH、WECHAT_BROWSER_EXECUTABLE、可选PYTHON_EXE传入实际路径，不硬编码开发者电脑。受限主机返回spawn EPERM时改用获准的浏览器运行环境，不换一堆焦点/坐标尝试；缺依赖才安装相应依赖。

```text
node <SKILL_ROOT>/scripts/browser_draft.cjs connect --workspace WORKSPACE
node <SKILL_ROOT>/scripts/browser_draft.cjs inspect --workspace WORKSPACE
node <SKILL_ROOT>/scripts/browser_draft.cjs push --workspace WORKSPACE --run RUN
```

第一次连接后由Agent根据真实DOM标定WORKSPACE/.wechat-ai/browser-selectors.json。它仅保存账号公开ID、可见账号文字、唯一选择器、图片/封面正常UI动作以及裁切核验记录；不保存含token编辑URL。单次编辑URL可由宿主在进程环境WECHAT_EDITOR_URL提供，严禁打印、分享或跨账号复用。inspect只列控件结构，不读取Cookie/密钥。选择器不唯一立即停在该步，重新观察实际DOM一次，不遍历坐标盲点。

标定字段：account_id、account_marker、account_text、title、body、可选digest、save、save_success；新稿另需editor_actions、draft_list、draft_entry；图片需要body_image_input与可选body_image_actions；封面需要cover_input、cover_before、cover_after、cover_success及实际双裁切核验crop_verified。既有稿封面确实未变且已在该稿核验时可记录cover_sha256以复用；不能把别的稿核验值通用化。

动作仅普通DOM点击、fill元数据、文件输入setInputFiles和键盘操作。正文用ClipboardItem写text/html，再对目标contenteditable正常全选粘贴，不能fill正文、evaluate改编辑器innerHTML、注入execCommand或调用平台内部接口。上传图按单张或已标定的小批等待实际新增URL集合，按公开图像像素登记原图SHA；映射图仍可访问且为图像才复用。上传结果不明先查，不能重复触发。封面双裁切只标定一次动作逻辑，每稿仍按批准图片核对安全区。

保存只点击草稿按钮；保存前记journal，成功观察后刷新同一稿号并读全文。新稿在官方草稿列表按唯一标题重开获得真实稿号；保存成功但身份不明时维持save_in_flight，不再建一条。保存后全文样式、图片、标题摘要检查不通过保持需复核。原生Chrome contenteditable默认粘贴可能去掉冗余继承CSS、将650字重变700；本地默认编辑器通过不证明微信ProseMirror通过。必须核对实际微信重开HTML，不能为通过检查放宽样式门槛。

独立资料目录已由用户扫码，在本机目标账号完成新稿、上传原图、富文本插入、双封面裁切、手动保存、同稿重开与官方阅读预览验证。期间借助正常UI逐项恢复，并非统一deliver命令零干预通过。新安装者仍需自己的首次扫码与选择器标定，不能复制开发者账号。已有内嵌浏览器登录不等于独立资料目录登录；没有新的批准文章，不新建测试稿。

## 动效在预览前处理，失败不假完成

新预览的motion-compat.js与传输motion_transport.py使用同一四款兼容构图：引文显影、三节点步骤接力、双栏对照、结论收束；单次播放，整卡点击或触摸可回播，无SVG id/clipPath依赖。预览和最终上传的结束文字、颜色、字体及尺寸保持一致。历史批准工坊版本不重写。

四款是发布推荐，其余16款保留在工坊并标记“试验款，需额外验收”，不说它们已在微信验证。新稿自动起点只推荐稳定款，但Agent仍须通读决定类型、位置和密度，不固定张数。四节点步骤、循环版仍未验证；不能只凭款式名称宣称兼容。快传plan先检查不可用ID引用、回播触发和试验款；未通过就停在预览验收，不先上传再修。

用户需要新的试验款时先做无id兼容与本地清理模拟，再保存微信后的实际阅读页测试，通过后才登记该结构。无法兼容须说明具体问题并交修改预览确认，不自行关动效。GIF是待研究后备路径：本次未实际验证微信GIF入稿，不列成已经接通的自动方案；禁止把GIF单帧截图算作动效成功。

真实保存并重开后生成新鲜官方/s阅读页临时链接，临时url文件不进入分享或日志。执行：

```text
node <SKILL_ROOT>/scripts/motion_check.cjs --url-file <临时文件> --out RUN/reader-motion --selector "#js_content svg"
```

最多四个独立卡片页面并发，按实际动画时长等播完，再点击空白处与第二次回播；比较前后像素确有变化并核对结束帧相同。脚本禁后台节流以避免测试页不活跃时暂停动画；不是加速文章动画。官方origin/path核验，检查完删临时链接；local_fixture报告reader:null，不能用于微信验收。物理手机与深色模式未测须明确说明。

停止条件：页面/账号不一致、质量过期、未保存修改、素材失败、保存结果不明、结构或可见动效失败，都写明确阶段和缺项。相同失败一次正常修复后仍失败，先读回并交代具体阻塞，不无限换窗口/重复上传。耗时按preflight/assets/paste/save/readback/reader分别记录；没有真实总计时不承诺“几秒上传”或提速百分比。

## 借鉴范围

[baoyu-post-to-wechat](https://github.com/JimLiu/baoyu-skills/tree/main/skills/baoyu-post-to-wechat)：HTML原稿、官方API与CDP目标页操作的分流。
[wechat-mp-mcp-server](https://github.com/xihe-lab/wechat-mp-mcp-server)：多后端与能力诊断的组织方式；不直接接入其Web私有接口。
[wechat-publisher](https://github.com/sakuraoxo-clio/wechat-publisher)：作者明确记录draft/add不包含SVG互动，据此采用保守的原生动效浏览器分支；这不是微信对所有账号的永久能力保证。
[微信文章结构规范](https://github.com/wechatjs/verify-article-structure-spec/blob/main/verify_article_structure.md)：事件兼容和正文结构参考。官方接口文档本次浏览失败，接口名经上述实际项目代码核查；权限/限制以连接账号实际结果为准。


本次实际UI校准：保存按钮使用button:has-text("保存为草稿")，其子span使button:text-is不匹配；成功提示实际是“已保存”。点击“文章”会创建新标签，须等待真实编辑URL，about:blank不是加载失败。文件输入支持multiple时可按小批上传，用新增URL集合及image_readback.py的公开原图像素比对确定SHA映射，不按DOM末尾顺序猜；缓存若不同SHA共用同一图片URL，停止并核验。上传时可能自动取得appmsgid，应立即记录到journal，恢复复用同一稿。粘贴遇“内容结构检测”时先核对并继续插入，再等当前全文到位。

实际阅读验收：滚到每张图片后等待mmbiz地址及naturalWidth>1，1×1占位图不是通过。微信阅读页可能给每张图创建全新材料地址，原始URL比对仍保留失败项，额外用公开图片像素与顺序核验，不放宽严格比较。表格thead/tbody正规化和编辑宽度变化分别记录；以官方阅读页的实际宽度、字体、颜色与横溢出判断可见效果，不能把CSS序列失败改成通过。普通正文黑色也在实际计算样式中检查。

草稿传输不自动改原创、创作来源或群发设置。发表须有当前明确授权，用户喊停立刻取消且记录授权撤销。内容自然表达与平台AI来源声明属于两件事；申报设置及平台要求在发表前明确，不能等到最后一步才给用户意外。状态以实际后台/发表记录为准，提交成功不等于已发表。
