# Serve speed estimation / 发球速度估算

Revision **2026.10.04-v19**. This describes the implemented reusable workflow,
not a claim of radar accuracy. The seven visual templates are unchanged.

## English

### What number are we estimating?

The ball's speed immediately after it leaves the racket. That is different from
distance divided by the total flight time: the ball slows down, follows a curved
path and has vertical as well as horizontal velocity. Every displayed number is
an estimate, not a radar reading. A sensitivity range is kept separately; its
upper end is never used as the fastest serve.

### First identify the actual event

Build a complete list of attempts, including first faults removed from the edit.
Abandoning a toss does not use a serve. Actually trying to serve and missing does
count as a fault, but produces no launch speed: do not record zero or impute one.
A first fault followed by a second-serve let and a replay remains **1, 2, 2**.

Use original frame times, not slow-motion playback time. Frame differences,
color and motion help find candidates; an agent checks the original adjacent
frames to confirm the same ball, racket contact and the first bounce/net impact.
An airborne ball visually overlapping the net band is not proof it touched it.
For variable-frame-rate video, use each frame's timestamp.

### Three estimation paths, plus a diagnostic

| Path | How it works | When to use it |
|---|---|---|
| Endpoint physics | Simulate flight from the racket and adjust initial speed until it reaches the observed endpoint at the observed time | Contact, first collision, distance and heights are sufficiently constrained |
| Partial 3D trajectory | Simulate several possible 3D flights, project through a calibrated camera and fit the observed ball positions | A useful continuous pre-impact track and independent geometry/depth constraints exist |
| Same-group fallback | Use the mean of independently supported serves from the same set, player and serve number; preserve the supporting IDs | Direct reconstruction is inadequate; explicitly display “imputed” |
| Distance/time diagnostic | Compute horizontal average flight speed | Sanity check only; neither launch speed nor independent corroboration of the endpoint method |

Choose a method based on evidence. Do not blindly average estimates that share
the same uncertain contact time or camera calibration. If the fallback has no
valid support, report the gap. Never feed imputed estimates into more imputation.

### Physics and parameters

The model includes gravity, air resistance proportional to speed squared, and
an optional sideways/lifting force representing spin. Gravity defaults to
9.81 m/s². Drag starts near 0.020 per metre, an explicit prior derived from
illustrative ball mass, diameter, air density and drag coefficient; it is not a
measurement of this particular ball. Unknown spin can start at zero lift, but
we vary lift to examine its influence. The coefficient is not a measured RPM.
The current model assumes still air and constant coefficients.

The endpoint solver works in a vertical plane, integrates the flight with RK4
and adjusts the initial horizontal/vertical velocity. The 3D solver uses RK45
and robust least squares to fit starting position and velocity with a supplied
camera, bounds and measurement priors. It does not automatically calibrate a
camera or discover a ball's spin. Court-line mapping supplies ground geometry;
airborne-ball pixels cannot simply be treated as ground positions.

Both paths depend on contact time, endpoint time, distance, contact height,
endpoint height and physical assumptions. The 3D path also needs camera
geometry and reliable ball positions. We deliberately perturb these assumptions
and keep the resulting range instead of applying an arbitrary speed discount.

### What changes for a let?

Stop the flight at the **first net impact**. The net changes the ball's motion;
the post-net bounce cannot be fitted as though the ball flew uninterrupted.
Use the pre-net endpoint if reliable, otherwise a stable partial pre-net track,
otherwise the clearly labelled same-group fallback. A net impact and a let
ruling are separate events: the label changes only after the replay ruling is
confirmed. A second-serve let is followed by another second serve.

### Why a plausible fit can still be wrong

A tiny pixel error does not establish the correct depth or speed. Reject fits
that hit parameter bounds, depend strongly on the starting guess, lack useful
geometry, predict held-out frames poorly or change greatly under plausible
timing/geometry/drag/lift changes. Both directions of each uncertainty family
must be checked. Interleaved-frame prediction tests internal consistency, not
independent speed truth. The shipped thresholds are adjustable engineering
screening defaults, not certified error percentages.

### Statistics, labels and validation

Every included real strike receives equal weight. Report first/second-serve
means by set/player and recompute overall means from individual serves. Keep
lets separate by default. A missed swing remains in fault statistics but not in
the speed denominator. Recheck the fastest central estimate and report coverage
and imputation influence. Panels and per-serve labels consume the same records.

The package includes event auditing, endpoint sensitivity, optional 3D fitting,
holdouts, quality gating, non-recursive fallback, label timing and synthetic
regressions. These make failures more detectable; without synchronized radar or
independent multi-camera ground truth, we cannot quantify real-world accuracy.

## 中文

### 算的是什么

