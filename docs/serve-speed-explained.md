# Serve-speed recovery / 发球估速恢复

Revision **2026.10.18-v25.7**. Video/model estimates remain conditional; the seven JSX templates are unchanged.

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

The numerical speed pool contains accepted central estimates, equally weighted per serve. N/A stays null and excluded; real serve/fault counts remain intact. Group means are no longer a default source of individual labels or speed statistics; explicit requested imputation remains separately identified and opt-in. Coverage and missingness bias must be disclosed. Sensitivity envelopes are not confidence intervals, and shared model errors do not average away. Independent radar or multi-camera ground truth is needed to measure real accuracy.

## 中文

以前的主要问题是执行未闭环：工具已有部分轨迹方法，但端点缺失、固定裁切漏球或未做标定容易被笼统记成“不可估”，随后转组均值；没有逐发记录来区分“未尝试”和“实际拒收”。新版把恢复步骤、适用方法执行和最终N/A资格连起来。

默认先核连续原帧触拍/出球，扩大搜索并处理灰白背景漏球；检查场地/网柱3D标定、独立深度和镜头变化。可信首落地/首碰网走端点反推；端点遮挡则补齐部分轨迹前置。短段失败继续查更长的碰撞前可见段，不跨剪口/碰撞、不造球点、不降低门槛。运行器统一执行多初值、留出预测、边界及五族扰动，特别加入微小球的相关像素定位误差。

通过后显示本发约值；可取得证据与适用路线处理完、仍无法稳健求解才显示纯N/A。N/A不进均值/最高值、不填0、不改发球机会；组均值默认不进入视频或速度池。当前估值仍依赖条件几何、阻力和旋转假设，不冒称雷达精度；真实精度须另用独立真值检验。

## Implementation

- [Method and physical boundaries](../skills/tennis-point-edit-review/references/serve-speed-model.md)
- [Recovery steps and runner input](../skills/tennis-point-edit-review/references/serve-speed-audit.md)
- [Label timing and N/A contract](../skills/tennis-point-edit-review/references/serve-speed-overlay.md)
- [Computed synthetic case](../skills/tennis-point-edit-review/examples/serve-speed-case.json), not a real-world benchmark
