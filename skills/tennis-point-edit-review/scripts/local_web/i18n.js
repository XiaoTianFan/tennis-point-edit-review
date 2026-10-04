// UI-only language state. Project content and protocol values are never translated.
export const messages = {
  title: ['Courtside — local tennis edit', 'Courtside — 本地网球剪辑'],
  language: ['Interface language', '界面语言'],
  connecting: ['Connecting…', '连接中…'], saved: ['Saved', '已保存'], saving: ['Saving…', '保存中…'],
  savedNeedsRefresh: ['Saved · refresh graphics', '已保存 · 待更新图形'],
  notSaved: ['Not saved', '未保存'], notConnected: ['Not connected', '未连接'],
  recover: ['Recover edits', '恢复编辑'], reload: ['Reload', '重新加载'], reloadHint: ['Read changes made by your agent', '读取 agent 对工程的更改'],
  handoff: ['Send to agent', '交给 agent'], export: ['Export video', '导出视频'],
  review: ['Point review', '逐分复核'], search: ['Find a point or note', '查找分号或备注'],
  editor: ['Video editor', '视频编辑器'], selectPoint: ['Select a point', '选择一分'], decodedImage: ['Decoded source frame', '已解码的源视频帧'],
  openSession: ['Open the session link printed by the local editor.', '请打开本地编辑器输出的会话链接。'],
  edited: ['Edited', '成片'], source: ['Source', '源片'], prevPoint: ['Prev point', '上一分'], nextPoint: ['Next point', '下一分'],
  prevFrame: ['−1 frame', '−1 帧'], nextFrame: ['+1 frame', '+1 帧'], play: ['Play', '播放'], pause: ['Pause', '暂停'],
  prevPointHint: ['Previous point [', '上一分 ['], nextPointHint: ['Next point ]', '下一分 ]'],
  prevFrameHint: ['Previous frame ←', '上一帧 ←'], nextFrameHint: ['Next frame →', '下一帧 →'], playHint: ['Play / pause Space', '播放 / 暂停 空格'],
  speed: ['Playback speed', '播放速度'], playhead: ['Video playhead', '视频播放位置'], clip: ['Clip', '片段'],
  in: ['In', '入点'], out: ['Out', '出点'], inFrame: ['Clip in frame', '片段入点帧'], outFrame: ['Clip out frame', '片段出点帧'],
  applyTrim: ['Apply trim', '应用剪口'], applyTiming: ['Apply timing', '应用时序'],
  moveLeft: ['Move left', '向前移'], moveRight: ['Move right', '向后移'],
  moveLeftHint: ['Move selected clip earlier', '将所选片段前移'], moveRightHint: ['Move selected clip later', '将所选片段后移'],
  undo: ['Undo', '撤销'], redo: ['Redo', '重做'], timeline: ['Timeline', '时间线'],
  timelineHint: ['Drag edges to trim · Ctrl/⌘ + wheel: pan · Alt + wheel: zoom', '拖边修剪 · Ctrl/⌘ + 滚轮：横移 · Alt + 滚轮：缩放'],
  zoom: ['Zoom', '缩放'], timelineZoom: ['Timeline zoom', '时间线缩放'], time: ['TIME', '时间'],
  sourceVideo: ['Source video', '源视频'], scoreboard: ['Scoreboard', '计分板'], serveTrack: ['Serve / speed', '发球 / 球速'],
  statistics: ['Statistics', '统计'], reviewGraphics: ['Review graphics', '复核图形'], editedPlayhead: ['Edited timeline playhead', '成片时间线播放位置'],
  keyPlay: ['play', '播放'], keyFrame: ['frame', '逐帧'], keyPoint: ['point', '逐分'], keyUndo: ['undo', '撤销'],
  localProject: ['Local project · media stays on this computer', '本地工程 · 媒体保留在本机'],
  projectStatus: ['{count} points · revision {revision} · local project', '{count} 分 · 版本 {revision} · 本地工程'],
  handoffTitle: ['Review saved for your agent', '复核已保存，可交给 agent'],
  handoffInfo: ['Your answers, clip changes and current position are saved in the project. Copy this message into your agent conversation.', '答案、片段更改和当前位置已保存在工程中。将以下消息复制到与 agent 的对话。'],
  close: ['Close', '关闭'], closeHandoff: ['Close review handoff', '关闭复核交接'], handoffMessage: ['Agent handoff message', '交给 agent 的消息'],
  copy: ['Copy message', '复制消息'], downloadReview: ['Download review JSON', '下载复核 JSON'], copied: ['Copied', '已复制'],
  copyFallback: ['Press Ctrl/⌘+C to copy the selected text', '按 Ctrl/⌘+C 复制所选文本'],
  handoffText: ['Continue reviewing “{title}”. Read {path} and its adjacent agent-context.json and review.json (revision {revision}). My current point is {point}, {mode} frame {frame}. Reconcile my saved answers and clip edits, then refresh the affected graphics.', '继续复核“{title}”。读取 {path} 及同目录的 agent-context.json、review.json（版本 {revision}）。当前位置为 {point}，{mode}第 {frame} 帧。请整合已保存的答案和片段更改，并更新受影响的图形。'],
  reviewResize: ['Resize point review and preview panes', '调整复核与预览面板宽度'], timelineResize: ['Resize preview and timeline panes', '调整预览与时间线面板高度'],
  resizeHint: ['Drag or use arrow keys; Shift for larger steps. Double-click or Home to reset.', '拖动或使用方向键；Shift 加大步长。双击或按 Home 恢复默认。'],
  jump: ['Jump to {point}', '跳转到 {point}'],
  pointMeta: ['Set {set} · Game {game} · ● {server} · Serve {serve}', '第 {set} 盘 · 第 {game} 局 · ● {server} · 第 {serve} 发'],
  viewerMeta: ['{review} / {point} · Game {game} · ● {server} · Serve {serve}', '{review} / {point} · 第 {game} 局 · ● {server} · 第 {serve} 发'],
  winner: ['Point winner', '得分方'], uncertain: ['Uncertain', '无法确定'], deadBall: ['Dead ball', '死球原因'],
  'cause.out': ['Out', '出界'], 'cause.net': ['Net', '下网'], 'cause.two_bounces': ['Two bounces', '两跳'],
  'cause.replay': ['Replay', '重赛'], 'cause.ace': ['Ace', 'ACE'], 'cause.winner': ['Winner', '制胜分'], 'cause.other': ['Other', '其他'],
  doubleFaultConfirmed: ['Double fault', '双误'], extra: ['Extra point', '多打'], reviewConfirmed: ['Reviewed', '已复核'], countingIssueResolved: ['Count checked', '计数已核对'],
  note: ['{point} note', '{point} 备注'], notePlaceholder: ['Evidence, correction or a question…', '证据、修正或疑问…'],
  'status.pending': ['To review', '待复核'], 'status.partial': ['In progress', '复核中'], 'status.resolved': ['Reviewed', '已复核'],
  'status.unresolved': ['Needs inference', '待推断'], 'status.replay': ['Replay', '重赛'],
  progress: ['{reviewed}/{total} reviewed', '已复核 {reviewed}/{total}'], unknown: [' · {count} unknown', ' · {count} 分未确定'],
  sourceOutside: ['Source · outside retained points', '源片 · 位于保留分段之外'],
  sourceTime: ['Source {seconds}s · {fps} fps proxy', '源片 {seconds} 秒 · {fps} fps 代理'],
  decodedFrame: ['Decoded frame {frame}', '已解码第 {frame} 帧'], decoding: ['Decoding frame…', '正在解码…'], playing: ['Playing', '播放中'],
  clipName: ['{name} clip', '{name} 片段'], trimStart: ['Trim start {id}', '修剪 {id} 入点'], trimEnd: ['Trim end {id}', '修剪 {id} 出点'],
  overlayHint: ['{name} · drag to move, edges to resize', '{name} · 拖动移动，拖动边缘调整时长'],
  'component.scoreboard': ['Scoreboard', '计分板'], 'component.serveLabel': ['Serve label', '发球标签'], 'component.serveSpeed': ['Serve speed', '发球球速'],
  'component.statsPanel': ['Statistics', '统计面板'], 'component.reviewId': ['Review ID', '复核编号'], 'component.reviewLabel': ['Review label', '复核标签'], 'component.explanation': ['Explanation', '说明'],
  draftStorage: ['Browser draft storage is unavailable. Keep this page open until edits are saved.', '浏览器草稿存储不可用。请保持页面打开，直到编辑保存完成。'],
  noClip: ['This point has no retained clip. Ask the agent to add its evidence.', '此分没有保留片段，请让 agent 补充证据。'],
  rebuild: ['Changes saved. Send to your agent to refresh the affected scores, statistics or timing.', '更改已保存。请交给 agent 更新受影响的分数、统计或时序。'],
  saveError: ['{error} Use Recover edits to retain the unsaved changes before reconciling.', '{error} 请先用“恢复编辑”保留未保存的更改，再处理差异。'],
  noPoints: ['There are no point clips in this timeline.', '时间线中没有逐分片段。'], wholeFrames: ['Use whole frame numbers.', '请输入整数帧号。'],
  draftDownloaded: ['Draft downloaded. Give it to your agent to compare with the current project; it has not been applied automatically.', '草稿已下载。请交给 agent 与当前工程对比；草稿尚未自动应用。'],
  draftAvailable: ['Unsaved edits from an earlier session are available through Recover edits.', '上次会话有未保存的更改，可通过“恢复编辑”下载。'],
  exporting: ['Exporting {done} / {total} clips…', '正在导出 {done} / {total} 个片段…'], exportComplete: ['Export complete', '导出完成'],
  downloadVideo: ['Download edited video', '下载成片'], exportStopped: ['Export stopped', '导出已停止'],
  decodeError: ['Video could not be decoded. Prepare a browser-compatible proxy.', '无法解码视频，请生成浏览器兼容的代理文件。'],
  browserError: ['Use a current browser with video frame callbacks.', '请使用支持视频帧回调的新版浏览器。'],
  requestError: ['Request failed: {detail}', '请求失败：{detail}'],
};
const errors = {
  'Failed to fetch': ['Cannot connect to the local editor. Check that its server is running.', '无法连接本地编辑器，请检查服务是否运行。'],
  'Project changed in another tab or agent; reload before retrying': ['Project changed in another tab or agent; reload before retrying.', '工程已被其他标签页或 agent 修改；请重新加载后再操作。'],
  'Another writer is active; reload and retry': ['Another writer is active; reload and retry.', '工程正在被其他进程写入；请重新加载后重试。'],
  'Clip outside source or empty': ['Clip must stay within the source and contain at least one frame.', '片段须位于源视频范围内，并至少保留一帧。'],
  'Empty overlay': ['A graphic must contain at least one frame.', '图形须至少保留一帧。'],
  'Nothing to undo': ['Nothing to undo.', '没有可撤销的操作。'], 'Nothing to redo': ['Nothing to redo.', '没有可重做的操作。'],
  'Invalid session or origin': ['Session expired. Open the current launch URL.', '会话已失效，请打开当前启动链接。'],
  'Open the launch URL containing this session token': ['Open the current launch URL containing the session token.', '请打开包含当前会话令牌的启动链接。'],
  'Reload before exporting review': ['Reload before exporting review.', '请先重新加载，再导出复核。'],
  'Reload before exporting video': ['Reload before exporting video.', '请先重新加载，再导出视频。'],
  'Export already running': ['An export is already running.', '已有导出任务正在运行。'],
  'Send the changes to your agent to refresh graphics before exporting': ['Send the changes to your agent to refresh graphics before exporting.', '请先将更改交给 agent 更新图形，再导出。'],
};
let locale = 'en';
export function getLocale() { return locale; }
export function setLocale(value) { locale = value === 'zh' ? 'zh' : 'en'; return locale; }
export function t(key, values = {}) {
  const text = messages[key]?.[locale === 'zh' ? 1 : 0] ?? key;
  return text.replace(/\{(\w+)\}/g, (match, name) => values[name] ?? match);
}
export function errorText(detail) { return errors[detail]?.[locale === 'zh' ? 1 : 0] ?? t('requestError', {detail}); }
export function translate(root = document) {
  for (const attr of ['text', 'title', 'placeholder', 'aria-label', 'alt']) {
    const data = attr === 'text' ? 'data-i18n' : 'data-i18n-' + attr;
    for (const node of root.querySelectorAll('[' + data + ']')) {
      const value = t(node.getAttribute(data));
      if (attr === 'text') node.textContent = value;
      else node.setAttribute(attr, value);
    }
  }
}
