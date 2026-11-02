# 写后 Humanizer 审稿：自然表达并保留选定文风

用户所选写作风格先写，随后完整读取本包固定版本的 [blader/humanizer 原始指令](vendor/humanizer/SKILL.md)，实际通读并改稿。不是关键词替换，也不是鉴定文章由谁写的；不提供虚构的“AI概率”或承诺通过检测器。MIT许可证与来源版本在vendor目录保留。

顺序：风格草稿 → `humanize.py prepare --run RUN`保留writing-draft.md → 标出具体问题 → 整段改写 → 再通读 → 更新claims/depth-review/tutorial-plan中的改动段落 → [第二道lieflat检查](dual-tone-review.md) → `humanize.py check --run RUN`（同时验证两道）→ 配图/标题/排版。主稿写body.md；审稿说明只放humanizer-review.json，不进入公众号正文。代码、路径、命令、图片及链接目标保留。正文在工坊修改后重新做与当前稿绑定的审稿；不覆盖用户保存的排版，已发布文章不擅自重新发表。

## 风格优先与真实信息

重新读取所选风格的高层规则和样稿，蒸馏风格用style-context中的实际版本。保留作者的节奏、立场、幽默、判断和有作用的短句；Humanizer清理重复铺垫、空泛升华、假反问、无必要对比和机械三段式。保留解决真实误区的对比，不将“Star不是安装”等有用说明当作口头套路删除。中文引号、术语及样稿中的标点不机械套英文规则。不能添“我昨天试了”“朋友告诉我”等虚构真人经历，也不能删掉真实失败、条件或限制来显得流畅。

教程以手把手说明为重心，卡兹克风格只体现在亲近的口吻、真实误区和判断上，不能靠亢奋开头、口头禅或鸡汤结尾制造文风。每一步让普通人知道当前页面、要点的按钮、要填的内容、完成后的状态；必要的注意事项放在对应动作旁。按钮英文名附中文含义，输入示例明确哪些可复制、哪些必须换成自己的内容。先讲动作再解释必要原因，保留截图和排错入口；不要反复宣布“读完你将获得”，不要扩写名词或靠重复总结凑长篇。新闻、观点和人物稿有各自读者需要，不套用教程的格式。

## 语言检查后看整篇是否好读

新闻与报道按 [阅读终审](news-reader-review.md) 检查具体断点：人物与事件是否推进、必要概念是否先解释、限定说明是否连续重复、截图能否就近理解、观点是否来自证据。第二道白名单不能替代结构编辑；终审发现结构问题就回写作与第一道，重新执行第二道及事实映射。记录通过不能冒充普通读者实测。

## 内部记录与验收

humanizer-context.json由prepare写，绑定原稿、文风输入和Humanizer固定版本。humanizer-review.json由实际改稿的宿主写：status、source_draft_sha256、body_sha256、prose_sha256（humanize.py hash输出）、writing_style，findings逐项写pattern、before、after、reason（删除冗余可after为空）；没有需要修改的地方写空findings与具体no_change_reason，不编造修改。

checks中的facts_preserved、voice_preserved、reader_fit、naturalness都记录status=pass及本稿具体reason；教程另有tutorial_handholding。事实检查对照claims和原始材料，检查版本、数字、操作路径和成功条件。文风检查至少指出具体保留的表达特征和删去的套路。脚本只检查绑定和保护内容，不替代语义阅读。新run启用humanizer_policy=humanizer-style-preserving-v1；缺少/过期审稿阻止audit。旧稿安装新版后不自动作废，改稿时才按当前任务启用。

正文不加来源编号、引用附录及“AI生成”图注。后台创作来源申报是独立的平台设置，去AI味审稿不代替或隐瞒它。传稿脚本不自动选择创作来源或发表；实际平台要求、当前选值及用户指令如有冲突，在提交前说明并停在草稿，不将保存成功报成发表成功。
