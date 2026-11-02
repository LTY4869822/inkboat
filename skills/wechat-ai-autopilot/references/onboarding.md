# 首次使用与能力分流

当前实际验证的周行关键文件哈希与运行时版本在assets/tested-dependencies.json。不同哈希不等于错误，表示需要再做本地渲染/保存验证，不能沿用旧兼容性结论。用户指定原项目卡兹克风格时优先安装真实khazix-writer；若无法安装，明确说明简版差异并询问是否接受，不把简版当同款。

首次使用先执行 `onboard.py doctor --workspace WORKSPACE`，复用已发现的宿主运行时。Agent将当前实际暴露的工具名及观察时间存入工作目录的host-capabilities.json，再用`--capabilities 文件 --out 检查结果.json`补检查。文件只列工具名，不存认证信息。present/declared_available不是调用成功；浏览器文件存在不等于登录有效。

按用户目标给一条最短可行路径：

| 当前条件 | 可以继续 | 要补什么 |
| --- | --- | --- |
| 没有周行 | 搜索、写作、改稿 | 用宿主skill-installer安装周行，成功后才生成本项目排版，不静默替换 |
| 没有公众号连接 | 文章、十套排版、工坊保存 | 用户要求入草稿时再连接；不要为了本地预览要求AppSecret |
| 没有X账号或Nitter | 公开搜索、已知公开帖读取、公司/项目/演示证据 | 原生中文X截图不保证可得；具体缺图另报告，不阻断其他内容 |
| 有内置生图 | 按正文需要实际调用 | 无须索要外部Key；工具未披露版本就不编模型名称 |
| 没有内置生图 | 询问是否配置；可选择不使用 | 配置时问厂商/模型，最小实际生成成功才标verified |
| 没有浏览器运行时 | 研究与写作 | 复用宿主Node/Playwright/pngjs/浏览器，或在工作目录隔离安装 |

不重复询问已经明确的选题、篇幅、字体、文风与配图选择。首次仅写入非敏感偏好：`onboard.py setup --workspace WORKSPACE`启用新版读者价值验收；`--output-mode local`适用于只预览，`draft_after_layout_selection`适用于确认后入草稿。保存偏好不授权上传。setup合并已有profile，不覆盖个人风格库、账号或文章。

运行时配置使用`--runtime runtime-input.json`，只接收已存在的node_executable、playwright_module_path、browser_executable本地路径；存入工作目录.wechat-ai/runtime.json。浏览器脚本自动读取，无需反复在命令里手写宿主路径。安装第三方代码仍遵守宿主权限；先检查再安装。

没有现成Node模块时，将assets/browser-runtime/package.json复制到工作目录的隔离运行时目录，在该目录执行`npm install --ignore-scripts --no-audit --no-fund`；包版本固定为当前实际使用的Playwright 1.62.1/pngjs 7.0.0。安装后记录模块路径，实际启动浏览器验证。缺浏览器可通过Playwright安装Chromium，记录真实可执行文件路径；不要假定每台机器都有Chrome。网络或版本不可用时明确报告，不自动换陌生镜像。这份配方没有宣称在所有宿主实测。

公众号两条通道见fast-publishing.md。第一次独立扫码与账号标定不可省略；后续核对实际登录账号。API只读doctor检查成功也不证明draft/add权限。任何渠道都须采用用户确认的保存版，止于草稿。

个人偏好只在工作目录：字体、封面方向、截图方式、文章长度、已学文风。发行默认用通用杂志方向与按场景截图；本项目已有电影感封面、楷体等选择继续由本地profile承接。当前请求优先于保存偏好，保存偏好优先于发行默认。
