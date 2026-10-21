# 辅助工具入口与契约

工具不判球果；路径与临时文件放当前任务。基础Python用标准库，CV需OpenCV/NumPy，3D另需SciPy。

## 编辑与图形

编辑器按[环境分流](editing-environments.md)选择，计算脚本不连接编辑器。示例均为虚构占位。

| 工具 | 调用与边界 |
|---|---|
| local_editor.py | workspace/doctor/media/init/serve/context/update/render；[本地工作台](local-editor.md)规定计划、版本围栏、用户导出及agent主动导出条件 |
| job_workspace.py | create/resolve/read；[任务工作区](job-storage.md)规定主检出outputs默认值、显式目录和迁移路径解析 |
| premiere_exchange.py | 生成FCP7 XML与源帧/tick映射，不操作Pr；[Pr分支](premiere-pro.md)规定CFR、范围和待执行操作 |
| premiere_mcp.cjs | 单请求stdio桥客户端；执行host操作，超时不盲重试，不当只读计算器 |
| render_overlays.cjs | React/esbuild/Playwright将七个正式JSX渲染为RGBA PNG和哈希清单；不连接编辑器 |
| make_mogrt.cjs | 生成五种简洁图形的AE创作脚本和映射，需在AE执行并验证Pr属性；复杂统计用PNG |
| template_pack.py | COMPONENT --props props.json --output bundle.json；输出正式源码、属性、尺寸及1080p比例；主机导入与验收另行完成 |

依赖、可编辑性和host验收见[图形适配](graphics-adapters.md)。

## 剪口、审核与计分

| 命令／函数 | 输入与依赖 |
|---|---|
| prepare_review.py plan.json NEW_DIRECTORY --mode agent-dominant\|human-first --surface html\|local\|both | 首次判赢家前准备入口；归组暂定加--provisional-points，不以剪口数充有效分数；见[首次标注](initial-labeling.md) |
| seam_detect.py scan/plan | 已剪成片的剪口候选、源身份及全帧分段；[剪口重建](rendered-video.md)。不判球果，不用于连续原片自动找分 |
| review_io.py build review-data.json review.html | 仅外部编辑器制作离线页，本地集成列表不另造HTML；[样例](../examples/review-data.json)、[模板](../examples/review-template.html)、[审核协议](ledger-and-review.md) |
| review_io.py merge ledger.json exported-review.txt ledger-next.json | 新文件合并，账本含source、ledgerRevision、players、points；按版本与P/R匹配，不按行号猜 |
| score_audit.py score-input.json | config与points，A/B映射当前双方；initialPoints是原始赢分次数；规则和默认见[输入](inputs-and-rules.md) |
| frame_evidence.py VIDEO START END OUTPUT --roi x,y,width,height --job WORK | 短窗动作／候选概览，不作精确PTS证据，不导入工程；更多取证见[原片检查](source-inspection.md) |
| evidence_audit.py coverage.json | scopes=[{source,startUs,endUs}]、intervals=[{source,startUs,endUs,kind,reviewed,retained,reason,pointId?}]；[覆盖样例](../examples/coverage-data.json) |
| audit_lineage(points,lineage) | points含pointId、active、sourceOrder、sourceStartUs；lineage含kind=merge/split、from/to数组、reason、revision；不自动迁移拆分答案 |

config模式：普通盘mode=sets，纯抢分mode=tiebreak，限时mode=timed；参数与抢分净胜规则见[输入](inputs-and-rules.md)。

审核字段、未知／重赛／多打、确认历史与逆推按[账本协议](ledger-and-review.md)；两发可用serveNumbers=[1,2]。

提前判局的recordedGameWinner、exceptionType、exceptionConfirmed及exceptionNote按[现场例外](coverage-and-exceptions.md)填写，不造补分。

## 统计事件

stats_aggregate.py annotated-input.json输入scope、audit、points及可选serveEstimates/shotEvents；每分statsIncluded显式true。pointId、winner、server、serveNumber、ending、shots、netPlayers和positionsAfterServe的口径见[统计](statistics.md)，缺失非0。

