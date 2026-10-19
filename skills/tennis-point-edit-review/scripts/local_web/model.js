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
export class ClipSelection {
  constructor() { this.ids = new Set(); this.anchor = null; this.explicit = false; }
  focus(id) {
    if (!this.explicit) { this.ids = new Set([id]); this.anchor = id; }
  }
  reconcile(clips) {
    const valid = new Set(clips.map(c => c.id));
    this.ids = new Set([...this.ids].filter(id => valid.has(id)));
    if (!valid.has(this.anchor)) this.anchor = null;
  }
  pick(order, id, {ctrlKey = false, metaKey = false, shiftKey = false} = {}, focused) {
    if (!order.includes(id)) return;
    const additive = ctrlKey || metaKey;
    if (shiftKey) {
      const anchor = order.includes(this.anchor) ? this.anchor : order.includes(focused) ? focused : id;
      const a = order.indexOf(anchor), b = order.indexOf(id);
      this.ids = new Set([...(additive ? this.ids : []), ...order.slice(Math.min(a,b), Math.max(a,b)+1)]);
      this.anchor = anchor;
    } else {
      if (additive) { if (this.ids.has(id)) this.ids.delete(id); else this.ids.add(id); }
      else this.ids = new Set([id]);
      this.anchor = id;
    }
    this.explicit = true;
  }
}
export function exportSummary(p, options = {}) {
  const ids = new Set(options.clipIds ?? []);
  const clips = p.clips.filter(c => options.scope !== 'selected' || ids.has(c.id));
  const seconds = clips.reduce((sum, clip) => sum + length(clip), 0) / rate(p);
  const fps = String(options.fps ?? p.fps), outputRate = rate({fps});
  const frames = clips.length ? Math.max(1, Math.round(seconds * outputRate)) : 0;
  return {width:options.width ?? p.width, height:options.height ?? p.height, fps, frames, seconds:frames / outputRate, reasons:[...(p.needsRebuild ?? [])]};
}
export function layout(p, view = 'full') {
  let start = 0;
  const points = new Set((p.review?.rows ?? []).map(r => r.pointId));
  return p.clips.filter(c => view !== 'review' || points.has(c.pointId)).map((c) => {
    const x = { ...c, startFrame: start, endFrame: start + length(c) };
    start = x.endFrame;
    return x;
  });
}
export const viewOverlays = (p, view) => p.overlays.filter(o => !o.view || o.view === 'both' || o.view === view);
export function snapEdge(delta, edge, cursor, pixelsPerFrame, bypass = false) {
  const snapped = !bypass && Math.abs((edge + delta - cursor) * pixelsPerFrame) <= 8;
  return {delta: snapped ? cursor - edge : delta, snapped};
}
export function gameSegments(p, view = 'full') {
  const rows = new Map((p.review?.rows ?? []).map(r => [r.pointId, r]));
  // A fault/let clip may inherit its point's unique recorded game, never a neighbor's.
  const pointGames = new Map();
  for (const c of p.clips) {
    if (!c.pointId || !Number.isInteger(c.gameNumber) || c.gameNumber < 1) continue;
    const known = {gameNumber:c.gameNumber, setNumber:c.setNumber ?? null};
    const previous = pointGames.get(c.pointId);
    if (!pointGames.has(c.pointId)) pointGames.set(c.pointId, known);
    else if (previous && (previous.gameNumber !== known.gameNumber || previous.setNumber !== known.setNumber)) pointGames.set(c.pointId, null);
  }
  const segments = [];
  for (const c of layout(p, view)) {
    const row = rows.get(c.pointId), x = p.answers?.[c.pointId];
    const inherited = pointGames.get(c.pointId);
    const value = key => p.review?.purpose === 'initial-labeling' && row && x && Object.hasOwn(x, key)
      ? x[key] : c[key] ?? inherited?.[key] ?? row?.[key] ?? null;
    const gameNumber = value('gameNumber'), setNumber = value('setNumber');
    const known = Number.isInteger(gameNumber) && gameNumber > 0;
    const game = {gameNumber:known ? gameNumber : null, setNumber:known ? setNumber : null};
    const last = segments.at(-1);
    if (last && last.gameNumber === game.gameNumber && last.setNumber === game.setNumber) last.endFrame = c.endFrame;
    else segments.push({...game, clipId:c.id, startFrame:c.startFrame, endFrame:c.endFrame});
  }
  return segments;
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
  const labels = p.review?.purpose === 'initial-labeling' ? {serverId:r.serverId ?? null, serveNumber:r.serveNumber ?? null, gameNumber:r.gameNumber ?? null, setNumber:r.setNumber ?? null} : {};
  return { ...blank(), ...labels, ...p.answers[r.pointId] ?? { ...r.initial, reviewConfirmed: false } };
}
export function reviewStatus(r, x) {
  if (!x.reviewConfirmed) return x.scoringPlayerId || x.deadBallType || x.note ? "partial" : "pending";
  if (x.winnerUndetermined) return "unresolved";
  if (r.countingIssueRequired && !x.countingIssueResolved) return "partial";
  if (x.deadBallType === "replay") return "replay";
  return x.scoringPlayerId && x.deadBallType ? "resolved" : "partial";
}
export function reviewBadge(r, x) {
  const status = reviewStatus(r, x);
  return x.reviewConfirmed && status === 'partial'
    ? r.countingIssueRequired && !x.countingIssueResolved ? 'reviewedCounting' : 'reviewedIncomplete'
    : 'status.' + status;
}
export function changeAnswer(p, r, x, field, value) {
  x = { ...x, [field]: value, updatedAt: (/* @__PURE__ */ new Date()).toISOString() };
  const server = p.review?.purpose === 'initial-labeling' ? x.serverId : r.serverId;
  if ((field === 'deadBallType' && value === 'ace' || field === 'doubleFaultConfirmed' && value) && !server) throw new Error('Resolve server before ACE/double fault');
  if (field === 'serverId' && (x.deadBallType === 'ace' || x.doubleFaultConfirmed)) Object.assign(x, {scoringPlayerId:null, deadBallType:null, doubleFaultConfirmed:null});
  if (field !== "reviewConfirmed" && field !== "note") x.reviewConfirmed = true;
  if (field === "scoringPlayerId") {
    x.winnerUndetermined = value === "undetermined";
    if (x.winnerUndetermined) {
      x.scoringPlayerId = null;
      x.doubleFaultConfirmed = null;
      x.countingIssueResolved = false;
      if (x.deadBallType === "ace") x.deadBallType = null;
    }
    if (x.deadBallType === "ace" && x.scoringPlayerId !== server) x.deadBallType = null;
    if (x.scoringPlayerId === server) x.doubleFaultConfirmed = null;
  }
  if (field === "deadBallType" && value === "replay") Object.assign(x, { scoringPlayerId: null, winnerUndetermined: false, doubleFaultConfirmed: null, extra: false });
  if (field === "deadBallType" && value === "ace") Object.assign(x, { scoringPlayerId: server, winnerUndetermined: false, doubleFaultConfirmed: null });
  if (field === "doubleFaultConfirmed" && value) {
    x.winnerUndetermined = false;
    x.scoringPlayerId = p.players.find((v) => v.id !== server).id;
    if (["ace", "winner", "two_bounces", "replay"].includes(x.deadBallType)) x.deadBallType = null;
  }
  if (field === "deadBallType" && ["winner", "two_bounces"].includes(value)) x.doubleFaultConfirmed = null;
  return x;
}
