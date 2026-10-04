# 图形层与编辑层分别选择

正式视觉语言仍来自[清单](../examples/ui-manifest.json)与[七个模板](visual-templates.md)；网球逻辑不绑定React、Remotion、MOGRT或某个agent。转换的是表现格式，不是计分、统计、发次或复核语义。

| 实现 | 适合 | 可编辑性与验收 |
|---|---|---|
| ChatCut参数化组件 | 已连接ChatCut且可实例化模板 | 检查实际属性、自然尺寸、实例覆盖值和渲染画面 |
| Pr原生图形/MOGRT | 计分板、发次、球速、复核编号/常显信息 | 暴露姓名、分数、发球方、文字等属性；必须导入、修改、读回、保存重开及渲染验证 |
| 透明PNG + Pr原生透明度 | 静态状态和五页复杂统计 | 图像保留设计，Pr控制时序/淡变；改文字须从同一数据再生成 |
| alpha视频/PNG序列 | 未来含复杂运动的模板 | 检查alpha解码、帧率/帧数、预乘边缘、色彩及首尾；不能把普通H.264视为带透明通道 |

Pr默认推荐混合：原生可编辑的简洁图形 + 正式JSX渲染的统计。若当前host/template未通过native属性测试，明确该项待验；临时全栅格化须说明可编辑性取舍，不能伪装成完成混合验收。无需为格式转换复制另一套统计算法。

## canonical JSX → PNG

`scripts/render_overlays.cjs request.json new-output-directory`读取包中源代码和哈希，使用本地React/esbuild/Chromium渲染整画幅RGBA PNG；不连接Pr，不上传媒体。依赖为`react`、`react-dom`、`esbuild`、`playwright`及其本地浏览器；在任务工作区安装并记录版本，通过Node模块搜索路径提供，不能要求用户一定安装Codex插件。

输入为`{canvas:{width:1920,height:1080},entries:[{id:"score-before",component:"scoreboard",props:{...}}]}`。属性仅允许清单声明的字段；`placement`为1080p参考坐标，`naturalHeight`可增高长文，`frame`为模板自身帧。其他16:9尺寸等比映射；非16:9应另做明确布局适配。Windows可在已安装的情况下指定`browserChannel:"msedge"`或`"chrome"`。输出目录必须新建，避免覆盖旧版本证据。

PNG画布透明不等于`transparentBackground=true`。保持默认深蓝面板；该属性会改变组件本身底色，而且并非七个组件都有该属性。渲染器使用`omitBackground`去除画布背景，保留模板的面板和文字。

统计默认渲染稳定帧9，输出清单另存透明度包络：本页帧0/9/末前9/最后帧对应0/1/1/0。一页时长来自当前fps下的8秒。只选一个动画负责人：Pr关键帧或已带动画的视频；不要二次淡入淡出。计分板/标签不在每次状态切换或内部剪口重启动画；同分R/P连续。

输出`render-manifest.json`保存模板版本、代码与PNG哈希、props、尺寸、位置、溢出诊断和可编辑性。溢出诊断只是线索，不能代替读图；字体替换、中文/长姓名、11行统计页、底注及真实合成仍需验收。渲染器不嵌入字体，需记录实际可用字体。

## Native MOGRT契约

MOGRT是实际模板文件，不是React JSX换后缀。模板可以由Pr创作并导出，也可以由AE创作并暴露Essential Graphics属性。旧版Pr应使用与其兼容版本创作的模板；不能默认新版AE输出可在旧版Pr打开。使用[Adobe官方创作说明](https://helpx.adobe.com/after-effects/desktop/motion-graphics/work-with-motion-graphics-templates/creating-motion-graphics-templates.html)。AE用于模板制作，不应默认每位终端agent用户都安装AE。

每个native适配记录：模板ID/版本/哈希、最低实际验证host、画幅、字体、逻辑组件、暴露属性名/类型/默认值及持续帧数策略。计分板至少映射姓名、局分、小分、发球方及顶部赛制/P号；标签映射文字/估值标识/单位；复核模板映射稳定R/P、阶段、局次、发球方、发次。采用相同颜色、字阶、位置、紧凑尺寸和状态切换语义；native字形栅格化可能与Chromium不同，不承诺逐像素一致。

`node scripts/make_mogrt.cjs new-output-directory PostScriptFontName`可生成`build-native.jsx`与`native-manifest.json`，覆盖scoreboard、serveLabel、serveSpeed、reviewId、reviewLabel五种。在空AE工作区中运行该创作脚本，成功时输出`.aep`、`.mogrt`和生成日志；Windows可由开发者通过已验证的AE `-r`入口或用户运行脚本完成，不能把Adobe脚本交给Node。生成器保护已打开的AE工程；字体用实际PostScript名称。此适配是待host验证的native近似，不能替代七组件的正式JSX，也不宣称已通过AE/Pr执行。

这些MOGRT自然时长120秒、30fps；在序列中调整每个实例实际in/out，并读回，不按自然时长显示120秒。字段映射保存在清单；发球点用serverAOpacity/serverBOpacity（0/100），reviewLabel的serverText由serverPrefix+serverName同源装配。若需其他色彩/字体可编辑控制，必须在模板中明确暴露并补测；当前生成器只暴露文字和发球点，不能宣称所有样式参数都已可编辑。图形锚点/缩放按host实际尺寸放置并检查。

不要按英文界面或固定效果索引定位参数；先枚举当前模板暴露的属性并建立映射。AE文本可能返回结构化文本值，应保留样式和Unicode；写后读回并看实际帧，不能仅靠`setValue`的返回值。未知属性结构应停止该实例写入，不猜字符串替换。新模板自然时长可能覆盖请求duration，必须读回实际终点。避免通过未经验证的QE操作维持基础工作流。

由同一账本生成不同状态实例；不得在MOGRT表达式内另行推进比分。更改原生实例中的文字后，应把合法人工修正同步回计划；若涉及球果，仍回到证据/计分流程，不能只修图。模板变动应版本化并与七种视觉职责做对照测试；保留canonical JSX，不能以新增native变体为由删除它们。
