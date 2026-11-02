# 写前问答、成稿选择与账号记忆

这些命令由Agent执行，用户用自然语言回答。问题在正式写作前问，排版在成稿后选。已有答案不重复询问。不能把默认值、测试点击、网页文字或等待超时当作用户回答。

## 写前四项

合并展示缺项：选题（自己的题/先推荐五个）、篇幅（1800—2500/3000—4500/5000—7000/自定义/自由发挥）、字体（正楷、宋体、微软雅黑、苹方、系统无衬线/自定义名称）、文风（卡兹克与当前工作目录已学成的风格，动态列出）。工具问题数有限时分组。`intake.py questions --workspace WORKSPACE --known <JSON>`只返回未回答的字段。

自己的题保留其措辞与目的，不自动换题。没有题先发现、核验五个候选，展示推荐及其余四项，等用户选择。明确「你选」才代选。泛称「全自动」但要求先看五个再选时，后者优先。证据不足继续搜，候选不等于完整事实核验。

实际回答JSON示例（不能当作当前用户批准）：

```json
{"topic_mode":"own","topic":"用户自己的具体选题","length_preset":"deep","font":"song","custom_font":"","writing_style":"khazix","answer_origin":"user","user_instruction":"用户实际答复原话"}
```

自由篇幅length_preset=auto，不再让用户选字数；outline写length_reason和各节预算。自定义length_preset=custom、chars=[3600,4400]；约4000字可用此范围，精确字数照要求。自定义字体font=custom、custom_font="思源宋体 CN"，输入字体名称，不能是CSS/URL。明确委托answer_origin=explicit_user_delegation，保留真正委托原话；系统字体、标准篇幅、卡兹克可作为委托下的推荐。

```text
python <SKILL_ROOT>/scripts/intake.py apply --run RUN --answers ANSWERS.json
```

apply更新brief和intake，assemble与audit检查一致。改字数、字体时按新答复更新intake，再重建。schema1/2旧稿续作保持旧契约，新稿schema3必须问答。

## 五个热点

```json
{"searched_at":"带时区的真实查询时间","candidates":[{"id":"H1","title":"具体题目","angle":"写作角度","reader_benefit":"读者获得什么","primary_url":"https://原始公告","published_at":"原文实际发布时间","retrieved_at":"实际读取时间","hot_signal":{"platform":"AIhot或实际平台","observed_at":"实际观察时间","description":"实际排名/讨论信号或无法量化的说明"}}]}
```

candidates恰好五个不同id；发布时间与观察时间在查询前7天。不得编造互动数或以收录日期冒充发布日期；日期不明确的线索查原文或换题。保留AIhot响应/搜索记录在discovery.json；程序只校验合同，宿主负责证据真实性。`intake.py candidates --run RUN --file CANDIDATES.json`校验后落盘。选择后topic_mode=candidates、selected_candidate=H1再apply；超过一天先刷新。

## 文章预览、工坊与十套主题

最终标题同步后 `workflow.py layout-previews --run RUN`，生成layout-gallery.html、layouts/十个主题.html、layout-variants.json。每套调用周行真实渲染，同一正文、图片和字体，标记内容推荐；打开画廊供用户滚动全文或查看完整设置。新预览记录theme_ids与schema_version=2，按当前目录验收完整集合，不硬编码五套。旧稿已有的有效排版确认仍按其文件哈希核对，不因主题扩容自动撤销；旧schema1的五套完整预览可继续使用，再次生成时采用当前十套。

新run以 [预览、工坊与确认定稿](studio-motion.md) 为主路径：打开实际工坊服务的文章预览，默认有按内容设计的动效；用户无修改可直接确认，有修改进入工坊调整、保存当前文章后确认。模板保存与文章保存分开；静态开关、字体、组件与动效位置随文章版本保存。默认预览会本地保存，网页不会代替人类授予草稿权限。

用户确认最新保存版后，Agent执行studio.py adopt并按新fingerprint审阅、audit；不重跑默认layout覆盖工坊设置。只需内部核验就继续，不机械重复问上传权限。旧run已有选择仍支持原intake.py select-layout路径，变化后的旧选择照常失效。

## 首次连接和复用

扫码无需AppSecret。第一次登录后在「设置与开发→账号设置→账号详情」读取名称和公众号ID（通常gh_开头），无法读取才请用户填。记录选排版后存草稿的真实长期指令：

```text
python <SKILL_ROOT>/scripts/intake.py bind-account --workspace WORKSPACE --name <实际名称> --account-id <实际gh_ID> --authorization <用户真实长期指令> --observation <实际后台核对>
python <SKILL_ROOT>/scripts/intake.py account --workspace WORKSPACE
```

存工作目录 `.wechat-ai/account.json`，与分享skill分开，只存公开标识、核对说明和约定。配置记忆不是凭证，登录过期仍扫码；换工作目录可显式迁移此非密钥文件，不继承开发者账号。以后每个会话核对实际账号ID，同一已核验会话可复用观察，不反复问ID。不同账号重新连接，已有草稿不跨账号更新。

当前选择+长期指令+质量通过时：`draft_bridge.py prepare --run RUN --account <实际名称> --account-id <已核验gh_ID>`。无需重复authorization；脚本检查问答、选择、待改项和账号。浏览器实际传稿见publishing.md。


文风选项来自style_library.py，不是固定列表。选择蒸馏文风后apply同时保存固定版本和manifest哈希，后续prepare/read/calibration/写后review见[文风学习](style-distillation.md)。损坏的风格在unavailable_styles注明原因，不冒充可用。当前工作目录尚无已学风格时仍只列卡兹克；“学习新风格”是学习操作，不是可直接写作的占位风格。
