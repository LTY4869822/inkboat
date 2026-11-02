# 参与墨舟

欢迎真实复现、内容决策经验、可验证的平台适配和易懂的文档改进。先说明用户的问题与结果，再讨论实现。

## 报告问题

提供版本、系统、Agent 宿主、使用的能力、发生阶段、期望行为、实际行为与最短复现。截图遮住账号资料和会话链接；不要提交 Cookie、AppSecret、API Key、扫码二维码或整个工作目录。

网络失败请区分接口返回与本机网络，记录实际时间。不要根据一次失败推断平台永久不可用。若是内容质量问题，请指出具体段落、读者想知道什么、缺少什么材料。

## 修改代码

1. Fork 后开一个明确范围的分支。
2. 保持 `skills/wechat-ai-autopilot` 可独立复制；宿主与工作目录路径不能硬编码到开发者机器。
3. 不把他人登录状态、私有语料、第三方截图混进包。保留第三方许可与版本记录。
4. 根据变更运行相关回归；涉及传输、状态、哈希或文件边界时应覆盖失败与恢复。
5. 更新文档与变更记录，说明真实验证范围。模拟测试不冒充真实平台成功。

```bash
python -m pip install Pillow PyYAML
python -m unittest discover -s skills/wechat-ai-autopilot/tests -p "test_*.py"
node skills/wechat-ai-autopilot/tests/test_browser_start.cjs
node skills/wechat-ai-autopilot/tests/test_runtime_resolution.cjs
python scripts/check_public.py
python skills/wechat-ai-autopilot/scripts/release_check.py --root skills/wechat-ai-autopilot
```

十套真实渲染另需安装周行依赖；浏览器与微信设备测试不由上述单元测试替代。不要为“通过”而删除失败记录、关闭用户动效或放宽样式验证。

## 文风、主题与动效贡献

- 文风：提交规则来源、样本使用依据和原创样稿，不上传未授权全文或冒充作者。
- 主题：提供适用题材、颜色角色、手机可读性、实际周行渲染与复制导出证据。
- 动效：保证静态版本保留必要信息；本地可动与微信兼容分别验收，不遮住正文。
- 内容方法：说明它解决哪类读者问题、何时不适用。不要为单篇失败累积无限固定模板。

## PR 说明

写清触发场景、改变后的行为、测试与未验证范围。不要包含会话密钥、账号后台 URL 或与问题无关的个人资料。贡献按本仓库 MIT 条款提供，第三方部分按其原许可保留。
