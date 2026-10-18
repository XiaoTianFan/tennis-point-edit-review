---
name: tennis-point-edit-review
description: 网球单打逐分剪辑、计分、必要复核、全量发球初速和五页统计；支持连续原片、已有工程和已剪成片的原剪口重建，以及ChatCut、Premiere Pro或本地工作台。 Tennis point editing, seam reconstruction, scoring and collaborative review.
---

# 网球逐分精剪、计分与复核

包版本 **2026.10.18-v25.6**。用于有连续比赛画面的网球单打录像。支持六局、四局、有占先、无占先、限时不限局、纯抢七及纯抢十；采用用户已给规则和下述默认值，只有影响结果且无法从素材核实的真实缺口才追问。不是比赛裁判或雷达测速工具。双打需要额外确认发球与接发顺序，再扩展规则，不能直接套用单打核算器。

网球剪辑任务即使用户未手动点选本技能，也应按任务类型检索并加载；未另指定UI技能/模板/风格时，直接复用本包正式模板，禁止随机重设计。优先级为用户当前明确要求、项目已确认风格、本包默认。

## 工作原则：主动完成本阶段，再交付检查点

- 从现有工程、答案与[阶段记录](references/workflow.md#阶段记录与接续)接续，不重做已确认事实。首次任务按[首次引导](references/onboarding.md)简述流程；继续、修正不重复介绍。
- 默认`agent-dominant`。剪辑／成片粗分段后、首次判赢家前准备[首次标注界面](references/initial-labeling.md)，未知留空；继续agent判读，不要求用户填全场。用户明确`human-first`才等待其标注或切回指令。
- 默认分阶段交付并询问是否继续；用户已授权连续执行则免逐阶段询问。阶段2有疑点直接完成阶段3再交付，不能在二者之间停下征询是否制作复核。每阶段完整覆盖、规定产物和必需自检均完成后才可收工；批次不是检查点。
- 以agent视觉判读为主，补查由agent负责。连续原片不开发自动整场找分工具；已剪成片使用[多信号CV剪口重建](references/rendered-video.md)，剪口与真实分归组分开。先看完整保留段，再判首次死球、赢家、发球方和发次；检测结果或终局吻合都不替代视觉证据。已查仍缺证据才是未知，未检查是待办；未知仅阻塞依赖项。
- 本地在同一工程下方切换完整／复核时间线，不另建复核工程或离线HTML；外部编辑器采用复核序列及独立HTML。聊天汇报精简，内部log不作为额外交付；不另造试听、模拟声音、演示或报告。

## Output language / 产物语言

按用户主要交互语言生成全部可见产物，明确指定的渲染语言优先；记录`outputLanguage=en/zh-CN`并传给全部生成器。界面语言不替代产物语言；姓名、原始证据和协议值不翻译。详见[语言策略](references/output-language.md)。

## 先区分对象与编号

| 对象 | 契约 |
|---|---|
| clip | 源片编辑段；一分可含一发、二发、let等多个段，不各计分 |
| P编号 | 内部账本稳定pointId；归组与证据可追溯，默认不交付 |
| 第N分 | 当前有效计分顺序displayNumber。增删合并后重生成，P号不改。计分资格未定时显示“定位 P…” |
| R编号 | 已发布复核子集内稳定R/P；首次标注用purpose=initial-labeling及独立版本，不冒称有效分母 |
| 常驻行 | 本轮已选审核行始终可见，搜索仅高亮定位；填写不隐藏、重排或跳行 |

## 开工与接续

先读[输入与规则](references/inputs-and-rules.md)、[编辑环境](references/editing-environments.md)和[图形适配](references/graphics-adapters.md)。ChatCut、Premiere Pro、本地为并列候选，沿用用户选择，缺能力时说明缺口并继续独立工作，不静默换编辑器；Pr读[Pr分支](references/premiere-pro.md)，本地读[工作台](references/local-editor.md)。终端和媒体检查即可启动，不以Computer Use为前提。

默认0:0第一分第一次发球开始；暂按没有未完局，须用尾段和计分链核验。未知持拍手仅问一次，未答暂按右手并记录default；已知手别优先。最终比分未知也可开始，默认与推定不得写成视觉证实。使用 [正式模板清单](examples/ui-manifest.json) 与 [模板说明](references/visual-templates.md)。场景、规则或画幅需要适配时保持已确认视觉语言。声明可编辑属性并在目标项目实测后才交付。主比较行与组件数量由正式清单和 [版本元数据](references/package-version.json) 核对。

两类已剪输入先沿用用户给出的[发球保留情况](references/inputs-and-rules.md#核实当前输入)；阶段2交付、统计前告知[发球证据限制](references/statistics.md#已剪素材的发球证据限制)。已有工程按[工程接续](references/workflow.md#已有逐分时间线接续)；仅有成片按[剪口重建](references/rendered-video.md)。用户已剪成片必须保留全部源帧和剪口，总时间线等于输入；分析与复核不再删除一发、等待或尾段。三类入口均在判赢家前备好首次标注；保护已有答案与编号谱系。

## 阶段顺序与必读细则

按当前阶段加载对应细则，无章节链接读全文；不适用时说明原因，跨阶段问题再补读相关专题。

| 阶段 | 工作与交付 | 必读 |
|---|---|---|
| 1 剪辑与重建 | 连续原片精剪；已剪成片逐帧CV恢复原剪口、全帧无损分段并核验。保存P/源映射，提供可播放定位的时间线和首次标注界面，暂不推进比分 | [判读](references/adjudication.md)、[原片检查](references/source-inspection.md)、[账本](references/ledger-and-review.md#内部账本)、[覆盖与谱系](references/coverage-and-exceptions.md)、[精剪](references/presentation-and-qa.md#剪辑)、[首次标注](references/initial-labeling.md) |
| 2 判分与基础图层 | 全部分核查赢家、发球者、发次及局界，推进计分并核对终局。全部目标段加入计分板和短时发次标签，有疑点直接继续阶段3 | [判读](references/adjudication.md)、[规则](references/inputs-and-rules.md)、[例外](references/coverage-and-exceptions.md)、[基础图层](references/presentation-and-qa.md#分析期逐分定位与基础图层) |
| 3 必要人工复核 | 只送补查后疑点；终局仍不符则问题整局逐分送审。本地同工程全片／复核切换和集成列表；外部编辑器复核序列＋HTML。交付前验收播放、定位、保存、恢复与全量答案导出 | [范围及协议](references/ledger-and-review.md#独立复核时间线与-html)、[布局](references/presentation-and-qa.md#局分与逐分复核时间线)、[常驻行验收](references/presentation-and-qa.md#行可见性验收) |
| 4 回填再核算 | 按P与版本合并，保留确认历史；重算整局及后续计分、图层，未解矛盾回阶段3。用户未知先清除旧采用赢家再按约束逆推 | [回填及逆推](references/ledger-and-review.md)、[依赖重算](references/workflow.md#更正后的依赖) |
| 5 技术统计与全量估速 | 从事件备齐五页数据，独立UE/FE和UE动作；逐盘估算全部真实发球，含主剪删除的一发。核验分母、覆盖和显示时序，不以抽样代替全量 | [统计](references/statistics.md)、[UE/FE](references/error-classification.md)、[初速](references/serve-speed-model.md)、[取证](references/serve-speed-audit.md)、[时序](references/serve-speed-overlay.md) |
| 6 统计与速度图层 | 用阶段5同版本数据实时合成五页默认各8秒面板及逐发球速，检查同步退出；数据缺口回阶段5 | [模板](references/visual-templates.md)、[合成](references/presentation-and-qa.md#阶段6统计面板与逐发球速图层)、[速度标签](references/serve-speed-overlay.md) |
| 7 合成验收交付 | 按用户导出要求或agent主动导出条件整片渲染，检查画面、声音、计分、统计与边界；交付工程、约定成片及实际覆盖和剩余限制 | [验收](references/presentation-and-qa.md#验证与交付)、[检查点](references/workflow.md#阶段检查点) |

## 全流程不能越过的边界

- **agent主动导出限制：** 未收到明确导出要求时，全部分归属与当前技术统计获用户确认前，agent不得自行渲染完整样片或复核片，以免重复占用磁盘；使用实时合成、代理、抽帧和透明图层缓存。用户点击导出或在对话中要求agent导出时，直接执行，不以归属／统计确认阻拦，也不代勾确认。接口见[导出与边界](references/local-editor.md#导出与边界)。
- 不为凑终局改赢家或造缺分。观察球果、采用判罚、用户确认、规则约束逆推与现场例外分开留证；矛盾先回查整局、遗漏及邻接边界。
- 原片首次死球、必要落点和反应不能截断；已剪输入由用户剪口界定保留范围，不用agent推测死球再次截短。练习挥拍、重抛与死球回送不凭外形增发次；真正尝试挥空算失误但无离拍速度。
- 复核左上R/P同分常驻，右上常显局次／发球者／发次，左下必须同源计分板，短说明置其上方避让；未知字段显示待核，已知照填。主剪发次是短标签，发球前出现、出球后最多3秒，遇更早剪口／分界／下一发即退；球速与大标签同帧退出。
- 用户已确认结果沿用；发次在阶段2核实，技术项阶段5补齐。null、pending/partial、人工未知、重打、多打等严格按[账本协议](references/ledger-and-review.md)处理，不清历史或让旧AI赢家继续计分。
- 初速、飞行均速、区间和补估分开；最高取中心值。先核实事件、碰网分段；部分轨迹须通过几何、边界、留出预测及敏感性检查，不称雷达精度。
- UE/FE依据来球压力，UE动作独立判类；第五页前两项仅UE内动作次数，措辞中性。未知单列，统计高亮与免责声明按[统计](references/statistics.md)和[画面规则](references/presentation-and-qa.md)执行。

## 数据与工具

姓名、持拍手、赛制、素材与路径均取当前任务；A/B仅内部映射，示例不提供默认结果。复用[辅助工具](references/helper-usage.md)，临时脚本放任务工作区；比赛执行不授权改技能包，只有用户要求收录且验证有效才新增通用工具。

恢复损坏文字先验证规范归档；恢复不等于更新账户技能。仅改技能时不启动比赛流程或修改既有审核草稿；用户同时要求返工时保留旧版与答案，按新标准另存或有围栏更新。
