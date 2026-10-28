# Serve-speed recovery / 发球估速恢复

Revision **2026.10.28-v27.0**. Video/model estimates remain conditional; the seven JSX templates are unchanged.

## Joint reconstruction and honest uncertainty

The endpoint and partial-flight recovery described below remain supported. The new [comprehensive architecture](../skills/tennis-point-edit-review/references/serve-speed-pipeline.md) adds a joint route when the source supports it: independently calibrated camera geometry, a shared toss/outgoing contact state and time, covariance-weighted flight observations, and first-collision constraints. A separate two-axis image curve can use nearby rebound points to localize a bounce without counting them as serve flight. First net contact ends the model; legal let classification remains independent.

The physical model fits initial velocity and the curved 3D path together. Full path distance is the integral of speed to the first collision; path length divided by flight time is the path **average**, whereas the displayed launch estimate is the initial velocity magnitude. Horizontal displacement/time remains a diagnostic. None of these distances is an independently measured 3D ground truth from a single camera.

Native source PTS govern clips, labels and audio. A separate evidence-based capture clock may test omitted intervals or rolling readout, including correction of the collision's sensor row. Timing hypotheses from one recording must not be inherited by the next. Whole-camera refits, paired trajectory refits and correlated localization errors feed the [conditional model range](../skills/tennis-point-edit-review/references/serve-speed-uncertainty.md). Failure/boundary counts and broad stress alternatives remain visible. A smaller range must be supported by evidence, not a desired fixed ± value; percentile ranges are not automatically calibrated confidence intervals.

The [joint API](../skills/tennis-point-edit-review/references/serve-speed-joint-api.md) implements reusable fitting, path metrics, quality/uncertainty contracts and optional label-plan metadata. Source review, camera/registration adapters, ensemble orchestration, net clearance and editor composition remain explicit work, not claimed automatic features. Full-length speed-only delivery retains every source frame, cut, fault/let and original audio. Hiding the uncertainty row leaves the same adopted centre and label window.

新版在原端点/部分轨迹恢复之上增加有证据支持的联合重建：独立相机标定、抛球与出球共享触拍状态/时刻、协方差加权观测、首碰撞约束及双轴局部反弹定位。完整3D路径积分与水平距离、路径均速、初速分开；源PTS与物理捕获时钟分开。全相机与轨迹成对扰动产生条件模型区间，保留失败/贴边计数和宽压力测试，不能为窄区间隐藏不利结果，也不能冒称已验证95%置信区间或雷达精度。纯估速交付保留全片及原声，隐藏区间不改中心值。详见上述架构、区间与API说明。

## What changed and why

An endpoint-only pass can mistake a fixed crop, colour threshold or missing calibration for missing source evidence. Previously, partial 3D fitting was available but described as an optional path, while group-mean fallback was easy to reach without a record of executed alternatives. That allowed untried work to be reported as failure. The new default requires a per-serve recovery decision and runs the numerical checks together.

| Stage | Required behaviour |
|---|---|
| Source | Recheck native adjacent contact/outgoing frames, full-frame candidates and adaptive crops; distinguish the live ball from old balls, bodies and rackets. Try brightness/motion contrast when colour fails. |
| Geometry | Review court/post metric controls, camera assumptions and independent contact depth; register camera changes with static features and held-out checks. A ground homography is insufficient for an airborne ball. |
| Method | Use a reliable first-bounce/net endpoint when available. Otherwise obtain the prerequisites for a partial pre-impact 3D fit or document why they cannot be obtained. |
| Recovery | If a short track or sensitivity check fails, seek a longer visible pre-impact segment within the source edit; revisit contact/calibration before rejecting it. Never cross a collision, invent observations or relax gates just to increase coverage. |
| Acceptance | Multi-start fits, alternating-frame holdouts, parameter bounds and timing/geometry/drag/lift/centroid perturbations must pass. Correlated pixel error matters for tiny balls even when fit residuals are small. |
| Display | An accepted individual estimate shows “约 N km/h”. A final audited gap shows “N/A” below the serve label, without a unit. Pending work does not qualify as N/A. |

`serve_recovery.py` executes the partial-flight screening from reviewed JSON inputs. It does not identify the ball, calibrate the camera automatically or certify accuracy. `unavailable_reason` checks that source/contact/geometry/extension steps and both route decisions are resolved before an N/A label is generated. Exact native CFR frame mapping supplements rounded microsecond timing to prevent an early label.

The final speed panel uses accepted central estimates from legal serves only, equally weighted per serve. Faults (including double faults), lets and N/A are excluded from the fastest serve and first-/second-serve means. N/A stays null and is excluded from numerical denominators; legal serves with N/A remain in the coverage denominator. Preserve all raw attempts and their speed records, plus the independent serve/fault counts. This is the skill's stated convention, not a claim about a uniform ATP definition. Group means are not a default source of individual labels or speed statistics; explicitly requested imputation stays separate and opt-in. Coverage and missingness bias must be disclosed. Sensitivity envelopes are not confidence intervals, and shared model errors do not average away. Independent radar or multi-camera ground truth is needed to measure real accuracy.

## 中文

以前的主要问题是执行未闭环：工具已有部分轨迹方法，但端点缺失、固定裁切漏球或未做标定容易被笼统记成“不可估”，随后转组均值；没有逐发记录来区分“未尝试”和“实际拒收”。新版把恢复步骤、适用方法执行和最终N/A资格连起来。

默认先核连续原帧触拍/出球，扩大搜索并处理灰白背景漏球；检查场地/网柱3D标定、独立深度和镜头变化。可信首落地/首碰网走端点反推；端点遮挡则补齐部分轨迹前置。短段失败继续查更长的碰撞前可见段，不跨剪口/碰撞、不造球点、不降低门槛。运行器统一执行多初值、留出预测、边界及五族扰动，特别加入微小球的相关像素定位误差。

通过后显示本发约值；可取得证据与适用路线处理完、仍无法稳健求解才显示纯N/A。最终面板仅汇总有效发球，最高及一/二发均速排除失误（含双误）、let和N/A。N/A不填0、不进入数值分母，有效但N/A仍在估速覆盖分母；完整原始尝试与测速记录保留，不改发球机会、进球率或双误统计。这是技能明确采用的口径，不冒称ATP统一官方规范。组均值默认不进入视频或速度池。当前估值仍依赖条件几何、阻力和旋转假设，不冒称雷达精度；真实精度须另用独立真值检验。

## Implementation

- [Method and physical boundaries](../skills/tennis-point-edit-review/references/serve-speed-model.md)
- [Recovery steps and runner input](../skills/tennis-point-edit-review/references/serve-speed-audit.md)
- [Label timing and N/A contract](../skills/tennis-point-edit-review/references/serve-speed-overlay.md)
- [Computed synthetic case](../skills/tennis-point-edit-review/examples/serve-speed-case.json), not a real-world benchmark
