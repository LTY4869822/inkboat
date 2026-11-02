# 混合配图、内置生图和周行导出

1. 先读完整正文，再做编辑设计。逐个关键段决定真实截图、概念图或不配图，并记录原因，完成后再定数量。`images-plan.json` 包含 `body_sha256`、`art_direction`、`coverage`（section对应每个二级标题、anchor、need=screenshot|generated|text-only、reason、asset_paths）及 `assets`，coverage必须考虑全部小节。每张正文图除path、role、insert_after等原字段外，写`value_check={question,reader_gain,why_this_medium,removal_cost,evidence_kind}`。evidence_kind用feature|data|case|operation|concept；identity-only不能算有效图。截图让读者看见原始事实与成果，生图解释关系与过程，纯文字已能说清的段落不必配图。无上限或固定配比，不能总是1张截图加1—2张生图；同样不能以多图展示努力。检查遗漏重要证据、重复信息、手机小字和连续图堆积。图解先列节点、分支和关系，不把文章缩成几个卡片。
2. 常规正文同时有真实截图和AI插图，封面不抵扣正文；有内置生图时实际使用，无内置时询问是否配置和具体模型。真实无增益例外与用户拒绝配置须留痕，详见 [能力分支](image-capability.md)。读全文决定数量，不设固定张数。公司发布稿捕捉功能、对比或案例的有用局部，教程用实际操作截图，详见 [real-screenshots.md](real-screenshots.md)。先核验时顺手采集，正文完成后补真实插入点及价值判断。AI图用于封面与必要的概念解释，不重绘公告或产品界面。所需概念图实际调用内置 image_gen；用户提到 image2.5 是需求，不是工具参数。工具无模型选择字段时actual_model=null并记录tool-native，不借用陌生代理站。无内置生图时进入配置问答；选择配置但未完成记image_pending，用户拒绝则用真实截图。自有图片登记user-supplied，不以SVG假装生图。
3. 封面默认cinematic-editorial，按 [电影感封面设计](cover-art-direction.md) 及用户偏好执行。正文图单独按 [用途决定风格与密度](adaptive-illustrations.md)：可以用信息插画、叙事、剖视、等距或艺术隐喻等适合本段的表达，不固定蓝金、3D、竖版或上一期张数。正文仅需保持概念标签和信息层级一致，不强制与封面配色呼应。注册、安装等教程读 [逐步截图规则](tutorial-screenshots.md)，每个实际步骤对应真实画面，缺图依次自行采集、检索原始画面、精确请用户帮助；AI不能补造UI。

   生成原图拷贝到 run/assets，绝不只引用临时路径。封面约2.35:1，核心位于中心1:1（x=(W-H)/2 到 (W+H)/2）并留内侧余量；主文案一般6—10汉字、最多两行，左右只延展背景。正文解释图优先手机可读，大段说明留正文。查看原图与横版、中心裁切、320px缩略图。默认插图不加「AI生成」图注，来源与概念性质留在 images.json 和内部审阅；画面不能带此类来源标注，也不能伪装产品界面或实测结果。功能示意可用准确内容标签。

   `visual-review.json` 的 `images` 以相对path为键，每项写sha256、status、checks，实际检查文字、主次、内容、手机字号及视觉表达是否适合本段；cover另看中心裁切，正文不强制统一色板或媒介。正文checks.reader_comprehension说明图片连同相邻文字怎样降低理解门槛。复杂图表保留必要条件，紧邻中文解释要点，详见real-screenshots.md。任何错字、错误连线、裁断核心、难懂或混乱都不算通过；指出问题后最多一次针对性修复，截图只重新采集/裁切，不生图修改事实。全篇再核对密度，不能以生成成功或固定图数宣称适量。
4. `register-image --run RUN --file ABS_PATH --role cover|body --prompt TEXT --backend native --provenance <实际生成记录JSON> --checked --note 具体检查结果`。路径必须在 run 内，自动登记 sha256，实际模型未知不填。同路径更新覆盖同条元数据，不另建 v2。
   真实截图使用`--backend screenshot --provenance <run内的capture.json>`；采集、裁切和插入规则见real-screenshots.md。截图不调用生图，也不填模型。所有图都通过原图哈希、视觉审阅、排版导出和草稿读回核对。
5. `assemble` 和 `layout` 后以宿主浏览器打开 preview.html。周行桌面设置栏与文章手机阅读是不同的页面，窄屏验收以 mobile-preview.html 的文章为准。
6. 点击 `#copyButton`，检查成功文字并读取 text/html。浏览器有 clipboard API 时可 `tab.clipboard.read()`，使用普通文件工具将返回的 text 保存 run/staged.html；不从不相关剪贴板读取私人内容。若宿主读到旧内容，首先停止使用旧剪贴板。layout 会在预览加入只读 `#autopilotExport`，由周行按钮自己的原始 formatter 写入同一份 htmlContent；实际点击按钮后，读取 textarea 的 value 保存 staged.html，调用 accept-html 时加 `--backend zhouxing-button-dom`，诚实记录导出路径。观察器及响应式复制适配只作用于本次预览：保留克隆根节点的auto外边距和最大栏宽，避免桌面计算的固定像素边距挤窄手机正文。原解析器、组件与复制内联化流程继续由周行提供，不修改其安装目录。可选 clipboard-capture.html 用页面按钮读取浏览器剪贴板，但读到旧内容也不得接受。所有途径均不可用则明确 export_pending。
7. `accept-html` 检查脚本、标题、正文是否丢失，图像顺序与内容哈希、来源链接，再生成 mobile-preview.html、paste-test.html、rich-import-test.html。优先在 paste-test 隔离编辑区通过宿主真实粘贴动作验证图文。宿主不能粘贴 HTML 时，使用 rich-import-test 的文件选择 UI 选择当前 article.html，点击导入；它实际调用浏览器编辑器插入 HTML。读取编辑区 outerHTML 保存为 roundtrip.html，以 workflow.html_check 比较完整正文、图像哈希和来源链接，并检查截图。rich_import 和 rich_paste 分别记录；导入通过绝不能填粘贴通过。至少一个真实富文本往返通过才可交付本地包，微信 editor 未实测独立写 not_tested。
8. 手机视口 390×844，确认图片加载、无横向溢出、标题/表格可读，再恢复桌面视口。预览外壳、工具名和账号推广不应出现在 article.html。

内嵌原图会让 HTML 达到数 MB。若宿主 DOM 读取限制字符串长度，先读取 textarea.value.length，然后按不超过 60000 字符的片段读取 value.slice(start,end) 并拼接到本地文件；核对拼接后长度。不能接受带截断标记的返回，也不要把整段 base64 打印给用户。

如果周行更新导致复制或解析协议改变，读新版本代码和 warning，修适配器并重新验收；不修改安装的周行 skill。纯文本饰条与 HTML装饰允许不同，核对正文时忽略 aria-hidden 的视觉元素。