shotEvents每拍含pointId、shotIndex、hitter、countsAsShot、evidence；终结拍加hand=FH/BH/other/null、terminalOutcome和errorDirection=net/out/null。一发失误及let不进入有效回合触拍。失误终结拍还需独立terminalErrorMotion=moving/stationary/unknown与motionEvidence={sourceTimes,sheet,note}；只有UE进入动作次数。受迫性未判用OTHER+terminalError=true，保留方向分母；[UE/FE判读](error-classification.md)不依赖最后姿态。

serveReturn={reviewed:true,serveIn:true/false,returnOutcome:in/error/ace/not_applicable,returnWinner:true/false,evidence:{sourceTimes,note}}；仅双误用not_applicable。serve_return_stats.aggregate_returns(points,require_complete=True)拒绝缺证据；标注由agent补核，不新增用户表单；partial数据不能进入最终面板。

build_stats_pages(metrics,speedSummary,diagnostics)生成五页39行及副文本。speedSummary是已选范围A/B聚合，跨盘先合并逐发原始记录。stat_comparison.direction/compare保留原始分数、比较规则与高亮；不从格式化文本反算；见[统计细则](statistics.md)。

## 发球初速与时序

[取证恢复](serve-speed-audit.md)规定原帧、几何、逐发路线尝试与N/A资格。serve_event_audit核发次；speed_evidence.estimate_endpoint反推端点并扰动；serve_recovery.py INPUT.json NEW_OUTPUT.json完整执行3D多初值/留出/五族敏感性；impute_same_group仅显式补估/诊断。launch_speed.aggregate_serves(records)只汇总outcome=in的有效发球，过滤失误、let和method=unestimated/速度null的N/A，按合格中心值逐发等权；结果未知须先核实，不凭included=true推定进区。原始尝试及机会计数另存；旧输入须从事件证据补齐outcome。默认拒绝纳入model_imputed，显式allow_imputed=True只供用户请求的另列补估统计，不混入默认面板。audit_speed_quality保留最高候选/补估影响诊断；build_speed_case.py为合成示例，不是实测。

serve_overlay.py INPUT.json PLAN.json：fps为有理数；records含setNumber/pointId/唯一serveId/serveNumber(1或2)、eventType(serve或let)、contactVerified=true、confirmedPostContactUs(原帧出球较晚边界)、launchSpeedKphEstimate、method、statsIncluded。clip含startFrame/durationFrames/sourceInUs(整数微秒)/playbackRate；可加pointEndFrame/nextServeStartFrame。CFR同时提供confirmedPostContactSourceFrame及clip.sourceInFrame/sourceFps，用精确源帧保护微秒取整；VFR依真实PTS，非恒速先分段。doubleFaultConfirmedUs/letConfirmedUs仅事件确证后切字，互斥、不重计时；挥空不输入助手。

最终无解记录另需method=unestimated、速度null、included=false及完整unavailableAudit，输出speedAvailable=false、speed=N/A、qualifier/unit为空；数值/均值不使用N/A。默认无补估标签，JSON的allowImputed=true（API的allow_imputed=True）只对应用户明确要求。应用后按[标签时序](serve-speed-overlay.md)验收实际合成帧。

## 自检

```sh
python -m unittest discover -p "check_*.py"
python scripts/package_check.py
python scripts/restore_package.py
```

从技能目录运行；[规则检查](../scripts/check_helpers.py)。计算后由agent通过当前编辑器接口应用，并按[画面验收](presentation-and-qa.md#验证与交付)自检。restore_package默认核对ASCII安全zlib/Base64与逐文件SHA-256，--repair只恢复本地损坏副本；有意编辑应重建归档，不用旧归档覆盖，亦不等于保存账户技能。

精确判线、网前死球、触拍和估速用[原生ROI／PTS工具](source-inspection.md#原生roi与目的限制)。实际阅读、规范观察落盘后调用[阶段缓存finish](stage-cache.md)，先提升关键图再回收本阶段自建过程图。
