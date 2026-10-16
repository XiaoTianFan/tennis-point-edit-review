# 本地编辑与复核工作台

本地模式复用包内 **Courtside / Edit**。agent使用终端与JSON，用户在本机浏览器剪辑和填写集成审核表；不为比赛重写UI，不另建离线HTML或复核工程。网球判读、统计与估速仍遵循各阶段细则。

## 启动与依赖

素材、工程、答案与输出放任务工作区，不写技能目录。需要Python 3.10+、FFmpeg/ffprobe、Node 20+、现代Chromium；图形渲染需要React、React DOM、esbuild、Playwright。网页无构建步骤、CDN和第三方脚本。

```sh
python "<skill>/scripts/local_editor.py" doctor
python "<skill>/scripts/local_editor.py" media "<source>" "<work>/source-proxy.mp4"
python "<skill>/scripts/local_editor.py" init "<work>/plan.json" "<work>/edit"
python "<skill>/scripts/local_editor.py" serve "<work>/edit" --open
```

`<skill>/<work>/<source>`替换为当前任务路径，参数加引号。缺模块时在工作区独立runtime运行`npm install --prefix "<work>/runtime" --save-exact react react-dom esbuild playwright`，保留锁文件并设置本进程`NODE_PATH`。可用已装Edge/Chrome，计划指定`browserChannel=msedge/chrome`；无浏览器时在runtime执行`npx playwright install chromium`。`doctor`仅证明依赖存在，实际`init`和合成预览才证明可用。

`serve`打印带令牌回环URL并写`session.json`，保持进程运行并把URL交用户。Ctrl+C停止；重启同目录恢复工程与答案并换令牌。不绑定公网、转发端口或上传令牌。没有浏览器控制能力仍可构建工程，再请用户打开会话URL。

## 媒体与时间

`media`继承源显示分辨率、有理fps、音频采样率和声道，生成H.264/AAC CFR媒体及`.media.json`；不改原片。旋转、SAR归一，奇数尺寸补偶数，源参数保留；`--fps/--width`仅用于明确转换。`--start/--duration`为有界片段。SDR颜色保留，最终输出Rec.709；HDR先确定并验收色调映射，不静默转换PQ/HLG。

计划可写`in/out/duration/start/endSeconds`，初始化只换算一次为整数帧、左闭右开；同一边界不能同时给秒与帧。原片时间=`sourceStartSeconds+frame/fps`；VFR代理可能重采样，估速和触拍必须保留原PTS，不把代理帧当原始精度。