目标是球刚离开球拍时的初速。距离除以飞行时间只是均速，不能直接当初速：球会减速，也有竖直运动。中心估值、敏感性范围和补估分开保存；不能拿区间上界充当最快发球。

### 先确认发生了什么

先列全每次尝试，包括精剪删掉的一发失误。主动放弃抛球不耗发次；真正尝试发球却挥空算失误，但没有离拍速度，不能填零或补估。一发失误、二发擦网、二发重发的发次是 **1、2、2**。

用原片时间，不用慢放后的播放时间。帧差、球色和运动连续性帮助找候选，再检查相邻原图确认同一颗球、触拍与第一次落地/碰网。画面上球与网带重叠，不等于实际碰网。可变帧率使用逐帧时间戳。

### 三种路径与一个诊断值

1. **端点物理反推**：知道触拍和第一次碰撞的时间、距离、高度，就不断调整初速度，让模拟球在正确时间到达正确位置。
2. **三维部分轨迹拟合**：有连续球路及可信相机、深度约束时，模拟不同三维轨迹，投回画面，与实际球位置比较。低像素误差还不够，必须检查解是否稳定。
3. **同组补估**：前两种不足时，取同盘、同人、同发次的独立可靠样本均值，明确标“补估”，保存支持样本。不能用补估继续支持补估；没有依据就保留缺口。

距离/时间另作飞行均速诊断，不混入初速，也不能算作与端点法独立的第二份证据。两种方法共享错误时间或标定时，平均它们不会自动变准。

### 模型用了哪些参数

基础物理是重力、与速度平方相关的空气阻力，以及可选的旋转升力/侧向力。默认重力 **9.81 m/s²**；阻力先验约 **0.020/m**，由示例球重、直径、空气密度和阻力系数得到，不是对本场球的实测。未知旋转可以先用零升力作中心假设，但要改变升力看结果有多敏感；升力系数不等于已测得转速。当前假设无风、系数恒定。

二维端点法用 RK4 把飞行分成很多小步，反调水平和竖直初速度；三维法用 RK45 推进，再以稳健最小二乘寻找合适的初始位置和速度。相机标定、初值范围和独立几何约束由取证提供，不会由脚本自动保证正确。球场线能校准地面，但不能把空中球直接投到地面当作它真实的位置。

共同输入是触拍时间、首次碰撞时间、距离、起点/终点高度和物理假设；三维法还需要相机几何与可靠的逐帧球位置。时间、几何、阻力、旋转都分别向合理范围两侧扰动，保存结果范围，不随意把球速打折。

### 擦网如何处理

**在第一次碰网处截断模型。** 网改变了球的运动，不能用碰网后的落地去反推一条连续自由飞行轨迹。碰网时刻和距离可信就用端点法；否则试碰网前的部分轨迹；还不可靠才补估。首次碰网和最后确认重发是两个事件，UI 在重发判罚确认后才显示擦网；二发擦网后仍是二发。

### 如何拦截看似合理的错解

拟合贴住参数边界、缺少深度约束、换一个初始猜测就得到不同速度、预测未参与拟合的帧很差，或合理改变输入就大幅变速，都需要拒收或降级。像素很贴合不等于深度和速度正确。交错帧留出只检查内部一致性，不是雷达真值；默认筛查阈值可以适配，不能宣传成误差保证。

### 怎样进入面板

纳入的每次真实出球等权统计，先按盘、选手、一/二发汇总，再从逐发数据重算全场。擦网默认另列；挥空保留失误/双误统计，排除速度分母。最高中心值单独回看，并保留覆盖和补估影响。面板与右上标签消费同一份数据。

本包把事件核对、敏感性、三维候选、留出预测、拒收条件、补估和标签时序做成了可复用工具，并有匿名合成回归。它们改善错误发现与可追溯性；没有同步雷达或独立多机位真值，目前不能承诺真实球速精度提高了多少。

## Implementation and sources / 实现与来源

- [Model and method selection](../skills/tennis-point-edit-review/references/serve-speed-model.md)
- [Evidence contracts, tools and fallback](../skills/tennis-point-edit-review/references/serve-speed-audit.md)
- [Computed synthetic timing example](../skills/tennis-point-edit-review/examples/serve-speed-case.json)
- [Rod Cross: drag and spin in ball trajectories](https://www.physics.usyd.edu.au/~cross/TRAJECTORIES/Trajectories.htm)
- [OpenCV: homography and planar geometry](https://docs.opencv.org/4.13.0/d9/dab/tutorial_homography.html)
- [ITF 2026 Rules of Tennis, rules 19 and 22](https://www.itftennis.com/media/7221/2026-rules-of-tennis-english.pdf)
