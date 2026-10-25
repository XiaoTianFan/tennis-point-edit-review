# 可选视觉证据管线

默认仍为 `agent-dominant`，完整检查、判分、统计与复核规则不变。
仅在用户选择 CV 辅助或研究路线时运行本接口。它提供可复现的观察与
待核候选；agent 阅读结构化结果、回看原生证据并处理缺口。有界接口提供
窗口复核；流式接口提供全长球检测观察与恢复。两者都不支持无人审核的
全场找分、自动判线或自动技术统计。

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

### 全长WASB观察与恢复

`cv_stream.py`处理完整输入流，按真实PTS保存球候选。它不读取历史答案，
不生成分组、赢家或技术统计。流式结果使用下文的全源事件复核入口；
有界结果使用窗口计划生成器。事件判断与逐分采用保持独立。

需另行提供已检查来源的[官方WASB实现](https://github.com/nttcom/WASB-SBDT)
中的`src/models/hrnet.py`、`src/configs/model/wasb.yaml`及官方网球权重。
模块路径会执行本地Python代码；只从已核实来源选择。权重按
`weights_only=True`加载，必须含`model_state_dict`；源码、配置、权重哈希
全部记录，不自动下载或随技能包分发。Python依赖同上，额外选择兼容的
PyTorch/CUDA；FP16仅在CUDA使用，不改变全局环境或其他服务。

```json
{"module":"/absolute/wasb/src/models/hrnet.py",
 "modelConfig":"/absolute/wasb/src/configs/model/wasb.yaml",
 "weights":"/absolute/models/tennis_best.pth.tar",
 "device":"cuda","half":true,"batch":4,"threads":4,
 "chunkFrames":1800,"maxFrames":1000000,"threshold":0.5,"crops":[null]}
```

```sh
python "<skill>/scripts/cv_stream.py" "<input>" "<work>/stream-run" --config "<work>/stream-config.json"
python "<skill>/scripts/cv_stream.py" "<input>" "<work>/stream-run" --config "<work>/stream-config.json" --resume
```

`crops`最多4个视图，`null`为全幅，其余为原生像素`[x,y,width,height]`。
裁切视图坐标映射回原图并保留view编号；多视图候选未经融合，不能合计为
多个真实球。RGB仿射512×288、ImageNet归一化、连续3帧输入/3帧输出；
最后不足3帧仅重复上下文，记录`paddedContext`，不制造新观察或插值球。
网络响应不是存在概率。每个视图超过1024个连通候选会明确报资源错误。

`chunkFrames`须为`3*batch`的倍数。执行器只保留一批预处理图像与一个块
的数值结果；提交块有SHA-256、起止PTS和帧数。`state.json`记录进度与每次
执行的成本；只有读到完整流尾、覆盖检查完成才发布`result.json`。
`--stop-after-chunks N`在本次N个块后保存检查点，不声称完成。

恢复先核对源、配置、代码、外部模型和已提交块，再定位最后已提交PTS，
确认它仍存在后处理后续每帧。配置或源变化须新建run；不能混用结果。
中断的未提交数据可保留在目录中，但不计入有效观察，不自动删文件。
同run不允许同时执行。`failed/interrupted/checkpointed`都不是完成；达到
预算、解码、模型或指纹错误会保留具体错误及最近已提交进度。

逐帧记录在`result.json`列出的`chunks`文件中；必须按该列表读取并校验
哈希，不能把目录里未提交文件加入结果。完整帧覆盖不是可见球召回，
检测成功不代表事件、统计、复核成本或生产验收通过。

### 同次解码的人体观察

全长配置可以显式增加`players`，在球观察旁保存独立人体框与17个COCO
关键点。需在任务隔离runtime中安装兼容的外部Ultralytics（已测试
8.3.239）及PyTorch/torchvision；第三方依赖与模型不随技能分发，使用前
核查其授权。不得因缺此依赖阻塞默认agent路线或仅球检测模式。

```json
{"players":{"weights":"/absolute/models/pose-state.pt",
 "architecture":"/absolute/models/pose-state.json",
 "device":"cpu","half":false,"stride":6,"inputSize":640,
 "threshold":0.15,"nmsIoU":0.7,"maxDetections":32,"crops":[null]}}
```

此对象合并到上方WASB配置；仍使用`cv_stream.py`命令。权重必须是预先
核实来源的纯Tensor state_dict，`weights_only=True`严格加载。
架构JSON含`stateSha256`和`architecture`，前者须匹配权重，后者为经过
来源审查的Ultralytics PoseModel定义；本接口不转换任意pickle，也不
接受未知来源的可执行架构定义。仅支持单类person、17×3关键点输出。
模型输入为RGB、等比缩放、32步长letterbox及114填充、0–1归一化，所有
坐标映回源编码像素，低响应关键点不删除、不当作已验证位置。

`stride`按实际源帧序号采样，VFR时不等于固定Hz；其余源帧仍保存球观察
及`playerObservations.sampled=false`。采样帧中的空检测数组表示本次未
检出，不能与未采样或确实无人混同。每项保留view、crop、边缘截断和
未校准响应；超过`maxDetections`的NMS结果数量记在该视图的
`omittedByResourceLimit`。多视图人体不自动融合为同一人。

`playerObservations`使用`tennis-player-frame/v1`，继承同一外层源PTS、
画幅和坐标空间。检测ID绑定帧/view，`playerId/trackId`为null，场端及
惯用手为unknown，`associations/motions`为空。人体框与关键点没有建立
球员身份、正反手/旋转、米制位置或触拍关系，后续推断和采用须另列证据。
未确认的人体观察不进入计分、技术统计或校准真值。

球与人体共用一个解码器；已采样帧的RGB转换在两后端间复用，缓存随该帧
释放。独立保留人体的采样/检测数、预处理/推理/后处理耗时；这不等于
完整流程或人工复核成本。人体配置、架构、权重、实现与运行时加入恢复
围栏；变更后新建run，不拼接旧块。无需人体观察时省略`players`。

CPU使用FP32；CUDA不可用会明确报错，改为`device=cpu,half=false`并新建
run，不静默改变已提交运行的后端。每个CLI进程使用run内的离线设置
目录，不下载模型、不启用Hub/同步；若外部包已在别的设置环境加载，须
使用新进程。当前实测按设备分别记录，Windows结果不能当Mac验证。

### 有界接口的观察层

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

### 全源事件复核

完整流式结果可配合显式事件提案交给`cv_review.py`。提案文件使用
`schema=tennis-vision-proposals/v1`、`status=complete`、同源`sourceIdentity`
及流式result文件的`streamIdentity.sha256`。`events`中每项含唯一`id`、
`kind`（`racket_contact/bounce/serve_onset/dead_ball/other`）、
`side`（`near/far/unknown/null`）、有理数`seconds`、`adjudication=null`；
可附`intervalSeconds=[起,止]`及模型支持证据。导航秒数必须是已经提交的
实际源PTS；支持窗须包含该秒数，不把窗宽当时刻精度或置信区间。
推断器需另行提供：球观察结果不自动成为这些事件。

```sh
python "<skill>/scripts/cv_review.py" "<work>/stream-run/result.json" "<work>/proposals.json" "<work>/working.media.json" "<work>/players.json" "<work>/vision-plan.json"
python "<skill>/scripts/local_editor.py" init "<work>/vision-plan.json" "<work>/vision-edit"
python "<skill>/scripts/local_editor.py" serve "<work>/vision-edit" --open
```

工作副本须覆盖完整流。生成器核对源/提案/工作副本身份、提交块哈希与
PTS，再创建保留全源的一个连续段，`purpose=vision-events`，不制造P号。
点击候选定位，记录事件类型、场端、判断、工作副本复核帧与原生证据引用；
VFR或重新采样时，工作帧号不是原片帧号，精确事件时刻仍依据原生PTS。
保存、撤销、重做和重开均保留独立`visionAnnotations`；跨行保存和语言
切换保留当前页未保存输入，关闭页面前仍须保存。`reviewSeconds`只计
选中事件时页面可见的停留时间，不证明注意力、真实agent耗时或token成本；
自动验收的停留时间须从效率评价剔除。

“交给agent”与下载输出源绑定`visionReview`，工程目录另存
`vision-review.json`；命令行`context`也含同一结构。它们不改变逐分答案、
技术统计和用户批准，事件复核工程不能确认整场归属/统计。需要将已核实
事件用于现有比赛时，仍按规范账本、证据和版本围栏单独采用。

### 可选末段向前核验

有末段检查需求的事件可附`terminalWindow`，其余事件表单保持原样：

```json
{"schema":"tennis-terminal-window/v1",
 "anchor":{"kind":"visual_discontinuity","seconds":"401/20"}}
```

把此对象放在事件的`terminalWindow`字段，同时提供源有理秒数的
`intervalSeconds=[起,止]`。区间包含事件定位时刻和锚点；事件不得晚于锚点，
整个窗口须位于绑定源内。锚点类型为`candidate_next_serve`、
`visual_discontinuity`、`recording_end`或`manual`。下一发和剪口只提供检查
位置，不证明已死球；`recording_end`必须匹配完整流的最后实际PTS。
动作示例与末段检查使用不同事件ID，避免混用判断状态。

表单的末段状态对应独立`visionAnnotations[eventId].terminalReview`：

| 状态 | 所需观察及含义 |
|---|---|
| `pending` | 待核，可保存未完成输入，不确立终局 |
| `continuation` | 最后观察到活球、向前检查范围及明确仍有有效延续；排除本次死球候选 |
| `cessation_only` | 明确停止且未见继续比赛，检查范围晚于活球；首次死球区间保持null |
| `verified` | 活球→首次死球区间→更晚向前证据的有序源时间，原生序列引用及明确停止/无延续 |
| `source_truncated` | 活球后到达明确源缺口，无法确立停止或精确死球，保留不确定 |
| `not_play` | 图文、非比赛画面等，不携带活球或死球断言；排除本次候选 |

非待核记录须有观察说明、记录者`actor={role:agent/owner,id}`和
`observedThroughSeconds`；涉及比赛的记录还需`lastLiveSeconds`。
`firstDeadBallWindowSeconds=[起,止]`只在精确死球状态使用；可填
`sourceGapSeconds`说明已检查到的缺口。所有时间使用源秒，支持小数及
分数，存储归一为有理数，须在绑定窗口内。记录者角色是本地声明，既不是
身份认证也不是整场用户批准。Agent不得代用户声明观察。

`sampling`区分`navigation`、`sampled_native`、`continuous_playback`和
`mixed`。精确死球必须用`sampled_native`或`mixed`，附非空
`nativeEvidence`；连续播放本身不能代替原生精确序列。界面使用证据引用
框填入这些引用，并从死球区间中点定位工作帧；工作帧不替代原生PTS。
引用字符串只记录出处，接口不验证文件内容或图像是否实际阅读；Agent须
先按[端点检查](endpoint-checks.md)读取序列，并保留实际采样PTS和观察。
跨缺口不能确认此前的停止或延续，也不能把缺口两侧拼成首次死球区间。

“播放末段检查窗口”按绑定区间播放并在终点暂停；其他定位取消该范围。
状态决定事件判断：延续/非比赛为排除，停止未定位/源截断为不确定，精确
死球为已核实。与当前状态不相容的时间输入在界面禁用，不作为该状态提交。
保存、撤销、重做、重开和JSON交接保留完整观察及`terminalStatusCounts`。
`adoptedForBoundaries/Scoring/Statistics`均为false；本记录不自动修剪、
判赢家、增加统计或批准输出。已有成片仍保留全部源帧和用户剪口。

### 可选动作示例与档案

全源事件可以附`motionExample`，把少量动作片段放进同一复核页。每项指定
`profileId`、`recordingGroupIds`、原源有理数`intervalSeconds`及可选
`suggested`标签；区间须包含事件定位时刻并处于绑定源范围。录制组表示
同一拍摄/比赛的关联来源，原片与不同成片不能因文件哈希不同便冒充独立组。
示例区间应覆盖完整校准短片；不把单个触拍帧当作校准片段的全部范围。

标签分为`playerId`、`handedness=left/right/unknown`、
`family=forehand/backhand/overhead/serve/unknown`、
`form=groundstroke/volley/smash/serve/unknown`和
`spin=flat/topspin/slice/kick/unknown`。正反手切削、正反手截击、高压和
发球分别组合记录；未知惯用手不在这个观察契约内默认补成右手。动作家族
和击球方式须相容，证据不足的旋转/身份保留未知。

页面支持`agent_proposed/agent_observed/owner_confirmed/unknown/skipped`，
保存确认者角色及标识、观察、证据和页面可见停留时间。Agent记录不得选择
用户确认；只有用户实际确认才能如此标记。角色是本地声明来源，接口并非
身份认证系统。未知或跳过不阻塞其他事件；保存示例不会采用比分、统计或
训练标签。观察与用户确认分别显示，不能用测试自动点击制造实际确认。
“播放示例片段”从绑定区间起点播放，到区间终点自动暂停；其他定位或播放
操作取消这次片段范围。原生触拍/判线仍须单独取证，工作副本帧不是源PTS。

给已有候选追加或修订示例，使用含上述字段的JSON及当前工程revision：

```sh
python "<skill>/scripts/cv_profiles.py" attach "<work>/vision-edit" EVENT_ID "<work>/example.json" --expected-revision REVISION
python "<skill>/scripts/cv_profiles.py" export "<work>/vision-edit" "<work>/motion-profile.json"
```

追加/修订有版本围栏；改变示例片段或档案会清除该示例旧判断，工程历史仍
保存旧版。撤销/重做一并恢复片段定义与判断。导出`tennis-motion-profile/v1`
包含工程revision、源身份、片段、建议和独立判断；`context`及交接输出中
的`visionReview.motionProfile`相同。不自动训练、下载模型或从一例推定全场。

在适应实验前，用`split`保存支持/查询隔离记录。查询JSON为含`id`、
`sourceIdentity.sha256`、`recordingGroupIds`、`intervalSeconds`的片段数组：

```sh
python "<skill>/scripts/cv_profiles.py" split "<work>/motion-profile.json" "<work>/query-clips.json" "<work>/query-split.json" --mode session_assisted --context-seconds 2
```

`unseen_recording`排除全部重叠录制组；`session_assisted`排除同源校准片段及
双方模型时序上下文，同组不同导出因缺时间映射而整体排除。未知/跳过的
已看示例也在排除范围内。上下文秒数须覆盖实际特征提取和时序模型感受野，
不是固定默认2秒。此检查依赖真实录制分组及完整片段范围，不代替数据
出处核验。冻结协议后才读查询标签；计入选例、确认、训练与后续复核成本。

### 有界窗口计划

为同一输入按[媒体准备](local-editor.md#媒体与时间)建立绑定工作副本，
至少覆盖全部扫描窗。`players.json` 为当前两位选手的 id/name 数组。

```sh
python "<skill>/scripts/cv_pipeline.py" plan "<work>/vision-run/result.json" "<work>/working.media.json" "<work>/players.json" "<work>/vision-plan.json"
python "<skill>/scripts/local_editor.py" init "<work>/vision-plan.json" "<work>/vision-edit"
python "<skill>/scripts/local_editor.py" serve "<work>/vision-edit" --open
```

此窗口入口只创建新实验工程；计划保留全部扫描窗，每窗为暂定 CV 编号，并非一分。
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
