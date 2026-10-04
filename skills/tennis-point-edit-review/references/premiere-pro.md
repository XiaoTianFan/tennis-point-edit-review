# Premiere Pro：终端agent的一级编辑分支

本分支不要求Computer Use、鼠标、键盘模拟、屏幕坐标或Codex/Claude专属工具。运行中的Pr + 已配置本地桥是编辑能力；terminal agent通过MCP stdio、已验证插件的命令/响应文件或其本地API操作。用户的首次host安装/激活与后续无人点击运行分别记录。

## 版本分支

| Host | 主通路 | 注意事项 |
|---|---|---|
| 旧版，例如Pr 23.5 | CEP面板 + ExtendScript DOM；FCP7 XML批量建序列，MOGRT/属性/导出由桥处理 | 不加载UXP API，不把React JSX当Adobe脚本；验证桥声明的最低版本 |
| Pr 25.2至25.5等过渡版本 | 默认已验证CEP；UXP仅按实际beta能力探测 | 不能套用25.6正式API保障 |
| Pr 25.6及更新 | 可选原生UXP插件/终端桥；也可继续使用该版本支持且已验证的CEP桥 | UXP正式发布不等于任意MCP的UXP后端成熟；按host/插件实际能力选择 |
| Pr 26.3及更新 | 同上，按当前API执行transaction/lockedAccess | 注意Action创建需在lockedAccess内，方法同步/异步签名有变化；不得直接照抄旧UXP示例 |

