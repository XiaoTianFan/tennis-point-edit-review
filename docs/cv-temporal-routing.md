# 时序候选与复核路由实验

`tools/cv_temporal_routes.py` 是仓库内可重复运行的研究工具，尚未进入
分发技能的默认或可选运行链。它读取已提交的 `cv_stream` 球观察和显式
源帧窗口，保留各视图独立轨迹，用分段线性与平滑二次拟合的差异定位
轨迹突变。输入候选、原始PTS和支持观察ID保留，不插值制造球观察。

同视图关联要求时间连续且空间相容；匹配竞争不足以区分时拆开轨迹。
持续小范围响应只标记为 `stationaryResponse` 并保留完整观察，不据此
认定为旧球。配置中的 `netProjectionBox` 只描述源像素矩形，落在其中的
候选标记为网面/地面深度待核，不能直接判触网、死球、发次或得分。
所有语义自动采用均为0，源片段和发球尝试不转换成有效分母。

运行需要Python和NumPy，可使用任务隔离runtime。四个参数均显式提供：

```text
python tools/cv_temporal_routes.py --stream STREAM_RESULT --windows WINDOWS_JSON --config CONFIG_JSON --output NEW_RUN_DIRECTORY
```

`windows` 包含与流式结果一致的 `sourceSha256` 及 `windows` 数组；每项
含 `id/startFrame/endFrameExclusive`，窗口不得重叠或越界。配置键及默认
阈值在工具的 `DEFAULTS` 中；可省略网区矩形。输出目录必须不存在。
工具在预测前保存代码、输入和参数哈希，并核验流式结果列出的每个块。
`predictions.json` 的 `status=complete` 才表示本轮路由完成。

实验先冻结假设、阈值、调整片段和比较片段，先保存比较片段的原始预测，
再开展独立参考判读。比较窗口可以有已知粗导航，须披露既往曝光，不能
冒称盲测；修改阈值后保留原轮结果，并换用未参与本次调整的开发片段。
连续原生帧的碰撞参考与不确定区间分开记录，多视图重复候选不能制造
额外真值。报告漏检、误报、不可观察、静止路径误排和实际修正量。

`proposedReviewIntervalsSeconds` 只是建议检查范围。无候选窗口明确回退，
有候选仍需遗漏审计；范围变短不等于工作量降低。分别计参考标注/研究、
冷启动上游推理、缓存读取、路由计算、实际引导复核及用户确认成本。
完整人工精读用于建立参考，不作为混合流程效率改善的证据。缺少同品质
配对操作时间或token时留null；零语义自动采用不能当作自动准确率通过。

针对性检查：`python -m unittest discover -s tools -p test_cv_temporal_routes.py`。
覆盖平滑球路、静止竞争响应、网区歧义、缺帧、跨视图保留和非法输入。

独立参考冻结后，用 `tools/cv_temporal_evaluate.py` 比较原始候选：

```text
python tools/cv_temporal_evaluate.py --run RAW_RUN_DIRECTORY --reference FROZEN_REFERENCE_JSON --windows WINDOWS_JSON --output NEW_EVALUATION_JSON
```

参考格式为 `tennis-temporal-route-reference/v1`，包含 `sourceIdentity`、
`priorPredictions.sha256`、`segmentIds`、`events`、`unknowns` 和
`observableIntervals`。事件提供唯一 `id`、`segmentId`、`event`、
`frameBracket`、`intervalSeconds`；实际原帧可用 `sourceFrames` 附带
`ordinal/pts/timeBase`。不确定区间和可判区间同样提供片段ID与源时间区间。
可判区间必须由连续原生证据支持，不能把稀疏导航或未读区域标成负例。

比较器验证源身份、冻结预测与窗口哈希，以有理数保留PTS精度；50ms容差
内执行最大匹配数的一对一配对。同一事件的额外候选单列重复并计入候选
精度分母。没有匹配的候选按未决参考、明确可判区间和未充分判读区间
分开记录；只有可判区间内才能认定误报。已知事件即使位于路由窗口外，
仍保留为漏检并注明窗口遗漏，不从召回分母移除。输出文件不可覆盖。

`knownEventTimingRecall` 只针对已知可观察事件；
`adjudicatedCandidateTimingPrecision` 只针对可判候选。仍有未决或未充分
判读候选时，整体精度为null。时间命中不独立验证球身份、碰撞语义、赢家
或统计；配对操作成本也保持独立。检查命令：
`python -m unittest discover -s tools -p 'test_cv_temporal*.py'`。