暂停／步进使用FFmpeg精确解码帧并叠加正式透明PNG；播放由浏览器视频帧回调实时合成，不预渲染整片。内部跳剪可能短暂停顿；最终编码音画验收须等[导出门禁](#导出与边界)开放。Source播放完整代理及原声、无图层；Edited播放当前视图。

## 剪辑计划

判赢家前按[首次标注](initial-labeling.md)准备集成列表，默认agent主导；已剪成片按[CV重建](rendered-video.md)保留完整源分段。`init`仅接受新目录；从[最小计划](../examples/local-edit-plan.json)替换示例。metadata/path相对计划解析，初始化后保存绝对路径。

| 字段 | 契约 |
|---|---|
| title/fps/width/height | 缺省由首资产继承；有理fps 1–240，偶数画幅各边≤8192；混合素材先显式统一 |
| players/assets | 当前两方id/name；稳定asset id及media元数据，核实实际帧率和帧数 |
| clips | 唯一master数组：稳定id、assetId、inFrame/outFrame、pointId与真实发球元数据；同分多段共P号 |
| hold | kind=hold、源inFrame、durationFrames，静音统计背景 |
| review | source/ledgerRevision/rows，稳定R/P、局盘、server、疑点和源定位；AI放initial，不预填人工已审 |
| overlays | id/clipId/component/props/startFrame/endFrame；anchor=source或clip，裁到可见范围；view=both（默认）/full/review |
| statistics/approval | 当前账本统计完成状态与用户确认；见导出门禁 |

理由由agent生成；阶段3仅列补查后必要疑点／问题局，全场定位用clip/P映射。[正式图形](graphics-adapters.md)经`init/update`缓存为整画幅透明PNG与哈希，预览和输出同源；模板不变，改文字须重生成。工作台处理统计页首尾约0.3秒淡变。

完整／复核视图共用一个clips数组：完整视图保留全部段；复核按rows中的P号保留其全部源段，其余暂时波纹隐藏，不复制、重剪或删除master。已剪成片不再删除失败发球、等待或尾段。计分板在两视图均可见；复核R/P、常显发球与说明仅review显示，短发次标签仅full显示。切换保留源帧锚点、各自缩放和滚动，不改答案；无复核片段时禁用review。说明放计分板上方避让。阶段5数据、阶段6图层、阶段7输出顺序见[阶段衔接](workflow.md)。

## 用户操作与agent接续

- 顶栏English/中文仅改UI。拖动面板分隔条调整布局；键盘方向键、Shift大步及Home／双击复位。时间线Ctrl/Cmd+滚轮横移，Alt+滚轮以指针缩放。
- 点审核行文字／空白或Enter/空格跳分；答案控件不触发跳转。游标定位到另一待审分时，列表自动滚动露出该行，不改焦点、答案或行序；播放和同分移动不反复拉动列表。所有行常驻，搜索仅高亮；协议见[账本](ledger-and-review.md)。
- 下方完整全片／仅复核切换视图。Edited/Source切换播放模式；Space播放，方向键±1帧、Shift±10帧、方括号逐分。拖clip边缘修剪，靠近游标8屏幕像素内吸附并高亮，Shift临时绕过；随缩放换算帧，不能越过合法源范围。入出帧框支持精确修剪；图层条可移动或改长，局部帧与源锚定帧不混用。片段重排仅改变呈现，不自动改比赛事实；复核重排保留隐藏段。
- 操作写project.json并递增revision，history保存前版，Undo/Redo保留40步。旧revision被拒后重读差异，不盲重试；未提交操作留浏览器草稿，用Recover edits交agent恢复，不覆盖新状态。
- “交给agent”写agent-context.json与review.json，保留当前clip、帧、模式和视图，用户复制消息回会话；网页不接云模型、不自动发送。`context`可直接读最新状态，不依赖先点击。

```sh
python "<skill>/scripts/local_editor.py" context "<work>/edit" --output "<work>/context.json"
python "<skill>/scripts/review_io.py" merge "<work>/ledger.json" "<work>/edit/review.json" "<work>/ledger-next.json"
python "<skill>/scripts/local_editor.py" update "<work>/edit" "<work>/updated-project.json" --expected-revision 12
```

updated-project从当前project副本修改，保留用户剪口、顺序、路径、answers和版本／R/P；不能拿初始plan覆盖。按needsRebuild回查证据、重算计分统计及图层后update，清除已处理项并留历史。纯呈现改动也先验映射和图层，不直接清提示。新增／合并／拆分审核点使用新版计划，按[谱系](coverage-and-exceptions.md)显式迁移确认事实和历史，不能静默移植分归属。

## 导出与边界

完整样片及复核片在确认前禁止渲染。UI、HTTP `/api/render`和CLI `render`共用门禁，缺字段默认锁定（含旧工程）：

- 用户通过底部控件明确确认全部分归属：approval.pointAttribution=true。
- statistics.status=complete且statistics.ledgerRevision与review.ledgerRevision一致，用户另确认approval.statistics=true。
- approval.ledgerRevision一致且needsRebuild为空；修剪、判罚或图层更改撤销确认，回填重算后重新确认。

agent不得替用户勾确认。确认前实时合成预览，允许源代理、抽帧与透明图层缓存，不导出QA样片绕过。最终门禁开放后：

```sh
python "<skill>/scripts/local_editor.py" render "<work>/edit" "<work>/new-export"
```

UI与CLI同路导出H.264/AAC MP4：逐段精准取帧、同源图形、统计淡变、剪口两帧音频淡变、定格静音，再统一换输出fps避免逐段舍入。沿用分辨率／fps／音频；可指定偶数宽高≤8192、fps 1–240、文件名与目录；比例不同时等比补边，时长误差≤半输出帧。CLI有--width/--height/--fps/--filename；UI支持Tk系统目录选择，缺Tk/桌面时填路径。输出不覆盖已有文件，保存project-snapshot.json及含帧数／哈希的export.json。最终验收内容见[画面验收](presentation-and-qa.md#验证与交付)；编码成功不等于听审或整片视觉通过。

当前为单视频顺序主轨、原速片段／静帧与七种正式覆盖层，无多机位、任意转场、混音、变速曲线或HDR；需要时显式扩展或用已认可编辑器。移动workspace后更新并核实素材路径；服务器仅服务注册资产，不开放任意文件浏览。

## Output language

project.outputLanguage与图形使用[产物语言策略](output-language.md)，UI切换独立；改产物语言要重生成图形，显式props优先。
