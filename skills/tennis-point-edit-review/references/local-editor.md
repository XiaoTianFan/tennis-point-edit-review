# 本地编辑与复核工作台

没有使用ChatCut或Premiere Pro时，默认复用包内 **Courtside / Edit**，不再为每场比赛重写播放器、时间线或审核表。agent通过终端和JSON操作，用户通过本机浏览器操作；agent不需要Computer Use。比赛判读、计分、统计和估速仍依照本技能各阶段执行。

## 启动与依赖

先确定用户素材与可写的任务工作区。媒体、工程、答案和导出均存工作区，不能写回技能目录。需要Python 3.10+、FFmpeg/ffprobe、Node 20+及现代Chromium浏览器。网页自身没有打包步骤、CDN或第三方脚本；正式图形渲染另需React、React DOM、esbuild、Playwright及Chromium。

以下`<skill>`、`<work>`、`<source>`由当前任务路径替换，命令参数中的路径始终加引号：

```sh
python "<skill>/scripts/local_editor.py" doctor
python "<skill>/scripts/local_editor.py" media "<source>" "<work>/source-proxy.mp4"
python "<skill>/scripts/local_editor.py" init "<work>/plan.json" "<work>/edit"
python "<skill>/scripts/local_editor.py" serve "<work>/edit" --open
```

缺少图形依赖时，在工作区独立依赖目录运行`npm install --prefix "<work>/runtime" --save-exact react react-dom esbuild playwright`，保留生成的版本锁；设置本进程`NODE_PATH`为该目录的`node_modules`，再运行`doctor`。如无已安装可用浏览器，在该依赖目录执行`npx playwright install chromium`；已安装Edge/Chrome可在计划中指定`browserChannel: "msedge"`或`"chrome"`。`doctor`检查可执行文件和模块，实际小规模`init`才能证明图形渲染可用。不得以安装成功代替合成验收。

`serve`打印带会话令牌的回环URL，并写入工作区`session.json`；保持进程运行，把URL交给用户。终止用Ctrl+C；重启同一目录即恢复工程与答案，并生成新的会话URL。无浏览器控制能力的agent仍可完成全部构建和导出，再请用户打开该URL。不要绑定公网、转发此端口或把会话令牌上传到仓库。

## 媒体与时间

`media`默认继承源片显示分辨率、标称有理数帧率、音频采样率及声道数，生成浏览器可解码的H.264/AAC恒定帧率媒体与`.media.json`，不改原片。旋转及像素宽高比归一为实际显示画幅；奇数尺寸补至偶数，源参数保留在元数据。`--fps`、`--width`仅用于用户明确要求的转换，不把低清代理作为默认交付源。可用`--start 秒 --duration 秒`制作有界片段。SDR颜色标签随媒体保留，最终合成统一输出SDR Rec.709；HDR先确定并验收色调映射，本工具拒绝静默转换PQ/HLG。

计划可用`inSeconds/outSeconds/durationSeconds/startSeconds/endSeconds`，初始化按继承帧率一次换算并保存为**媒体整数帧、左闭右开**；同一边界不可同时提供秒和帧。已有整数帧计划保持原坐标，fps可用`30000/1001`等有理数字符串。原片呈现时间=`sourceStartSeconds + frame / fps`；VFR转CFR会重复/舍弃帧，代理帧号不等于原片帧号。估速、真实触拍及死球证据保留原片PTS/整数微秒，不能从代理帧数反推为原始测量精度。

暂停、单帧前后步进使用FFmpeg解码静帧，按原尺寸叠加正式PNG；播放使用浏览器视频帧回调与当前片段边界。浏览器连续播放在内部跳剪处可能短暂停顿，不能作为音画连续性或精确输出验收；最终FFmpeg成片单独检查。Source模式显示完整代理原声与画面，不显示成片覆盖层；Edited模式按剪辑计划播放。

## 剪辑计划

