export const $ = (id) => document.getElementById(id);
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
