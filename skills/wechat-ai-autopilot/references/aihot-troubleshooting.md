# AIhot：先辨识失败层次，再决定下一步

官方匿名v1接口无需Key、Authorization或Cookie。本机安装版aihot v1.1.2已使用这个接口，故障不是缺AIhot密钥或安装过旧。JevRouter所需OPENROUTER_API_KEY属于另一项服务，不要混淆。

## 2026-10-04实测根因

同机、同脚本、同URL、同UA、无密钥：受限exec环境返回ConnectionRefusedError/10061，无HTTP响应；在主机审核准许的网络环境里，返回HTTP200、schemaVersion=1、10条热点。分别保存sandbox-probe.json和permitted-network-probe.json。13:50旧运行曾取得数据，后续运行只记录笼统connection failed，丢失错误类型和执行环境；相同网络层失败重试两个端点也无益。

结论限定本机这次已对比的环境：**主机网络权限限制了请求**，不是AIhot服务器故障。别的用户看到10061时还可能是代理/网络不可达，不能未经对比就下同一结论。

## 正确宿主调用

1. doctor列出网络检查；读取本机aihot说明。网络已证实受限且宿主支持审批时，直接通过其获准网络执行`workflow.py discover --run RUN`，不先在已知失败环境重复试三次。
2. 不清楚环境时运行一次`workflow.py diagnose-aihot --run RUN`。结果写aihot-diagnostic.json，含状态、errno、HTTP状态、尝试次数和下一步。脚本不自动扩大权限，宿主负责正常审批；不改系统代理、不关闭TLS或沙箱保护。
3. transport_connection_refused、transport_dns_failure、transport_tls_failure立即停止同域名重复请求；先检查宿主网络或获准环境。单个连接拒绝只提示check-host-approved-network，不假称服务端坏了。获准重跑成功才记录confirmed root cause。
4. 暂时超时/5xx最多三次，566/567最多两次；429遵循Retry-After，较长等待交回宿主调度，不阻塞循环。错误保留requestId/help（若服务端提供），不伪造Mozilla UA、不轮换身份、不反复刷API。
5. HTTP200才解析v1对象，HTML/异常结构报告invalid_response；304仅复用相同完整URL缓存，保留原fetched_at。完整返回的attribution和原始链接保存在discovery，热点只是线索，仍读原文。
6. 获准网络也失败时如实记录具体状态，转宿主全网/平台搜索，来源标明。网络失败不能记“AIhot成功”；缓存过期不能装成当下新热点。无法搜索时指出缺项。

discover兼容原errors列表，同时增加requests与error_details；请求记录包含HTTP200/304、缓存命中和尝试次数。只见错误时不生成假候选。该修复消除了本次可重现原因与盲目重试，不能保证第三方服务永不超时。

当前workspace可在.wechat-ai/aihot-transport.json保留两种执行环境的实际对比证据和execution_hint，doctor读出供宿主复用；它不授予权限、不设置代理，也不进分享ZIP。换机或环境改变仍重新诊断。缓存写入的文件系统错误单独报告local_filesystem_error，不误称服务网络失败，也不重复请求。
