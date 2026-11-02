# 全网找线索，回到原始材料做深度

正文仍不展示文献引用和来源附录；下面所有记录仅内部审稿。广搜不等于全覆盖，有登录、索引和视频可读性限制时说明实际范围。

## 可复用的检索路径

先写3—5个读者问题，再拆成产品/公司/版本的中英文名，加具体任务、输入、产出、评测、失败、限制等词。先找近7天新闻原文；机制与背景案例可更早，必须保留日期和当时版本，不冒充本周新功能。

`python scripts/research.py plan --run RUN --topic TOPIC --alias ENGLISH_NAME`生成计划；脚本不执行搜索。默认网页、GitHub、X、抖音、B站、小红书各两个角度，宿主按真实问题调整计划，避免无意义的固定关键词。可用--platforms选择相关平台，增加知乎/公众号公开页。无搜索工具不伪造执行日志。

| 渠道 | 当前可用路线 | 完成标准 |
| --- | --- | --- |
| 官方网站、论文、GitHub | 宿主全网搜索，阅读原文/原始文件 | 看到参数、输入输出、原始数据或机制，保存定位 |
| X/Twitter | 按[X素材读取](x-materials.md)获取已知推文；关键词用已配置Nitter或宿主搜索，截图/独立长文用浏览器 | 原帖及上下文、作者与时间；代理先做候选，回复只是用户报告 |
| 抖音 | 域名检索定位，再在浏览器读原视频详情/作者说明 | 作者说明可证明其报告过什么；关键视频结论需查看对应片段 |
| B站 | 公开搜索定位，浏览器读详情、合法可读字幕/片段 | 记录BV链接与时间点，简介不等于看完整视频 |
| 小红书、知乎、公众号 | 公开索引或已授权登录浏览器；也可导入用户链接 | 原文及实际日期；登录墙记录login_required |

分别搜索各平台，不把混合查询中出现几个B站结果称作查遍全网。公开索引没有结果不等于平台没有内容。页面403/412、登录墙、验证码分别登记；不能把一次超时推断为所有网页不可用。若用户希望站内覆盖，提前请其自行完成缺失登录，同时继续公开材料调研。已有授权连接器可优先使用；没有时不声称API已接通，不抓私有接口、不代买爬虫服务、不保存密码Cookie。

## 什么算有价值的素材

整理cases.json，技术任务（case_type省略或task）说明谁、何时/版本、任务、输入、过程、产出、限制及迁移。人物或组织用case_type=human_or_organization，字段为actor、goal（目标）、context（处境/约束）、choices（选择）、perspectives（不同声音或缺少的视角）、outcome（结果或当前处境）、limitations、application。两类都保留origin、evidence及正文对应段落；未知写出具体缺口，不虚构受访声音。核心observations来自实际读过的原文/真实片段/代码或输出；摘要和平台AI总结只作lead。

origin区分author_report、vendor_demo、synthetic_demo、own_experiment。第三方自报“30秒”只能作为其声称，不是我们的实测，不宜直接推广成一般效率结论。模拟数据演示不能写成真实客户成功。重要事实需要独立核验，作者报告可作案例但不能独自证明普遍规律。

保存内部sources的read_record={access,artifact_path,artifact_sha256,observed_at}。access允许full_text/author_caption/video_segment/artifact/human_supplied；只看到摘要不能标full_text。artifact是run内实际阅读摘记，含原始链接、作者、日期、观察原句、定位；不需要复制整篇文章。视频记录实际查看时间点和观察，不把自动生成摘要当原音逐字稿。

案例evidence含source_id、locator、observation_quote；原句必须在保存的阅读记录里。own_experiment另填experiment_id，关联真实输出。成稿后案例补body_quote，绑定本稿具体段落。图片直接从这些核验过的案例产出、对照图或步骤采集，不能只截图公告标题。

## 先证据、再长文

材料不足时继续找原始案例/对照/失败，或收窄角度；不先凑5000字，再补“明确目标、检查结果”通用建议。outline每节写具体读者问题、支撑材料与信息增量。读者至少能获得一种新判断、可复用流程、输入/输出样例或可解释的反常现象；不同节不能重复同一结论。

长文至少有两处实质证据展开，其中包含具体案例或在同条件下的比较；这是底线，不是素材数量配额。围绕主线安排：详细拆解最有价值的案例/结果，解释机制，给出可操作迁移，说明失败边界或反证。案例和配图数量由文章实际需要决定。

写完depth-review.json，逐节记录section、question、kind（case/comparison/finding/mechanism/procedure/synthesis）、reader_gain、当前body_quote、supporting_ids。正文所有二级小节必须对应，短稿无标题时用“全文”。长文应用小标题。每个实质单元必须用到真实claims或cases，证据不能放在别节冒充本节支撑。

审稿额外检查counterevidence、transferability、non_generic：给出本稿段落和具体原因。input_hashes绑定body.md、sources.json、claims.json、cases.json、research-plan.json、research-log.json；改稿重新审，不复制上篇“通过”。运行`research.py check --run RUN`。新版init启用editorial_policy=research-depth-v1，audit实际调用这些检查；旧run不自动改变。

## 查询与阅读日志

research-log.json的queries逐条对应计划ID，写platform、observed_at、method、status、observation、source_ids。method为host_search/browser/authorized_api/public_http/user_link；public_http用于已定位的公开原始材料或已配置的公开检索后端，代理结果保留实际通道与范围，不抓浏览器私有接口。status为read/lead_only/no_results/login_required/blocked/skipped。skipped必须说明为何不适合本题或同平台重复，没有执行的不填read。拿到原创材料才能形成案例，不能只靠扩大平台数量制造深度。

自动检查只是文件、溯源及段落对应检查；无法证明内容新颖、推理正确或阅读体验好。Agent仍须实际通读，不把结构检查passed当作“深度已由算法保证”。
