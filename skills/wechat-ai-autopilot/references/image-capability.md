# 正文生图能力与配置分支

能力检查不决定张数或画风。正文按 [adaptive-illustrations.md](adaptive-illustrations.md) 逐段选择用途、风格、位置和数量，封面偏好不自动继承；教程实际步骤仍按tutorial-screenshots.md配真实画面，不以AI图填补缺截图。

常规正文应同时有有用的真实截图与AI插图。封面负责吸引，正文生图负责解释抽象关系、过程、空间或视觉隐喻；不能用封面抵扣正文，不重画证据或伪造产品界面。先读全文逐节规划，再决定图数和位置。每张图都有删除后损失；不能把“至少各一张”做成永远只有各一张的固定配额，也不每节强行加图。

## 宿主能力决定下一步

检查当前会话实际暴露的工具/已连接服务，不能根据Agent名称、skill已安装、环境变量存在或旧运行推断能力。

1. **有内置生图工具：** 使用宿主内置工具实际生成所需正文插图，不额外向用户索要API Key。记录实际工具名；工具未暴露底层版本时actual_model=null，不把用户口头的image2.5当成已核验模型版本。生成失败先做有限针对性修复，仍失败记录image_pending，不自动改用外部付费服务。
2. **没有内置工具：** 一次简洁询问“当前Agent没有内置生图，是否配置生图模型？”可选“配置”或“本次及后续不使用AI插图”。使用用户已保存且仍有效的选择，不重复询问；换宿主重新检查工具，出现内置工具时按当前指令处理。
3. **选择配置：** 询问具体厂商和模型，支持自填；不替用户选择陌生代理、默认订阅或将文本模型当成生图模型。若用户只给模型名，确认其官方/用户指定渠道和认证方式。读该厂商当前官方接入文档，优先现有正规connector或官方SDK/CLI；安装到项目隔离环境，按照文档配置endpoint、model和环境变量名。密钥由用户在本机安全输入，不在聊天、日志、profile、研究材料或分享包保存。已有连接先检查，不重装。做一次最小生成验证，实际成功且图片可读才标verified；记录费用信息和失败原因，不凭“配置文件已写好”宣布已连通。缺少账户、用户尚未输入凭证或权限拒绝时保存进度并明确缺项。
4. **选择不配置：** 保存用户原话与选择，正常使用真实截图完成文章，不自动创建占位图。用户提供的现成图片可使用，但不能登记为本次模型生成。以后用户改变选择再配置。

本包Python只编排和校验，不能代宿主接通任意厂商。配置步骤是需要宿主实际执行的条件分支，未经调用验证的厂商不得列为“已验证接入”。平台登录、收费和权限按宿主及用户授权办理。

仅将非敏感偏好（configured/declined、provider、model、工具名、环境变量**名称**）保存工作目录.wechat-ai/profile.json；不保存变量值。每篇images-plan.json记录该次实际状态，旧成功不等于当前连接仍可用。

## 文件与检查

新run启用visual_policy={mode:"mixed",min_screenshots:1,selection:"content-driven-v2",body_ai:"when_available"}。旧run不追溯撤销确认，用户要求补图时迁移并重建预览。

images-plan.json增加generation，例如宿主内置路径：

```json
{
  "builtin_available": true,
  "capability_evidence": "当前会话实际暴露image_gen__imagegen工具",
  "mode": "builtin",
  "tool": "image_gen__imagegen"
}
```

无内置时builtin_available=false。未答复mode=pending；用户拒绝mode=declined并有user_decision原话；已配置mode=configured并含user_decision、provider、model、tool、setup_status=verified。检查会拦截pending与未经验证的连接，不把等待时间当答复。

每张本次生成的正文图保存实际调用记录到run内JSON：status=success、tool、generated_at、output_sha256；外部路径另有provider/model。`register-image --backend native|configured --provenance 生成记录.json`读入generation_record。外部配置图另传`--actual-model 用户所选实际模型`。不复制工具密钥或响应中的认证信息。生成记录与图片字节相绑，仍需实际看图；它是执行留痕，不是独立审计证明。

确实不适合生图的稿件，在generation.no_gain_exception写status=editor-reviewed、具体reason及anchors（逐节coverage里的真实正文锚点）。说明为什么概念、过程或空间解释没有增益；“已有截图”“时间不够”“没想到”不算理由。有generated规划却缺图、只有封面或图片未插入时不能通过。用户当前另有明确配图指示时优先调整本稿约定，不用默认规则强迫生图。

插入位置通常在第一次解释关系之后、下一段应用之前；不远离关联段，也不打断同题截图对照。按实际排版宽度检查，概念性质与来源留内部；正文不添加AI生成图注。
