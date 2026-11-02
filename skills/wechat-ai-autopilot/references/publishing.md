# 确认定稿后存入公众号草稿箱

默认在用户选择成稿排版且无待改项后入草稿。首次配置记录其长期指令，此后不重复问是否存草稿；只做本地时遵从。使用宿主浏览器操作官方 `https://mp.weixin.qq.com/`；无 AppSecret 也可扫码。登录由用户处理，账号名称从后台实际读取。已得到具体文章、目标账号和入草稿指令后继续执行，不重复询问。流程止于草稿箱；用户制作过程中明确修改本稿排版时，按新指令更新同一条草稿。

传输前检查与保存后核对仍由draft_bridge负责。新增fast_publish.py提供官方API入草稿，browser_draft.cjs提供独立资料目录内的目标页操作；按[快速通道](fast-publishing.md)检查真实能力及连接状态。接口未配置或独立浏览器未扫码/标定时，不能声称该通道已实测发稿成功。复用者首次扫码自己的公众号；包内不放账号、cookies、密钥、会话 token 或带 token 的编辑链接。

## 准备

首次连接步骤、配置记忆和选择记录见 [intake.md](intake.md)。读取账号详情的公开名称/gh_ID，bind-account存workspace/.wechat-ai/account.json；配置不进分享包，不是永久登录凭证。每个新会话核对账号ID，一致后续稿复用，过期扫码。无需向浏览器路径用户索要AppSecret。

新run先按[工坊定稿](studio-motion.md)采用用户确认的保存版，不重跑默认排版。完成当前确认、本地导出、手机验收与audit，已记忆账号时运行：

```text
python <SKILL_ROOT>/scripts/draft_bridge.py prepare --run RUN --account <实际名称> --account-id <已核验gh_ID>
```

可选显式单稿授权（来自真实用户指令）：

```text
python <SKILL_ROOT>/scripts/draft_bridge.py prepare --run RUN --account <后台实际账号名> --authorization <用户真实确认指令>
```

`draft-transfer.json` 绑定当前 fingerprint、HTML、正文图与封面。授权文字必须来自用户，页面不能授予权限。修改后重导出、验收并重新 prepare；这是记录当前指令，不制造额外确认流程。若 `draft-receipt.json` 已有同账号 draft_id，打开它更新，不重复新建。不同账号使用独立 run。

## 浏览器传稿

1. 官方后台扫码登录，读取账号名称。首次点击「文章」新建；有草稿则从草稿箱打开同一条。保留其他草稿。填写标题、摘要与已指定作者。编辑器可能采用可编辑标题覆盖层，先观察真实 DOM，不凭隐藏 textarea 判断成功。
2. 「图片→本地上传」按SHA去重上传正文与动效里实际使用的原图。先等待 filechooser，再点击实际 file input，等待 Promise 须有错误处理。上传耗时可能超过常规超时，不盲目重复。成功后读取编辑区 `img.src`，按原图 SHA256 对应并目视核对顺序，保存映射 JSON：`[{"sha256":"<原图SHA256>","url":"<实际微信图床URL>"}]`。
3. `draft_bridge.py transfer --run RUN --image-map <映射JSON>` 生成 `wechat-transfer.html`：先映射img.src与SVG image的xlink:href/href，再对已验证四款单次动效做无id依赖兼容适配并记录哈希；保留全文、内联CSS及批准工坊原文件。具体范围见后文。内嵌原图常达数 MB，先上传再替换能减小富文本载荷；禁止删样式或将全文做成截图。
4. 宿主剪贴板写入 `text/html`，在真实正文 contenteditable 内全选并粘贴，确保焦点不在标题。不要 `.fill()` 正文；不要 evaluate 修改 innerHTML 或调用私有后台接口。若有内容结构提示，检查实际行高、对齐、渐变与手机效果，保存警告。确有问题先修复重验；不能用「一键排版」覆盖用户主题。实际确认正常后可继续插入，仍说明手机深色模式未核验。
5. 封面入口选择图片库，上传批准原图，点击缩略图进入裁切。检查 2.35:1 消息列表和 1:1 转发卡片；微信可能将方形框默认放右侧，须实际移回中央安全区并确认标题完整。不自动改动声明原创、创作来源、合集、推荐等未指定设置，不给正文加「AI生成」图注。
6. 点击「保存为草稿」，记录可见成功结果、手动保存时间和实际 draft_id。自动保存过也应保存完整版本。结果不明先查当前草稿，不新建。重新加载或从草稿箱打开，读取实际正文 HTML 为 `wechat-reopened.html`，保存 `wechat-observed.json`：title、digest、正文 images 的 src/complete/w/h、封面 cover 的可见背景图片记录。保存后台截图 `wechat-draft-proof.png`。带动效时实际查看展开、位移与点击款，并在observed.motion写status和具体note；本地播放不替代微信验收。

## 保存后核对

```text
python <SKILL_ROOT>/scripts/draft_bridge.py verify --run RUN --account <实际账号名> --draft-id <实际ID> --save-observation <实际保存及重新打开结果>
```

