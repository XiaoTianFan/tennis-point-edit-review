# 原片检查工具

用于阶段1精剪及后续补查，证据存入内部log；ChatCut、Pr与本地流程共用，不改变[判读](adjudication.md)和[覆盖](coverage-and-exceptions.md)规则。优先复用可用的媒体查看能力；以下终端工具帮助agent取得证据，不自动识别得分，也不要求用户逐帧标注。

## 按问题取证

| 要回答的问题 | 取证方式 |
|---|---|
| 全片结构、身份、机位或光线变化 | 分批全幅概览，保留场外参照；局部裁切另附原图 |
| 候选发球及归组 | 扩到前一分结束和发球间隙，结合球、双方动作及可用原声 |
| 重抛/触拍、首次落点/死球 | 直接查事件前后连续原帧；必要时向前后扩窗，不重复依赖同一稀疏摘要 |
| 漏分或局界矛盾 | 回查相关整局和相邻间隙，包括检测器未命中的范围 |

5秒概览、1秒定位、0.5秒观察、0.25秒附近定位可作起点，不是固定阶梯或充分性标准；短事件可直接逐帧。原图中的远端球太小时提高图幅或另作裁切，不能靠增加小缩略图数量代替可辨认证据。抽帧成功只表示已提取；覆盖记录的reviewed由agent实际检查后填写，并在reason注明检查方式、证据清单和仍缺的事件，不把采样概览算成连续观察。

## 可直接运行

路径均来自当前任务；输出放任务工作区的新目录。采样/连续帧需要OpenCV与NumPy；时间检查需要ffprobe。分批采样限制资源占用，可按原时间窗继续下一批，不把分批边界当分界。

```sh
python scripts/source_inspect.py SOURCE 0 120 WORK/overview --step 5
python scripts/source_inspect.py SOURCE 20 35 WORK/detail --step 0.5 --roi x,y,width,height
python scripts/frame_evidence.py SOURCE 23 26 WORK/contact --no-candidates
python scripts/media_probe.py SOURCE WORK/timing.json
```

`source_inspect`输出分页联系表、每张全幅原图和`samples.json`：源哈希、请求/实际解码时间、帧号、寻址误差及裁切/缩放。缺帧或不可用时间戳单列，不静默补图；只有已提取范围可供检查。图上的时间来自decoder POS_MSEC，精确触拍/估速仍须核对原片PTS，代理不能增加原始精度。`frame_evidence`保留原短窗接口，`--no-candidates`仅关闭候选标记。

## 可选CV配置

先在当前片段已目视确认的正例及易混淆反例上检查，再决定是否使用。球色、大小、运动阈值、ROI随素材与机位/光照变化调整；可从新原帧取样，不能沿用另一场球色或把某种场地配色当通用标准。若不能提高定位效率，关闭候选继续视觉检查，不把完成检测器开发作为开工条件。

`frame_evidence`提供`--hsv-low H,S,V`、`--hsv-high H,S,V`、`--motion-threshold N`、`--max-area N`和`--max-span N`；HSV使用OpenCV的H=0–179、S/V=0–255。证据JSON保存配置、各帧实际大小限制及颜色/运动/ROI过滤后的像素数、接受/排除的连通区域数。零命中应检查各过滤阶段与原图，不能自动归因为球色错误或没有球；候选数量不等于发球或得分数量。对手出画/静止不能单独排除一分；双方出现、球路密集也不能单独排除练习。分类仍由上下文证据决定。

## 原片时间检查

`media_probe`流式检查全部视频帧的PTS，记录time base、间隔分布、缺失/非递增PTS、源哈希及音视频stream元数据。`cfr`表示某个报告帧率与全部PTS在一个time-base tick内一致；`variable_or_discontinuous`需继续诊断；证据不足为`unknown`。它不数重复画面，也不把转码产生的dup/drop说成原片丢帧。

Pr交换可加`--probe-media`核对实际视频时间、尺寸和帧数并将报告收入交换清单；原`--check-files`仍只检查文件存在。已有可信、同源哈希的完整检查可复用。VFR/未知不能借改写`timing=cfr`通过；按[Pr时间约定](premiere-pro.md)选择显式标准化或已验证的host路径，保留原证据和映射。未实测导入、合成和声音仍按原验收执行。
