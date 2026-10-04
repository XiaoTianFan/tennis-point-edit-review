# 发球估速取证与可复用工具

阶段5先读[模型与方法选择](serve-speed-model.md)，由agent逐发核实触拍、首次碰撞与几何依据，再用下列工具计算并检验敏感性。

## 每次复核的顺序

1. 冻结已确认逐分归属，建立完整尝试清单，包含剪掉的一发失误、擦网、放弃抛球和真正挥空。分是否纳入统计与某次速度是否纳入均值是两个字段。
2. 逐点运行 `serve_event_audit.audit_attempts` 核对发次；它接收 agent 已判读的事件。放弃抛球/练习挥拍不耗机会；实际尝试发球却挥空算失误但无出球速度；let 保持当前发次。一次合法发球或二次失误后，本分发球序列关闭。
3. 在原始连续帧中确认同一颗活球。差分、HSV、局部区域和运动连续性只产生候选；排除衣服、球拍、旧球、掉球及邻场球。移动镜头先配准；VFR 使用逐帧时间戳。
4. 记录触拍和首次落地/首次碰网的时间夹逼；向前后追查球路，区分经过网带投影与实际碰撞，保留原帧及候选接受、拒绝理由。
5. 只拟合第一次碰撞前的飞行段。分别检查时间、距离、高度、镜头标定、阻力和旋转假设；运行端点反推或三维部分轨迹候选及质量检查。
6. 无合格观测解时，才使用同盘、同选手、同发次的独立证据补估；没有支持样本就留下真实缺口，不捏造帧、触拍或数值。
7. 所有中心估值最高的候选回查原帧；输出覆盖率、补估比例、均值变化与敏感性范围。此工作由 agent 完成，不增加用户逐发审核。
8. 更新估速记录后重算速度统计及相关标签映射；检查发生改动的合成帧。单纯速度修正不重写已确认球果或无关剪口。

## 最小证据记录

每次保留 set、server、pointId、serveId、serveNumber、eventType、speedApplicable、included、contactVerified、ballIdentityVerified、flightSegmentVerified、原始时间夹逼、几何输入及来源、方法、中心估值、敏感性范围与候选质量结果。补估另存 imputationBasis；最高值另存 fastestCandidateReviewed。所有 verified 字段代表已完成的画面检查，不由数值拟合自动填 true。

`serve_event_audit.audit_attempts(events, initial_serve=1)` 的 kind 为 serve、serve_miss、aborted_toss、toss_catch 或 practice_swing。serve 的 outcome 为 in、fault、let。输入必须是同一分的有序事件，eventId 唯一；若录像从二发开始，必须先确定 initial_serve=2。输出实际触球、发次、是否计失误、是否双误及速度适用性。统计口径纳入范围仍须按比赛账本设定，不能仅因实际触球就把赛后练习纳入比赛。

## 端点反推输入

`speed_evidence.estimate_endpoint(evidence)` 接受如下结构；数字仅为合成示例：

```json
{
  "eventType": "let",
  "ballIdentityVerified": true,
  "crossesEarlierCollision": false,
  "contact": {"kind":"racket_contact","verified":true,"estimateSeconds":10.00,"bracketSeconds":[9.99,10.01],"note":"合成触拍夹逼"},
  "endpoint": {"kind":"first_net_impact","verified":true,"estimateSeconds":10.70,"bracketSeconds":[10.69,10.71],"note":"合成首次碰网夹逼"},
  "horizontalDistanceMetres": {"value":12,"range":[11,13],"basis":"合成场地几何"},
  "contactHeightMetres": {"value":2.7,"range":[2.45,2.95],"basis":"合成触拍高度"},
  "endpointHeightMetres": {"value":0.94,"range":[0.89,0.99],"basis":"合成网面接触高度"},
  "dragPerM": {"value":0.020,"range":[0.012,0.028],"basis":"建模先验，非实测"},
  "liftPerM": {"value":0,"range":[-0.004,0.004],"basis":"未知旋转的示例扰动"}
}
```

正常球终点可为 first_bounce；let 必须为 first_net_impact，不能使用碰网后的落地点反推原始初速。脚本拒绝未确认事件、估计时刻不在夹逼区间、跨更早碰撞、不合理范围和非有限数。它返回中心值及输入区间角点求解的敏感性包络；这不是统计置信区间，也不保证非线性内部不存在更极端值。根据曲率补充中间取样，必要时扩大区间。

## 单机位三维部分轨迹

可选依赖 NumPy、SciPy。`partial_trajectory.fit_partial` 接受按源时间递增的 `[seconds, pixelX, pixelY]`、已校准的 3×4 camera 矩阵、触拍时刻、六维初态猜测/上下界、独立测量先验、阻力和升力向量。世界坐标必须以米为单位、z 向上，像素需与镜头畸变处理、裁切和标定一致；摄像机移动必须分段重新标定或采用相应模型。

初态为 `[x,y,z,vx,vy,vz]`；priors 为 `{index,mean,sigma}`。固定相机、时间及物理参数后拟合初态，不同时放开所有相机、深度、触拍时间、阻力、旋转参数以追求低残差。collision_lower_seconds 设置首次碰撞最早边界；其后的观测不得进入拟合。短段或深度不受约束时保留多个起点的候选，发现不同速度同样贴合像素即视为不可辨识。

输出 qualityAccepted 默认 false。先用 `alternating_holdouts` 在交错帧训练、预测另半帧，再独立改变 timing、geometry、drag、lift 四族假设，每族检查正负方向与有依据的边界（variant 使用 family 和 side=low/high）。把候选、两份留出结果、扰动结果和画面检查送入 `speed_evidence.assess_partial_quality`。visual_checks 须确认 ballIdentityVerified、contactBracketVerified、preImpactSegmentVerified、cameraCalibrationReviewed、metricDepthConstraintReviewed、initialStateStabilityReviewed。只有返回 accepted 才可登记 qualityAccepted=true；小残差但贴参数边界、留出不稳或缺乏深度约束均不能通过。`visual_checks.frameHeight`传入实际源画面高度以自动缩放像素残差阈值；时间使用原片PTS秒数，帧率改变不改变物理时长。最低观测数量是证据要求，不因低帧率自动放宽；默认阈值仍是未由雷达标定的工程筛查起点。

## 补估及复现

`speed_evidence.impute_same_group(target, records)` 只使用同盘、同选手、同发次（有 conditionGroup 时也相同）的独立已确认真实发球。支持样本须已确认触拍、球身份与首次碰撞前飞行段；部分轨迹还须通过质量检查。排除 let、未纳入比赛的球、目标自身、挥空及其他补估。输出算术均值与支持事件 ID，绝不循环补估。supportEnvelope 仅描述支持样本，不能冒充目标球的误差区间。

`python scripts/build_speed_case.py examples/serve-speed-case.json` 以真实求解器生成匿名合成案例，演示把球在画面中经过网带的时刻错当碰网会缩短飞行时间、抬高反推速度。案例用于回归，不能充当真实测速基准或自动证明事件判读正确。

从 scripts 目录运行 `python -B -m unittest discover -p check_*.py`。没有可选依赖时三维测试可能跳过，必须单独报告；不能把跳过当已验证。