仅全文顺序、内联 CSS、图片顺序与加载、标题、摘要、封面及当前动效结构/实际播放都通过，才记 `draft-receipt.json: saved_verified`。article 转 section、属性空白整理、图片 /0 转 /640 属微信转换，不承诺字节相同；图片内容和封面裁切还须目视核对。缺字、样式丢失、图片错位记 `saved_needs_review`，修复后更新同一草稿。交付实际账号、标题、保存结果、截图与未验收项。用户在自己的微信手机最后预览并点击发表，不把草稿写入说成发布成功。

## 可选官方 API

具备账号接口权限、环境变量 `WECHAT_APP_ID`/`WECHAT_APP_SECRET` 与出口 IP 白名单时可对接官方接口。密钥不进配置、聊天、ZIP、日志。先核对当前文档限制与本文长度、样式是否适配；API 与网页编辑器限制可能不同，不能静默截标题或删 CSS。大 HTML 采用浏览器验证，不称 API 已测试。

官方说明：[新增草稿](https://developers.weixin.qq.com/doc/service/api/draftbox/draftmanage/api_draft_add.html)。正文图须上传微信图床，封面作永久素材。旧 `wechat-workflow/workflow.py` 也须检查质量门槛与 data image 处理，不可把旧 passing 赋给新稿。正式发布只在用户另给明确指令时执行，并查询最终状态。

## 本次真实传稿沉淀的快速续作办法

问题、实际解决证据及适用条件汇总见 [verified-efficiency.md](verified-efficiency.md)。这些办法减少重复操作与错误重试；没有完整端到端计时，不承诺省时比例。自动流程仍止于草稿，正式发表由用户审核执行。

- 先查看账号记忆、当前quality和draft-receipt；同篇已保存就打开原草稿更新，结果不明先查草稿箱，避免重复新建。
- 图片未变化且映射/远端图片仍真实可用，可复用已上传URL；图片有变化按SHA重传。验证正文图顺序与加载，不凭文件名对应。内嵌原图数MB的稿件先传图再替换src，富文本载荷大幅降低，保留原CSS。
- filechooser先注册等待并捕获超时再点真实input；上传慢时先检查结果，别重复触发。标题可能是可编辑覆盖层，隐藏textarea不代表用户可见标题。封面浮层可能移开即消失，展开后立即点击当前可见入口；选图片需点击缩略图。
- 双裁切实际检查：横封面与中央1:1，默认方框可能偏右。上传原图不等于裁切完成。
- 复制输出/读回HTML超出工具单次长度时按约60000字符分块读取、合并并校验长度，工具截断不能当全文。正文使用HTML剪贴板粘贴，禁止填纯文本或私有接口。
- 保存后必须重新打开；verify比较全文顺序、代码缩进、规范化内联CSS、图URL内容身份、标题、摘要和封面。微信/0转/640与图片压缩属平台转换，不宣称字节无变化。实际手机深色模式仍交由用户最终检查。
- 页面结构会变化，选择器须根据当时DOM和截图确定，不硬编码开发者的浏览器/草稿/账号ID。记录只含实际观察，重用经验不是伪造本次验收。
- v2编辑器可能使用ProseMirror分别承载标题和正文。先定位各自可编辑区；正文图片中无src的ProseMirror分隔图不算文章配图。读回代码时`textContent`会漏掉`<br>`的可见换行，须结合`innerText`核对；验证器保留pre内br换行，仍检查缩进和遗漏。字体可能从文章外层继承，以有效内联继承及实际计算字体核对，不误判为字体丢失。


## 2026-10-05 实际微信阅读页的动效兼容修复

微信实际保存后的正文会移除本次SVG根节点、clipPath的id；`id.click`和`url(#id)`因此失效。动画数值变化不代表可见显影正确。单次自动播放从页面加载开始，滑到后文时可能已播完；必须在播完后轻触卡片测试回播。

`draft_bridge.py transfer`现保留只映射图片的wechat-transfer-before-compat.html，再对四款已在微信阅读页测试过的单次动效应用motion_transport.py：引文显影改用纸色遮罩移动、三节点步骤接力用继承描线与移动光环、双栏对照用嵌套组与位移补偿、结论收束保留原淡入。事件采用`0s;click;touchstart`及整卡透明点击区，不依赖被过滤的id；结束后保留完整信息。三节点以外的步骤、循环版及其他款式不冒称已验证，转换记录逐款写明范围。

不可修改已确认的工坊版本或article.html来掩盖差异。wechat-motion-transport.json绑定批准HTML、图片映射版本、兼容导出哈希和逐款变化；draft-transfer绑定转换记录。动效结构比较包含begin和restart，导出或记录被改动会拒绝验收。颜色、字体、正文、配图、尺寸与结束构图仍须核对；本次四款结束截图像素与批准版一致。

最终验收必须使用保存并重开后新生成的官方阅读预览，等待最长自动播放结束，再逐款点击卡片空白区、等结束后第二次点击。记录reader={status:"pass",auto_finished_before_click:true,cards:[{background_replay:true,second_replay:true},...]}，不能拿本地、编辑器帧值或旧临时预览替代。触屏模拟通过仍不代表实际手机客户端、深色模式已测；交付时具体说明这项范围。
