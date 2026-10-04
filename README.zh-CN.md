# Tennis Match Edit · 网球逐分精剪、计分与复核

[English](README.md) · [技能入口](skills/tennis-point-edit-review/SKILL.md) · [演示图库](docs/gallery.md) · [账户同步](docs/synchronization.md)

把网球录像整理为逐分精剪、可追溯计分、少量必要复核以及五页技术统计。原片取证、判断、剪辑与检查由 agent 承担，避免把技术统计变成用户逐字段填写的任务。

![虚构数据演示：计分板、发球速度和说明](docs/images/scoreboard.png)

所有截图使用虚构选手、合成事件与程序绘制球场，不含真实比赛视频或个人资料；显示球速也是演示值。

## 工作流

首次简短引导 → 1逐分精剪并排入时间线 → 2判读计分与基础图层 → 3人工复核 ⇄ 4回填再核算 → 5统计与全量估速数据 → 6五页面板与球速图层 → 7合成验收。

默认每轮完成一个阶段，报告产物、自检与下一步；明确要求一口气完成时连续执行。阶段1交完整精剪时间线，暂不计分，账本留作内部log；阶段2由agent逐分判读核算并加基础图层。复核/回填可多轮往返；阶段5备齐数据，阶段6统一制作面板和球速图层。

保留死球落点及必要反应；主剪和复核都逐分剪辑。人工复核仅收自查后仍未知的分，或仍无法与指定终局核对一致的问题整局。HTML默认不带视频，“所有行常驻”仅指复核子集；人工无法归属与尚未审核分开。UE/FE先看压力，再统计UE内移动/站定次数，不当作失误概率。

ChatCut、**Premiere Pro**、本地独立流水线均为一级候选；编辑层和图形层分别选择。[Pr分支](skills/tennis-point-edit-review/references/premiere-pro.md)明确区分旧版CEP/ExtendScript与新版UXP，包含新机器配置和终端执行指南，正常执行不依赖Computer Use或鼠标点击。[图形契约](skills/tennis-point-edit-review/references/graphics-adapters.md)说明原生可编辑图形与渲染覆盖层的选择。agent先检查host版本与模板支持的属性，再构建时间线。

![发球与第三拍统计](docs/images/stats-serve.png)

五页分别为总览与关键分、发球与第三拍、接发、回合与击球结果、击球位置与上网。共39个主比较行，默认每页8秒。深蓝/青柠模板、指标优向高亮与逐发标签时序均在技能包内。

## 安装

克隆本仓库后，可在仓库根目录运行：

```sh
npx skills add . --skill tennis-point-edit-review
```

也可按所用 agent 的技能安装方式复制整个 `skills/tennis-point-edit-review/`，不能只拿走入口文件。技能正文主要使用中文；实际剪辑仍需支持媒体检查与时间线操作的编辑环境。

在 ChatCut 中，让已连接的 agent 把该目录保存或更新为账户中的同名 Skill，再从 My Skills 选择使用。

使用示例：

> 请使用 `<技能目录>/SKILL.md`，用 Premiere Pro 剪辑 `<原视频路径>`。

编辑器也可不指定。agent读取工作流、探测环境并配置；仅对无法自行核实的信息或必需的人工激活动作提问。

## 维护和验证

```sh
python -m pip install -r requirements-dev.txt
npm ci
npm run demo:capture
python tools/validate.py
npm run check:adapters
```

工作流与编辑器指南在 `references/`，正式模板在 `examples/`，计算与取证工具在 `scripts/`。当前版本 **2026.10.05-v23.1**；估速方法详见[中英文说明](docs/serve-speed-explained.md)。

账户保存版本没有可以直接交给 Git 的目录地址。建议以本仓库作可版本管理的维护源。也支持先修改账户版本，再由 agent 完整取回、差异比较、合并、验证和提交；不会自动同步，更不会自动公开到 GitHub。详见[双向同步流程](docs/synchronization.md)。

MIT许可证；参见[发布步骤](docs/publishing.md)与[贡献说明](CONTRIBUTING.md)。

## 本地编辑与复核

未使用ChatCut或Pr时，复用技能内的[Courtside工作台](skills/tennis-point-edit-review/references/local-editor.md)：成片/原片播放、单帧与逐分跳转、剪口/顺序/图层时序编辑、左侧逐分审核、可追溯JSON回填及FFmpeg导出。agent只需终端，用户在本机浏览器操作。