参照Adobe [版本变更](https://developer.adobe.com/premiere-pro/uxp/changelog/)、
[Project](https://developer.adobe.com/premiere-pro/uxp/ppro-reference/classes/project/)与
[SequenceEditor](https://developer.adobe.com/premiere-pro/uxp/ppro-reference/classes/sequenceeditor/)。
核实installed version/build，再枚举能力；不要用最新版文档推断旧host支持。旧、新两条路线都消费同一剪辑计划与图形数据，不改变网球审阅规则。

## 新机器配置：一次性建立通路

1. 只读检查Pr是否已安装/授权、确切版本、OS、Node/Python/FFmpeg、媒体目录权限、可用字体与导出预设。不要自动升级Pr；不要要求改变用户主机版本才能开工。
2. 选择并说明具体桥及版本。可选社区候选为[npm `adobe-premiere-pro-mcp`](https://github.com/hetpatel-11/Adobe_Premiere_Pro_MCP)；1.2.8使用CEP，其UXP包为experimental，不能当正式UXP默认。记录下载来源、版本/完整性摘要。检查安装脚本副作用，不凭相同可执行文件名确认包身份。
3. 把Node包安装在稳定的本地工具目录，保留依赖锁与版本，按当前任务授权范围安装桥。该候选的Windows安装脚本默认还会改多个CEP debug注册表版本、Claude和VS Code配置；terminal-only使用不需要这些client配置。可使用`-SkipBuild -SkipCopilotConfig -SkipClaudeDesktopConfig -SkipAdobeDebugMode`分离动作，仅为实际runtime按Adobe开发设置要求处理debug，并保存原值。macOS按其安装文档核对对应偏好；不要照搬Windows路径。
4. 该候选默认有匿名遥测；明确配置`PREMIERE_MCP_TELEMETRY=0`/`DO_NOT_TRACK=1`及面板配置`telemetry:false`。可设置`PREMIERE_MCP_UPDATE_CHECK=0`，由维护流程显式检查更新。保留用户既有配置，仅改选定桥需要的字段，不覆盖其他MCP、权限或账户配置。不要把token写入技能或Git。
5. CEP需当前用户扩展目录中的面板、所需开发设置，以及Pr加载面板。**首次激活**（无Computer Use时请用户操作）：启动Pr，先创建或打开一个空白scratch工程，再打开Window → Extensions → MCP Bridge (CEP)，确认面板与服务端使用同一个命令目录并启动桥。23.5的Home页未打开工程时Extensions不可用。保存这个空工程及其本机路径，作为后续终端启动入口。已支持自动启动的面板仍须实测下次Pr启动后能否恢复。terminal agent没有通路时只给出这一明确配置动作，不要求它点击菜单，也不把安装文件存在说成已连通。
6. UXP需与host兼容、已安装/启用的插件及其被授予的文件/本地通信访问。开发测试可由开发者通过UXP Developer Tool加载；正式用户应按插件分发方式安装/激活，不假定UDT、developer mode或未受限filesystem已开启。使用插件实际公开的命令协议并记录权限。没有已验证UXP终端桥时可在host仍支持的情况下明确选择CEP；不能伪称当前CEP候选已成为UXP。
7. 终端只读检查连通，返回host版本、当前工程、序列、timebase和能力；未通过即说明具体缺口。安装/启动失败时先完成独立数据准备，不反复发送编辑命令。认证、缺少授权或阻塞对话框需要用户处理；不绕过。
8. 在新scratch工程中做最小导入/读回/渲染/保存重开测试。交付记录安装目录、桥版本、启动方式、配置文件位置、恢复原设置办法、可用导出预设，以及实测的host/能力组合。不要安装完成后静默关闭用户需要的桥；若测试后清理，按记录恢复而不是删除其他扩展。

### Windows CEP候选的具体配置位置与命令

以下命令针对1.2.8包布局；其他版本须核对实际文件位置。先备份现有扩展与配置，再安装，不能覆盖另一任务正在运行的桥。Node最低20；生产机器使用仍受支持且兼容的Node版本。

```powershell
$premiereToolRoot = Join-Path $env:LOCALAPPDATA 'tennis-tools\premiere-mcp-1.2.8'
$premiereCommandDir = Join-Path $env:LOCALAPPDATA 'tennis-tools\premiere-commands'
New-Item -ItemType Directory -Path $premiereToolRoot -Force | Out-Null
npm.cmd install --prefix $premiereToolRoot --save-exact --omit=dev --ignore-scripts adobe-premiere-pro-mcp@1.2.8
if ($LASTEXITCODE -ne 0) { throw 'MCP package installation failed' }
$premierePackageRoot = Join-Path $premiereToolRoot 'node_modules\adobe-premiere-pro-mcp'
& (Join-Path $premierePackageRoot 'scripts\install-windows.ps1') -SkipBuild -SkipCopilotConfig -SkipClaudeDesktopConfig -SkipAdobeDebugMode -TempDir $premiereCommandDir
```

使用现有PowerShell执行策略；策略阻止脚本时先说明并按机器管理员要求解决，不全局放宽。安装脚本仅检查`dist/index.js`存在，不能代替实际Node启动检查。保留生成的`package-lock.json`；MCP配置的`args`指向上面包目录的`dist/index.js`，不依赖同名全局命令。Pr扩展复制到`%APPDATA%\Adobe\CEP\extensions\MCPBridgeCEP`；安装前记录它是否存在及其备份位置。

候选面板配置在`%USERPROFILE%\.premiere-mcp-bridge\config.json`。在面板未运行时读取现有JSON、保存原件，再合并`tempDirectory`（与服务端`PREMIERE_TEMP_DIR`完全一致）、`telemetry:false`、`updateCheck:false`三个字段；不要清空其他字段。安装脚本的`-TempDir`只准备目录及可选client配置，**不会替你写入这份面板配置**。面板内Save Configuration也会写命令目录的`config.json`；两处不能互相指向旧任务目录。随后用户打开面板，确认状态是运行中；若未自动运行，再用面板Start Bridge/Test Connection完成首次配置。

未签名CEP面板需要相应运行库的`PlayerDebugMode`。例如Pr 23.5的CSXS.11可使用`HKCU:\Software\Adobe\CSXS.11`下的字符串`PlayerDebugMode=1`；须核对已安装CEP运行库，不能循环开启所有CSXS版本。更改前记录键和值是否存在、原值和类型；只有明确需要开发面板且当前任务已授权安装时才写。此设置放宽该用户相应CEP运行库的扩展签名检查。恢复时原值存在则还原，原值不存在则仅移除新增值，不删除整个Adobe注册表分支。

终端检查失败时按实际状态分流：`premiere_not_running`需要先启动Pr；`bridge_panel_not_running`需要加载面板；心跳来自错误目录时修正两端配置并重启面板。`launchIfNeeded:false`明确不尝试启动，候选返回的“could not be launched”文案不能作为已尝试启动的证据。只在用户完成设置或状态改变后再检查；不要轮询编辑命令碰运气。首次setup记录应包括上述备份、路径、版本、debug差异、面板激活步骤、终端检查原始结果及重启后恢复结果。

## 不需要原生MCP客户端的终端调用

技能提供`scripts/premiere_mcp.cjs`，用Node启动一个stdio MCP服务，执行**一个**JSON工具请求并保存完整结果；不自动重试、不操作桌面。配置文件位于当前任务私有目录，例如：

```json
{
  "command": "node",
  "args": ["/absolute/tools/premiere-server/dist/index.js"],
  "env": {
    "PREMIERE_TEMP_DIR": "/absolute/private/premiere-command-dir",
    "PREMIERE_MCP_TELEMETRY": "0",
    "PREMIERE_MCP_UPDATE_CHECK": "0",
    "DO_NOT_TRACK": "1"
  },
  "timeoutMs": 60000
}
```

路径由当前机器确定；Node配置路径可用正斜杠或转义反斜杠。**传给Windows版Pr DOM的文件路径应先用`new File(path).fsName`转为原生路径**，不能由Node接受正斜杠推断Pr各API都接受。只读请求文件：

```json
{"name":"verify_premiere_connection","arguments":{"launchIfNeeded":false}}
```

执行`node scripts/premiere_mcp.cjs config.json request.json result-001.json`。随后读取结果。`returned`只表示收到响应，不是host操作/渲染验收通过；`tool_error`与`unknown`要读具体原因。该候选的较大目录使用`search_tools`/`get_tool_schema`发现参数，再通过`invoke_tool`调用；不得把这里的示例名推广到所有MCP。

MCP不是必须：已有CEP面板可调用`CSInterface.evalScript`进入ExtendScript；UXP插件可用`require("premierepro")`和事务API。两者都必须向终端公开有请求ID、项目/序列约束、结果/错误和超时状态的通信通路。终端不能通过`node require("premierepro")`直接获得host DOM；也不存在把任意React JSX交给Pr可执行文件就完成剪辑的保障。

## 编辑层：XML加有界host操作

FCP7 XMEML可一次构建轨道、原声和保留范围，再经MCP `import_fcp_xml`或同版本host的`importFiles`导入。它不是FCPXML 1.x，也不是直接编写`.prproj`。XML提供交换能力；自动导入、native图形、读回和导出仍需host桥。无法连接Pr时，生成XML只能标“待导入”。

`scripts/premiere_exchange.py plan.json cut.xml --check-files`提供有界生成器：

- 输入`tennis-edit-plan/v1`，含revision、sequence、assets、clips；序列name/fps/width/height/durationFrames明确。fps使用`30`或`30000/1001`等精确值，不用29.97近似。
- asset含id、绝对path、kind=video/image、width/height。video另含fps、durationFrames、timing=cfr、timingEvidence；有音频须给audioChannels=1/2和sampleRate。生成器要求媒体与序列同fps和全画幅；VFR/混合fps先显式标准化或改用已验证的host直接剪辑，不能猜测通过。
- clip含稳定id、assetId、1起算track、startFrame、durationFrames、sourceInFrame（默认0）、audio、可选audioTrack/P/R/name/sourceMapping。基础轨道须连续覆盖；上层透明图形间隙正常。原声拆为关联声道并保存与画面一致的区间。
- 不支持的变速、效果、缩放、混音参数直接报错。需要的MOGRT、透明度、淡出等放`postImport`，每项给operation/target与参数；报告原样列为待执行。不得把pending项目当已渲染。
- 输出XML和相邻`.report.json`，保留帧/tick/逻辑ID映射与哈希。输出不能覆盖旧版本。此生成器通过离线结构检查不等于已通过目标Pr版本导入。

Windows本地盘的XMEML URI使用`file://localhost/C%3a/media/clip.mov`形式；路径中的中文、空格、`#`和`%`也需百分号编码。23.5可能把`file:///C:/...`误读为网络路径并弹出Link Media。导入后核对所有媒体在线，UNC/macOS路径也须在目标host验证。

`audioTrack`在交换计划中指1起算的XML声道槽。立体声占相邻两槽，使用Pr的exploded Stereo轨道分组；Pr导入后合并为一条stereo轨道。不要把两个普通mono轨道当作保留立体声，它们可能居中混合。相同声道槽不能混用mono/stereo布局，先标准化或分配独立槽。导入后按实际轨道/clip ID绑定音量，不直接沿用XML轨道号。

VFR须检查实际PTS/packet间隔；名义与平均fps不同是线索，不是完整诊断。标准化保留原始证据时间、转码窗口偏移、采样率/色彩/方向及映射误差。估速仍使用原片证据，不能拿重复/丢弃后的CFR帧提升测量精度。长片只需测试时优先标准化短窗；完整转码前考虑磁盘和时间。

需核实视频的CFR声明时加`--probe-media`：使用ffprobe检查全部PTS、尺寸和帧数，报告随交换清单保存；不足或不符即报错。原`--check-files`不承担媒体分析，离线生成仍可用。取证命令及报告范围见[原片检查工具](source-inspection.md)。

导入后记录新序列ID并读回宽高、fps/timebase、总帧数、各剪口source in/out、音频声道/同步、媒体在线状态和图层占用。不要把上层图形空档当基础视频黑洞。MOGRT、统计透明度、定格背景、音频淡出按[图形契约](graphics-adapters.md)完成并逐项销账。避免基础流程依赖QE DOM；必须用时单独实测实际clip匹配，不能用QE索引等同常规DOM索引。

## 新旧版本都需通过的host验证

先合成短片，再检查原片短段，最后处理整场。至少检查：连接；XML导入/读回/往返；CFR与原PTS映射；透明PNG；native MOGRT中文属性写入读回及持续时间；球速出球后出现/大小标签共同退出；双误改字不重启；R/P跨内部剪口连续；11行统计与5页各8秒；原声、淡出和定格；保存重开；实际导出文件可解码、时长和声音正确。

帧检查通过桥导出的合成PNG或真实导出视频进行；不依赖桌面截图。某些`export_frame`会用未文档化接口或失败，需验证文件和像素；无法可靠导帧时先导出短视频再用FFmpeg取帧，不假称API返回成功就是画面正确。音频需实际监听/可用音频检查；只有波形或轨道存在不能证明主观接点自然。

导出需具体存在的`.epr`或已验证的host导出设置；格式名不等于预设。入队job ID不等于完成。检查落盘文件、帧数、时长、音画和对应版本，再交付原生工程、素材/overlay清单及复核定位。

## CEP属性操作与故障恢复

- 先比对`app.project.path`与预期工程的`File.fsName`，再按明确的`sequenceID`和clip ID执行；序列数组顺序会变化。下述DOM代码可作为`execute_extendscript`的`script`经终端客户端发送，不需要UI或QE。先枚举组件的`matchName`、属性名和值，再绑定当前host的属性；中文界面不要用英文显示名硬查。
- 统计透明度定位`AE.ADBE Opacity`组件，23.5的透明度为0–100。`setTimeVarying(true)`后，对每个源时间创建`Time`，设置精确`ticks`，调用`addKey(time)`、`setValueAtKey(time,value,true)`，并用`getValueAtTime(time)`读回。关键帧使用clip源时间：例如30fps、8秒、inPoint=0的PNG，四个关键帧为0/9/231/239；非零inPoint需加源偏移。保持线性插值并检查实际过渡帧；不要重放未知结果的写入。
- Stereo音量组件可用`Internal Volume Stereo`识别；23.5的0 dB原始值约0.177828，不能把1当作统一的0 dB。先读取并保留当前原声基准及已有关键帧，再写入首尾包络并读回。用PCM对照检查声道、增益和样本偏移，单独检查AAC等交付编码的延迟；不要为补偿编码延迟而移动源片剪口。
- SDR透明面板须核实序列色彩与合成设置。`compositeLinearColor`会影响半透明图层的合成；与HTML/PNG参照比较时，可在scratch序列通过`setSettings`检查false设置下的淡变和稳定帧。按当前参考与色彩流程选择，不照搬到HDR工程。
- 保存到新路径时使用`app.project.saveAs(new File(destination).fsName)`，拒绝覆盖已存在版本。若封装工具使用不兼容的路径形式，改用原生路径保存。检查文件时间/大小，关闭重开后读回轨道和效果，不能只看保存返回值。
- 关闭最后一个工程会卸载CEP面板，关闭操作可能已经完成而客户端报告桥失联。先确认关闭结果，再从终端用实际Pr可执行文件和带正确引号的绝对`.prproj`参数打开保存工程；不要通过依赖已卸载桥的`open_project`陷入循环。例如PowerShell使用`Start-Process -FilePath $premiereExe -ArgumentList ('"' + $projectPath + '"') -WindowStyle Hidden`，两个变量均来自本机已核实路径。打开后再只读验证，不能仅凭进程启动成功认定桥已恢复。
- `get_encoder_presets`可能只列用户预设，空列表不等于无导出能力。在当前Pr安装目录`MediaIO/systempresets`查找实际`.epr`，检查H.264或PCM等所需预设。保留所用预设路径与哈希，不把版本相关目录名写死成所有机器的路径。
- 1.2.8在host模态对话框阻塞时可能报告“bridge is not running”。检查缺失媒体、保存路径或MOGRT加载错误，并确认命令是否发生部分变更。导帧报错后也须检查是否已有输出文件。保存响应、检查文件与工程状态，停止后续依赖变更；终端agent确需清除对话框时请用户处理具体提示。不要反复导入、重装桥、改权限或假定失败无副作用。
