import { $, el, layout, length, bounds, rate, tc } from "./model.js";
export class Timeline {
  constructor(url, select, seek, save) {
    this.url = url;
    this.select = select;
    this.seek = seek;
    this.save = save;
    this.zoom = 1;
    $("zoom").oninput = () => {
      this.zoom = Number($("zoom").value);
      this.render();
    };
    new ResizeObserver(() => {
      if (this.p) this.render();
    }).observe($("timeline-scroll"));
    $("ruler").onpointerdown = (e) => this.scrub(e);
    $("playhead").onpointerdown = (e) => this.scrub(e);
    $("playhead").onkeydown = (e) => {
      if (["ArrowLeft", "ArrowRight"].includes(e.key)) {
        e.preventDefault();
        e.stopPropagation();
        this.seek(this.frame + (e.key === "ArrowLeft" ? -1 : 1));
      }
    };
  }
  setProject(p) {
    this.p = p;
    this.render();
  }
  scrub(e) {
    e.preventDefault();
    const move = (event) => {
      const box = $("timeline").getBoundingClientRect();
      this.seek(Math.max(0, Math.min(this.total - 1, Math.round((event.clientX - box.left) / this.px))));
    };
    move(e);
    let last = 0;
    const update = (event) => {
      if (performance.now() - last > 70) {
        last = performance.now();
        move(event);
      }
    };
    const end = (event) => {
      move(event);
      document.removeEventListener("pointermove", update);
      document.removeEventListener("pointerup", end);
    };
    document.addEventListener("pointermove", update);
    document.addEventListener("pointerup", end, { once: true });
  }
  render() {
    const clips = layout(this.p);
    const reviewLanes = ["reviewId", "reviewLabel", "explanation"].filter(component => this.p.overlays.some(o => o.component === component));
    const reviewHeight = reviewLanes.length * 24;
    document.documentElement.style.setProperty("--review-height", reviewHeight + "px");
    document.documentElement.style.setProperty("--timeline-height", (232 + reviewHeight) + "px");
    document.querySelector(".track-labels>div:last-child").hidden = !reviewHeight;
    $("review-track").hidden = !reviewHeight;
    this.clips = clips;
    this.total = clips.at(-1).endFrame;
    this.fps = rate(this.p);
    this.px = Math.max(0.25, ($("timeline-scroll").clientWidth - 24) / this.total) * this.zoom;
    const width = Math.max($("timeline-scroll").clientWidth, this.total * this.px + 24);
    $("timeline").style.width = width + "px";
    for (const id of ["ruler", "video-track", "score-track", "serve-track", "stats-track", "review-track"]) $(id).replaceChildren();
    const step = Math.max(1, Math.ceil(90 / (this.fps * this.px)));
    for (let second = 0; second < this.total / this.fps; second += step) {
      const tick = el("span", tc(Math.round(second * this.fps), this.fps), { class: "tick" });
      tick.style.left = second * this.fps * this.px + "px";
      $("ruler").append(tick);
    }
    for (const c of clips) {
      const block = el("div", null, { class: "clip-block", "data-clip": c.id, draggable: "true", tabindex: "0", role: "button", "aria-label": `${c.pointId ?? c.label ?? c.id} clip` });
      block.style.left = c.startFrame * this.px + "px";
      block.style.width = length(c) * this.px + "px";
      const img = el("img", null, { src: this.url(`/api/frame?asset=${c.assetId}&frame=${c.inFrame}`), alt: "", loading: "lazy" });
      block.append(img, el("span", c.pointId ?? c.label ?? c.id, { class: "clip-caption" }));
      block.onclick = () => this.select(c.id);
      block.onkeydown = (e) => {
        if (e.key === "Enter") this.select(c.id);
      };
      block.ondragstart = (e) => {
        if (this.trimming) {
          e.preventDefault();
          return;
        }
        e.dataTransfer.setData("text/plain", c.id);
        e.dataTransfer.effectAllowed = "move";
      };
      block.ondragover = (e) => e.preventDefault();
      block.ondrop = (e) => {
        e.preventDefault();
        const id = e.dataTransfer.getData("text/plain");
        if (id === c.id || !clips.some((v) => v.id === id)) return;
        const ids = clips.map((v) => v.id).filter((v) => v !== id);
        ids.splice(ids.indexOf(c.id) + (e.offsetX > block.clientWidth / 2 ? 1 : 0), 0, id);
        this.save({ type: "reorder", ids });
      };
      for (const side of ["start", "end"]) {
        const handle = el("span", "", { class: "trim-handle " + side, role: "separator", "aria-label": `Trim ${side} ${c.id}` });
        handle.onpointerdown = (e) => this.trim(e, c, side, block);
        handle.onclick = (e) => e.stopPropagation();
        block.append(handle);
      }
      $("video-track").append(block);
    }
    for (const o of this.p.overlays) {
      const c = clips.find((v) => v.id === o.clipId), [a, b] = bounds(o, c);
      if (b <= a) continue;
      const track = o.component === "scoreboard" ? "score-track" : ["serveLabel", "serveSpeed"].includes(o.component) ? "serve-track" : o.component === "statsPanel" ? "stats-track" : "review-track";
      const bar = el("button", o.label ?? o.component, { class: "overlay-block " + o.component, "data-overlay-id": o.id, title: (o.label ?? o.component) + " · drag to move, edges to resize" });
      bar.style.left = (c.startFrame + a) * this.px + "px";
      bar.style.width = Math.max(3, (b - a) * this.px) + "px";
      if (track === "review-track") bar.style.top = (2 + reviewLanes.indexOf(o.component) * 24) + "px";
      bar.onclick = () => {
        if (!this.trimming) this.select(c.id, o.id);
      };
      bar.onpointerdown = (e) => this.overlayDrag(e, o, c, bar, "move");
      for (const side of ["start", "end"]) {
        const handle = el("span", "", { class: "trim-handle " + side, "aria-hidden": "true" });
        handle.onpointerdown = (e) => this.overlayDrag(e, o, c, bar, side);
        bar.append(handle);
      }
      $(track).append(bar);
    }
    $("timeline-duration").textContent = tc(this.total, this.fps);
    this.setFrame(this.frame ?? 0);
  }
  trim(e, c, side, block) {
    e.stopPropagation();
    e.preventDefault();
    this.trimming = true;
    const start = e.clientX, baseIn = c.inFrame, baseOut = c.outFrame, baseDuration = length(c), limit = this.p.assets.find((a) => a.id === c.assetId).frames;
    let changed;
    const move = (event) => {
      const delta = Math.round((event.clientX - start) / this.px);
      if (c.kind === "hold") {
        const n = Math.max(1, baseDuration + delta * (side === "start" ? -1 : 1));
        changed = { type: "trim", id: c.id, durationFrames: n };
        block.style.width = n * this.px + "px";
      } else {
        const i = side === "start" ? Math.max(0, Math.min(baseOut - 1, baseIn + delta)) : baseIn, o = side === "end" ? Math.max(baseIn + 1, Math.min(limit, baseOut + delta)) : baseOut;
        changed = { type: "trim", id: c.id, inFrame: i, outFrame: o };
        block.style.width = (o - i) * this.px + "px";
      }
    };
    const end = () => {
      document.removeEventListener("pointermove", move);
      document.removeEventListener("pointerup", end);
      setTimeout(() => this.trimming = false, 0);
      if (changed) this.save(changed);
      else this.render();
    };
    document.addEventListener("pointermove", move);
    document.addEventListener("pointerup", end, { once: true });
  }
  setFrame(frame) {
    this.frame = frame;
    $("playhead").style.left = frame * this.px + "px";
    $("playhead").setAttribute("aria-valuenow", frame);
    $("playhead").setAttribute("aria-valuemin", 0);
    $("playhead").setAttribute("aria-valuemax", Math.max(0, this.total - 1));
  }
  overlayDrag(e, o, c, bar, side) {
    e.stopPropagation();
    e.preventDefault();
    const x = e.clientX, offset = o.anchor === "source" ? c.inFrame : 0, limit = offset + length(c), span = o.endFrame - o.startFrame;
    let operation;
    const move = (event) => {
      const delta = Math.round((event.clientX - x) / this.px);
      if (!delta) return;
      this.trimming = true;
      let start = o.startFrame, end2 = o.endFrame;
      if (side === "start") start = Math.max(offset, Math.min(end2 - 1, start + delta));
      else if (side === "end") end2 = Math.min(limit, Math.max(start + 1, end2 + delta));
      else {
        start = Math.max(offset, Math.min(Math.max(offset, limit - span), start + delta));
        end2 = Math.min(limit, start + span);
      }
      operation = { type: "overlay", id: o.id, startFrame: start, endFrame: end2 };
      bar.style.left = (c.startFrame + Math.max(0, start - offset)) * this.px + "px";
      bar.style.width = Math.max(3, (Math.min(limit, end2) - Math.max(offset, start)) * this.px) + "px";
    };
    const end = () => {
      document.removeEventListener("pointermove", move);
      document.removeEventListener("pointerup", end);
      if (operation) this.save(operation);
      else this.select(c.id, o.id);
      setTimeout(() => this.trimming = false, 0);
    };
    document.addEventListener("pointermove", move);
    document.addEventListener("pointerup", end, { once: true });
  }
  highlight(clipId, overlayId) {
    for (const e of document.querySelectorAll(".clip-block")) e.classList.toggle("selected", e.dataset.clip === clipId);
    for (const e of document.querySelectorAll(".overlay-block")) e.classList.toggle("selected", e.dataset.overlayId === overlayId);
  }
}
