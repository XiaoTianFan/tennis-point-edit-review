import { t } from "./i18n.js";
import { $, rate, length, layout, bounds, tc, buttonIcon } from "./model.js";
export class Player {
  constructor(url, changed, error) {
    this.url = url;
    this.changed = changed;
    this.error = error;
    this.video = $("video");
    this.frameImage = $("exact-frame");
    this.mode = "edited";
    this.frame = 0;
    this.playing = false;
    this.seekGeneration = 0;
    new ResizeObserver(([entry]) => {
      const w = Math.min(entry.contentRect.width, entry.contentRect.height * 16 / 9);
      $("canvas").style.width = w + "px";
      $("canvas").style.height = w * 9 / 16 + "px";
    }).observe($("viewer"));
    this.video.onended = () => {
      if (this.mode === "edited" && this.frame < this.total - 1) this.seek(this.clips.find((c) => c.id === this.clip.id).endFrame, true);
      else this.pause();
    };
    this.video.onerror = () => this.error("decodeError");
    const tick = (_now, metadata) => {
      if (this.playing && (this.mode === "source" || this.clip?.kind !== "hold") && !this.video.seeking) {
        const sf = Math.round(metadata.mediaTime * this.fps);
        if (this.mode === "source") {
          this.frame = Math.min(this.asset.frames - 1, sf);
          this.paint();
        } else if (sf >= this.clip.outFrame) {
          if (this.clip.endFrame < this.total) this.seek(this.clip.endFrame, true);
          else this.pause();
        } else if (sf >= this.clip.inFrame) {
          this.frame = this.clip.startFrame + sf - this.clip.inFrame;
          this.paint();
        }
      }
      this.video.requestVideoFrameCallback(tick);
    };
    if (this.video.requestVideoFrameCallback) this.video.requestVideoFrameCallback(tick);
    else this.error("browserError");
  }
  setProject(p) {
    this.p = p;
    if (this.mode === "source" && this.asset) this.asset = p.assets.find(a => a.id === this.asset.id);
    this.fps = rate(p);
    this.clips = layout(p);
    this.total = this.clips.at(-1).endFrame;
    this.overlayIds = null;
    this.seek(this.mode === "source" ? this.frame : Math.min(this.frame, this.total - 1));
  }
  async seek(frame, play = false) {
    if (!this.p) return;
    const generation = ++this.seekGeneration;
    this.playing = false;
    cancelAnimationFrame(this.holdTimer);
    this.video.pause();
    this.frame = Math.max(0, Math.min(Math.round(frame), this.mode === "source" && this.asset ? this.asset.frames - 1 : this.total - 1));
    if (this.mode === "edited") {
      this.clip = this.clips.find((c) => this.frame >= c.startFrame && this.frame < c.endFrame) ?? this.clips[0];
      this.asset = this.p.assets.find((a) => a.id === this.clip.assetId);
    } else if (!this.asset) {
      this.clip = this.clips[0];
      this.asset = this.p.assets.find((a) => a.id === this.clip.assetId);
    }
    const sourceFrame = this.sourceFrame();
    const src = this.url("/media/" + this.asset.id);
    if (this.video.getAttribute("src") !== src) this.video.src = src;
    if (this.video.readyState < 1) {
      await new Promise((resolve) => {
        this.video.addEventListener("loadedmetadata", resolve, { once: true });
        this.video.addEventListener("error", resolve, { once: true });
      });
    }
    if (generation !== this.seekGeneration) return;
    this.video.currentTime = (sourceFrame + 0.1) / this.fps;
    this.frameImage.hidden = true;
    this.paint();
    if (play && !(this.mode === "edited" && this.clip.kind === "hold")) this.play();
    else {
      const imageUrl = this.url(`/api/frame?asset=${this.asset.id}&frame=${sourceFrame}`);
      this.frameImage.onload = () => {
        if (generation === this.seekGeneration && !this.playing) {
          this.frameImage.hidden = false;
          $("frame-status").textContent = t("decodedFrame", {frame: sourceFrame});
          if (play) this.play();
        }
      };
      this.frameImage.src = imageUrl;
    }
  }
  sourceFrame() {
    if (this.mode === "source") return this.frame;
    return this.clip.inFrame + (this.clip.kind === "hold" ? 0 : this.frame - this.clip.startFrame);
  }
  switchMode(mode) {
    if (mode === this.mode) return;
    const sf = this.sourceFrame();
    this.mode = mode;
    if (mode === "source") this.seek(sf);
    else {
      const matching = this.clips.find((c) => c.assetId === this.asset.id && c.kind !== "hold" && sf >= c.inFrame && sf < c.outFrame) ?? this.clip;
      this.seek(matching.startFrame + Math.max(0, Math.min(length(matching) - 1, sf - matching.inFrame)));
    }
  }
  pause() {
    this.playing = false;
    this.video.pause();
    cancelAnimationFrame(this.holdTimer);
    this.seek(this.frame);
  }
  play() {
    this.playing = true;
    this.frameImage.hidden = true;
    if (this.mode === "edited" && this.clip.kind === "hold") {
      this.frameImage.hidden = false;
      const base = this.frame, start = performance.now();
      const tick = () => {
        if (!this.playing) return;
        this.frame = base + Math.floor((performance.now() - start) / 1e3 * this.fps * this.video.playbackRate);
        if (this.frame >= this.clip.endFrame) {
          if (this.clip.endFrame < this.total) this.seek(this.clip.endFrame, true);
          else {
            this.frame = this.total - 1;
            this.pause();
          }
          return;
        }
        this.paint();
        this.holdTimer = requestAnimationFrame(tick);
      };
      this.holdTimer = requestAnimationFrame(tick);
    } else this.video.play().catch((e) => {
      this.playing = false;
      this.error(e);
    });
    this.paint();
  }
  paint() {
    let linked = this.mode === "edited";
    if (this.mode === "source") {
      const match = this.clips.find(c => c.assetId === this.asset.id && c.kind !== "hold" && this.frame >= c.inFrame && this.frame < c.outFrame);
      linked = !!match;
      if (match) this.clip = match;
    }
    const c = this.clip, local = this.frame - c.startFrame;
    const active = this.mode === "edited" ? this.p.overlays.filter((o) => o.clipId === c.id && local >= bounds(o, c)[0] && local < bounds(o, c)[1]) : [];
    const ids = active.map((o) => o.id).join("|");
    if (ids !== this.overlayIds) {
      this.overlayIds = ids;
      $("graphics").replaceChildren(...active.map((o) => {
        const img = document.createElement("img");
        img.src = this.url("/graphics/" + o.id);
        img.alt = t("component." + o.component);
        img.dataset.overlay = o.id;
        return img;
      }));
    }
    for (const o of active) {
      $("graphics").querySelector(`[data-overlay="${o.id}"]`).alt = t("component." + o.component);
      let opacity = 1;
      if (o.component === "statsPanel") {
        const [start, end] = bounds(o, c);
        opacity = Math.max(0, Math.min(1, (local - start) / 9, (end - 1 - local) / 9));
      }
      $("graphics").querySelector(`[data-overlay="${o.id}"]`).style.opacity = opacity;
    }
    $("empty-view").hidden = true;
    buttonIcon($("play"), this.playing ? "pause" : "play");
    $("play").setAttribute('aria-label', t(this.playing ? "pause" : "play"));
    $("edited").classList.toggle("active", this.mode === "edited");
    $("source").classList.toggle("active", this.mode === "source");
    $("timecode").textContent = tc(this.frame, this.fps) + " / " + tc(this.mode === "source" ? this.asset.frames : this.total, this.fps);
    $("source-position").max = (this.mode === "source" ? this.asset.frames : this.total) - 1;
    $("source-position").value = this.frame;
    const original = (this.asset.sourceStartSeconds ?? 0) + this.sourceFrame() / this.fps;
    $("source-time").textContent = t("sourceTime", {seconds: original.toFixed(3), fps: this.p.fps});
    $("frame-status").textContent = this.playing ? t("playing") : this.frameImage.hidden ? t("decoding") : t("decodedFrame", {frame: this.sourceFrame()});
    this.changed(this.frame, c, this.mode, linked);
  }
}
