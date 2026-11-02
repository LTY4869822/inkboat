# 文风写作后执行两道自然表达审稿

默认新稿顺序为所选文风写作 → [Humanizer](vendor/humanizer/SKILL.md) → [lieflat-less-ai-tone](vendor/lieflat-less-ai-tone/SKILL.md) → 事实与文风复核。第二道使用用户指定的独立项目，不以 writing-dna 内的旧副本代替。两者均为写作规则，不是判断文章作者是否为 AI 的检测器。

第一道仍按 `humanizer-review.md` 实际修改并记录。完成其 review 后执行：

```powershell
python -B SKILL_ROOT/scripts/lieflat_review.py prepare --run RUN
```

prepare 保存 Humanizer 的实际输出为 `humanizer-output.md`，固定第一道审阅哈希、目标文风与第二道源版本。读取完整第二道 SKILL 与目标文风后，只改它明确命中的 1—11 号规则。不改没命中的句子，不改段落顺序和数量，不借去 AI 味补造细节。作者既有口语、设问或标点有明确文风依据时保留。

第二道修改 body.md 后写 `lieflat-review.json`：`status=pass`、`input_sha256`、当前 `prose_sha256`、`writing_style`；`checks` 包含 facts_preserved/voice_preserved/whitelist_only/structure_preserved，各记录实际观察与具体 reason。`findings` 为实际修改数组，每项包含整数 rule（1—11）、准确 before/after 和命中理由 reason。脚本按这些最小修改重建最终文字，不允许记录之外的偷偷改稿。确实无修改则 findings=[] 并记录具体 no_change_reason，不能为填表编造问题。

```powershell
python -B SKILL_ROOT/scripts/lieflat_review.py check --run RUN
python -B SKILL_ROOT/scripts/humanize.py check --run RUN
```

第二道后重读全文，核对事实、范围与目标文风，再绑定最新正文的 claims、标题和配图。数字、名字、日期、引语和「可能」等限定词不能改变；代码、链接与已存在图片受保护。新增配图不会失效纯文字检查，改正文或第一道记录则必须重审。教程保留具体起点、动作与成功状态，新闻保留事件叙事，不把所有文章改成同一口语模板。

新 run 的 `tone_policy=dual-tone-style-preserving-v1` 启用此门槛，原稿、第一道结果与两道审阅进入 fingerprint。旧已确认稿保留原契约，明确改稿才迁移；用户无需重复确认历史作品。
