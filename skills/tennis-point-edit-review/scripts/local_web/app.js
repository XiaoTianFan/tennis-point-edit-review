import { $, rate, length, layout, buttonIcon, exportSummary } from "./model.js";
import { Review } from "./review.js";
import { Timeline } from "./timeline.js";
import { Player } from "./player.js";
import { t, errorText, translate, getLocale, setLocale } from "./i18n.js";
import { initPanes } from "./view-state.js";
try { setLocale(localStorage.getItem('courtside-language') ?? (navigator.language.startsWith('zh') ? 'zh' : 'en')); } catch { setLocale('en'); }
translate();
document.documentElement.lang = getLocale() === 'zh' ? 'zh-CN' : 'en';
function languageButton() { $('language').textContent = getLocale() === 'en' ? '中文' : 'EN'; }
languageButton();
buttonIcon($('undo'), 'undo-2'); buttonIcon($('redo'), 'redo-2'); buttonIcon($('play'), 'play');
initPanes();
const fragment = new URLSearchParams(location.hash.slice(1));
const token = fragment.get("token") || sessionStorage.getItem("courtside:" + location.port) || "";
if (token) sessionStorage.setItem("courtside:" + location.port, token);
const url = (path) => path + (path.includes("?") ? "&" : "?") + "token=" + encodeURIComponent(token);
let project, selectedClip, selectedOverlay, queue = Promise.resolve(), pending = 0, contextData;
let noticeState, noticeTimer, handoffValues;
let exportJob = {state: "idle"}, exportBusy = false, exportError = null, exportTimer;
let exportDefaults, pickerBusy = false;
function renderNotice() {
  const node = $('notice');
  node.hidden = !noticeState;
  if (!noticeState) { node.replaceChildren(); return; }
  const {key, values} = noticeState;
  const params = Object.fromEntries(Object.entries(values).map(([k,v]) => [k, v instanceof Error ? errorText(v.message) : v]));
  node.textContent = key instanceof Error ? errorText(key.message) : t(key, params);
  if (key === 'exportComplete') {
    const link = document.createElement('a');
    link.href = url('/api/export'); link.download = exportJob.settings?.filename ?? 'edited.mp4'; link.textContent = t('downloadVideo');
    node.append(' · ', link);
  }
}
function notice(key, values = {}) {
  clearTimeout(noticeTimer);
  noticeState = key ? {key, values} : null;
  renderNotice();
  if (key) noticeTimer = setTimeout(() => { noticeState = null; renderNotice(); }, key === 'exportComplete' ? 30000 : 10000);
}
function saveState(key) { $('save-state').dataset.i18n = key; $('save-state').textContent = t(key); }
function projectStatus() { $('project-status').textContent = t('projectStatus', {count: project.review.rows.length, revision: project.revision}); }
function handoffText() {
  if (handoffValues) $('handoff-text').value = t('handoffText', {...handoffValues, mode: t(handoffValues.mode)}) + '\n\n' + JSON.stringify(contextData.review, null, 2);
}
$('language').onclick = () => {
  setLocale(getLocale() === 'en' ? 'zh' : 'en');
  languageButton();
  try { localStorage.setItem('courtside-language', getLocale()); } catch { /* Language still changes in this session. */ }
  document.documentElement.lang = getLocale() === 'zh' ? 'zh-CN' : 'en';
  translate(); renderNotice(); handoffText();
  if (project) { review.localize(); timeline.render(); player.paint(); inspector(true); projectStatus(); refreshExport(); }
};
const draftKey = () => "courtside-draft:" + (project.projectId ?? [project.review.source, project.review.ledgerRevision, project.title].join(":"));
function drafts() {
  try {
    return JSON.parse(localStorage.getItem(draftKey()) ?? "[]");
  } catch {
    return [];
  }
}
function storeDrafts(values) {
  try {
    if (values.length) localStorage.setItem(draftKey(), JSON.stringify(values));
    else localStorage.removeItem(draftKey());
    if (!values.length) $("recover-draft").hidden = true;
  } catch {
    notice("draftStorage");
  }
}
async function api(path, data) {
  const r = await fetch(path, { headers: { "X-Session-Token": token, ...data ? { "Content-Type": "application/json" } : {} }, ...data ? { method: "POST", body: JSON.stringify(data) } : {} });
  const value = await r.json();
  if (!r.ok) throw new Error(value.error ?? "Request failed");
  return value;
}
const review = new Review((pid) => {
  const c = layout(project).find((c2) => c2.pointId === pid);
  if (c) select(c.id);
  else notice("noClip");
}, save);
const timeline = new Timeline(url, select, (frame) => {
  if (player.mode !== "edited") player.switchMode("edited");
  player.seek(frame);
}, save);
const player = new Player(url, (frame, clip, mode, linked) => {
  timeline.setFrame(mode === "edited" ? frame : clip.startFrame + Math.max(0, Math.min(length(clip) - 1, frame - clip.inFrame)));
  review.highlight(linked ? clip.pointId : null);
  if (selectedClip !== clip.id) {
    selectedClip = clip.id;
    selectedOverlay = null;
    inspector();
  }
  timeline.highlight(selectedClip, selectedOverlay);
  const row = linked && project.review.rows.find((r) => r.pointId === clip.pointId);
  $("viewer-context").textContent = row ? t("viewerMeta", {review: row.reviewId, point: row.pointId, game: row.gameNumber ?? "?", server: project.players.find((p) => p.id === row.serverId)?.name ?? row.serverId, serve: clip.serveNumber ?? row.serveNumber ?? "?"}) : mode === "source" ? t("sourceOutside") : clip.label ?? t("statistics");
}, notice);
function setProject(p) {
  project = p;
  if (!p.overlays.some(o => o.id === selectedOverlay)) selectedOverlay = null;
  $("project-title").textContent = p.title;
  projectStatus();
  saveState(p.needsRebuild?.length ? "savedNeedsRefresh" : "saved");
  for (const id of ['save-state']) {
    if (p.needsRebuild?.length) { $(id).dataset.i18nTitle = 'rebuild'; $(id).title = t('rebuild'); }
    else { delete $(id).dataset.i18nTitle; $(id).removeAttribute('title'); }
  }
  review.setProject(p);
  timeline.setProject(p);
  player.setProject(p);
  inspector();
  if (p.needsRebuild?.length) notice("rebuild");
  else notice("");
  $("export-video").disabled = false;
  refreshExport();
  $("undo").disabled = !p.undo?.length;
  $("redo").disabled = !p.redo?.length;
}
function save(operation) {
  const draftId = crypto.randomUUID();
  storeDrafts([...drafts(), { id: draftId, revision: project.revision, operation }]);
  pending++;
  saveState("saving");
  refreshExport();
  queue = queue.then(async () => {
    const result = await api("/api/operation", { revision: project.revision, operation });
    storeDrafts(drafts().filter((d) => d.id !== draftId));
    project = result;
    pending--;
    if (!pending) setProject(result);
    return result;
  }).catch((e) => {
    pending = 0;
    $("recover-draft").hidden = !drafts().length;
    saveState("notSaved");
    refreshExport();
    notice("saveError", {error: e});
    throw e;
  });
  queue.catch(() => {
  });
  return queue;
}
function select(id, overlayId = null) {
  const c = layout(project).find((c2) => c2.id === id);
  if (!c) return;
  selectedClip = id;
  selectedOverlay = overlayId;
  player.mode = "edited";
  player.seek(c.startFrame + (overlayId ? Math.max(0, project.overlays.find((o) => o.id === overlayId).startFrame - (project.overlays.find((o) => o.id === overlayId).anchor === "source" ? c.inFrame : 0)) : 0));
  inspector();
  timeline.highlight(id, overlayId);
  timeline.reveal(player.frame);
}
function inspector(labelsOnly = false) {
  if (!project) return;
  const c = project.clips.find((c2) => c2.id === selectedClip) ?? project.clips[0];
  selectedClip = c.id;
  const o = project.overlays.find((o2) => o2.id === selectedOverlay);
  $("selection-name").textContent = o ? o.label ?? t("component." + o.component) : c.pointId ?? c.label ?? c.id;
  if (!labelsOnly) $("clip-in").value = o ? o.startFrame : c.inFrame;
  if (!labelsOnly) $("clip-out").value = o ? o.endFrame : c.kind === "hold" ? c.inFrame + c.durationFrames : c.outFrame;
  $("clip-in").disabled = c.kind === "hold" && !o;
  $("apply-trim").textContent = t(o ? "applyTiming" : "applyTrim");
}
function jump(direction) {
  const clips = layout(project).filter((c) => c.pointId);
  const unique = clips.filter((c, i) => i === 0 || c.pointId !== clips[i - 1].pointId);
  if (!unique.length) { notice("noPoints"); return; }
  let index = unique.findIndex((c) => c.pointId === player.clip?.pointId);
  if (index < 0) index = direction < 0 ? unique.length : 0;
  select(unique[Math.max(0, Math.min(unique.length - 1, index + direction))].id);
}
$("play").onclick = () => player.playing ? player.pause() : player.play();
$("prev-frame").onclick = () => player.seek(player.frame - 1);
$("next-frame").onclick = () => player.seek(player.frame + 1);
$("prev-point").onclick = () => jump(-1);
$("next-point").onclick = () => jump(1);
$("edited").onclick = () => player.switchMode("edited");
$("source").onclick = () => player.switchMode("source");
$("speed").onchange = () => player.video.playbackRate = Number($("speed").value);
$("source-position").oninput = () => player.seek(Number($("source-position").value));
$("apply-trim").onclick = () => {
  const i = Number($("clip-in").value), o = Number($("clip-out").value), c = project.clips.find((c2) => c2.id === selectedClip);
  if (!Number.isInteger(i) || !Number.isInteger(o)) {
    notice("wholeFrames");
    return;
  }
  save(selectedOverlay ? { type: "overlay", id: selectedOverlay, startFrame: i, endFrame: o } : c.kind === "hold" ? { type: "trim", id: c.id, durationFrames: o - i } : { type: "trim", id: c.id, inFrame: i, outFrame: o });
};
$("undo").onclick = () => save({ type: "undo" });
$("redo").onclick = () => save({ type: "redo" });
$("reload").onclick = async () => {
  try {
    await queue.catch(() => {
    });
    queue = Promise.resolve();
    setProject(await api("/api/project"));
  } catch (e) {
    notice(e);
  }
};
document.addEventListener("keydown", (e) => {
  if (e.target.matches("input,textarea,select,[role=separator]") || $("handoff-dialog").open || $("export-dialog").open) return;
  if (e.code === "Space") {
    e.preventDefault();
    $("play").click();
  }
  if (e.key === "ArrowLeft" || e.key === "ArrowRight") {
    e.preventDefault();
    player.seek(player.frame + (e.key === "ArrowLeft" ? -1 : 1) * (e.shiftKey ? 10 : 1));
  }
  if (e.key === "[") jump(-1);
  if (e.key === "]") jump(1);
  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "z") {
    e.preventDefault();
    const button = $(e.shiftKey ? "redo" : "undo");
    if (!button.disabled) button.click();
  }
});
$("handoff").onclick = async () => {
  try {
    player.pause();
    await save({ type: "selection", clipId: player.clip.id, frame: player.frame, mode: player.mode });
    contextData = await api("/api/handoff", { revision: project.revision });
    handoffValues = {title: project.title, path: contextData.projectPath, revision: project.revision, point: player.clip.pointId ?? player.clip.label ?? player.clip.id, mode: player.mode, frame: player.frame};
    handoffText();
    $("handoff-dialog").showModal();
  } catch (e) {
    notice(e);
  }
};
$("close-handoff").onclick = () => $("handoff-dialog").close();
$("copy-handoff").onclick = async () => {
  try {
    await navigator.clipboard.writeText($("handoff-text").value);
    $("copy-status").dataset.i18n = "copied"; $("copy-status").textContent = t("copied");
  } catch {
    $("handoff-text").focus();
    $("handoff-text").select();
    $("copy-status").dataset.i18n = "copyFallback"; $("copy-status").textContent = t("copyFallback");
  }
};
$("download-review").onclick = () => {
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([JSON.stringify(contextData.review, null, 2)], { type: "application/json" }));
  a.download = "review.json";
  a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 1e3);
};
$("recover-draft").onclick = () => {
  const recovery = { schema: "tennis-local-draft/v1", source: project.review.source, ledgerRevision: project.review.ledgerRevision, projectId: project.projectId, operations: drafts() };
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([JSON.stringify(recovery, null, 2)], { type: "application/json" }));
  a.download = "unsaved-edits.json";
  a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 1e3);
  notice("draftDownloaded");
};
function exportOptions() {
  return {width:Number($('export-width').value), height:Number($('export-height').value), fps:$('export-fps').value.trim(), filename:$('export-filename').value.trim()};
}
function refreshExport() {
  if (!project) return;
  const options = exportOptions(), outputRate = rate(options), summary = exportSummary(project, options);
  const valid = $('export-form').checkValidity() && /^\d+(\.\d+)?(\/\d+)?$/.test(options.fps) && outputRate >= 1 && outputRate <= 240;
  $('export-duration').textContent = valid ? t('durationFrames', {seconds: summary.seconds.toFixed(2), frames: summary.frames}) : '—';
  const audio = exportDefaults?.audio ?? project.audio;
  $('export-audio').textContent = audio ? t('audioSettings', {rate:audio.sampleRate/1000, channels:audio.channels}) : t('silentAudio');
  $('export-warning').hidden = !project.needsRebuild?.length;
  const running = exportJob.state === 'running';
  $('start-export').disabled = exportBusy || running || pickerBusy || pending > 0 || drafts().length > 0 || !valid;
  $('browse-export').disabled = pickerBusy;
  $('export-status').textContent = exportError ? errorText(exportError.message) : pickerBusy ? t('pickerOpen') : exportBusy ? t('exportChecking') : running ? t('exporting', {done:exportJob.completedClips ?? 0, total:exportJob.totalClips}) : pending ? t('exportWaiting') : drafts().length ? t('exportUnsaved') : exportJob.state === 'failed' ? errorText(exportJob.error) : exportJob.state === 'complete' ? t('exportComplete') + ' · ' + t('exportJobRevision', {revision:exportJob.revision}) : !valid ? t('invalidExport') : '';
  $('export-download').hidden = exportJob.state !== 'complete';
  $('export-download').href = url('/api/export');
  $('export-download').download = exportJob.settings?.filename ?? 'edited.mp4';
}
$('export-form').onsubmit = e => { e.preventDefault(); if (!$('start-export').disabled) $('start-export').click(); };
$('export-form').oninput = e => { if (['export-width','export-height'].includes(e.target.id)) $('export-size').value = 'custom'; exportError = null; refreshExport(); };
$('export-size').onchange = () => {
  const value = $('export-size').value;
  if (value !== 'custom') {
    const [w,h] = value === 'project' ? [project.width, project.height] : value.split('x').map(Number);
    $('export-width').value = w; $('export-height').value = h;
  }
  refreshExport();
};
$('browse-export').onclick = async () => {
  pickerBusy = true; exportError = null; refreshExport();
  try { const result = await api('/api/pick-directory', {directory:$('export-directory').value}); if (result.directory) $('export-directory').value = result.directory; }
  catch(e) { exportError = e; }
  finally { pickerBusy = false; refreshExport(); }
};
$('export-video').onclick = async () => {
  player.pause();
  exportBusy = true; exportError = null;
  refreshExport(); $('export-dialog').showModal();
  try {
    if (!exportDefaults) {
      exportDefaults = await api('/api/export-settings');
      for (const key of ['width','height','fps','filename','directory']) $('export-' + key).value = exportDefaults[key];
    }
    exportJob = await api('/api/job');
    if (exportJob.state === 'running') { clearTimeout(exportTimer); exportTimer = setTimeout(poll, 1000); }
  } catch (e) { exportError = e; }
  finally { exportBusy = false; refreshExport(); }
};
$('close-export').onclick = () => $('export-dialog').close();
$('start-export').onclick = async () => {
  exportBusy = true; exportError = null; refreshExport();
  try {
    await queue;
    if (drafts().length) return;
    exportJob = await api('/api/render', {revision: project.revision, options:exportOptions(), directory:$('export-directory').value.trim()});
    clearTimeout(exportTimer); exportTimer = setTimeout(poll, 500);
  } catch (e) { exportError = e; }
  finally { exportBusy = false; refreshExport(); }
};
async function poll() {
  try {
    exportJob = await api('/api/job');
    exportError = null;
    refreshExport();
    if (exportJob.state === 'running') {
      if (!$('export-dialog').open) notice('exporting', {done:exportJob.completedClips ?? 0, total:exportJob.totalClips});
      clearTimeout(exportTimer); exportTimer = setTimeout(poll, 1000);
    } else if (exportJob.state === 'complete') notice('exportComplete');
    else notice(exportJob.error ? new Error(exportJob.error) : 'exportStopped');
  } catch (e) { exportError = e; refreshExport(); notice(e); }
}
window.addEventListener("beforeunload", (e) => {
  if (pending) {
    e.preventDefault();
    e.returnValue = "";
  }
});
try {
  setProject(await api("/api/project"));
  $("recover-draft").hidden = !drafts().length;
  if (drafts().length) notice("draftAvailable");
  if (project.selection?.clipId) {
    select(project.selection.clipId);
    player.mode = project.selection.mode ?? "edited";
    player.seek(project.selection.frame ?? 0);
  }
} catch (e) {
  notice(e);
  saveState("notConnected");
}
