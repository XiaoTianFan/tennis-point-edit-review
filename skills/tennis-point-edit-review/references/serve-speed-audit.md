# 发球估速取证与执行契约

阶段5按[方法选择](serve-speed-model.md)执行。工具可用不等于本发已尝试；未执行是pending，不得写成拟合失败或N/A。由agent补查，不增用户逐发表。

## 默认恢复路径

1. 冻结已确认球果/剪口，列全真实发球及排除事件；逐点用`serve_event_audit.audit_attempts`核发次。事件字段见助手；二发起录先定initial_serve=2，合法发球/双误后关闭本分。
2. 通过[原生ROI取证](source-inspection.md#原生roi与目的限制)回看连续原帧，夹逼球拍接近、拍球相遇与出球分离，防止把随挥时刻当触拍。保留PTS，CFR另记原帧号/精确帧率；旧定位、粗抽帧及拟合时刻须复核。
3. 全画幅搜索后用随轨迹扩展的原尺寸ROI、多候选时序关联和静态旧球排除。差分/HSV只产候选；浅色背景、拖影或网格漏检时尝试局部亮度/运动对比，不只放松颜色阈值。人工核同球身份；遮挡/插值/神经网络推断不计真实可见观测。
4. 按本片场地、网柱、站位建立[米制几何](serve-speed-model.md#物理与米制几何)，检查控制点与镜头变化，不以只有地面H为B前置已齐。校准前置能从素材补齐就执行，不能把未标定当球不可估。
5. 先审首次碰撞。可信落地或网面端点走A；缺端点则检查并补齐B前置，执行碰撞前3D部分轨迹。记录不适用/缺前置的具体源证据；不得按serveId硬排除或用通用拒绝文案代替逐发检查。
6. 短段或敏感性失败先补查更长、仍在首次碰撞前的可见段，处理ROI/灰白背景/人体干扰；贴边时回查触拍、控制点和高度先验。不得跨碰撞/用户剪口、造球点或放宽质量门槛追求全数。已覆盖可访问证据且无适用的未执行路线，才登记unestimated并显示N/A；均值不作默认降级。
7. 回查中心最高候选，存覆盖、拒因与缺测偏差；回填同版记录/统计/面板/标签，核显示边界，不改已确认球果。

## 端点与部分轨迹

`speed_evidence.estimate_endpoint`的完整输入见[真实助手生成的匿名案例](../examples/serve-speed-case.json)：实际触拍、首次碰撞均须原帧verified及时间夹逼；距离/高度/阻力/升力各给value/range/basis。let只用first_net_impact，禁止跨更早碰撞。合成例非实测基准。

`partial_trajectory.fit_partial`用真实`[sourceSeconds,x,y]`、米制camera、contact_seconds、初态`[x,y,z,vx,vy,vz]`、bounds及priors。collision_lower_seconds可取已查仍在空中的安全截止或首碰撞最早边界；禁止把任意窗口末端称碰撞证据。

## 一次运行完整B筛查

`python scripts/serve_recovery.py INPUT.json NEW_OUTPUT.json`接收：

- observations、camera、options：传给fit_partial；options必须给collision_lower_seconds，另给cutoffBasis。
- contactBracketSeconds：原帧夹逼，包围options.contact_seconds，所有观测在夹逼后。
- variants：至少geometry/drag/lift各low/high，每项含family、side、basis及可选camera、options覆盖；几何扰动实际相机/米制深度，不能仅改无关项。
- centroidError={pixels,basis}：据原片球的像素大小/拖影给定位误差；不固定套每片1像素。visualChecks：frameHeight及下述原帧检查；policy仅有独立依据时修改。

助手执行基准、两组速度初值、两组交错帧留出、触拍低/高端、所给几何/阻力/升力，以及定位误差的正负相关曲率和固定种子位置噪声扰动。不会自动标定、判球或把verified置true。输出candidate、multistarts、holdouts、variants、variantFailures、quality，只有quality.accepted才能登记qualityAccepted=true。

`assess_partial_quality`默认至少12观测、0.18秒，1080p残差≤2.5px/留出≤3.5px（按frameHeight缩放）、留出速度差≤12%、敏感性跨度≤35%，所有拟合收敛且不贴边。timing/geometry/drag/lift/centroid五族都需低/高方向；多初值还须稳定。visualChecks须由agent实际核实ballIdentityVerified、contactBracketVerified、preImpactSegmentVerified、cameraCalibrationReviewed、metricDepthConstraintReviewed、initialStateStabilityReviewed。低残差不证明深度/速度正确；阈值非雷达误差保证。

## 证据账本与最终N/A

每发保留set/server/pointId/serveId/serveNumber、事件资格、源时刻/原帧、触拍夹逼、真实观测、几何/假设来源、方法尝试及结果、采用理由、中心值/范围和最高候选复查。分/发球机会统计与速度池纳入分开。

无解用method=unestimated、launchSpeedKphEstimate=null、included=false，保留真实发球统计及原因。`unavailableAudit`含sourceSearch/contactReview/geometryReview/preImpactExtension，每项status=complete/unavailable/not_applicable及reason；methods含endpoint_physics、partial_trajectory_model，每项status=rejected/unavailable/not_applicable及reason。rejected还须attempted=true、resultRef；未补齐前置与不可取得前置须区分，不能以“脚本没做”冒称素材不可用。`unavailable_reason`拒绝pending、已accepted或无执行记录的rejected。仅此最终状态允许[下方N/A](serve-speed-overlay.md)，不显示失败候选或组均值。

