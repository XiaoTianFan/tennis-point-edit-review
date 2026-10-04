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
    this.sync();
  }
  build() {
    this.nodes.clear();
    $("review-list").replaceChildren();
    for (const r of this.p.review.rows) {
      const card = el("article", null, { "data-point": r.pointId, class: "point-card" }), head = el("button", r.reviewId + " / " + r.pointId, { class: "point-heading", "aria-label": "Jump to " + r.pointId });
      head.onclick = () => this.select(r.pointId);
      card.append(head, el("span", "", { class: "row-status" }));
      const server = this.p.players.find((p) => p.id === r.serverId)?.name ?? r.serverId;
      card.append(el("div", `Set ${r.setNumber ?? 1} · Game ${r.gameNumber ?? "?"} · ● ${server} · Serve ${(r.serveNumbers ?? [r.serveNumber]).join(" → ")}`, { class: "point-meta" }), el("p", r.reason ?? "", { class: "point-reason" }));
      const inputs = [];
      for (const [field, choices] of [["scoringPlayerId", [...this.p.players.map((p) => [p.id, p.name]), ["undetermined", "Uncertain"]]], ["deadBallType", causes]]) {
        const group = el("fieldset", null, { class: "choices " + (field === "deadBallType" ? "causes" : "winners") });
        group.append(el("legend", field === "deadBallType" ? "Dead ball" : "Point winner"));
        for (const [value, label] of choices) {
          const lab = el("label", null, { class: "choice" }), input = el("input", null, { type: "radio", name: field + r.pointId, value, "aria-label": r.pointId + " " + label });
          lab.append(input, el("span", label));
          group.append(lab);
          input.onchange = () => this.changed(r, field, value);
          inputs.push({ input, field, value });
        }
        card.append(group);
      }
      const checks = el("div", null, { class: "review-checks" });
      for (const [field, label] of [["doubleFaultConfirmed", "Double fault"], ["extra", "Extra point"], ["reviewConfirmed", "Reviewed"], ...r.countingIssueRequired ? [["countingIssueResolved", "Count checked"]] : []]) {
        const lab = el("label"), input = el("input", null, { type: "checkbox", "aria-label": r.pointId + " " + label });
        lab.append(input, document.createTextNode(label));
        checks.append(lab);
        input.onchange = () => this.changed(r, field, input.checked || (field === "doubleFaultConfirmed" ? null : false));
        inputs.push({ input, field });
      }
      card.append(checks);
      const note = el("textarea", null, { "aria-label": r.pointId + " note", placeholder: "Evidence, correction or a question…", rows: "2" });
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
  changed(r, field, value) {
    const x = changeAnswer(this.p, r, answer(this.p, r), field, value);
    this.p.answers[r.pointId] = x;
    this.sync();
    this.save({ type: "review", pointId: r.pointId, answer: x });
  }
  sync() {
    let reviewed = 0, unknown = 0;
    this.savedNotes = {};
    for (const r of this.p.review.rows) {
      const x = answer(this.p, r), n = this.nodes.get(r.pointId), s = reviewStatus(r, x);
      this.savedNotes[r.pointId] = x.note;
      if (["resolved", "replay", "unresolved"].includes(s)) reviewed++;
      if (s === "unresolved") unknown++;
      n.card.querySelector(".row-status").textContent = { pending: "To review", partial: "In progress", resolved: "Reviewed", unresolved: "Needs inference", replay: "Replay" }[s];
      n.card.dataset.status = s;
      for (const { input, field, value } of n.inputs) {
        input.checked = value ? value === "undetermined" ? x.winnerUndetermined : x[field] === value : !!x[field];
        input.disabled = x.deadBallType === "replay" && ["scoringPlayerId", "doubleFaultConfirmed", "extra"].includes(field);
      }
      if (document.activeElement !== n.note) n.note.value = x.note;
    }
    $("review-progress").textContent = `${reviewed}/${this.p.review.rows.length} reviewed${unknown ? " · " + unknown + " unknown" : ""}`;
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
