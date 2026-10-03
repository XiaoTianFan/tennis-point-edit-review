# 辅助材料用法与边界

脚本不连接编辑器、不编辑时间线，也不携带原项目绝对路径或素材ID。路径通过参数传入。Python基础脚本用标准库；逐帧和单应映射需要OpenCV及NumPy。浏览器复核页离线运行，无外部库。

## 数据与命令
- 构建网页：python scripts/review_io.py build review-data.json review.html。输入形状见 examples/review-data.json；只填当前待审分，行序匹配复核时间线。每行提供 reviewId、pointId、gameNumber（必要时 setNumber）、serverId 和 serveNumber；记录含一发与二发的连续证据时可用 serveNumbers=[1,2] 表达。R/P 映射与时间线共用，局次和发球方逐行常显。局次为正整数，未知值留 null；发次不明也留 null，不借显示默认值猜填。输出为可独立使用的交互列表，不需要嵌入或附带视频，不增加视频转码/导出步骤；录像在对应复核时间线查看。
- 合并用户结果：python scripts/review_io.py merge ledger.json exported-review.txt ledger-next.json。输出新文件；输入账本需 source、ledgerRevision、players、points。旧结构先显式适配，绝不靠行号猜测。
- 核对计分：python scripts/score_audit.py score-input.json。输入含config和points。内部仅A/B为两位选手的逻辑键，映射到用户ID；初始points为原始赢分计数，不是字符串15/30/40。
- 汇总：python scripts/stats_aggregate.py annotated-input.json。含scope、audit（计分核对结果）、points（逐分技术标注）。技术字段参见函数顶部读取，statsIncluded必须显式true；不把缺失当0。
- 差分：python scripts/frame_evidence.py VIDEO START_SECONDS END_SECONDS OUTPUT --roi x,y,width,height。只选短窗；输出原图和对比，不导入项目。
- 旧几何均速诊断：python scripts/serve_speed.py speed-input.json。每个样本含 pointId、serveNumber、validServe、let、contactCourtMetres、bounceCourtMetres、contactTimeSeconds、bounceTimeSeconds、timeToleranceSeconds、distanceToleranceMetres；此输出不能直接标为初速。
- 初速模型：从 scripts/launch_speed.py 导入 reconstruct(distance,duration,height,end_height,drag,lift)，输入已观测或明确假设的米、秒及物理系数；以参数扰动检验敏感性。该函数不自动取证或确认相机标定。
- 全盘速度：aggregate_serves(records)，每发含 setNumber、serveId、serverId、serveNumber、launchSpeedKphEstimate、method，必要时 included=false；同组补估必须 method=model_imputed 且有 imputationBasis。函数逐盘、逐人汇总全部纳入发球，拒绝重复和缺数，最高值只取中心估值。stats_aggregate 输入可另带 serveEstimates 以输出 launchSpeedsBySet。原 fastestMeasuredValidServe/firstServeMeanKph/secondServeMeanKph 为旧飞行均速诊断字段，不能拿去绘制初速行。
- 自检：python scripts/check_helpers.py；python scripts/check_launch_speed.py。

## config 示例
限时：mode=timed，advantage=false，nextServer=A，initialPoints={A:0,B:0}，initialGames={A:0,B:0}。
普通盘：mode=sets，bestOf=1/3/5，gamesToWin=4/6，tiebreakAt=3/4/5/6（须匹配盘长），advantage=true/false，nextServer=A，tiebreakTarget=7；可指定finalSetTiebreakTarget=10。
纯抢分：mode=tiebreak，tiebreakTarget=7/10，nextServer=A；中途开录需initialPoints及tiebreakFirstServer。
默认辅助计算是净胜两分的抢分；若约定封顶、特殊短抢分或以抢十替代整盘，需要按已确认规则扩展并增加边界检查，不能强套当前核对器。finalSetTiebreakTarget=10指决胜盘平局后的十点抢分，不代表用抢十替代整盘。

## 注释契约
stats输入每分须有：pointId、statsIncluded、winner、server、serveNumber、ending(ACE/DF/W/UE/FE/OTHER)、shots、netPlayers(A/B列表)、positionsAfterServe([{player,zone}])。zone为deep/near/inside/null；未知必须保留null。可选speed来自估速器结果。
正常局含拍数1的W需要慎查是否漏分成ACE；接发实际触球后失误通常至少2拍。所有分类与源证据保持对应，脚本只汇总不判读。
计分输出states同时包含before/after；画面比分在死球前用before，死球后才切after。局末after已重置小分，必要时短暂停留赢局状态再开始下一局。

