// UI geometry is independent of the match and project schema.
export const clamp = (value, min, max) => Math.max(min, Math.min(max, value));
export function paneLimits(width, height) {
  return {review: [250, Math.max(250, width - 426)], timeline: [170, Math.max(170, height - 385)]};
}
export function zoomAt(zoom, delta, scroll, pointer) {
  const next = clamp(zoom * Math.exp(-delta * 0.002), 0.5, 8);
  return {zoom: next, scroll: Math.max(0, (scroll + pointer) * next / zoom - pointer)};
}
export function wheelPixels(event, pageSize) {
  return (event.deltaY || event.deltaX) * (event.deltaMode === 1 ? 16 : event.deltaMode === 2 ? pageSize : 1);
}
export function initPanes() {
  const root = document.documentElement, app = document.getElementById('app');
  const key = 'courtside-panes-v1';
  let saved = {};
  try { const value = JSON.parse(localStorage.getItem(key)); if (value && typeof value === 'object') saved = value; } catch { /* Use defaults. */ }
  const defaults = () => ({review: innerWidth <= 1150 ? 300 : 350, timeline: 256});
  const handles = {review: document.getElementById('review-divider'), timeline: document.getElementById('timeline-divider')};
  const props = {review: '--review-width', timeline: '--timeline-pane-height'};
  const persist = () => { try { localStorage.setItem(key, JSON.stringify(saved)); } catch { /* Session layout still works. */ } };
  function apply() {
    const limits = paneLimits(app.clientWidth, app.clientHeight);
    for (const kind of Object.keys(handles)) {
      const [min, max] = limits[kind];
      const value = clamp(Number.isFinite(saved[kind]) ? saved[kind] : defaults()[kind], min, max);
      root.style.setProperty(props[kind], value + 'px');
      for (const [name, n] of Object.entries({min, max, now: Math.round(value)})) handles[kind].setAttribute('aria-value' + name, n);
    }
  }
  for (const [kind, handle] of Object.entries(handles)) {
    const reset = () => { delete saved[kind]; persist(); apply(); };
    handle.ondblclick = reset;
    handle.onkeydown = (e) => {
      const keys = kind === 'review' ? ['ArrowLeft', 'ArrowRight'] : ['ArrowDown', 'ArrowUp'];
      if (![...keys, 'Home'].includes(e.key)) return;
      e.preventDefault(); e.stopPropagation();
      if (e.key === 'Home') return reset();
      saved[kind] = clamp(Number(handle.getAttribute('aria-valuenow')) + (e.key === keys[0] ? -1 : 1) * (e.shiftKey ? 50 : 10), ...paneLimits(app.clientWidth, app.clientHeight)[kind]);
      persist(); apply();
    };
    handle.onpointerdown = (e) => {
      if (e.button !== 0) return;
      e.preventDefault(); handle.focus(); handle.setPointerCapture(e.pointerId);
      const start = kind === 'review' ? e.clientX : e.clientY;
      const base = Number(handle.getAttribute('aria-valuenow'));
      document.body.classList.add('resizing-' + kind);
      handle.onpointermove = (event) => {
        const delta = kind === 'review' ? event.clientX - start : start - event.clientY;
        saved[kind] = clamp(base + delta, ...paneLimits(app.clientWidth, app.clientHeight)[kind]); apply();
      };
      const end = () => {
        handle.onpointermove = null; handle.onpointerup = null; handle.onpointercancel = null; handle.onlostpointercapture = null;
        document.body.classList.remove('resizing-' + kind); persist();
      };
      handle.onpointerup = end; handle.onpointercancel = end; handle.onlostpointercapture = end;
    };
  }
  new ResizeObserver(apply).observe(app);
  apply();
}
