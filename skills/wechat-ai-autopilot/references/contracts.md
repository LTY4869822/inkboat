# 文件契约（新运行schema_version=3，兼容旧版1/2）

2026-10-05新run另启用tutorial_policy=step-screenshots-v1及illustration_policy=content-fit-v1，旧run不追溯。reader-intent.article_type=tutorial或tutorial_sections非空必须建立tutorial-plan.json，细节见tutorial-screenshots.md；每步有before/action/input_hint/expected_result/attention/body_quote/image_paths/status，待人工缺项保存在missing_images，不放行完整交付。images-plan的正文生成图增加style_decision={style,reason}；density_review={status,body_quote,excess_check,gap_check}记录全篇预览后的密度判断，见adaptive-illustrations.md。数量没有固定上限/配额，正文风格独立于封面。步骤账本和reader-intent纳入新政策run的fingerprint。

brief.visual_style用于封面方向，正文风格以每图style_decision为准。density_review排版前status=planned可通过check-images，实际全篇/手机预览后status=pass才可通过audit；不能为进入预览提前填最终通过。

run 中保存 UTF-8，工作时间含 UTC offset，默认北京时间。不将 AppSecret、access_token 或 API Key 写进任何文件。

- brief.json：type、topic、audience、min_chars、max_chars、body_images、theme、length_preset、counting_basis、visual_style、practical_mode、profile、presentation。新建默认 presentation={citations:"internal",image_captions:"none"}；用户明确更改可 configure --citations internal|inline --image-captions none|labeled。没有此字段的旧运行保留原内联引用契约，不能将其悄悄重写。
- 新建brief另有visual_policy={mode:"mixed",min_screenshots:1,selection:"content-driven-v2",body_ai:"when_available"}，body_images默认"auto"：读完全文，逐节决定是否需要图片及其媒介。至少1张有效真实截图只是底线，不是截图配额；常规正文需要真实截图与实际AI生图，封面不计；数量按增益决定。images-plan.generation保存能力、配置问答或有依据的无增益例外，详见image-capability.md。用户明确指定数字时仍作数量下限。旧run不追溯撤销确认，旧稿补图须按改稿规则重建。
- outline.json：reader_promise、input_mode、sections数组，每节question、purpose、materials、target_chars；预算总和在用户范围内。
- layout-choice.json：recommended_theme、reason、body_sha256、created_at，由recommend-layout写；用户指定主题优先于推荐。
- images-plan.json：body_sha256、art_direction、coverage、assets和generation（新v2）。coverage逐节记录section（对应正文二级标题）、anchor（本稿原句）、need=screenshot|generated|text-only、reason、asset_paths；必须覆盖所有小节，文字已能讲清时不配装饰图。每张正文asset写backend、purpose、insert_after及value_check={question,reader_gain,why_this_medium,removal_cost,evidence_kind}；evidence_kind只能为feature|data|case|operation|concept，只有Logo/标题/日期不合格。插入图、规划图和逐节决策必须一致。参考图只借鉴设计语言，不复制未经核验事实。
- visual-review.json：images对象，相对图片路径映射到sha256、status、checks对象；记录实际文字、主题对应、构图、手机可读性、配色和封面中心裁切观察。后续正文图另有checks.reader_comprehension={status,reason}，具体说明普通读者通过图片及附近正文能理解的重点与边界；复杂图表补explanation_quote（紧邻正文原句）、conditions_note（必要条件）。重要英文图例与比较条件须在附近用中文讲清，不能只填“有用/可读”。这是实际编辑审阅，不代表自动检查已证明理解速度或已做读者测试；旧run不追溯改写。字数和格式检查不能替代视觉审阅。
- discovery.json：原始热点/精选响应、完整 URL、fetched_at、provider、错误与 attribution。候选不是已核验来源。
- 新discovery另有requests（HTTP状态、缓存命中、尝试次数）与error_details（code、errno、http_status、action及可用的requestId/help）。连接拒绝立即停止同域重试；aihot-diagnostic.json来自真实diagnose-aihot，不从安装状态推断服务成功。
- topic.json：working_title、angle、reader_benefit、selection_reason、hot_signal（原始 rank/sourceCount 及来源时间，不能编造）、duplicate_note。
- sources.json：数组，每条 `{id:"S1",title,url,published_at,retrieved_at,kind:"primary|secondary|lead|experiment",independence_group,summary,verified:true,verification_note}`。来源日期缺失可为 null，不能假用收录时间。independence_group 填信息实际起源，如 cloudflare，不只填不同域名；转载同一公告不算独立。experiment 的 url 可以为 run 相对路径，必须有实际文件。
- claims.json：内部数组 `{id:"C1",text,source_ids:["S1"],status:"verified",locator:"正文小节/段落",body_quote:"本稿中的事实原句",note}`。internal 模式必须有至少8字且仍存在于正文的 body_quote 与定位，audit 从此获取使用过的来源；未知来源和失效段落仍失败。逐项核对数字、版本和可用性，编辑推论注明其性质，不冒充实测。
- body.md：无 H1，默认没有引用编号、文献引用、来源附录及生成来源图注。图片用 `![内容说明](assets/name.png)` 直接插入。默认 assemble 仅追加标题，不输出内部来源。仅用户明确改为 inline 时恢复事实编号及来源附录；旧带图注稿的计数器兼容仍保留。文章可自然写发布主体与厂商自报，不伪装发现者。
- experiments.json：数组 `{id,date,environment,actions,input,output_path,observations,failures,limitations}`，路径必须为 run 内真实记录。
- images.json：register-image 维护；包含 path/role/source/backend/actual_model/prompt/sha256/visually_checked/check_note。封面 role=cover，正文 role=body。生图实际版本无法确认填 null。
- screenshot记录另含provenance：kind=announcement|operation、source_ids、page_url、page_title、captured_at、capture_method、capture_sha256、viewport、clip、observed_text、insert_after、review_note。browser-clip对应浏览器原始局部像素；pdf-render-crop对应已核验官方PDF原始图表，另须pdf_file、pdf_sha256、page_number（从1开始）、page_size_points、render_scale；viewport/clip按渲染后像素记录且与页尺寸、缩放一致。公告对应已核验primary页面/PDF，操作对应实际experiment；URL不含凭证，不截整页，锚点在本稿且位于图前。字段校验不能证明像素真实性，仍须实际查看。
- titles.json：`{body_sha256,provider,selected:"T1",digest,candidates:[{id,title,method,scores:[8维数字],risk,risk_reason,evidence}]}`。
- 新editorial_policy=research-depth-v1：titles候选至少12个、至少6个method，shortlist三个ID，selected在其中；候选另含reader/hook/promise/opening_reason/body_quote，短于26或长于42可见字符须length_reason，第一人称实测标题另有experiment_ids。用户固定标题例外详见titles.md。
- review.json：`{fingerprint,checks:{facts:{status:"pass",reason},voice:...,type_value:...,title_alignment:...,image_fidelity:...,cover_safe_zone:...,mobile:...,rich_paste:...,rich_import:...},wechat_paste:"not_tested|pass|fail"}`。脚本不能代替语义审阅，reason 必须具体。真实粘贴或真实编辑器 HTML 导入至少通过一项，路径分别记录，不能把导入写成粘贴。微信与剪贴板未验证会列为 warning，不能称它们通过。
- V2 review.checks 另含length_depth、layout_fit、visual_design，每项status和具体reason；schema1仍按旧契约检查，不把旧短文标成新版标准篇幅。
- export.json、layout.json：脚本写，绑定 article.md hash，任何源稿更改要求重建。
- quality.json：脚本生成，不手改结果。passed=true 表示本地包当前契约通过，语义项由 Agent 负责真实审阅；fingerprint 和 review_sha256 绑定当前产物与审阅，发布实现需再次检查未改动。

