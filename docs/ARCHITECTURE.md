# 架构与目录

```text
inkboat/
├── README.md                 项目入口
├── docs/                     用户与开发文档、公开效果图
├── examples/demo-article.md  原创演示稿
├── scripts/                  仓库演示与公开包检查
└── skills/wechat-ai-autopilot/
    ├── SKILL.md              Agent 发现与工作入口
    ├── agents/openai.yaml    宿主显示信息
    ├── assets/               工坊、主题、示例配置与依赖配方
    ├── references/           按任务读取的具体规则
    │   └── vendor/           已注明许可的第三方资源
    ├── scripts/              内容状态、验证、预览与草稿传输
    └── tests/                回归测试
```

## 职责分工

| 层 | 负责 | 不负责 |
| --- | --- | --- |
| 宿主 Agent | 阅读、检索、写作、审稿、浏览器与生图 | 不得把工具不存在说成成功 |
| Python 编排 | run、哈希、问答、来源映射、质量与打包 | 不自动推断“已阅读全文”或文章有价值 |
| 周行适配器 | 调用实际渲染器，合并五套原创主题，保持黑色正文 | 不分发周行源码，不覆写宿主其他主题 |
| 本地文章工坊 | 主题、排版、文字、动效、保存与版本 | 不因点保存就获取发稿授权 |
| 草稿桥 | 绑定确认稿、素材映射、传输与重开验证 | 不把提交成功当正式发表 |

## 主要入口

| 脚本 | 用途 |
| --- | --- |
| `onboard.py` | 能力诊断与工作目录设置 |
| `intake.py` | 写前选择、候选与账号标识 |
| `workflow.py` | 初始化、成稿、真实排版、检查、状态 |
| `research.py` / `reader_value.py` | 研究与题材价值的记录契约 |
| `humanize.py` | 写后审稿上下文与有效性检查 |
| `learning.py` / `style_library.py` | 内容学习批次及个人风格库 |
| `studio.py` / `studio_state.py` | 工坊服务、保存版本与采用 |
| `draft_bridge.py` | 成稿锁定、图片映射和传输读回核对 |
| `fast_publish.py` / `browser_draft.cjs` | 两种草稿通道 |
| `motion_check.cjs` | 实际渲染像素回播验收 |
| `release_check.py` / `package_skill.py` | 可分发文件集合与 ZIP |

每个入口以 `--help` 的实际输出为准。`SKILL_ROOT` 始终指完整 skill 目录，不是仓库根目录。

## 每篇文章的产物

工作目录下的独立 run 通常有 `body.md`、`article.md`、`article.html`、`preview.html`、`sources.json`、`claims.json`、`images.json`、`images-plan.json`、`quality.json` 及 `studio/`。

研究和学习任务按需增加案例、原文阅读、文风及双审记录；草稿路径增加传输 manifest、图片映射、观察及回执。它们是实际工作资料，不进入公共代码包。

## 状态为什么绑定哈希

内容、配图、偏好或当前保存版变化时，旧审阅不能继续冒充新稿的审阅。保存版本与采用是两步：系统可以为预览自动存一版，但只有用户确认才可采用用于上传。

独立设计模板存配色、字体与组件，不存这一篇的引文和私人图片。工坊的未保存修改会阻止上传旧版。

## 扩展边界

新平台接入要分别证明读取、搜索、截图与登录能力；新文风要有样本和原创样稿；新主题应走周行真实校验；新动效需检查静态可读与微信实际回播。不要用一个“成功”字段代替这些不同的验收。
