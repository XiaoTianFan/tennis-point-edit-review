# 可选视觉证据管线

默认仍为 `agent-dominant`，完整检查、判分、统计与复核规则不变。
仅在用户选择 CV 辅助或研究路线时运行本接口。它提供可复现的观察与
待核候选；agent 阅读结构化结果、回看原生证据并处理缺口。当前接口是
有界窗口原型，不支持无人审核的全场找分、自动判线或自动技术统计。

## 输入、依赖与运行

使用原片或现存成片均可。成片作为新的独立源，保留其 SHA-256 和真实
PTS；不可将历史原片秒数直接套到成片。需 Python 3.10+、PyAV、NumPy、
OpenCV、FFmpeg/ffprobe。额外依赖可在独立任务 runtime 中安装：

```sh
python -m pip install -r "<skill>/scripts/requirements-vision.txt"
python "<skill>/scripts/cv_pipeline.py" scan "<input>" "<work>/vision-run" --config "<work>/vision-config.json"
```

配置为 JSON，例如：

```json
{"backend":"classical","windows":[[0,5],[10,15]],"maxFrames":1200,
 "hsvLow":[18,42,80],"hsvHigh":[62,255,255],"motionThreshold":12,
 "maxArea":190,"maxSpan":35,"courtEvery":60,"threads":8}
```

窗口按**输入绝对 PTS 秒**排列、互不重叠，每窗最多30秒；默认总帧预算1200。
达到预算或解码失败时写 `failure.json`，不发布完成结果。使用新 run
目录，不能覆盖旧结果。配置阈值是起点，需在当前素材正反例上验证。
当前支持 SDR、无旋转、方形像素；其他显示变换须另行明确适配。

`backend=local-tracknet` 额外需要 PyTorch，并显式给出 `module`、
`ballWeights`、`courtWeights` 绝对路径及 `device=cpu/cuda`。`module` 是
用户选定的本地 `TennisProject/tracknet.py`，必须先检查代码来源；加载会
执行该 Python 模块。只加载 `weights_only=True` 的 state_dict。权重和
第三方实现不随本技能分发、不自动下载；不得用 PyTorch 缺失阻塞默认
agent 路线。未验证的 checkpoint 兼容性会报错，不偷偷换模型。

该后端输入为 BGR 当前/前一/前二帧、640×360，逐原帧输出候选；坐标
分别按宽高映射回输入编码像素。原始 class intensity 不作 uint8×255
溢出转换；阈值及处理方法写入 provenance。模型训练数据的机位、帧率和
遮挡分布不保证覆盖当前素材。运行时不训练、不填补失踪球。

## 证据契约

`observations.jsonl` 每个实际解码帧一行：

| 层 | 内容与限制 |
|---|---|
| 源 | `sourceIdentity`、完整 probe、整数 PTS、time base、有理秒数、编码画幅；`windowFrame` 只在该窗内编号 |
| 原始观察 | `colourCandidates` / `modelCandidates` 全部候选及响应；模型响应不是球存在的校准概率 |
| 时序推断 | `track`、选择理由、`segmentId`、相机稳定性；多候选/跳变/无球/无法配准时拒判，不插值 |
| 球场 | 原始14点候选与冗余几何拟合分开；至少6点、75%一致；残差只是内部拟合一致性 |
| 事件 | `bounce_candidate` 为图像轨迹转折，同时保留触拍/误跟踪等解释、支持帧和时间窗；`adjudication=null` |
| 边界 | `visual_discontinuity` 只是剪口提案；发球起始/首次死球未建立时 `pointProposals` 明确拒判 |
| 统计 | `not_qualified`、值为 null；未采用的视觉候选不能进入比分、合法发球速度或技术统计分母 |

