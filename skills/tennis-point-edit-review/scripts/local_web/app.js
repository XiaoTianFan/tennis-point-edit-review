import { $, rate, length, layout } from "./model.js";
import { Review } from "./review.js";
import { Timeline } from "./timeline.js";
import { Player } from "./player.js";
const fragment = new URLSearchParams(location.hash.slice(1));
const token = fragment.get("token") || sessionStorage.getItem("courtside:" + location.port) || "";
if (token) sessionStorage.setItem("courtside:" + location.port, token);
const url = (path) => path + (path.includes("?") ? "&" : "?") + "token=" + encodeURIComponent(token);
let project, selectedClip, selectedOverlay, queue = Promise.resolve(), pending = 0, contextData;
const notice = (message) => {
  $("notice").textContent = message;
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
    notice("Browser draft storage is unavailable. Keep this page open until edits are saved.");
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
  else notice("This point has no retained clip. Ask the agent to add its evidence.");
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
  $("viewer-context").textContent = row ? `${row.reviewId} / ${row.pointId}  ·  Game ${row.gameNumber ?? "?"}  ·  ● ${project.players.find((p) => p.id === row.serverId)?.name ?? row.serverId}  ·  Serve ${clip.serveNumber ?? row.serveNumber ?? "?"}` : mode === "source" ? "Source · outside retained points" : clip.label ?? "Statistics";
}, notice);
function setProject(p) {
  project = p;
  if (!p.overlays.some(o => o.id === selectedOverlay)) selectedOverlay = null;
  $("project-title").textContent = p.title;
  $("project-status").textContent = `${p.review.rows.length} points · revision ${p.revision} · local project`;
  $("save-state").textContent = "Saved";
  review.setProject(p);
  timeline.setProject(p);
  player.setProject(p);
  inspector();
  if (p.needsRebuild?.length) notice("Changes saved. Send to your agent to refresh the affected scores, statistics or timing.");
  else notice("");
  $("export-video").disabled = !!p.needsRebuild?.length;
  $("undo").disabled = !p.undo?.length;
  $("redo").disabled = !p.redo?.length;
}
function save(operation) {
  const draftId = crypto.randomUUID();
  storeDrafts([...drafts(), { id: draftId, revision: project.revision, operation }]);
  pending++;
  $("save-state").textContent = "Saving…";
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
    $("save-state").textContent = "Not saved";
    notice(e.message + " Use Recover edits to retain the unsaved changes before reconciling.");
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
}
function inspector() {
  if (!project) return;
  const c = project.clips.find((c2) => c2.id === selectedClip) ?? project.clips[0];
  selectedClip = c.id;
  const o = project.overlays.find((o2) => o2.id === selectedOverlay);
  $("selection-name").textContent = o ? o.label ?? o.component : c.pointId ?? c.label ?? c.id;
  $("clip-in").value = o ? o.startFrame : c.inFrame;
  $("clip-out").value = o ? o.endFrame : c.kind === "hold" ? c.inFrame + c.durationFrames : c.outFrame;
  $("clip-in").disabled = c.kind === "hold" && !o;
  $("apply-trim").textContent = o ? "Apply timing" : "Apply trim";
  $("move-left").disabled = !!o || project.clips[0].id === c.id;
  $("move-right").disabled = !!o || project.clips.at(-1).id === c.id;
}
function jump(direction) {
  const clips = layout(project).filter((c) => c.pointId);
  const unique = clips.filter((c, i) => i === 0 || c.pointId !== clips[i - 1].pointId);
  if (!unique.length) { notice("There are no point clips in this timeline."); return; }
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
    notice("Use whole frame numbers.");
    return;
  }
  save(selectedOverlay ? { type: "overlay", id: selectedOverlay, startFrame: i, endFrame: o } : c.kind === "hold" ? { type: "trim", id: c.id, durationFrames: o - i } : { type: "trim", id: c.id, inFrame: i, outFrame: o });
};
for (const [id, d] of [["move-left", -1], ["move-right", 1]]) $(id).onclick = () => {
  const ids = project.clips.map((c) => c.id), i = ids.indexOf(selectedClip);
  if (i + d >= 0 && i + d < ids.length) {
    [ids[i], ids[i + d]] = [ids[i + d], ids[i]];
    save({ type: "reorder", ids });
  }
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
    notice(e.message);
  }
};
document.addEventListener("keydown", (e) => {
  if (e.target.matches("input,textarea,select") || $("handoff-dialog").open) return;
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
    $("handoff-text").value = `Continue reviewing “${project.title}”. Read ${contextData.projectPath} and its adjacent agent-context.json and review.json (revision ${project.revision}). My current point is ${player.clip.pointId ?? player.clip.label ?? player.clip.id}, ${player.mode} frame ${player.frame}. Reconcile my saved answers and clip edits, then refresh the affected graphics.

${JSON.stringify(contextData.review, null, 2)}`;
    $("handoff-dialog").showModal();
  } catch (e) {
    notice(e.message);
  }
};
$("close-handoff").onclick = () => $("handoff-dialog").close();
$("copy-handoff").onclick = async () => {
  try {
    await navigator.clipboard.writeText($("handoff-text").value);
    $("copy-status").textContent = "Copied";
  } catch {
    $("handoff-text").focus();
    $("handoff-text").select();
    $("copy-status").textContent = "Press Ctrl+C to copy the selected text";
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
  notice("Draft downloaded. Give it to your agent to compare with the current project; it has not been applied automatically.");
};
$("export-video").onclick = async () => {
  try {
    await queue;
    await api("/api/render", { revision: project.revision });
    $("export-video").disabled = true;
    poll();
  } catch (e) {
    notice(e.message);
  }
};
async function poll() {
  try {
    const job = await api("/api/job");
    if (job.state === "running") {
      notice(`Exporting ${job.completedClips ?? 0} / ${job.totalClips} clips…`);
      setTimeout(poll, 1e3);
    } else if (job.state === "complete") {
      const a = document.createElement("a");
      a.href = url("/api/export");
      a.download = "edited.mp4";
      a.textContent = "Download edited video";
      $("notice").replaceChildren("Export complete · ", a);
      $("export-video").disabled = !!project.needsRebuild?.length;
    } else {
      notice(job.error ?? "Export stopped");
      $("export-video").disabled = !!project.needsRebuild?.length;
    }
  } catch (e) {
    notice(e.message);
  }
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
  if (drafts().length) notice("Unsaved edits from an earlier session are available through Recover edits.");
  if (project.selection?.clipId) {
    select(project.selection.clipId);
    player.mode = project.selection.mode ?? "edited";
    player.seek(project.selection.frame ?? 0);
  }
} catch (e) {
  notice(e.message);
  $("save-state").textContent = "Not connected";
}
