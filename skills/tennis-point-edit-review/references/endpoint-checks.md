# 连续原片的端点检查

阶段1及任何剪口返工，按[下一发锚点与正向核验](adjudication.md#首次死球与剪口核验)检查每个保留的比赛片段，包括同分let或二发；不要求先判赢家。用户已剪输入保留全部原帧和剪口，不套用重新裁尾流程；统计定格不属于比赛端点。

内部记录使用当前工程生成绑定，CLI先核对所用原片SHA-256与时钟，填完观察后检查；新建模板不覆盖旧文件，重剪只更新已重新检查的行，不把旧观察整体重新绑定来清除报错：

```sh
python scripts/endpoint_audit.py WORK/project/project.json --template WORK/endpoints.json
python scripts/endpoint_audit.py WORK/project/project.json --evidence WORK/endpoints.json
```

外部编辑器用同结构的assets、fps、clips源映射快照运行；inFrame/outFrame为工作源CFR帧，不是输出时间线累计帧。每个视频clip必须有一行，pointId可以重复，不能将一发／二发／let各计一分。

| 字段 | 填写依据 |
|---|---|
| binding | 工具生成当前assetId、pointId、inFrame/outFrame、原片SHA-256、originSeconds、timeBase、fps；源身份、归组、剪口或时钟变化后重新核验 |
| anchor | kind=next_serve、recording_end或source_gap，sourceSeconds为较晚锚点；next_serve另记relation=same_point/next_point/unknown，其他锚点写reason。锚点必须在可检查的工作源范围内；有界代理不冒称录制结束 |
| lastLiveSeconds | 最后已观察到仍在比赛的原片时间；不是最后挥拍的默认别名 |
| endWindowSeconds | verified时填写首次死球夹逼窗[较早,较晚]；不确定时为null，不伪造精确时间 |
| retainThroughSeconds | 必须出现在保留片段中的最后证据／必要反应帧时间；uncertain时覆盖确已停止比赛的上下文 |
| forwardWindowSeconds | 实际正向检查的原片范围，从lastLiveSeconds之前或当时开始，越过实际剪口；只有已到录制末端／源缺口才允许止于剪口 |
| continuationFound | 明确查过拟删部分后填false；发现仍可合法回球或漏落点则先修复，不能填false绕过检查 |
| status / cessationObserved | verified已定位死球；uncertain未定位精确死球但已观察停止比赛，cessationObserved=true；source_truncated录制中断，保留至可用边界。模板pending不能交付为完成 |
| reason / evidence | 简述看到的终结事件或具体缺口；evidence为已保留观察／证据文件路径列表，相对endpoints.json或绝对路径；不引用将被回收的唯一证据 |

所有Seconds字段均为**原片绝对PTS秒数**，可以写有理数字符串；工作源帧f对应originSeconds+f/fps。精确事件用[原生ROI／PTS](source-inspection.md#原生roi与目的限制)，不能混入剪辑时间线秒数或把VFR原帧号除以名义fps。证据窗不必是单个抽帧批次，连续批次应重叠核对。

剪口为左闭右开：原帧证据对应工作网格帧e时，outFrame必须大于e；事件或必要反应恰好等于outFrame的时间仍会被截掉。按观察的不确定度和反应需求向后保留，不用固定几帧代替核验。

检查覆盖全部当前视频片段，核对绑定、时间顺序、出点后的检查与证据文件存在。checksPassed=false时修复再查；checksPassed=true而complete=false时只可交付带provisionalClipIds的保守剪辑和具体限制，继续后续取证，不宣称全部死球已核实。记录与程序都不能证明视觉判断正确，也不更新比分、人工答案或新增导出批准点。交付前实际播放源片与编辑片段的尾部，确认保存的剪口确实生效。
