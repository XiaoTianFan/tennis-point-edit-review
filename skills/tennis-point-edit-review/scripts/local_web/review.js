import { t } from "./i18n.js";
import { $, el, answer, causes, changeAnswer, reviewStatus } from "./model.js";
export class Review {
  constructor(select, save) {
    this.select = select;
    this.save = save;
    this.nodes = /* @__PURE__ */ new Map();
    $("search").oninput = () => this.search();
    $("search").onkeydown = (e) => {
      if (e.key === "Enter") document.querySelector(".search-match")?.scrollIntoView({ block: "center" });
    };
  }
  setProject(p) {
    this.p = p;
    const ids = JSON.stringify([p.review.rows, p.players]);
    if (this.ids !== ids) {
      this.ids = ids;
      const scroll = $("review-list").scrollTop;
      this.build();
      $("review-list").scrollTop = scroll;
    }
    this.localize();
    this.sync();
  }
  build() {
    this.nodes.clear();
    $("review-list").replaceChildren();
    for (const r of this.p.review.rows) {
      const card = el("article", null, { "data-point": r.pointId, class: "point-card" }), head = el("button", r.reviewId + " / " + r.pointId, { class: "point-heading", "aria-label": t("jump", {point: r.pointId}) });
      head.onclick = () => this.select(r.pointId);
      card.tabIndex = 0;
      card.onclick = (event) => {
        if (event.target.closest('input,textarea,select,button,label,a,[contenteditable]')) return;
        if (window.getSelection()?.isCollapsed === false) return;
        this.select(r.pointId);
      };
      card.onkeydown = (event) => {
        if (event.target === card && ['Enter', ' '].includes(event.key)) {
          event.preventDefault(); event.stopPropagation(); this.select(r.pointId);
        }
      };
      card.append(head, el("span", "", { class: "row-status" }));
      card.append(el("div", "", { class: "point-meta" }), el("p", r.reason ?? "", { class: "point-reason" }));
      const inputs = [];
      for (const [field, choices] of [["scoringPlayerId", [...this.p.players.map((p) => [p.id, p.name]), ["undetermined", t("uncertain")]]], ["deadBallType", causes]]) {
        const group = el("fieldset", null, { class: "choices " + (field === "deadBallType" ? "causes" : "winners") });
        group.append(el("legend", t(field === "deadBallType" ? "deadBall" : "winner")));
        for (const [value, label] of choices) {
          const lab = el("label", null, { class: "choice" }), input = el("input", null, { type: "radio", name: field + r.pointId, value, "aria-label": r.pointId + " " + label });
          lab.append(input, el("span", label));
          group.append(lab);
          input.onchange = () => this.changed(r, field, value);
          inputs.push({ input, field, value, lab });
        }
        card.append(group);
      }
      const checks = el("div", null, { class: "review-checks" });
      for (const field of ["doubleFaultConfirmed", "extra", "reviewConfirmed", ...r.countingIssueRequired ? ["countingIssueResolved"] : []]) {
        const label = t(field);
        const lab = el("label"), input = el("input", null, { type: "checkbox", "aria-label": r.pointId + " " + label });
        lab.append(input, el("span", label));
        checks.append(lab);
        input.onchange = () => this.changed(r, field, input.checked || (field === "doubleFaultConfirmed" ? null : false));
        inputs.push({ input, field, lab });
      }
      card.append(checks);
      const note = el("textarea", null, { "aria-label": t("note", {point: r.pointId}), placeholder: t("notePlaceholder"), rows: "2" });
      let timer;
      note.oninput = () => {
        clearTimeout(timer);
        this.p.answers[r.pointId] = { ...answer(this.p, r), note: note.value };
        timer = setTimeout(() => this.changed(r, "note", note.value), 400);
      };
      note.onblur = () => {
        clearTimeout(timer);
        if (note.value !== this.savedNotes?.[r.pointId]) this.changed(r, "note", note.value);
      };
      card.append(note);
      this.nodes.set(r.pointId, { card, inputs, note });
      $("review-list").append(card);
    }
  }
  localize() {
    for (const r of this.p.review.rows) {
      const n = this.nodes.get(r.pointId), server = this.p.players.find(p => p.id === r.serverId)?.name ?? r.serverId;
      n.card.querySelector('.point-heading').setAttribute('aria-label', t('jump', {point: r.pointId}));
      n.card.setAttribute('aria-label', t('jump', {point: r.pointId}));
      n.card.querySelector('.point-meta').textContent = t('pointMeta', {set: r.setNumber ?? 1, game: r.gameNumber ?? '?', server, serve: (r.serveNumbers ?? [r.serveNumber ?? '?']).join(' → ')});
      n.card.querySelector('.winners legend').textContent = t('winner');
      n.card.querySelector('.causes legend').textContent = t('deadBall');
      for (const {input, field, value, lab} of n.inputs) {
        const label = field === 'scoringPlayerId' ? value === 'undetermined' ? t('uncertain') : this.p.players.find(p => p.id === value).name : field === 'deadBallType' ? t('cause.' + value) : t(field);
        lab.querySelector('span').textContent = label;
        lab.title = label;
        input.setAttribute('aria-label', r.pointId + ' ' + label);
      }
      n.note.placeholder = t('notePlaceholder');
      n.note.setAttribute('aria-label', t('note', {point: r.pointId}));
    }
    this.progress();
  }
  progress() {
    let reviewed = 0, unknown = 0;
    for (const r of this.p.review.rows) {
      const status = reviewStatus(r, answer(this.p, r));
      if (['resolved', 'replay', 'unresolved'].includes(status)) reviewed++;
      if (status === 'unresolved') unknown++;
      this.nodes.get(r.pointId).card.querySelector('.row-status').textContent = t('status.' + status);
    }
    $('review-progress').textContent = t('progress', {reviewed, total: this.p.review.rows.length}) + (unknown ? t('unknown', {count: unknown}) : '');
  }
  changed(r, field, value) {
    const x = changeAnswer(this.p, r, answer(this.p, r), field, value);
    this.p.answers[r.pointId] = x;
    this.sync();
    this.save({ type: "review", pointId: r.pointId, answer: x });
  }
  sync() {
    this.savedNotes = {};
    for (const r of this.p.review.rows) {
      const x = answer(this.p, r), n = this.nodes.get(r.pointId), s = reviewStatus(r, x);
      this.savedNotes[r.pointId] = x.note;
      n.card.dataset.status = s;
      for (const { input, field, value } of n.inputs) {
        input.checked = value ? value === "undetermined" ? x.winnerUndetermined : x[field] === value : !!x[field];
        input.disabled = x.deadBallType === "replay" && ["scoringPlayerId", "doubleFaultConfirmed", "extra"].includes(field);
      }
      if (document.activeElement !== n.note) n.note.value = x.note;
    }
    this.progress();
    this.search();
  }
  highlight(pid) {
    for (const [id, n] of this.nodes) n.card.classList.toggle("selected", id === pid);
  }
  search() {
    const q = $("search").value.trim().toLowerCase();
    let count = 0;
    for (const r of this.p.review.rows) {
      const n = this.nodes.get(r.pointId), found = !!q && [r.pointId, r.reviewId, r.reason, answer(this.p, r).note].join(" ").toLowerCase().includes(q);
      n.card.classList.toggle("search-match", found);
      if (found) count++;
    }
    $("search-count").textContent = q ? String(count) : "";
  }
}
