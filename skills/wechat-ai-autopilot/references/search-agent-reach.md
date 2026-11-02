# Agent-Reach 搜索扩展

用户指定的 [Panniantong/Agent-Reach](https://github.com/Panniantong/Agent-Reach) 已嵌入固定版本的 skill 与 references，MIT 原许可保留；CLI 在工作目录的独立搜索环境中安装。固定 commit、工具版本与文件哈希在 `vendor/agent-reach/provenance.json`。这是后端选择与体检层，不把安装成功当作平台连通。

搜索前按题材读 [Agent-Reach](vendor/agent-reach/SKILL.md) 与相关分类 reference。宿主权限、用户范围和本包来源契约优先。无需为它的宽泛触发描述改用已坏后端，也不自动创建监控、更新工具或导入账号。

## 可复用调用

初次安装由用户授权后执行。已装环境先复用，不重建、不全局安装。

```powershell
python -B SKILL_ROOT/scripts/agent_reach_bridge.py setup --workspace WORKSPACE
python -B SKILL_ROOT/scripts/agent_reach_bridge.py doctor --workspace WORKSPACE --output RUN/readings/reach-doctor.json
python -B SKILL_ROOT/scripts/agent_reach_bridge.py search --workspace WORKSPACE --query "选题 原始案例" --limit 5 --output RUN/readings/reach-search.json
python -B SKILL_ROOT/scripts/agent_reach_bridge.py read --workspace WORKSPACE --url "https://公开原文地址" --output RUN/readings/reach-read.json
```

适配器用明确的独立 mcporter 配置，不导入编辑器账号；Windows 直接调用 Node 脚本，避免 `sh` 缺失与 `.cmd` 子进程启动错误。每次查询有实际时间、返回码与原始结果；35秒远端调用、45秒外层超时后转宿主检索，不循环重试。Jina 遇挑战页不能计作读完。Exa 是另一个检索通道，结果与摘要仍是线索；回到官方页面或原作者作品阅读后才写 sources/cases。

X 已知链接继续优先本包 x-tweet-fetcher；关键词查询选实际可用的已授权后端，无账号则公开搜索和原始链接，不制造中文推文截图。B站保留已经实测的 `search_backends.py` 公开检索；视频标题不代表看过视频。Reddit、小红书等需要登录的后端仅在用户要求且提供适当授权后配置。缺少登录态时记录具体缺口并使用公开来源，不让整篇文章停在可选平台上。

## 截图边界

本项目不会自动把检索文本变成真实截图。找到有用材料后，仍按 `real-screenshots.md` 到原页面取得浏览器像素，完整帖子、中文翻译、框选与内容核对各自验收。Jina/Exa 返回 Markdown 不等于现场截图。

联网测试原始记录保存在工作目录的 integration run，分享包只含能力、固定源与适配代码，账号、查询记录、Cookie 和个人浏览器配置不进入 skill。

2026-10-08 Windows实际验证：隔离环境已装Agent-Reach 1.5.0、mcporter 0.14.2；Jina成功读取OpenAI数学公告和AHM完整声明，Exa返回5项相关候选。Exa首次直连失败，Node为ECONNRESET、urllib为403；经用户明确授权使用现有本机代理后，Node增加`--use-env-proxy`并只在搜索子进程设HTTP(S)_PROXY，查询成功。不关闭TLS验证，不修改系统代理。其他用户有相同故障时先诊断；需要代理由用户明确授权后用`configure --proxy http://可信代理地址`配置，不能照抄本机端口。
