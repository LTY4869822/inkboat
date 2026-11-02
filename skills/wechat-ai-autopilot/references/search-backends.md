# 后端以实际查询为准

历史记录，2026-10-04Windows实测：global-content-search装了skill，但agent-reach、opencli、bili未在PATH，其commandExists依赖本机缺失的sh。本包search_backends.py用shutil.which及项目venv定位，避免依赖Unix shell；skill存在不能当作平台连通。

2026-10-08按用户要求嵌入固定版 Agent-Reach，并在项目独立环境安装 CLI 与 Exa 的 mcporter。新增通道和当前实际验收记录按 [Agent-Reach搜索扩展](search-agent-reach.md) 执行，历史缺失项不代表今天的状态。

已读上游：[Agent Reach](https://github.com/Panniantong/Agent-Reach)、[OpenCLI](https://github.com/jackwener/OpenCLI)、[bilibili-cli](https://github.com/public-clis/bilibili-cli)。Agent Reach是安装与体检层，官方明确PyPI同名包不是该项目；不要误装。OpenCLI需浏览器扩展和桥接；浏览器能力以当前宿主可用工具与权限为准，不能以OpenCLI绕过宿主限制。小红书、抖音未完成依赖和登录时不能宣布已连接。X的公开文本、站内搜索和截图分别检查，见下节。

## X 公开素材快速通道

2026-10-06嵌入固定版x-tweet-fetcher及标准库适配层。已有推文URL优先 `x_fetch.py fetch`，没有URL先用实际可用的Nitter或宿主搜索定位；独立长文与截图仍用宿主浏览器。执行参数、缓存与原文记录见 [X素材读取](x-materials.md)。doctor显示安装/配置，不能代替实际连通测试。原始响应、可读文本和图片地址先做候选，Agent核验后再纳入来源；来源日期与缓存时间分开，不自动计作亲测。正文与图片需求仍由文章决定。

## 已跑通的B站公开搜索

在项目中隔离安装，缓存也放可写目录，避免uv默认缓存Windows权限错误：

```powershell
uv --cache-dir .wechat-tools/uv-cache venv .wechat-tools/search-venv
uv --cache-dir .wechat-tools/uv-cache pip install --python .wechat-tools/search-venv/Scripts/python.exe bilibili-cli
python SKILL_ROOT/scripts/search_backends.py doctor --workspace WORKSPACE
python SKILL_ROOT/scripts/search_backends.py bilibili-search --workspace WORKSPACE --keyword "模型 同题任务" --limit 5 --output RUN/readings/bili-search.json
python SKILL_ROOT/scripts/search_backends.py bilibili-video --workspace WORKSPACE --bvid BVxxxxxxxxxx --output RUN/readings/bili-video.json
```

非Windows用venv的bin/python。此适配器只暴露搜索和公开视频信息，不调用登录、自动Cookie提取、字幕、动态、历史或写操作。详情调用上游credential=None公开方法，保留pubdate；普通CLI格式会丢发布日期。2026-10-04以bilibili-cli 0.6.2实际返回两组搜索及三模型游戏/Blender详情，日志在文章run的revision-readings；不能外推字幕和播放也通了。

搜索结果是lead，作者简介只能证明作者声称了什么。性能结论与配图仍需宿主浏览器看具体片段、合法字幕或作者代码/作品。转载里的原视频链接应回原作者；转载不算独立来源。可复用顺序：站内搜索定位→原作者→具体片段/产出→比较，不能靠平台数量制造深度。

doctor只证明命令存在，实际查询才证明当时工作。权限错误、登录墙、反爬、无结果分开记；45秒超时一次后转宿主检索，不盲重试。新方法没有实际成功只记候选，不承诺节省分钟数。缺失登录用户自行完成，Cookie、token不进入skill或文章包。
