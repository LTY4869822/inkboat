当前截图范围以[场景截图规则](screenshot-strategy.md)为准；本文保留溯源、登记和实际采集验证方法。

# 普通读者能跟着完成的逐步教程

用于注册、安装、设置、提交、部署等操作。纯观点和资讯不强制套教程；只含教程段时仅为相应段建立步骤。reader-intent.article_type=tutorial表示纯教程，tutorial_sections列出文章中的教程小节。

## 从起点到成功，不省略中间状态

先核对当前官方流程，记录核验日期、入口、设备、语言、版本、所需材料。不要默认第一次使用的读者已注册、已登录、知道设置在哪里或认识专业词。

每个编号步骤写清：当前在哪个页面；点击哪个可见控件；填什么及格式要求；完成后应该看到什么；常见错误与如何恢复。无需输入就明确说明。一个界面内可以一次完成的相邻微动作合为一步，但必须逐项写出；换页面或到关键状态另列步骤并配图，不以“完成注册”等一句话跳过多段流程。

例如注册GitHub，要核验从公开入口到实际注册完成的路径，包含当前出现的信息填写、验证、邮件确认或其他必要分支，以及最终成功标志。这里只定义核验范围，不硬编码GitHub当前界面；入口、账号状态和流程变化时按真实情况写。可选引导明确是否可跳过。未完成必要验证不能称“我们成功注册”。写教程不自动授权创建账号、接受条款或使用他人身份；本人邮箱、验证码等无法代办的步骤由用户帮助。

## 每一步配对应真实画面

在步骤说明旁插入保留一屏上下文并框出操作区的真实截图（用户另选范围时依其指示），并用正文告诉读者看哪里；保留定位所需标题和上下文。最后一步展示实际成功画面，不能用注册首页代表注册成功。每一步的图不能被固定数量限制删掉；通过合理分组、裁切和排版控制长度，而非省略关键步骤。

补图顺序：

1. 在权限允许的环境打开原产品，按当前流程实际操作并截图，依real-screenshots.md登记。不能把演示当自己的执行。
2. 自行采集不了，搜索官方帮助或可靠作者的原始教程、视频关键帧。实际打开看图/播放相应位置，核对版本、入口、语言、动作与结果；保存链接、作者、原发时间（未知如实记）、视频时间点及图片使用依据。搜索缩略图、AI摘要、过期界面不能直接顶替。第三方画面不写成我们的操作结果。
3. 仍找不到，记录manual_needed并逐张告知用户：第几步、缺什么画面、必须看见的控件/成功信息、已尝试的来源及具体障碍、需要他做什么、影响哪段教程。例如请完成邮箱确认后提供可证明账号可用的界面；不索取密码、验证码或无关个人资料。继续完成其余内容，保留明确缺项，不称完整或直接存草稿。

不能用AI生成UI、重画按钮、替换验证结果，或跳过无法完成的步骤。用户提供后核对上下文、步骤和使用权限，保留原图，不冒称自己操作。正文保持正常操作说明及注意事项，无来源附录或AI生成图注，来源仅存内部。

## 步骤账本和原图溯源

tutorial-plan.json绑定body_sha256，记录task_context、starting_point、success_definition、steps。每步唯一id、title、before、action、input_hint、expected_result、attention、body_quote（本稿原句）、image_paths、status；status为ready/capture_pending/search_pending/manual_needed。每个ready步骤必须有已登记且在相关说明之后实际插入的真实截图，概念图、封面及只登记未插入的图不能抵扣。

missing_images每项写step_id、need、reason、tried、help_action，将同样缺项简洁交给用户，不能只说“缺几张图”。最后expected_result与截图须兑现success_definition；脚本不能凭关键词证明成功。可在branch记录条件，按选定路径写清必需步骤，未完成验证不标ready。

自己操作图用kind=operation关联真实experiment；外部原图可用kind=public-case及浏览器/视频截图。下载或用户提供的原始截图使用kind=tutorial-step、tutorial_origin=external|user、capture_method=source-image-crop，保存original_image_file、original_image_sha256、原像素尺寸viewport、实际clip、output_pixel_size、pixel_operation=crop_only、usage_basis及正常观察字段。外部图page_url对应已核验作者页面，记录platform、author、post_time、evidence_scope。用户图关联access=human_supplied的来源并写supplied_by=user；未知URL留空，不能编链接。原图本来就是有用局部时可用完整原图矩形，记录already_partial=true和具体partial_note；整页长图不能借这个标记通过。

按390px查看每一步图文，检查名称、状态、顺序、成功条件。check-images与audit拦截缺步骤账本、缺图、AI代替截图、待人工、过期正文和未解除缺项。交付前再从“未开始”逐步跟到“已成功”，核验文字与真实画面相互兑现。


## 2026-10-05 完整一屏与操作框线

以下框线分支适用于教程完整一屏或用户明确选择；其他场景统一按[screenshot-strategy.md](screenshot-strategy.md)决定，不能将一屏规则套在中文整帖任务上。个人截图偏好保存在工作目录profile，不绑入发行默认。完整页面仍需有用的信息与紧邻说明。

完整未标注原图先存evidence。框线作为独立几何标注添加，不改变原图尺寸、不翻译替换文字、不重绘按钮和结果，不用生图模型重造产品界面。原作者或官方只提供表单局部时保留其原始范围，记录source_extent=provided-partial，不把它称为现场完整屏幕，也不补造背景；必要时寻找完整画面或具体报告缺项。

使用scripts/screenshot_annotations.py --original 原图 --output 标注图 --frames 框线JSON --record 输出记录。框选仅此分支按需使用Pillow，先检查宿主已提供；缺失时安装到工作目录隔离环境，核心编排仍用标准库。实际验证原始像素与标注图：输出必须等于原图加已声明框线，框内文字也不可改动。不是仅凭“看起来一样”认定真实。

自己采集用capture_method=browser-annotation，外部原图用source-image-annotation及kind=tutorial-step和真实tutorial_origin。保存original_image_file/sha256、完整viewport与clip、output_pixel_size、pixel_operation=frame_overlay_only、annotations数组、user_instruction原话及正常来源和插入记录。annotations每项x/y/width/height、color、stroke_width必须对应实际控件，不能画框造出新的结论。旧的局部裁切方式和已确认旧稿仍兼容。

完整一屏在390px检查框线能否定位操作，按钮名和输入要求由紧邻中文正文讲清；截图字太小时选合适实际视口、增加有必要的独立步骤，而非宣称放大后就已通过快速理解。保持原始界面，框线不等于已操作成功，也不以首页证明邮箱已验证。