断点以文件与哈希为准，阶段为 discovery → evidence → writing → images → layout → titles → export → review → complete。首次初排无标题候选也能进行，final 导出必须有已绑定正文的标题。不要为断点续作生成第二份近似正文。

V3新增：

- intake.json：四项实际回答、topic_mode、topic、selected_candidate（按需）、length_preset/min_chars/max_chars、font/custom_font、writing_style=所选可用风格id（默认khazix），蒸馏文风另存writing_style_version与writing_style_manifest_sha256、answer_origin=user|explicit_user_delegation、user_instruction、status=ready_to_write。与brief字段必须一致；初始默认值不充当已回答。
- brief.json另有font、custom_font、writing_style；profile.output_mode默认draft_after_layout_selection，用户要求只做本地时为local。auto篇幅的outline.length_reason必填。
- topic-candidates.json：searched_at、五个唯一候选，各有title/angle/reader_benefit/primary_url/published_at/retrieved_at/hot_signal。日期对应实际查询前7天；用户选候选或明确委托，不自动代替其选择。
- layout-variants.json：全文和body hash、图片hash、字体、推荐、当前十个真实预览路径/hash（按主题目录生成，不锁死数量）。
- layout-selection.json：人类选择原话、decision_origin=user、theme、font、no_pending_edits、article/body/variants/selected_preview hash。测试点击不写作用户选择；改稿或原图变化旧选择失效。
- .wechat-ai/account.json：位于workspace而非run/skill，存公开名称/公众号ID、browser backend、用户长期入草稿指令与核对说明。不存密码、cookie、token或AppSecret；分享包不包含。
- draft-transfer.json：当前授权、account/account_id、质量fingerprint、HTML与图片hash、existing_draft_id。自动路径由记忆账号+本稿有效选择提供授权，无需再问一次；账号不匹配不写。
- draft-receipt.json：实际draft_id、saved_verified|saved_needs_review、published=false、真实保存观察、读回结果及截图。保存不代表发表。