## 重用前检查
参数化版本源自本次已用过的HTML/CV/估速/显示方法，但扩展赛制须用边界样例再验证。脚本并不是黑箱自动识别比赛；不可因它输出JSON就声称判球可靠。


## 人工无法归属的交换字段
review_io 支持 status=unresolved 与 winnerUndetermined=true。字段只表示用户已看过仍不确定；导出另有 inferenceRequired。回填清除旧的采用胜者并保留历史，requiresScoreInference=true 表示后续需要约束计算，脚本本身不实现逆推。人工已复核的数量与已解决的数量分开。旧的 pending/partial、空双误与不计分语义保持兼容。


HTML 的状态字段仅驱动标记、数量和导出，不能驱动隐藏、移除或重排记录。搜索只高亮定位，完整列表始终可见。

## 覆盖、谱系与模板工具
- 原片覆盖：python scripts/evidence_audit.py coverage.json。输入scopes=[{source,startUs,endUs}]、intervals=[{source,startUs,endUs,kind,reviewed,retained,reason,pointId?}]。参考examples/coverage-data.json；声明检查范围，不推测缺失画面。
- 编号谱系：audit_lineage(points,lineage)，points含pointId、active、sourceOrder、sourceStartUs；lineage含kind=merge/split、from数组、to数组、reason、revision。输出按源时间排序的活动分；不自动迁移用户答案到拆分结果。
- 现场未完局判局：在最后真实分填recordedGameWinner、exceptionType=onsite_award_before_rule_completion、exceptionConfirmed=true、exceptionNote。score_audit将实际分保留，输出rulesWinner=null、rulesComplete=false及现场归属，接续换发与下一局；统计器消费同一审计，不额外补分。
- 球速质量：audit_speed_quality(records)接受逐发初速及可选fitAtParameterBoundary、ballIdentityVerified、flightSegmentVerified、fastestCandidateReviewed。输出agentChecks和分组补估影响；flag不是自动判无效，不新增用户表单。
- 正式UI：python scripts/template_pack.py COMPONENT --props current-props.json --output template-bundle.json，COMPONENT见ui-manifest.json。输出与当前产品工具参数无关的源代码、可编辑属性、自然尺寸和1080p比例；按当前动效创作能力导入。统计行从stats-pages.json构建，需显式逐盘/全场范围；不复用旧飞行均速作为初速。
- 包检查：python scripts/check_canonical.py；python scripts/package_check.py；原check_helpers.py和check_launch_speed.py仍需通过。浏览器检查模板的正常/长文案与11行统计，运行记录写入validation.md，不伪称已跨录像验证。

文字完整性：scripts/restore_package.py 默认核对ASCII安全文本备份；--repair仅恢复当前本地技能副本，不写回保存的技能。再运行package_check.py。模板校验对换行格式归一化，兼容Windows与其他平台。


## 逐发球速时段
python scripts/serve_overlay.py input.json plan.json。输入fps（支持整数、十进制或30000/1001等有理数）、records。每条包含setNumber、pointId、唯一serveId、serveNumber=1/2、eventType=serve/let、contactVerified=true、confirmedPostContactUs（已从原帧证实出球的较晚边界）、launchSpeedKphEstimate、method、statsIncluded；补估还须imputationBasis。clip包含当前startFrame、durationFrames、sourceInUs、playbackRate，另可给pointEndFrame、nextServeStartFrame作为退出上限。时间戳为整数微秒、帧为整数。
输出球速开始/结束帧、持续帧数、约/补估标识、四舍五入的中心值及单位，以及labelStartFrame、labelEndFrame、labelStates；labelEndFrame与球速endFrame相同。可给doubleFaultConfirmedUs表示独立核实的二发失误较晚边界，脚本在其后一帧切换“二发 · 双误”，不重启计时；超出显示窗则outcomeAfterOverlayWindow=true，不重新显示。仅生成计划，不调用编辑器。向后取整保证没有出球前预显，3秒上限按成片fps计算，变速仅支持恒定倍速；非线性变速需先逐段映射。必须输入实际保留片段，缺证据或已裁掉触拍的片段会报错以提醒agent自行处理。不同擦网/重发不得共用serveId或挪用下一发球速，statsIncluded独立保留，不改变统计分母。回归检查：python scripts/check_serve_overlay.py。

