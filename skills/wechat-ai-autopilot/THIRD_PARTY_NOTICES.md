# 第三方来源与许可

本包原创编排、适配与主题资源采用根目录MIT许可。以下嵌入资源仍保留作者原有许可证和声明，不改写其版权。

| 资源 | 原项目 | 固定信息/许可文件 |
| --- | --- | --- |
| Humanizer | [blader/humanizer](https://github.com/blader/humanizer) | references/vendor/humanizer/provenance.json记录commit与文件哈希；LICENSE为MIT |
| Agent-Reach | [Panniantong/Agent-Reach](https://github.com/Panniantong/Agent-Reach) | references/vendor/agent-reach/provenance.json固定commit与文件哈希，LICENSE为MIT；CLI/依赖在工作目录隔离安装，不嵌入账号配置 |
| Lieflat Less AI Tone | [larashero3-dotcom/lieflat-less-ai-tone](https://github.com/larashero3-dotcom/lieflat-less-ai-tone) | references/vendor/lieflat-less-ai-tone/provenance.json固定独立项目版本，LICENSE为MIT |
| Writing DNA | [larashero3-dotcom/writing-dna-skill](https://github.com/larashero3-dotcom/writing-dna-skill) | 本发行包manifest锁定实际嵌入文件哈希；references/vendor/writing-dna-skill/LICENSE为MIT |
| X Tweet Fetcher | [ythx-101/x-tweet-fetcher](https://github.com/ythx-101/x-tweet-fetcher) | references/vendor/x-tweet-fetcher/provenance.json及VERSION；LICENSE为MIT |

周行、AIhot安装版、khazix-writer及标题skill由宿主单独安装，本包不分发它们的源码。周行适配器调用已安装实现；缺失不能宣称使用原项目。Node浏览器依赖只提供固定版本安装配方，不随发行包捆绑node_modules，依赖许可由安装包保留。宿主运行时路径保存在用户工作目录，不写进发行包。

账号内容、研究原文、个人风格语料和第三方截图不进入本skill包。文章素材的使用依据在每篇内部记录，不因本项目MIT许可而改变其原许可。
