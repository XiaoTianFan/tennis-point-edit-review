# 视觉组件研究（2026-10-25）

本轮检查上游 API 的默认分支 commit、文件树、源码、LICENSE、README 与
模型链接。只把本机实际运行过的组件标为已测。公开项目名中的 Hawk-Eye
不构成精度或裁判认证。所有数值评估仍以当前成片实测为准。

## 候选与选型

| 组件 / 固定版本 | 可复用部分、检查结果 | 授权 / 权重 / 本地条件 | 本轮状态 |
|---|---|---|---|
| [TennisProject](https://github.com/yastrebksv/TennisProject/tree/b7552e955253c008c7612298cb40694682a74ef9) `b7552e9`，2024-08-26 | TrackNet球、14点场地、CatBoost落点组合；源码固定scale=2，要求720p；落点默认用样条补缺失轨迹，不能当原始观察 | 未发现根LICENSE；球/场地/落点权重有Drive链接，本地已有；PyTorch/OpenCV/SciPy，CatBoost另选 | 外部本地模型已加载；独立适配器更正坐标比例、禁止插值；不打包上游代码/权重 |
| [TrackNet PyTorch](https://github.com/yastrebksv/TrackNet/tree/730ea17a324321c553c480179caa8ff13e4cf553) `730ea17`，2024-03-17 | 3帧BGR、640×360；训练生成0–255强度热图。逐帧强度类别不是校准存在概率；训练文件的随机帧划分不等于跨比赛盲测 | 未发现根LICENSE；Drive checkpoint公开链接；CPU能跑但慢 | 用TennisProject对应架构与已有权重实际推理；此仓库训练/推理代码审读 |
| [TennisCourtDetector](https://github.com/yastrebksv/TennisCourtDetector/tree/e5cd4f1ce26b15361700d3d89e068cbf0e82749e) `e5cd4f1`，2024-03-15 | 广播视角14点热图；线段细化与单应性有用。公开数据8841图、720p；README指标不移植到低机位手机录像 | 未发现根LICENSE；场地权重本地已有；同PyTorch栈 | 真实画面运行；保留原点与几何拒判，未按README精度承诺 |
| [WASB-SBDT](https://github.com/nttcom/WASB-SBDT/tree/923462cacdeb3353b84ddebdedb3f4b7a8553b0f) `923462c`，2023-11-23 | 论文基线和多后端评估；检查tennis配置按game1–7训练、8–10测试，适合下一轮公平比较；模型配置使用HRNet | 代码MIT；MODEL_ZOO含tennis专用权重链接，权重适用条款应单列核对；官方测试Python3.8/CUDA11.3/Ubuntu，Windows未测 | 审读配置/推理和模型清单，未下载/运行。优先下一轮后端 |
| [TrackNetV3](https://github.com/qaz812345/TrackNetV3/tree/6eda442ada1740573f200f836d93edc9a541ee86) `6eda442`，2026-09-03 | 原项目面向羽毛球；背景融合与轨迹修复可参考，但插值/修复必须单列。不能把“V3”自动等同更好网球模型 | 实际LICENSE为MIT且明确覆盖pretrained checkpoints（API标Other）；代码和模型链接可见；PyTorch，Windows未测 | 仅审读；网球域迁移需新实验 |
| [ArtLabss/tennis-tracking](https://github.com/ArtLabss/tennis-tracking/tree/3a633be55f13667649c385ff76055176bf074c6b) `3a633be`，2022-11-22 | 单机位球场、TrackNet、YOLOv3人物与小地图组合；可参考几何/展示，不能沿用名称中的精度暗示 | 仓库Unlicense；上游依赖/权重仍各有条款；旧TF/PyTorch/YOLO栈，Windows本地有改动 | 本地检出只读审计，未执行整个应用 |
| [MaximeBataille/tennis_tracking](https://github.com/MaximeBataille/tennis_tracking/tree/0d0682a7109b6dd54ecd557a3750fefe8604b397) `0d0682a`，2022-03-19 | 类似球/球员/场地组合，可作结构对照；本地曾修改predict_video | 未发现根LICENSE，已有YOLOv3权重；旧依赖 | 未运行，不作为维护主干 |
| [abdullahtarek/tennis_analysis](https://github.com/abdullahtarek/tennis_analysis/tree/d557527793820f1e6b06872256824255facd47fd) `d557527`，2024-03-22 | 教学工程：YOLO球/球员、CNN场线、速度/拍数。源码缺球用interpolate+bfill；固定25帧趋势判触拍；ball dict复写同一ID。不可直接作为证据或发球分割 | 未发现根LICENSE；权重链接及本地文件存在；Ultralytics依赖，Windows本地有改动 | 代码检查，未运行完整应用 |
| [Ultralytics](https://github.com/ultralytics/ultralytics/tree/fdddc0c91de84f41af65d1c9a3bd94053a6b3b36) `fdddc0c`，2026-10-24 | 人物检测/跟踪可作后续姿态、触拍语境；通用人物框不能确定球落地或网球胜负 | 当前代码AGPL-3.0，另有商业授权路线；专用球权重需另核对，不能当普通球类检测即可 | 本轮未安装；球/场地优先，避免提前引入完整人物栈 |
| [TennisExpert](https://github.com/LZYAndy/TennisExpert/tree/8b778bc1321229639a2cc56c281589a51ff46dfd) `8b778bc`，2026-06-22 | Qwen3-VL-8B与职业比赛语义/评论数据；适合作为语义评价研究，不能替代逐帧球证据。README宣称的解析器能力须逐文件验证 | 未发现根LICENSE；数据/权重链接；8B多模态推理和训练栈，非本轮最小CPU实验 | 仅审读README/文件清单；不采纳其未经本机验证的实时能力 |

上述“未发现LICENSE”是所检查固定版本的事实，不是授权判断。现有五个
本地仓库的HEAD分别与对应上游默认分支一致，但多个工作树有修改，已保存
其状态/哈希；不将本地修改误称上游行为，也不更新或覆盖它们。

截至检查时这些仓库均未标 archived。大多数网球专项仓库最后代码提交在
2022–2024年；TrackNetV3最近2026-09，Ultralytics为2026-10。pushedAt
与默认分支提交日期不同，报告采用后者作维护信号；星标数不证明维护质量。
上游/API快照、实际文件hash和权重hash存于私有实验目录。

## 论文、数据与适用边界

- [TrackNet 原论文](https://arxiv.org/abs/1907.03698)：多帧对小球和模糊轨迹有价值，但广播数据的可见性标注和帧率不能当本地60fps低机位的真值。
- [WASB 论文](https://arxiv.org/abs/2311.05237)及[官方模型表](https://github.com/nttcom/WASB-SBDT/blob/923462cacdeb3353b84ddebdedb3f4b7a8553b0f/MODEL_ZOO.md)：提供可比较的网球权重路线；模型优势仍需相同输入、相同拒判政策的实测。
- [TrackNetV3 论文](https://people.cs.nycu.edu.tw/~yushuen/data/TrackNetV3.pdf)：背景融合和轨迹修复是方法候选，羽毛球结果不直接转成网球召回率。
- [OpenCV 单应性](https://docs.opencv.org/4.x/d9/dab/tutorial_homography.html)：平面变换用于地面接触假设；离地飞行球不能通过平面投影恢复真实3D。单目遮挡、曝光、低分辨率和透视压缩限制仍需显示。

没有下载全量公开数据集或进行训练。首轮采用用户指定的现存成片与规范
agent记录，评价相对实用表现；样本选择、人工修正和未测指标须同时报告。

## 选择

先**组装模块化适配器**，不接管任何旧研究应用。利用用户已有TrackNet与
场地权重做可运行比较，用本仓库的源/PTS、缓存、几何、复核和编辑接口
承接。HSV/运动为廉价对照；CatBoost只作无插值的额外实验。源码检查发现
旧TennisProject热图 `feature_map *= 255` 后转uint8会回绕，独立适配器
按训练的强度类别阈值取连通区域，因此实验是适配器表现，非逐字复现上游。

后续优先WASB网球checkpoint的GPU/ONNX对照和低机位场线校正，再加入人物
位置与动作语境解释触拍/死球。服务/结束事件必须与画面、历史规范记录和
agent补查共同判断；缺球和一条运动曲线不足以分割整场。包内不分发授权
不明确的第三方实现/权重，后端选择不会改变审核、计分或统计权威。