## 接发标注与汇总
从scripts/serve_return_stats.py导入aggregate_returns(points, require_complete=True)，输入已选择同一盘/全场范围的有效分，statsIncluded=true，沿用server、winner、serveNumber与ending。每分新增serveReturn={reviewed:true,serveIn:true/false,returnOutcome:"in"/"error"/"ace"/"not_applicable",returnWinner:true/false,evidence:{sourceTimes:[...],note:"..."}}。只有双误用not_applicable；其他特殊原因另选明确范围，不猜填。evidence为当前agent源片复核记录，不要求用户填写。
输出serveDirectRate、returnIn、returnFirstIn、returnSecondIn、returnWinners及覆盖。默认缺证据即报错；stats_aggregate为兼容旧账本使用require_complete=false，有缺失时五个新指标为null并列出缺失分，模板装配仍拒绝最终渲染，促使agent先补核。每个比率保存分子、分母；源事实不互换成最终胜者。回归检查：python scripts/check_serve_return.py。

## 五页诊断统计
向stats_aggregate.aggregate提供shotEvents即可同时调用diagnostic_stats.aggregate_diagnostics。每条有效触拍含pointId、shotIndex、hitter、countsAsShot及evidence；终结拍另含hand（FH/BH/other/null）、terminalOutcome与errorDirection（net/out/null）。发球尝试另存，不把一发失误或let拼进有效回合。build_stats_pages(metrics,speedSummary,diagnostics)生成39行及副文本；speedSummary是已选盘/全场的A/B汇总映射，跨盘先汇总原始逐发记录。执行python -m unittest discover -p "check_*.py"和python package_check.py。



失误终结拍在shotEvents的真实最后一拍加入terminalErrorMotion=moving/stationary/unknown及motionEvidence={sourceTimes:[...],sheet:...,note:...}；已判标签必须有连续画面依据。diagnostic_stats输出ueMotionCounts（moving/stationary/unknown）、ueMoving与ueStationary次数；仅UE进入集合。旧errorMotionCounts/errorMoving/errorStationary仅保留作兼容诊断，不再用于默认主面板。按error-classification.md完成来球压力独立判读，调用error_review.review_coverage核查每个实际失误已有依据；不能只看最后姿态或直接复用旧UE/FE。受迫性未判用OTHER+terminalError=true，保留所有错误方向分母。stat_comparison.direction/compare负责39行比较语义与原始分数比较；build_stats_pages保存comparisonValues、comparison、highlight。请运行check_error_motion.py、check_stat_comparison.py及现有回归，核对高/低/中性/并列/缺失。

## 工具与材料导航

- [离线复核页](../examples/review-template.html) + [构建/回填工具](../scripts/review_io.py)：仅交互列表，无需附带视频；两位得分方、独立“人工无法确定”列、七种死球类型、双误、额外多打、备注、离线草稿、复制全部结果。
- [独立计分核对器](../scripts/score_audit.py)：参数化有/无占先、短盘、抢七/十、限时赛；只读数据并返回计分和矛盾，不更改编辑器。
- [统计汇总器](../scripts/stats_aggregate.py)：逐分标注、计分校验与初速逐盘汇总共同驱动五页39行比较指标，回合分布与正反手拆分嵌入原行；详细输入见[辅助材料用法](helper-usage.md)。
- [逐帧证据助手](../scripts/frame_evidence.py)：短时间窗原帧、帧差、球色候选；候选不构成判罚。
- [初速模型与逐盘汇总](../scripts/launch_speed.py)：有约束的重力/二次阻力反解，模型补估必须注明依据；最高值取中心估值，二发进球率单列。
- [逐发球速时段助手](../scripts/serve_overlay.py)：将已核实的出球证据映射到当前主剪，限制球速最多3秒，生成发球前标签、判定后双误状态以及大/小标签共同结束帧；不负责自动判读或编辑时间线。
- [球速计算助手](../scripts/serve_speed.py)：已确认的击球/落地端点、时间误差和场地标定；不自动宣称出拍速度。
- [视觉模板说明](visual-templates.md)；examples 下保存正式计分板、主剪/复核发球标签、稳定复核编号、临时说明及五页统计模板；[模板装配工具](../scripts/template_pack.py) 输出源代码、属性和比例。
- [最小样例](../examples/review-data.json) 与 [规则边界检查](../scripts/check_helpers.py)。所有示例均为虚构占位数据，不继承原比赛。
- [草案验证记录](validation.md) 说明哪些已实际验证、哪些仍需在新项目里检查。
这些脚本只辅助取证、计算、交换数据，不代替当前产品的剪辑、素材管理或导出能力；不要把历史工具参数写死进技能。

## 接发数据完整性边界

新增统计由 [接发汇总助手](../scripts/serve_return_stats.py) 消费agent逐分视觉标注；模板在证据未齐时拒绝把缺失绘成0。用户不需额外填写接发技术字段，定义与分母见 [统计口径](statistics.md)。
