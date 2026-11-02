# 安装与环境

## 先分清三个部分

1. **Agent 宿主**：负责读 skill、调用模型、搜索、浏览器和生图。墨舟不会自己提供这些模型服务。
2. **Skill 文件夹**：`skills/wechat-ai-autopilot`，需要完整复制到宿主可发现的位置。
3. **文章工作目录**：生成稿件、个人配置、学习库和登录资料。它与你下载的公共代码包分开，不应上传 GitHub。

建议先在一个新的空工作目录里试用，再连接公众号。Codex 的安装示例见[首页](../README.md#快速开始)。其他宿主按其实际 skill 发现机制安装；目录约定不等于全链路兼容认证。

## 环境清单

| 项目 | 何时需要 | 说明 |
| --- | --- | --- |
| Python 3.10+ | 脚本编排、状态与质量检查 | 核心仅标准库 |
| 周行 `zhouxing-paiban-wx` | 十套真实排版与工坊 | 必需，单独安装；适配器不重写原目录 |
| 浏览器或宿主浏览器工具 | 真实截图、按钮导出、草稿与阅读验收 | 文件上传和 HTML 剪贴板能力分别检查 |
| Node 20+、Playwright、pngjs | 独立浏览器与像素动效验收 | 优先复用宿主提供的运行时 |
| Chrome/Chromium | 独立浏览器链路 | 可使用已安装浏览器，避免重复下载 |
| Pillow | 截图框选与部分图像核验 | 按需要安装 |
| 生图能力 | 内容需要概念图或封面时 | 优先宿主内置工具；否则询问用户配置 |

本项目保存的测试依赖版本见 [`tested-dependencies.json`](../skills/wechat-ai-autopilot/assets/tested-dependencies.json)。这是已观察版本，不是对上游任意新版本的兼容保证。渲染器模板改变时，适配器可能明确拒绝生成；应检查变化而不是绕过检查。

## 第一次诊断

在仓库根目录运行：

```bash
python skills/wechat-ai-autopilot/scripts/onboard.py doctor --workspace .
```

安装到宿主目录以后，用实际安装位置替换命令中的 `skills/wechat-ai-autopilot`。`--workspace` 指文章工作目录。把输出交给 Agent 处理即可，不要求普通作者手工维护 JSON。

需要启用当前工作目录的新版检查和偏好时，由 Agent 执行：

```bash
python skills/wechat-ai-autopilot/scripts/onboard.py setup --workspace . --output-mode local
```

`setup` 合并配置，不授予上传权限。已有账号与作品不应通过重建目录来“修复”。

## 浏览器依赖

优先询问宿主是否已提供 Node、Playwright、pngjs 与浏览器路径。确实缺失时，可在独立运行时目录使用包内配方：

```bash
cd skills/wechat-ai-autopilot/assets/browser-runtime
npm install
```

这会从 npm 安装配方中的固定版本；不要把 `node_modules` 打进公共仓库。安装好依赖不代表浏览器已下载或平台已登录。若没有可用浏览器，可按 Playwright 自身说明安装 Chromium；有 Chrome 时优先配置它。

可配置工作目录下 `.wechat-ai/runtime.json`：

```json
{
  "node_executable": "/actual/path/to/node",
  "playwright_module_path": "/actual/runtime/node_modules/playwright",
  "browser_executable": "/actual/path/to/chrome"
}
```

这里是路径结构示意，必须替换为本机真实绝对路径。环境变量 `PLAYWRIGHT_MODULE_PATH`、`WECHAT_BROWSER_EXECUTABLE` 可覆盖对应字段。配置不含密钥。完整分支见[内部环境说明](../skills/wechat-ai-autopilot/references/onboarding.md)。

## 可选依赖与降级

- AIhot 已有匿名客户端；网络失败要区分连接拒绝、HTTP 服务状态与接口变化，再转真实公开检索。
- 安装 `khazix-writer` 或标题 skill 时优先读取实际版本；缺失时明确用本包简版，不冒称已经调用。
- Humanizer、独立 Lieflat、Writing DNA 指令及指定素材读取资源已经内嵌，保留许可；Agent-Reach 的实际 CLI 与平台依赖仍按需要在独立环境安装。
- 不要求每个安装者都配置 Nitter 或 X 账号。先用可用公开入口，有缺口再解释需要什么授权。

## 升级与迁移

预发布 ZIP 与 `SHA256SUMS` 可从 [GitHub Releases](https://github.com/LTY4869822/inkboat/releases/tag/v0.9.0-beta.3) 下载。完整解压后，保留顶层 `wechat-ai-autopilot` 文件夹，按前文复制到宿主 skill 目录。可用 `sha256sum` 或 PowerShell `Get-FileHash -Algorithm SHA256` 对照校验；源码快照与预制 skill ZIP 是两种不同的下载。

备份旧 skill → 核对新版本与文件哈希 → 替换代码资源 → 在新会话刷新发现 → 做环境检查和一篇本地预览。工作目录里的 `.wechat-ai`、文章、个人风格库与浏览器资料不属于代码更新包。

不能将开发者的登录目录或账号配置复制给其他用户。独立教程版也不在本仓库中。