从[最小计划](../examples/local-edit-plan.json)开始，替换所有示例身份、素材与事实。`init`只接受新工程目录；素材`metadata`及`path`可相对计划文件，其余生成的媒体/图形路径保存为绝对路径。

| 字段 | 契约 |
|---|---|
| `title`, `fps`, `width`, `height` | 时间线名称；省略`fps/width/height`时由首个媒体继承，偶数画幅各边≤8192，1–240 fps；混合帧率素材先显式统一到时间线帧率 |
| `players` | 当前两方`id/name`映射；比赛身份与双打限制遵循输入规则 |
| `assets` | 稳定`id`加`media`生成的`metadata`路径；初始化核实实际帧率与帧数 |
| `clips` | 按播放顺序排列；稳定`id`、`assetId`、`inFrame/outFrame`；比赛段带`pointId/serveNumber/serveId`，同分可含多个clip，不另计分 |
| 定格clip | `kind: "hold"`、源`inFrame`及`durationFrames`；默认为静音，用于干净尾帧上的统计页 |
| `review` | `source/ledgerRevision/rows`沿用[复核输入](../examples/review-data.json)，稳定R/P、局/盘、发球方、疑点及证据定位；初始AI判断放`initial`，不预填人工已审 |
| `overlays` | 稳定`id`、`clipId`、正式`component/props`、`startFrame/endFrame`；`anchor: "source"`绑定代理源帧，`"clip"`绑定片段局部帧；自动裁到片段可见范围 |

逐分说明`review.rows[].reason`由agent依据当前素材证据生成；工作台只展示工程中的说明，加载视频不会自动生成分析。

覆盖层的属性与位置复用[正式清单](../examples/ui-manifest.json)和[图形适配](graphics-adapters.md)。源码模板不复制、不修改；`init/update`渲染整画幅透明PNG，浏览器和导出复用同一批图形及props。静态标签直接切换，其他比例采用等比居中的参考布局适配，播放器画布继承实际宽高比；统计页由工作台按当前帧率负责首尾约0.3秒淡变，不能再叠加第二份动画。文字与分数从账本重生成，网页支持修改图层时序，不声称图片内文字可直接编辑。

agent在阶段2建立主剪计划，必要复核在阶段3另建复核计划与工作区；按分保留充分证据，复核图形使用`reviewId/reviewLabel/explanation`及常显规则。工作台共用同一个播放器与复核协议，但主剪/复核仍各有明确用途，不能用主剪删去的一发替代审核证据。阶段5–7调用既有计分、统计、估速与`template_pack.py`生成正式props，再加入五页统计定格及逐发球速；示例计划不提供默认比赛结果。

## 用户操作与agent接续

- 顶栏可切换English/中文；语言与面板尺寸保存在本浏览器，不改比赛文字、图形或答案。拖动复核/预览之间、预览/时间线之间的分隔条调整布局；分隔条也支持方向键、Shift大步调整及Home或双击复位。时间线内`Ctrl/Cmd+滚轮`横移，`Alt+滚轮`以指针位置缩放。
- 左侧逐分列表点击卡片文字或空白处定位该分首个保留片段；卡片聚焦后也可按Enter/空格定位。选项随面板宽度自动换行。查看得分方、人工无法确定、死球原因、双误、多打与备注；答案控件和备注框保持独立操作，不触发跳转。所有行保持原序常驻，搜索只高亮。与独立HTML使用相同`tennis-point-review/v1`导出及pending/partial/resolved/replay/unresolved语义。
- 右侧切换Edited/Source，拖动播放条或时间线游标，按`Space`播放、方向键单帧、`Shift+方向键`十帧、`[`/`]`逐分跳转。按住clip两端修剪，拖动clip改变播放顺序；也可用入/出帧精确修剪。图层条可拖动或缩短/延长，点击后用同一数字框修改时序。局部图层帧与源锚定帧不可混用。
- 有效更改自动写入`project.json`并增加revision；`history/`保存更改前版本，Undo/Redo最多保留40步。不要用新工程覆盖旧工程或替用户清空答案。agent同时写入或另一标签页修改时，旧revision被拒绝；重读当前上下文后处理差异，不盲目重试。未提交的操作保留在本浏览器草稿中；连接失败或版本冲突时用Recover edits下载，交agent与当前工程对比，不自动覆盖较新的状态。
- **Send to agent**保存`agent-context.json`、`review.json`与当前片段/游标，给出可复制消息和完整JSON；用户自行粘贴到agent会话，网页不连接云端模型、不自动发送消息。单独导出的JSON也可交给现有`review_io.py merge`。

