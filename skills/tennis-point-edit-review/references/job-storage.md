# 任务工作区与迁移

## 新任务的默认位置

用户明确指定工作目录时使用该目录；继续已有工程时沿用已确认工作区，不因新默认值擅自搬迁。素材路径或最终成片路径不等于用户指定了工作目录。

未指定工作目录时，先用 `local_editor.py workspace --source "<source>"` 创建工作区，再开始代理、抽帧、剪口和统计。默认根为**技能项目主检出的 `outputs/`**，每场独立 `YYYYMMDD-素材名/`；同名新任务自动加序号，不能混用上一场目录。命令返回绝对目录和各子目录，后续工具使用这些路径。

默认根通过技能所在仓库的 Git common directory 定位主检出；即使从 linked worktree 调用，也不把比赛数据放进临时 worktree、技能包目录或任意当前目录。独立安装包无法定位主检出时，使用已确认的绝对 `TENNIS_OUTPUTS_ROOT` 或 `--outputs-root`；没有配置则明确报错，不猜路径。`--work-dir "<user-directory>"` 指定精确的新工作目录，优先于默认根；目录已存在时直接接续，不重新初始化。

`outputs/` 必须由仓库忽略，不能提交比赛数据。每场工作区集中保存：

| 子目录 | 用途 |
|---|---|
| media | 代理及媒体元数据；源录像继续引用用户原位置 |
| edit | 同一 Courtside/Edit 工程、图层、答案和 Undo/Redo；由 init 创建 |
| analysis / statistics / evidence | 阶段记录、逐分账本、计分、技术统计、估速、PTS与证据 |
| cache / runtime | 本片缓存和确有需要的独立运行依赖；已有共享依赖继续共享 |
| exports / audit | 任务导出和清理／迁移记录；工作台工程内导出记录继续保留，用户指定最终成片目录优先 |

`job-workspace.json` 记录路径和源片。临时脚本也放本场工作区。旧工程内部结构可保留，不为统一目录名改动答案或比赛事实。这里的目录组织不改变[收尾清理](cleanup.md)的保留与授权边界。

## 已授权迁移与路径解析

迁移前盘点本片所有位置，包括编辑器外的统计、程序性分析与证据，去重重叠根，核对写入进程和未保存状态。用显式文件清单记录绝对路径、大小、修改时间及SHA-256；拒绝reparse穿越。先复制到已核实的目标根，逐文件校验，确认源片、最终成片、工程、图层、统计与恢复依赖可用，再删除清单中的旧副本和空目录。移动字节数与净释放空间分开报告。迁移授权不等于额外删减保留数据。

每场根目录可保存 `relocation-map.json`，格式为 `{"schema":"tennis-job-relocation/v1","mappings":[{"old":"<absolute-old-root>","new":"<absolute-new-root>"}]}`。目标必须位于该场目录内；按完整路径边界、最长前缀匹配，一次映射，不递归串接。原录像和最终成片不纳入迁移映射。

Courtside/Edit 的JSON读取会查找最近的该映射，在内存中解析工程、图层、Undo/Redo和统计引用；不重写历史清理清单、导出快照、证据或原始工程字节，不改变revision、P/R、答案和统计值。后续正常编辑按既有版本围栏保存。历史路径通过映射查阅；独立分析脚本不要假定旧绝对路径仍存在：

```sh
python "<skill>/scripts/job_workspace.py" resolve "<old-path>" --workspace "<job>"
python "<skill>/scripts/job_workspace.py" read "<old-json>" --workspace "<job>"
```

Python可用 `read_document(path, workspace=job)` 得到已解析的JSON视图。原始文本、日志、脚本中的历史路径保持原文；需要重新运行旧脚本时先按映射更新其运行参数。缺失引用须区分迁移前已有缺口与新增缺口，不能补造或覆盖历史。启动器指向新的工程目录和当前技能脚本；迁移后验证媒体播放、图层、统计及恢复依赖，再交付。
