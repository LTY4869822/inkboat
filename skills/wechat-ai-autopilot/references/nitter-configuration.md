# Nitter 实例配置与验收

仅在用户要求连接Nitter或修复此通道时使用；正常写文章无需部署新服务。

已有实例时运行：

```text
python SKILL_ROOT/scripts/nitter_setup.py --workspace WORKSPACE --nitter https://USER_INSTANCE --query AI --user OpenAI
python SKILL_ROOT/scripts/x_fetch.py search --workspace WORKSPACE --run RUN --query "AI coding" --limit 5
python SKILL_ROOT/scripts/x_fetch.py timeline --workspace WORKSPACE --run RUN --user OpenAI --limit 5
```

最多两个用户指定实例。验证对每个实例实际请求关键词搜索和from:用户名时间线，单请求8秒、无重试、最多2个并发；页面需包含推文ID、作者和正文。首页可访问、HTTP 200、验证机器人页面、空壳或空结果均不能启用。失败不覆盖已有配置，诊断写 `.wechat-tools/x-nitter-last-check.json`；成功才保存 `.wechat-tools/x-nitter.json`。评论不因搜索通过而自动标记已测试，后续实际任务需要时再验证。

`--nitter` > XTF_NITTER/NITTER_URL > 当前工作目录配置；doctor带--workspace读取同一配置。迁移用户需重新配置自己的实例，不把个人地址或账号会话打包到公共skill。服务失效时正常查询仍有25秒截止，改走宿主检索，不连续测试整个实例列表。

## 用户要求自建时

先核实 [官方README](https://github.com/zedeus/nitter)、[Compose](https://github.com/zedeus/nitter/blob/master/compose.yml) 和 [会话要求](https://github.com/zedeus/nitter/wiki/Creating-session-tokens)。当前官方方案需要容器运行时或Nim及系统库、Redis/Valkey、实际X账号会话sessions.jsonl；缺这些时不能声称已部署。

按本机实际条件选择Docker或用户已有服务器。容器只绑定本机127.0.0.1端口，Redis不对公网开放；配置、随机HMAC与会话置于工作目录专用私有文件夹，现有文件不覆盖。缺少运行时或登录会话时说明具体缺项，让用户在本机完成必要登录或填私有文件；不索要聊天中的密码、auth_token、ct0，也不擅自提取已有浏览器Cookie。实际启动成功后仍执行上面的正文级验收，再启用搜索。

## 2026-10-06 本机实际诊断

官方列表8个HTTPS实例均未通过本机from:OpenAI搜索：TLS连接异常、403、404、451、503，以及一例HTTP 200 Anubis验证页。这个结果只证明本机当时无法用公开HTTP读取，不能外推为所有实例永久失效。没有把任何失败地址写为活动配置。初次检查本机无Docker/Podman/Nim，WSL提示尚未安装；自行填localhost不会产生一个运行的Nitter服务。

随后实际安装官方Docker Desktop及WSL，Nitter加载1个有效格式的用户会话，缓存healthy、首页200，但搜索和时间线仍未通过正文验收。先发现容器不能解析X域名；用户明确授权后，仅给Nitter配置现有HTTP代理。代理可读取X公开robots.txt，但Nitter SearchTimeline返回Cloudflare 400错误页。本机部署和会话文件就绪不代表X接受该客户端，也不能据此判断用户Cookie一定失效；本次没有启用本机搜索地址。

实际排障顺序：先查引擎及缓存，再查会话是否载入，最后区分容器DNS/连接错误与上游HTTP拒绝。读取日志前过滤Cookie、ct0、auth_token、Authorization和会话字段；不要原样输出日志或私有配置。容器访问宿主已有代理使用host.docker.internal，端口可连接仍需做真实请求验收。带登录会话的请求经过代理前，须确认用户信任且授权该代理路径；只修改对应服务，不擅自改变系统代理。

本机已实践的安装修复：在线WSL安装发生Windows安全频道错误，改用核对微软发布SHA256及有效签名的官方MSI离线安装成功；旧Agent进程找不到docker-credential-desktop，仅给启动命令进程补Docker的resources/bin路径后拉取成功；实际确认Valkey镜像账号后指定该账号，缓存健康启动。不关闭TLS校验，不把本机安装器或个人会话纳入分享包。

遇到上游拒绝后保留失败状态和脱敏诊断，不盲目重试、增加账号或修改请求来绕过访问限制。当前文章任务应继续用已有公开链接读取通道、宿主浏览器或用户导入的材料；不要让不可用Nitter阻塞整篇文章。