```sh
python "<skill>/scripts/local_editor.py" context "<work>/edit" --output "<work>/current-context.json"
python "<skill>/scripts/review_io.py" merge "<work>/ledger.json" "<work>/edit/review.json" "<work>/ledger-next.json"
python "<skill>/scripts/local_editor.py" update "<work>/edit" "<work>/updated-project.json" --expected-revision 12
python "<skill>/scripts/local_editor.py" render "<work>/edit" "<work>/new-export"
```

`context`直接读取最新持久化状态，不依赖用户先点按钮。`updated-project.json`从**当前project.json副本**修改，保留用户剪口、顺序、映射及素材路径；不能把最初plan直接覆盖回来。先按[依赖重算](workflow.md)处理`needsRebuild`，再用原计分/统计/估速工具重算受影响事实和props。`update`保留用户answers、source、ledgerRevision和R/P映射，重新渲染图形并以预期revision原子提交；成功后清除待重算项，保留历史并开始新的Undo边界。发布另一轮审核或增删分时另建有版本的新计划，显式沿用已确认事实。

修剪会标记证据与时序待查，重排标记呈现顺序待查，答案变化标记计分/统计待查。重排只改变呈现，不能自动重排比赛事实。未处理这些变化仍可直接导出；界面仅提示计分板、统计或图形时序可能与用户编辑不一致，导出报告保留待查项。不要为消除提示而直接清空`needsRebuild`；确认没有事实影响的纯呈现修改也需检查图层与源映射后通过`update`提交。

## 导出与边界

Export video提供分辨率预设和自定义宽高、整数或有理数fps、文件名、目标目录及系统文件夹选择器。默认沿用当前时间线；输出变化不修改工程帧坐标或证据，整条合成后一次换帧率以避免各剪口累积舍入，输出时长误差≤半个输出帧。宽高不同比例时等比补边，图形随视频一起缩放。支持偶数尺寸各边≤8192及1–240 fps；音频沿用工程采样率与声道数。系统选择器使用Python Tk（Windows/macOS原生对话框，Windows启用逐显示器DPI感知）；缺少Tk或无桌面时可直接填路径。终端`render`同样接受`--width/--height/--fps/--filename`。不覆盖已有文件，请换名后导出。

Export video与终端`render`使用同一路径：逐段精准取帧、同源PNG合成、统计淡变、剪口两帧音频淡变、定格静音，然后输出H.264/AAC MP4。输出文件写入用户选定目录；每次在工程内使用新的渲染工作目录，保存`project-snapshot.json`与带帧数/哈希的`export.json`；不能只验证PNG、忽略最终视频。至少检查发球前后、大小标签同帧退出、分界、五页统计、定格接点、原声及起止帧；确认总帧数、时长和有效音轨。两帧音频淡变不代替人工检查剪口声音。

当前实现为单视频主轨、顺序拼接、原速片段与静帧、七种正式覆盖层；不含多机位、任意转场、音频混音、变速曲线或HDR。需要这些能力时明确扩展计划或选择用户认可的编辑环境；不要静默丢失特性。源文件、代理和workspace一并移动后需更新路径并验证；本地服务器仅服务已注册素材和图形，不提供任意文件浏览。