`result.json` 保存配置、代码哈希、后端/权重/环境、完成覆盖、事件与成本。
`observationsSha256` 绑定数值记录；处理成功不等于视觉复核成功。
原始观察、模型推断和 agent/用户采用判断不得混写。报告覆盖率时分别
列“有候选帧”“选定轨迹帧”“经检查帧”，拒判不等于没有球。

可提供显式 `calibration`：源 SHA-256、`nativeSize`、`validWindows`、
`imagePoints`、`courtPoints`、`referenceKind`。坐标为双打近端左角(0,0)、
远端左角(0,23.77)米，单打左右线 x=1.37/9.60。至少6个对应点，必须
记录人工/agent/模型来源，限定稳定机位有效窗；任一观察点与拟合相差超过
三倍容差时整组拒判，避免RANSAC舍弃整侧场线后输出假坐标。当前手动标定只适用于
单窗、首段且没有检测到机位变化的范围；变化后必须重新标定。

`conditionalGround` 只表示“若此像素确为地面接触”的平面位置及像素
扰动敏感度，不投影飞行球当作真实地面轨迹，不是置信区间；标定、镜头、
滚动快门、球半径/模糊及事件时刻误差仍未包括。近线不输出自动内外判罚，
单目不声称厘米精度或 Hawk-Eye 等级。

## 现有工作台交接

为同一输入按[媒体准备](local-editor.md#媒体与时间)建立绑定工作副本，
至少覆盖全部扫描窗。`players.json` 为当前两位选手的 id/name 数组。

```sh
python "<skill>/scripts/cv_pipeline.py" plan "<work>/vision-run/result.json" "<work>/working.media.json" "<work>/players.json" "<work>/vision-plan.json"
python "<skill>/scripts/local_editor.py" init "<work>/vision-plan.json" "<work>/vision-edit"
python "<skill>/scripts/local_editor.py" serve "<work>/vision-edit" --open
```

只创建新实验工程；计划保留全部扫描窗，每窗为暂定 CV 编号，并非一分。
复核理由包含事件时间，用户在原有完整/复核时间线播放、定位、步进。
答案、赢家、局次、发次、采用结论和批准不预填。实验窗口是内部研究
表面，不向既有比赛工程发布新一轮全场人工审核。

采用任何事件前按[原片检查](source-inspection.md#原生roi与目的限制)
提取该输入的原生 ROI / 相邻 PTS，保存观察并提升关键证据。修订现有
剪口或统计必须走原有账本、谱系、版本围栏与端点核验。未知项交回 agent，
不能用最终比分替模型补标签。完整成片导出和收尾清理仍遵守原有授权。

## 历史成片基线映射

```sh
python "<skill>/scripts/cv_reference.py" "<old-project>/project.json" "<old-export>/export.json" "<render>" "<work>/reference-map.json"
```

检查导出完成、项目 revision、fps、实际帧数、clip 顺序、trim 和 hold。
`map_label` 将旧源秒数/事件夹逼窗映射到所有保留出现位置，去除的事件、
跨 trim 的夹逼窗、统计定格不制造新事件。旧工程仅在保存的 sourceProbe
证明零起点时提供标记为条件性的 legacy 映射。不同 fps、缺 ranges 的旧
导出明确拒判，需另行验证映射。`manifest_consistent` 不证明像素对应；
须检查关键对应画面，历史记录注明 `agent_baseline`，不改称独立真值。

正例抽查可用 `cv_evaluate.py RESULT REFERENCE OUTPUT`。REFERENCE含同源
`sourceIdentity`、`referenceKind`、`points`（整数pts/timeBase与x/y）。按
原始PTS对齐，分别报告最近候选与选定轨迹在5/10/15像素内的数量、缺测
与距离；正例样本不能给出全片precision/recall。重复使用同一agent标注
不得称独立真值，未测token/复核时间为null。

图层遮挡、接缝、删除的等待/一发和截断事件记为覆盖限制。成片可以检验
当前工作流相对表现，但不能验证完整原片中等待筛除、找分召回或遗漏分。
