export const $ = (id) => document.getElementById(id);
/* Lucide icons: https://github.com/lucide-icons/lucide (play, pause, undo-2, redo-2)
 * ISC License — Copyright (c) 2026 Lucide Icons and Contributors
 * Permission to use, copy, modify, and/or distribute this software for any
 * purpose with or without fee is hereby granted, provided that the above
 * copyright notice and this permission notice appear in all copies.
 * THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES
 * WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF
 * MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR
 * ANY SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES
 * WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN
 * ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF
 * OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.
 */
export const icons = {
  play: [['path', {d: 'M5 5a2 2 0 0 1 3.008-1.728l11.997 6.998a2 2 0 0 1 .003 3.458l-12 7A2 2 0 0 1 5 19z'}]],
  pause: [['rect', {x:14,y:3,width:5,height:18,rx:1}], ['rect', {x:5,y:3,width:5,height:18,rx:1}]],
  'undo-2': [['path', {d:'M9 14 4 9l5-5'}], ['path', {d:'M4 9h10.5a5.5 5.5 0 0 1 5.5 5.5a5.5 5.5 0 0 1-5.5 5.5H11'}]],
  'redo-2': [['path', {d:'m15 14 5-5-5-5'}], ['path', {d:'M20 9H9.5A5.5 5.5 0 0 0 4 14.5A5.5 5.5 0 0 0 9.5 20H13'}]],
};
export function buttonIcon(button, name) {
  if (button.dataset.icon === name) return;
  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  for (const [key, value] of Object.entries({viewBox:'0 0 24 24', width:18, height:18, fill:'none', stroke:'currentColor', 'stroke-width':2, 'stroke-linecap':'round', 'stroke-linejoin':'round', 'aria-hidden':'true', focusable:'false'})) svg.setAttribute(key,value);
  for (const [tag, attrs] of icons[name]) {
    const node = document.createElementNS(svg.namespaceURI, tag);
    for (const [key, value] of Object.entries(attrs)) node.setAttribute(key,value);
    svg.append(node);
  }
  button.replaceChildren(svg);
  button.dataset.icon = name;
}
export function el(tag, text, attrs = {}) {
  const e = document.createElement(tag);
  if (text != null) e.textContent = text;
  for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v);
  return e;
}
export const rate = (p) => {
  const [a, b = 1] = String(p.fps).split("/").map(Number);
  return a / b;
};
export const length = (c) => c.kind === "hold" ? c.durationFrames : c.outFrame - c.inFrame;
export function exportSummary(p, options = {}) {
  const seconds = p.clips.reduce((sum, clip) => sum + length(clip), 0) / rate(p);
  const fps = String(options.fps ?? p.fps), outputRate = rate({fps});
  const frames = Math.max(1, Math.round(seconds * outputRate));
  return {width:options.width ?? p.width, height:options.height ?? p.height, fps, frames, seconds:frames / outputRate, reasons:[...(p.needsRebuild ?? [])]};
}
export function layout(p) {
  let start = 0;
  return p.clips.map((c) => {
    const x = { ...c, startFrame: start, endFrame: start + length(c) };
    start = x.endFrame;
    return x;
  });
}
export function bounds(o, c) {
  const offset = o.anchor === "source" ? c.inFrame : 0;
  return [Math.max(0, o.startFrame - offset), Math.min(length(c), o.endFrame - offset)];
}
export function tc(frame, fps) {
  const seconds = Math.floor(frame / fps), f = Math.floor(frame - seconds * fps);
  return [Math.floor(seconds / 60), seconds % 60, f].map((x) => String(x).padStart(2, "0")).join(":");
}
export const causes = [["out", "Out"], ["net", "Net"], ["two_bounces", "Two bounces"], ["replay", "Replay"], ["ace", "Ace"], ["winner", "Winner"], ["other", "Other"]];
export const blank = () => ({ scoringPlayerId: null, winnerUndetermined: false, deadBallType: null, doubleFaultConfirmed: null, extra: false, reviewConfirmed: false, countingIssueResolved: false, note: "" });
export function answer(p, r) {
  return { ...blank(), ...p.answers[r.pointId] ?? { ...r.initial, reviewConfirmed: false } };
}
export function reviewStatus(r, x) {
  if (!x.reviewConfirmed) return x.scoringPlayerId || x.deadBallType || x.note ? "partial" : "pending";
  if (x.winnerUndetermined) return "unresolved";
  if (r.countingIssueRequired && !x.countingIssueResolved) return "partial";
  if (x.deadBallType === "replay") return "replay";
  return x.scoringPlayerId && x.deadBallType ? "resolved" : "partial";
}
export function changeAnswer(p, r, x, field, value) {
  x = { ...x, [field]: value, updatedAt: (/* @__PURE__ */ new Date()).toISOString() };
  if (field !== "reviewConfirmed" && field !== "note") x.reviewConfirmed = true;
  if (field === "scoringPlayerId") {
    x.winnerUndetermined = value === "undetermined";
    if (x.winnerUndetermined) {
      x.scoringPlayerId = null;
      x.doubleFaultConfirmed = null;
      x.countingIssueResolved = false;
      if (x.deadBallType === "ace") x.deadBallType = null;
    }
    if (x.deadBallType === "ace" && x.scoringPlayerId !== r.serverId) x.deadBallType = null;
    if (x.scoringPlayerId === r.serverId) x.doubleFaultConfirmed = null;
  }
  if (field === "deadBallType" && value === "replay") Object.assign(x, { scoringPlayerId: null, winnerUndetermined: false, doubleFaultConfirmed: null, extra: false });
  if (field === "deadBallType" && value === "ace") Object.assign(x, { scoringPlayerId: r.serverId, winnerUndetermined: false, doubleFaultConfirmed: null });
  if (field === "doubleFaultConfirmed" && value) {
    x.winnerUndetermined = false;
    x.scoringPlayerId = p.players.find((v) => v.id !== r.serverId).id;
    if (["ace", "winner", "two_bounces", "replay"].includes(x.deadBallType)) x.deadBallType = null;
  }
  if (field === "deadBallType" && ["winner", "two_bounces"].includes(value)) x.doubleFaultConfirmed = null;
  return x;
}
