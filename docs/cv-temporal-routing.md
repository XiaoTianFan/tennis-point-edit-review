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