新稿阶段：intake/topic-candidates → evidence → writing → images → provisional-layout → titles → five-previews → user-selection → final-export/review → connected-account-draft。fingerprint绑定V3输入和选择，质量需在选择之后重新审阅。旧run不因安装新版自动重写契约。

editorial_policy新契约：research-plan.json为平台查询计划，research-log.json为对应实际执行与可读范围；sources另含read_record及其文件hash；cases.json为原始观察支持的案例卡；depth-review.json绑定六项输入hash、所有实际小节的信息增量、当前段落与claims/cases，并含counterevidence/transferability/non_generic实际审阅。具体字段见research-depth.md与research.py。audit对新run调用检查；该政策及内部材料变化使旧审阅失效。checks只验证记录对应关系，不能证明案例结果或自动保证深度。

2026-10-04内容学习合并后，cases可选case_type=human_or_organization，按人物/组织的目标、处境、选择和不同声音记录；省略case_type继续使用既有技术任务字段。两种类型的原文、哈希、引用定位与origin检查相同，不能靠改类型把来源或真实执行要求跳过。

文章学习不使用写作run的brief或草稿权限。其study.json、articles.json、lessons.json、summary.md和integration.json在用户工作目录，字段及命令见 [content-learning.md](content-learning.md)；learning.py只验证记录一致性，不代替实际阅读。


蒸馏风格专有文件：style-context.json（固定风格版本、五份文档、相关五篇样本和文件哈希），style-calibration.json（宿主实际阅读及体裁适配），style-writing-review.json（当前正文对规则的落实、原创性和白名单清理审阅）。缺少、变更或旧审阅阻止assemble/audit；fingerprint涵盖这些文件与复制的十个输入。注册契约及工作目录风格索引见[文风学习](style-distillation.md)。旧卡兹克稿不强制补这些文件。

2026-10-05工坊版新run另启用motion_policy=article-motion-v1与studio_policy=saved-final-v1，流程以[studio-motion.md](studio-motion.md)为准。motion-plan.json绑定本稿章节和文字，每项有用途、位置与参数，默认enabled=true，用户可在预览关闭。studio/latest.json与revisions/rNNNN保存当前版本，studio-final.json、selection_backend=studio-saved-final的layout-selection.json绑定实际人类确认；旧版画廊确认仍兼容。fingerprint覆盖motion-plan、studio-final、latest、动效依赖及所选动效原图。保存或内容改动使旧审阅失效；dirty状态阻止上传旧版。review新增motion_design实际审阅。draft-transfer的images包含按sha去重的SVG背景图，image_occurrences包含重复使用的图片位置；verify增加SVG结构和后台实际动效观察，不以本地通过冒充微信通过。


完整一屏框选来源契约：browser-annotation或source-image-annotation支持完整原始尺寸与frame_overlay_only。保存完整未标注原图、哈希、实际annotations矩形、用户选择、图片来源和插入位置；校验逐像素等于原图加声明框线，不允许改写框内/框外UI。官方原图本为局部时如实记录source_extent，不称完整现场屏幕。详见real-screenshots.md。


2026-10-05新增humanizer_policy=humanizer-style-preserving-v1：新run先按选定文风写作，再按humanizer-review.md实际改稿。writing-draft.md、humanizer-context.json、humanizer-review.json纳入fingerprint；review绑定原稿hash、当前prose_sha256、文风和真实问题记录，教程增加tutorial_handholding。单独插入配图不会改变规范化正文hash；图片原文、代码及链接仍受保护，文案改动须重审。脚本不是AI来源检测器。普通正文统一黑色，标志性文字维持各主题表达；微信读回增加实际计算颜色核对。


2026-10-08新run启用tone_policy=dual-tone-style-preserving-v1，Humanizer后执行独立版lieflat白名单检查。humanizer-output.md、lieflat-context.json、lieflat-review.json加入fingerprint，第一道绑定中间稿、第二道绑定当前正文；缺任一道、偷偷改未命中句或结构改变不能通过audit。旧已确认稿不追溯失效，详见dual-tone-review.md。Agent-Reach检索原始结果写入文章run的readings，仍须实际阅读与来源核验；doctor不代替搜索与截图成功。
