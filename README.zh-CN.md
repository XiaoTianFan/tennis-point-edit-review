# Tennis Match Edit · 网球逐分精剪、计分与复核

[English](README.md) · [技能入口](skills/tennis-point-edit-review/SKILL.md) · [演示图库](docs/gallery.md) · [账户同步](docs/synchronization.md)

把网球录像整理为逐分精剪、可追溯计分、少量必要复核以及五页技术统计。原片取证、判断、剪辑与检查由 agent 承担，避免把技术统计变成用户逐字段填写的任务。

![虚构数据演示：计分板、发球速度和说明](docs/images/scoreboard.png)

所有截图使用虚构选手、合成事件与程序绘制球场，不含真实比赛视频或个人资料；显示球速也是演示值。

## 工作流

首次简短引导 → 逐分判读及稳定账本 → 计分链与精剪 → 必要复核与回填 → 技术统计及全量发球初速估算 → 五页统计面板 → 逐发球速标签 → 实际合成验收。

保留死球落点及对手必要反应；主剪和复核都逐分剪辑。复核 HTML 默认不带视频，所有行常驻；人工无法归属与尚未审核分开。UE/FE先根据来球压力判断，再独立统计UE内移动/站定次数，不把次数解释成该动作的失误概率。

![发球与第三拍统计](docs/images/stats-serve.png)

五页分别为总览与关键分、发球与第三拍、接发、回合与击球结果、击球位置与上网。共39个主比较行，默认每页8秒。深蓝/青柠模板、指标优向高亮与逐发标签时序均在技能包内。

## 安装

克隆本仓库后，可在仓库根目录运行：

```sh
npx skills add . --skill tennis-point-edit-review
```

也可按所用 agent 的技能安装方式复制整个 `skills/tennis-point-edit-review/`，不能只拿走入口文件。技能正文主要使用中文；实际剪辑仍需支持媒体检查与时间线操作的编辑环境。

在 ChatCut 中，让已连接的 agent 把该目录保存或更新为账户中的同名 Skill，再从 My Skills 选择使用。

## 维护和验证

```sh
python -m pip install -r requirements-dev.txt
npm ci
npm run demo:capture
python tools/validate.py
```

维护细则与发球物理模型在 `references/`，正式模板在 `examples/`。当前版本 **2026.10.04-v19** 保留全部正式模板与迁移对照，新增事件取证、擦网分段、三维候选质量检查及补估工具；详见[中英文球速方法说明](docs/serve-speed-explained.md)。具体比赛的姓名、视频和路径不作为固定要求。

账户保存版本没有可以直接交给 Git 的目录地址。建议以本仓库作可版本管理的维护源。也支持先修改账户版本，再由 agent 完整取回、差异比较、合并、验证和提交；不会自动同步，更不会自动公开到 GitHub。详见[双向同步流程](docs/synchronization.md)。

MIT许可证；参见[发布步骤](docs/publishing.md)与[贡献说明](CONTRIBUTING.md)。
