import { CATEGORIES, changeLabel, metric, shortDate, term, tipHtml } from "../lib/glossary.js";

// The leaderboard page: headline charts, detail chart cards (tabs, table view, image download,
// links), the readiness summary and the tables. Data comes from the JSON embedded in the page.
const DATA = JSON.parse(document.getElementById("owb-data").textContent);
const NS = "http://www.w3.org/2000/svg";
const FAMILIES = ["moonshot", "zhipu", "deepseek", "qwen", "mistral", "meta", "minimax", "nvidia"];
const FAMILY_LABEL = { moonshot: "Moonshot", zhipu: "Z.ai", deepseek: "DeepSeek", qwen: "Qwen", mistral: "Mistral", meta: "Meta", minimax: "MiniMax", nvidia: "NVIDIA", anchor: "Closed reference", simulated: "Simulated test agent", reference: "Reference", other: "Other" };
const TOKENS = [
  { key: "output_tokens", label: "Output", color: "var(--tk-out)" },
  { key: "input_tokens", label: "Input", color: "var(--tk-in)" },
  { key: "cache_write_tokens", label: "Cache write", color: "var(--tk-cw)" },
  { key: "cache_read_tokens", label: "Cache read", color: "var(--tk-cr)" },
];
const TARGETS = DATA.index.targets || {};
const LEVELS = (TARGETS.levels || []).filter((l) => l.index != null);
const hasOpen = DATA.subjects.some((s) => s.board === "open-weights");
const hasReal = DATA.subjects.some((s) => s.type === "model" || s.type === "product");
const appModels = DATA.subjects.filter((s) => s.board === "open-weights" && s.type === "product").length;
const hasClosed = DATA.subjects.some((s) => !s.simulated && s.type !== "reference" && s.board !== "open-weights");
const state = { board: "all", harness: appModels >= 2 ? "openwork" : "both", showTest: !hasReal };
/** Short names for the readiness bars drawn on the Work Index charts. */
const BAR_NAME = { delegable: "Delegable", supervised: "With review" };

const fmt = (v, d = 1) => (v == null || Number.isNaN(v) ? "–" : Number(v).toFixed(d));
const money = (v) => (v == null ? "n/a" : v < 0.01 ? "$" + v.toFixed(4) : "$" + v.toFixed(v < 1 ? 3 : 2));
const mins = (s) => (s == null ? "–" : (s / 60).toFixed(s < 60 ? 2 : 1));
const kfmt = (v) => (v == null ? "–" : v >= 1e6 ? (v / 1e6).toFixed(v >= 1e7 ? 0 : 1) + "M" : v >= 1e3 ? Math.round(v / 1e3) + "k" : String(Math.round(v)));
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const BASE = document.documentElement.dataset.base || "";
const slug = (id) => String(id).toLowerCase().replace(/[^a-z0-9.-]+/g, "-");
const changeSlug = (c) => c.title.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
const modelHref = (s) => `${BASE}/models/${slug(s.id)}/`;
const taskHref = (t) => `${BASE}/tasks/${slug(t.id)}/`;
const el = (tag, attrs = {}, parent) => { const n = document.createElementNS(NS, tag); for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, v); if (parent) parent.appendChild(n); return n; };
const famOf = (s) => (s.type === "reference" ? "reference" : s.simulated ? "simulated" : s.anchor ? "anchor" : FAMILIES.includes(s.family) ? s.family : "other");
const loop = (s) => s.harness === "owb-agent";
/** The entity's own colour: marks, legend swatches and table dots. */
const solid = (s) => {
  const f = famOf(s), i = FAMILIES.indexOf(f);
  if (i >= 0) return `var(--f${i + 1})`;
  if (f === "anchor") return "var(--ref)";
  if (f === "simulated") return "var(--f3)";
  return "var(--neutral)";
};
/** Fill for a mark: simulated agents are hatched; plain-loop runs wear a lighter tint (see `tint`). */
const fill = (s) => (famOf(s) === "simulated" ? "url(#hatch)" : solid(s));
const tint = (s) => (loop(s) ? 0.5 : 1);
/** Plain-loop bars keep a thin outline in their colour so the lighter tint still reads as a bar. */
const edge = (s) => (loop(s) ? { stroke: solid(s), "stroke-width": 1.25, "stroke-opacity": 0.9 } : {});
const short = (s) => s.label.replace(/^Simulated: /, "Sim: ").replace(/\s*\(.*?\)\s*/g, " ").replace(/\s*·\s*plain loop/, " · loop").replace(/\s+/g, " ").trim();
const name = (s) => s.label + (s.anchor ? " (closed, for reference)" : "");
const harnessName = (s) => (s.harness === "openwork-desktop" ? "Agent app" : s.harness === "owb-agent" ? "Plain loop" : s.harness || s.type);
/** A small "i" that explains a metric or term on hover and opens its page on click. */
const info = (id) => { const t = term(id); return t ? `<a class="info" href="${BASE}/${t.page || "metrics/"}" data-tip="${esc(tipHtml(id))}" aria-label="What is ${esc(t.name)}?">i</a>` : ""; };
const badge = (s) => (s.readiness ? `<a class="ready ${esc(s.readiness.id)}" href="${BASE}/readiness/#${esc(s.readiness.id)}" data-tip="${esc(tipHtml(s.readiness.id) + (s.readiness.reason ? `<br>Reason: ${esc(s.readiness.reason)}` : ""))}">${esc(s.readiness.label)}</a>` : "");
const th = (label, id, cls = "") => `<th${cls ? ` class=${cls}` : ""}>${esc(label)}${id ? info(id) : ""}</th>`;
const catHref = (c) => `${BASE}/categories/${c}/`;

function visible() {
  return DATA.subjects.filter((s) => {
    if (s.simulated || s.type === "reference") return state.showTest;
    if (state.board === "open" && s.board !== "open-weights") return false;
    if (state.harness === "openwork" && s.type !== "product" && !s.anchor) return false;
    if (state.harness === "control" && s.type !== "model" && !s.anchor) return false;
    return true;
  });
}
const real = () => visible().filter((s) => s.type !== "reference");
function tipFor(s, extra) {
  const ow = s.open_weights || {};
  return `<b>${esc(name(s))}</b><br>${esc(harnessName(s))}${s.readiness ? " · " + esc(s.readiness.label) : ""}<br>${extra}${ow.hf_repo ? `<br>Weights ${esc(ow.hf_repo)} @ ${esc((ow.revision || "").slice(0, 10))} · ${esc(ow.license || "")}` : ""}${s.served_by && s.served_by.length ? "<br>Served by " + esc(s.served_by.join(", ")) : ""}`;
}
function defs(svg) {
  const d = el("defs", {}, svg);
  const h = el("pattern", { id: "hatch", width: 5, height: 5, patternUnits: "userSpaceOnUse", patternTransform: "rotate(45)" }, d);
  el("rect", { width: 5, height: 5, fill: "var(--f3)", opacity: 0.3 }, h);
  el("line", { x1: 0, y1: 0, x2: 0, y2: 5, stroke: "var(--f3)", "stroke-width": 3 }, h);
}
/** A round upper bound and tick step for an axis that starts at zero: the tightest of 3–6 ticks. */
function niceAxis(max) {
  if (!(max > 0)) return { max: 1, step: 0.25 };
  const mag = 10 ** Math.floor(Math.log10(max));
  let best = null;
  for (const f of [0.1, 0.2, 0.25, 0.5, 1, 2]) {
    const step = f * mag, n = Math.ceil(max / step - 1e-9);
    if (n < 3 || n > 6) continue;
    if (!best || n * step < best.max - 1e-9) best = { max: n * step, step };
  }
  return best || { max, step: max / 4 };
}

// Vertical bars, one per subject: optional CI whiskers, stacked segments, target lines and a y axis.
function columns(host, rows, opts) {
  host.innerHTML = "";
  if (!rows.length) { host.innerHTML = `<p class="empty">${opts.empty}</p>`; return; }
  const W = Math.max(280, host.clientWidth), H = opts.height || 360;
  const longest = Math.max(...rows.map((s) => short(s).length));
  const flat = (W - 60) / rows.length >= Math.max(96, longest * 6.8 + 10);
  const gutter = (opts.targets || []).length ? (W < 520 ? 76 : 96) : 8;
  const m = { l: opts.axis ? 52 : 8, r: gutter, t: opts.whisker ? 34 : 26, b: flat ? 44 : Math.min(176, 30 + Math.min(28, longest) * 5.1) };
  // Angled names run down-left from the first bar: leave room so the first one is not clipped.
  if (!flat) m.l = Math.max(m.l, Math.min(120, Math.min(28, short(rows[0]).length) * 4.4 - (W - m.l - m.r) / rows.length / 2 + 6));
  const svg = el("svg", { width: W, height: H, viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": opts.aria }, host);
  defs(svg);
  const vals = rows.map(opts.value);
  const hi = rows.map((s, i) => (opts.whisker && opts.whisker(s) ? opts.whisker(s)[1] : vals[i]));
  const axis = opts.max ? { max: opts.max, step: opts.max / 4 } : niceAxis(Math.max(...hi) * 1.08);
  const max = axis.max;
  const bw = (W - m.l - m.r) / rows.length, barW = Math.max(8, Math.min(opts.maxBar || 56, bw * 0.62));
  const y = (v) => m.t + (1 - Math.min(v, max) / max) * (H - m.t - m.b);
  for (let i = 1; i * axis.step <= max + 1e-9; i++) {
    const t = +(i * axis.step).toPrecision(10);
    el("line", { x1: m.l, x2: W - m.r, y1: y(t), y2: y(t), stroke: "var(--grid)", "stroke-dasharray": "2 4" }, svg);
    if (opts.axis) el("text", { x: m.l - 10, y: y(t) + 4, "text-anchor": "end", class: "tick" }, svg).textContent = opts.tick ? opts.tick(t) : t;
  }
  (opts.targets || []).forEach((t) => el("line", { x1: m.l, x2: W - m.r + 6, y1: y(t.v), y2: y(t.v), stroke: "var(--ink-3)", "stroke-width": 1, "stroke-dasharray": "3 4" }, svg));
  rows.forEach((s, i) => {
    const v = vals[i], cx = m.l + bw * i + bw / 2, x0 = cx - barW / 2, base = H - m.b;
    const a = el("a", { href: modelHref(s), "aria-label": `${s.label}: ${opts.label(v, s)}`, "data-tip": tipFor(s, opts.tip(v, s)) }, svg);
    el("rect", { x: cx - bw / 2, y: m.t, width: bw, height: base - m.t, fill: "transparent" }, a);
    const top = y(v);
    if (opts.stack) {
      // Segments bottom to top, a 2px surface gap between them, the top one rounded.
      const parts = opts.stack(s);
      let acc = 0;
      const drawn = parts.map((p, j) => ({ ...p, j })).filter((p) => p.v > 0);
      drawn.forEach((p, n) => {
        const yb = y(acc), yt = y(acc + p.v); acc += p.v;
        const gapB = n > 0 ? 1 : 0, gapT = n < drawn.length - 1 ? 1 : 0;
        const y1 = yt + gapT, h = Math.max(0, yb - gapB - y1);
        if (h <= 0) return;
        const r = n === drawn.length - 1 ? Math.min(4, barW / 4, h) : 0;
        el("path", { d: `M${x0},${y1 + h} V${y1 + r} Q${x0},${y1} ${x0 + r},${y1} H${x0 + barW - r} Q${x0 + barW},${y1} ${x0 + barW},${y1 + r} V${y1 + h} Z`, fill: p.color }, a);
      });
    } else {
      const h = Math.max(2, base - top), r = Math.min(4, barW / 4, h / 2);
      el("path", { d: `M${x0},${top + h} V${top + r} Q${x0},${top} ${x0 + r},${top} H${x0 + barW - r} Q${x0 + barW},${top} ${x0 + barW},${top + r} V${top + h} Z`, fill: fill(s), "fill-opacity": tint(s), ...edge(s) }, a);
    }
    const ci = opts.whisker && opts.whisker(s);
    if (ci) {
      const w = Math.min(10, barW / 3);
      const d = `M${cx},${y(ci[0])} V${y(ci[1])} M${cx - w},${y(ci[0])} H${cx + w} M${cx - w},${y(ci[1])} H${cx + w}`;
      // A surface halo keeps the whisker visible where it crosses a dark bar.
      el("path", { d, stroke: "var(--panel)", "stroke-width": 4, fill: "none", "stroke-linecap": "round", opacity: 0.9 }, a);
      el("path", { d, stroke: "var(--ink)", "stroke-width": 1.5, fill: "none", "stroke-linecap": "round", class: "whisker" }, a);
    }
    // Values sit above the bar (or its whisker) in text ink, never on the colour.
    const label = opts.label(v, s);
    el("text", { x: cx, y: ci ? y(ci[1]) - 8 : top - 7, "text-anchor": "middle", class: "val" }, svg).textContent = label;
    const nm = short(s);
    if (flat) {
      el("text", { x: cx, y: base + 22, "text-anchor": "middle", class: "lbl" }, svg).textContent = nm;
    } else {
      const lx = cx + 4, ly2 = base + 16;
      el("text", { x: lx, y: ly2, "text-anchor": "end", class: "lbl", transform: `rotate(-50 ${lx} ${ly2})` }, svg).textContent = nm.length > 28 ? nm.slice(0, 27) + "…" : nm;
    }
  });
  el("line", { x1: m.l, x2: W - m.r, y1: H - m.b, y2: H - m.b, stroke: "var(--line)" }, svg);
  // Readiness labels sit in the right gutter, clear of the bars; hover explains, click opens the page.
  (opts.targets || []).forEach((t) => {
    const g = el("a", { href: `${BASE}/readiness/#${t.id}`, "data-tip": `${tipHtml(t.id)}`, "aria-label": `${t.name} bar at ${t.v}` }, svg);
    el("text", { x: W - m.r + 12, y: y(t.v) - 2, class: "bar-name" }, g).textContent = t.name;
    el("text", { x: W - m.r + 12, y: y(t.v) + 12, class: "bar-sub" }, g).textContent = t.sub;
  });
}

// Index against a cost or time measure: the attractive quadrant, the Pareto line, labelled points.
function scatter(host, rows, opts) {
  host.innerHTML = "";
  if (!rows.length) { host.innerHTML = `<p class="empty">${opts.empty}</p>`; return; }
  const W = Math.max(300, host.clientWidth), H = opts.height || 440, m = { l: 58, r: 24, t: 18, b: 56 };
  const xs = rows.map(opts.x);
  let lo = Math.log10(Math.min(...xs)), hi = Math.log10(Math.max(...xs));
  if (hi - lo < 0.6) { const mid = (hi + lo) / 2; lo = mid - 0.3; hi = mid + 0.3; }
  lo -= 0.12; hi += 0.12;
  const yLo = Math.max(0, Math.min(90, Math.floor(Math.min(...rows.map((s) => s.index)) / 10) * 10 - 10));
  const x = (v) => m.l + ((Math.log10(v) - lo) / (hi - lo)) * (W - m.l - m.r);
  const y = (v) => m.t + (1 - (v - yLo) / (100 - yLo)) * (H - m.t - m.b);
  const svg = el("svg", { width: W, height: H, viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": opts.aria }, host);
  defs(svg);
  const sorted = (a) => a.slice().sort((p, q) => p - q);
  const medX = sorted(xs)[Math.floor(xs.length / 2)], medY = sorted(rows.map((s) => s.index))[Math.floor(rows.length / 2)];
  el("rect", { x: m.l, y: m.t, width: Math.max(0, x(medX) - m.l), height: Math.max(0, y(medY) - m.t), fill: "var(--quad)" }, svg);
  el("text", { x: m.l + 10, y: m.t + 18, class: "quad-lbl" }, svg).textContent = opts.quadrant;
  for (let g = Math.ceil(yLo / 10) * 10; g <= 100; g += 10) {
    el("line", { x1: m.l, x2: W - m.r, y1: y(g), y2: y(g), stroke: "var(--grid)" }, svg);
    el("text", { x: m.l - 10, y: y(g) + 4, "text-anchor": "end", class: "tick" }, svg).textContent = g;
  }
  // Ticks at 1, 2 and 5 of each decade, thinned to what fits.
  const ticks = [];
  for (let p = Math.floor(lo); p <= Math.ceil(hi); p++) for (const f of [1, 2, 5]) { const v = f * 10 ** p; if (Math.log10(v) >= lo && Math.log10(v) <= hi) ticks.push(v); }
  const every = Math.max(1, Math.ceil((ticks.length * 56) / (W - m.l - m.r)));
  ticks.forEach((v, i) => {
    if (i % every) return;
    el("line", { x1: x(v), x2: x(v), y1: m.t, y2: H - m.b, stroke: "var(--grid)" }, svg);
    el("text", { x: x(v), y: H - m.b + 18, "text-anchor": "middle", class: "tick" }, svg).textContent = opts.xTick(v);
  });
  el("text", { x: m.l + (W - m.l - m.r) / 2, y: H - 10, "text-anchor": "middle", class: "axis-title" }, svg).textContent = opts.xTitle;
  const ay = m.t + (H - m.t - m.b) / 2;
  el("text", { x: 16, y: ay, "text-anchor": "middle", class: "axis-title", transform: `rotate(-90 16 ${ay})` }, svg).textContent = "OpenWork Bench Work Index";
  // Pareto line: no other model is both better and cheaper (or faster).
  const front = [];
  rows.slice().sort((a, b) => opts.x(a) - opts.x(b) || b.index - a.index).forEach((s) => { if (!front.length || s.index > front[front.length - 1].index) front.push(s); });
  if (front.length > 1) el("polyline", { points: front.map((s) => `${x(opts.x(s))},${y(s.index)}`).join(" "), fill: "none", stroke: "var(--ink-2)", "stroke-width": 2, "stroke-dasharray": "0.5 6", "stroke-linecap": "round", class: "pareto" }, svg);
  // Labels go beside their point where they touch no other point or label.
  const pts = rows.map((s) => ({ x: x(opts.x(s)), y: y(s.index) }));
  const boxes = [];
  const free = (b) => b.x0 >= m.l && b.x1 <= W - m.r && b.y0 >= m.t && b.y1 <= H - m.b &&
    !boxes.some((o) => b.x0 < o.x1 && b.x1 > o.x0 && b.y0 < o.y1 && b.y1 > o.y0) &&
    !pts.some((p) => p.x > b.x0 - 9 && p.x < b.x1 + 9 && p.y > b.y0 - 9 && p.y < b.y1 + 9);
  rows.slice().sort((a, b) => b.index - a.index).forEach((s) => {
    const cx = x(opts.x(s)), cy = y(s.index), label = short(s), w = label.length * 6.7 + 4;
    const a = el("a", { href: modelHref(s), "aria-label": s.label, "data-tip": tipFor(s, opts.tip(s)) }, svg);
    el("circle", { cx, cy, r: 16, fill: "transparent" }, a);
    el("circle", { cx, cy, r: 7.5, fill: fill(s), "fill-opacity": tint(s), stroke: loop(s) ? solid(s) : "var(--panel)", "stroke-width": loop(s) ? 1.5 : 2 }, a);
    const spots = [];
    for (const dy of [0, -14, 14, -28, 28]) spots.push(["start", cx + 13, cy + 4 + dy], ["end", cx - 13, cy + 4 + dy]);
    spots.splice(2, 0, ["middle", cx, cy - 15], ["middle", cx, cy + 23]);
    const box = ([an, tx, ty]) => ({ x0: an === "start" ? tx : an === "end" ? tx - w : tx - w / 2, x1: an === "start" ? tx + w : an === "end" ? tx : tx + w / 2, y0: ty - 11, y1: ty + 3 });
    const inside = (b) => b.x0 >= m.l && b.x1 <= W - m.r && b.y0 >= m.t && b.y1 <= H - m.b;
    const pick = spots.find((sp) => free(box(sp))) || spots.find((sp) => inside(box(sp))) || spots[0];
    boxes.push(box(pick));
    el("text", { x: pick[1], y: pick[2], "text-anchor": pick[0], class: "lbl pt" }, svg).textContent = label;
  });
}

// Shared legend: families present, plus the textures in use.
function familyLegend(rows, extra = "") {
  const fams = [...new Set(rows.map(famOf))];
  let h = fams.map((f) => {
    const i = FAMILIES.indexOf(f);
    const sw = i >= 0 ? `var(--f${i + 1})` : f === "anchor" ? "var(--ref)" : f === "simulated" ? "var(--f3); opacity:.55" : "var(--neutral)";
    return `<span><i style="background:${sw}"></i>${esc(FAMILY_LABEL[f] || f)}</span>`;
  }).join("");
  if (rows.some(loop) && rows.some((s) => !loop(s) && !s.simulated)) h += `<span><i class="sw-tint"></i>Lighter: plain loop</span>`;
  return h + extra;
}
const tokenLegend = () => TOKENS.map((t) => `<span><i style="background:${t.color}"></i>${t.label}</span>`).join("");
const tradeLegend = () => `<span><i style="background:var(--quad);box-shadow:inset 0 0 0 1px var(--line)"></i>Most attractive quadrant</span><span><i class="sw-dots"></i>Pareto line</span>`;

function table(rows, cols) {
  return `<table><thead><tr><th class=l>Model</th>${th("Harness", "harness", "l")}${cols.map((c) => th(c.h, c.id)).join("")}</tr></thead><tbody>${rows.map((s) => `<tr><td class=l><span class="dot" style="background:${solid(s)}"></span><a href="${modelHref(s)}">${esc(name(s))}</a></td><td class=l>${esc(harnessName(s))}</td>${cols.map((c) => `<td>${c.v(s)}</td>`).join("")}</tr>`).join("")}</tbody></table>`;
}

// ---- Chart cards: tabs, table view, image download and links ----
const CARDS = [];
function card(id, views) {
  const root = document.getElementById(id);
  if (!root) return;
  const c = { id, root, views, active: 0, table: false };
  const tabs = root.querySelector(".cc-tabs");
  if (tabs) {
    tabs.innerHTML = views.map((v, i) => `<button type="button" role="tab" data-i="${i}" id="${id}-${v.key}">${esc(v.tab)}</button>`).join("");
    tabs.addEventListener("click", (e) => { const b = e.target.closest("button[data-i]"); if (b) { c.active = +b.dataset.i; draw(c); } });
  }
  root.querySelector('[data-act="table"]').addEventListener("click", () => { c.table = !c.table; draw(c); });
  root.querySelector('[data-act="png"]').addEventListener("click", () => downloadPng(c));
  root.querySelector('[data-act="link"]').addEventListener("click", (e) => copyLink(c, e.currentTarget));
  CARDS.push(c);
}
function draw(c) {
  const v = c.views[c.active], rows = v.rows();
  c.root.querySelector(".cc-title").innerHTML = esc(v.title) + info(v.metric);
  c.root.querySelector(".cc-sub").textContent = v.sub;
  const more = c.root.querySelector(".cc-more"), m = metric(v.metric);
  if (more && m) { more.href = `${BASE}/metrics/${m.id}/`; more.textContent = "How it is measured →"; }
  c.root.querySelectorAll(".cc-tabs button").forEach((b, i) => b.setAttribute("aria-selected", String(i === c.active)));
  c.root.querySelector('[data-act="table"]').setAttribute("aria-pressed", String(c.table));
  const chart = c.root.querySelector(".chart"), tbl = c.root.querySelector(".cc-table");
  chart.hidden = c.table; tbl.hidden = !c.table;
  if (c.table) tbl.innerHTML = rows.length ? table(rows, v.cols) : `<p class="empty">${v.empty}</p>`;
  else v.draw(chart, rows);
  c.root.querySelector(".cc-legend").innerHTML = v.legend ? v.legend(rows) : familyLegend(rows);
}
function copyLink(c, btn) {
  const url = `${location.origin}${location.pathname}#${c.id}/${c.views[c.active].key}`;
  const done = () => { btn.classList.add("done"); btn.title = "Link copied"; setTimeout(() => { btn.classList.remove("done"); btn.title = "Copy a link to this chart"; }, 1600); };
  history.replaceState(null, "", `#${c.id}/${c.views[c.active].key}`);
  if (navigator.clipboard) navigator.clipboard.writeText(url).then(done, done); else done();
}
// The chart as a PNG, with its title and the site's name, in the current theme.
async function downloadPng(c) {
  if (c.table) { c.table = false; draw(c); }
  const svg = c.root.querySelector(".chart svg");
  if (!svg) return;
  const clone = svg.cloneNode(true);
  const src = svg.querySelectorAll("*"), dst = clone.querySelectorAll("*");
  const props = ["fill", "stroke", "stroke-width", "stroke-dasharray", "stroke-linecap", "opacity", "font-family", "font-size", "font-weight", "paint-order", "stroke-linejoin"];
  src.forEach((n, i) => { const cs = getComputedStyle(n); props.forEach((p) => dst[i].style.setProperty(p, cs.getPropertyValue(p))); });
  const cs = getComputedStyle(document.documentElement);
  const v = c.views[c.active], W = +svg.getAttribute("width"), H = +svg.getAttribute("height"), pad = 32, head = 76, foot = 40;
  const out = el("svg", { xmlns: NS, width: W + pad * 2, height: H + head + foot, viewBox: `0 0 ${W + pad * 2} ${H + head + foot}` });
  el("rect", { width: "100%", height: "100%", fill: cs.getPropertyValue("--panel").trim() }, out);
  const txt = (t, x, y, size, weight, color) => { el("text", { x, y, style: `font: ${weight} ${size}px Inter, Helvetica, Arial, sans-serif; fill: ${color}` }, out).textContent = t; };
  txt(v.title, pad, 40, 22, 500, cs.getPropertyValue("--ink").trim());
  txt(v.sub.length > 130 ? v.sub.slice(0, 129) + "…" : v.sub, pad, 62, 13, 400, cs.getPropertyValue("--ink-2").trim());
  const g = el("g", { transform: `translate(${pad} ${head})` }, out);
  g.appendChild(clone);
  txt("OpenWork Bench · different-ai.github.io/openwork-bench", pad, H + head + 26, 12, 500, cs.getPropertyValue("--ink-3").trim());
  const img = new Image();
  img.src = "data:image/svg+xml;charset=utf-8," + encodeURIComponent(new XMLSerializer().serializeToString(out));
  await img.decode();
  const scale = 2, canvas = document.createElement("canvas");
  canvas.width = (W + pad * 2) * scale; canvas.height = (H + head + foot) * scale;
  const ctx = canvas.getContext("2d"); ctx.scale(scale, scale); ctx.drawImage(img, 0, 0);
  canvas.toBlob((blob) => { const a = document.createElement("a"); a.href = URL.createObjectURL(blob); a.download = `openwork-bench-${v.key}.png`; a.click(); setTimeout(() => URL.revokeObjectURL(a.href), 2000); }, "image/png");
}

const ciText = (s) => (s.ci ? `${fmt(s.ci[0])}–${fmt(s.ci[1])}` : "–");
const valueText = (s) => (s.value_per_dollar ? "$" + Math.round(s.value_per_dollar).toLocaleString("en-US") : "–");
const scored = () => visible().filter((s) => s.index != null);
const byIndex = (a, b) => b.index - a.index;
const targets = () => LEVELS.map((l) => ({ v: l.index, id: l.id, name: BAR_NAME[l.id] || l.label, sub: `Index ${l.index}` }));
/** What the dashed lines mean, under each Work Index chart. */
const lower = (t) => (t ? t[0].toLowerCase() + t.slice(1) : "");
const readinessKey = () => LEVELS.map((l) => `<a class="key" href="${BASE}/readiness/#${esc(l.id)}" data-tip="${esc(tipHtml(l.id))}"><i class="sw-dash"></i> <b>${esc(l.label)}</b> at ${l.index} · ${esc(lower((term(l.id) || {}).short))}</a>`).join("");

card("c-index", [{
  key: "index", tab: "Work Index", title: "OpenWork Bench Work Index", metric: "work-index",
  sub: "Category-weighted mean task score (0–100) · Whiskers show 95% likely ranges · Dashed lines are readiness bars · Higher is better",
  empty: "No models to show.", rows: () => scored().sort(byIndex),
  draw: (host, rows) => columns(host, rows, { value: (s) => s.index, whisker: (s) => s.ci, max: 100, axis: true, height: 420, maxBar: 64, aria: "Work Index with confidence intervals", empty: "No models to show.", targets: targets(), label: (v) => fmt(v, 0), tip: (v, s) => `Work Index ${fmt(v)} · likely range ${ciText(s)}<br>Right every time on ${Math.round(s.pass_hat_k * 100)}% of tasks` }),
  legend: (rows) => familyLegend(rows) + `<span class="key-row">${readinessKey()}</span>`,
  cols: [{ h: "Work Index", id: "work-index", v: (s) => `<b>${fmt(s.index)}</b>` }, { h: "Likely range", id: "likely-range", v: ciText }, { h: "First-try success", id: "first-try", v: (s) => fmt(s.pass_at_1 * 100, 0) + "%" }, { h: "Right every time", id: "every-time", v: (s) => fmt(s.pass_hat_k * 100, 0) + "%" }, { h: "Readiness", id: "readiness", v: (s) => badge(s) || "–" }],
}]);

card("c-efficiency", [
  {
    key: "cost", tab: "Cost per Task", title: "Cost per Task", metric: "cost", sub: "Average cost (USD) per task attempt, billed by the provider where available · Lower is better",
    empty: "No cost data for these models yet.", rows: () => real().filter((s) => s.cost_per_task != null).sort((a, b) => a.cost_per_task - b.cost_per_task),
    draw: (host, rows) => columns(host, rows, { value: (s) => s.cost_per_task, axis: true, tick: (t) => "$" + (t < 0.1 ? t.toFixed(t < 0.01 ? 3 : 2) : t.toFixed(2)), height: 400, aria: "Cost per task", label: (v) => money(v), tip: (v, s) => `${money(v)} per task (${esc(s.cost_source || "list price")})` }),
    cols: [{ h: "Cost per task", id: "cost", v: (s) => money(s.cost_per_task) }, { h: "Source", v: (s) => esc(s.cost_source || "list price") }, { h: "Work value per $1", id: "value", v: (s) => valueText(s) }],
  },
  {
    key: "time", tab: "Time per Task", title: "Time per Task", metric: "time", sub: "Wall-clock time (minutes) per task attempt, first request to final answer · Lower is better",
    empty: "No timing data for these models yet.", rows: () => real().filter((s) => s.time_per_task).sort((a, b) => a.time_per_task - b.time_per_task),
    draw: (host, rows) => columns(host, rows, { value: (s) => s.time_per_task / 60, axis: true, tick: (t) => t.toFixed(t < 1 ? 1 : 0) + "m", height: 400, aria: "Time per task", label: (v) => (v < 1 ? v.toFixed(2) : v.toFixed(1)), tip: (v, s) => `${v.toFixed(2)} min per task${s.speedup_vs_expert ? ` · ${s.speedup_vs_expert}× faster than an expert` : ""}` }),
    cols: [{ h: "Minutes per task", id: "time", v: (s) => mins(s.time_per_task) }, { h: "Faster than an expert", id: "speedup", v: (s) => (s.speedup_vs_expert ? s.speedup_vs_expert + "×" : "–") }],
  },
  {
    key: "output", tab: "Output Tokens", title: "Output Tokens per Task", metric: "tokens", sub: "Average output tokens per task attempt, reasoning included · Lower is better",
    empty: "No token data for these models yet.", rows: () => real().filter((s) => s.usage_per_task).sort((a, b) => a.usage_per_task.output_tokens - b.usage_per_task.output_tokens),
    draw: (host, rows) => columns(host, rows, { value: (s) => s.usage_per_task.output_tokens, axis: true, tick: kfmt, height: 400, aria: "Output tokens per task", label: (v) => kfmt(v), tip: (v) => `${Math.round(v).toLocaleString()} output tokens per task` }),
    cols: [{ h: "Output tokens", id: "tokens", v: (s) => s.usage_per_task.output_tokens.toLocaleString() }, { h: "Steps per task", id: "steps", v: (s) => fmt(s.steps_per_task) }],
  },
  {
    key: "tokens", tab: "Tokens by Type", title: "Tokens per Task by Type", metric: "tokens", sub: "Average tokens per task attempt · Segmented by token type · Lower is better",
    empty: "No token data for these models yet.", rows: () => real().filter((s) => s.usage_per_task).sort((a, b) => a.tokens_per_task - b.tokens_per_task),
    draw: (host, rows) => columns(host, rows, { value: (s) => TOKENS.reduce((n, t) => n + (s.usage_per_task[t.key] || 0), 0), stack: (s) => TOKENS.map((t) => ({ v: s.usage_per_task[t.key] || 0, color: t.color })), axis: true, tick: kfmt, height: 400, aria: "Tokens per task by type", label: (v) => kfmt(v), tip: (v, s) => TOKENS.map((t) => `${t.label}: ${(s.usage_per_task[t.key] || 0).toLocaleString()}`).join("<br>") }),
    legend: () => tokenLegend(),
    cols: TOKENS.map((t) => ({ h: t.label, v: (s) => (s.usage_per_task[t.key] || 0).toLocaleString() })).concat([{ h: "Total", v: (s) => `<b>${s.tokens_per_task.toLocaleString()}</b>` }]),
  },
  {
    key: "steps", tab: "Steps per Task", title: "Steps per Task", metric: "steps", sub: "Average model turns per task attempt, each a tool call or a reply · Lower is better",
    empty: "No step data for these models yet.", rows: () => real().filter((s) => s.steps_per_task).sort((a, b) => a.steps_per_task - b.steps_per_task),
    draw: (host, rows) => columns(host, rows, { value: (s) => s.steps_per_task, axis: true, height: 400, aria: "Steps per task", label: (v) => fmt(v), tip: (v) => `${fmt(v)} steps per task` }),
    cols: [{ h: "Steps per task", id: "steps", v: (s) => fmt(s.steps_per_task) }],
  },
]);

card("c-tradeoffs", [
  {
    key: "vs-cost", tab: "Index vs. Cost", title: "Work Index vs. Cost per Task", metric: "value", sub: "OpenWork Bench Work Index · Average cost (USD) per task attempt",
    empty: "No cost data for these models yet.", rows: () => real().filter((s) => s.index != null && s.cost_per_task > 0),
    draw: (host, rows) => scatter(host, rows, { x: (s) => s.cost_per_task, xTick: (v) => "$" + (v >= 1 ? v : v.toPrecision(1)), xTitle: "Cost per Task (USD, Log Scale)", quadrant: "Most attractive quadrant", aria: "Index vs cost per task", empty: "No cost data for these models yet.", tip: (s) => `Work Index ${fmt(s.index)} · ${money(s.cost_per_task)} per task${s.value_per_dollar ? `<br>${valueText(s)} of expert work per $1` : ""}` }),
    legend: (rows) => familyLegend(rows, tradeLegend()),
    cols: [{ h: "Work Index", id: "work-index", v: (s) => fmt(s.index) }, { h: "Cost per task", id: "cost", v: (s) => money(s.cost_per_task) }, { h: "Work value per $1", id: "value", v: (s) => valueText(s) }],
  },
  {
    key: "vs-time", tab: "Index vs. Time", title: "Work Index vs. Time per Task", metric: "speedup", sub: "OpenWork Bench Work Index · Wall-clock time (minutes) per task attempt",
    empty: "No timing data for these models yet.", rows: () => real().filter((s) => s.index != null && s.time_per_task > 0),
    draw: (host, rows) => scatter(host, rows, { x: (s) => s.time_per_task / 60, xTick: (v) => (v >= 1 ? v : v.toPrecision(1)) + "m", xTitle: "Time per Task (Minutes, Log Scale)", quadrant: "Most attractive quadrant", aria: "Index vs time per task", empty: "No timing data for these models yet.", tip: (s) => `Work Index ${fmt(s.index)} · ${mins(s.time_per_task)} min per task${s.speedup_vs_expert ? `<br>${s.speedup_vs_expert}× faster than an expert` : ""}` }),
    legend: (rows) => familyLegend(rows, tradeLegend()),
    cols: [{ h: "Work Index", id: "work-index", v: (s) => fmt(s.index) }, { h: "Minutes per task", id: "time", v: (s) => mins(s.time_per_task) }, { h: "Faster than an expert", id: "speedup", v: (s) => (s.speedup_vs_expert ? s.speedup_vs_expert + "×" : "–") }],
  },
]);

// ---- Headline charts ----
function headline() {
  const subs = scored();
  columns(document.getElementById("indexChart"), subs.slice().sort(byIndex), {
    value: (s) => s.index, max: 100, aria: "Index scores", empty: "No models to show.", targets: targets(),
    label: (v) => Math.round(v), tip: (v, s) => `Work Index ${fmt(v)}${s.ci ? ` · likely range ${ciText(s)}` : ""}<br>Right every time on ${Math.round(s.pass_hat_k * 100)}% of tasks`,
  });
  const r = subs.filter((s) => s.type !== "reference");
  columns(document.getElementById("timeChart"), r.filter((s) => s.time_per_task).sort((a, b) => a.time_per_task - b.time_per_task), {
    value: (s) => s.time_per_task / 60, aria: "Time per task", empty: "No timing data for these models yet.",
    label: (v) => (v < 1 ? v.toFixed(2) : v.toFixed(1)), tip: (v) => `${v.toFixed(2)} min per task`,
  });
  columns(document.getElementById("costChart"), r.filter((s) => s.cost_per_task != null).sort((a, b) => a.cost_per_task - b.cost_per_task), {
    value: (s) => s.cost_per_task, aria: "Cost per task", empty: "No cost data for these models yet.",
    label: (v) => money(v), tip: (v, s) => `${money(v)} per task (${esc(s.cost_source || "list price")})`,
  });
  document.getElementById("familyLegend").innerHTML = familyLegend(subs);
  const key = document.getElementById("indexKey");
  if (key) key.innerHTML = readinessKey();
}

function updates() {
  const log = DATA.changelog || [];
  document.getElementById("updates").innerHTML = log.slice(0, 2).map((c) => `<a class="update" href="${BASE}/changelog/#${changeSlug(c)}"><span class="k">${esc(c.kind)}</span><span class="t">${esc(c.title)}</span><span class="d">${esc(c.text)}</span><span class="arrow" aria-hidden="true">↗</span></a>`).join("");
  document.getElementById("changelog").innerHTML = log.map((c) => `<li><a href="${BASE}/changelog/#${changeSlug(c)}"><span class="m">${esc(changeLabel(c.kind))} · ${esc(shortDate(c.date))}</span><span class="t">${esc(c.title)}</span></a></li>`).join("") || '<li><span class="m">No changes yet.</span></li>';
}

function tiers() {
  const subs = visible().filter((s) => s.readiness);
  document.getElementById("tiers").innerHTML = (TARGETS.levels || []).map((l) => {
    const names = subs.filter((s) => s.readiness.id === l.id).map(short);
    return `<a class="tier-row" href="${BASE}/readiness/#${esc(l.id)}" data-tip="${esc(tipHtml(l.id))}"><b>${esc(l.label)}</b><span>${names.length ? esc(names.join(", ")) : "None"}</span></a>`;
  }).join("");
}

const seq = (v) => (v == null ? "var(--s0)" : `var(--s${Math.max(0, Math.min(7, Math.round((v / 100) * 7)))})`);
const ink = (v) => (v != null && v >= 64 ? "var(--s-ink-hi)" : "var(--ink)");

function catTable() {
  const cats = DATA.index.categories, ct = TARGETS.category;
  let h = `<thead><tr><th class=l>Model</th>${th("Readiness", "readiness", "l")}${th("Work Index", "work-index")}${Object.entries(cats).map(([id, c]) => `<th><a class="th-link" href="${catHref(id)}" data-tip="<b>${esc(c.label)}</b><br><i>${esc(CATEGORIES[id]?.question || "")}</i><br>${esc(CATEGORIES[id]?.work || "")}<br><span class=more>Click for its tasks and scores</span>">${esc(c.label)}</a></th>`).join("")}</tr></thead><tbody>`;
  for (const s of visible()) {
    h += `<tr><td class=l><span class="dot" style="background:${solid(s)}"></span><a href="${modelHref(s)}">${esc(name(s))}</a>${loop(s) ? '<span class="tag">plain loop</span>' : ""}${s.simulated ? '<span class="tag">sim</span>' : ""}</td><td class=l>${badge(s)}</td><td><b>${fmt(s.index)}</b></td>`;
    for (const c of Object.keys(cats)) {
      const v = s.categories[c], hit = ct != null && v != null && v >= ct;
      h += `<td class="heat" style="background:${seq(v)};color:${ink(v)}" data-tip="<b>${esc(s.label)}</b><br>${esc(cats[c].label)}: ${fmt(v)}${ct != null ? (hit ? " · meets" : " · below") + " the " + ct + " target" : ""}">${fmt(v, 0)}${hit ? " ✓" : ""}</td>`;
    }
    h += "</tr>";
  }
  document.getElementById("catTable").innerHTML = h + "</tbody>";
}

function relChart() {
  const bar = (v, c, l) => `<div class="mini" data-tip="${l}: ${fmt(v * 100, 0)}%"><span style="width:${Math.max(0, v * 100)}%;background:${c}"></span><b>${fmt(v * 100, 0)}%</b></div>`;
  let h = `<div class="bars"><div class="h">Model</div><div class="h">First-try success${info("first-try")}</div><div class="h">Right every time${info("every-time")}</div><div class="h">Unsafe actions${info("unsafe")}</div>`;
  for (const s of visible()) {
    h += `<div><span class="dot" style="background:${solid(s)}"></span><a href="${modelHref(s)}">${esc(short(s))}</a></div>${bar(s.pass_at_1, solid(s), "First-try success")}${bar(s.pass_hat_k, solid(s), "Right every time")}${bar(s.safety_rate, "var(--critical)", "Unsafe actions")}`;
  }
  document.getElementById("relChart").innerHTML = h + "</div>";
}

function mainTable() {
  let h = `<thead><tr><th>#</th><th class=l>Model</th>${th("Readiness", "readiness", "l")}${th("Harness", "harness", "l")}${th("Work Index", "work-index")}${th("Likely range", "likely-range")}${th("First-try success", "first-try")}${th("Right every time", "every-time")}${th("Unsafe actions", "unsafe")}${th("Cost per task", "cost")}${th("Min per task", "time")}${th("Tokens per task", "tokens")}${th("Work value per $1", "value")}${th("Faster than an expert", "speedup")}${th("Tasks run", "coverage")}${th("Weights", "weights", "l")}</tr></thead><tbody>`;
  visible().forEach((s, i) => {
    const ow = s.open_weights || {};
    const weights = ow.hf_repo ? `<a href="https://huggingface.co/${esc(ow.hf_repo)}/tree/${esc(ow.revision || "main")}">${esc(ow.license || "open")}</a>` : s.anchor ? "closed" : "–";
    h += `<tr><td>${i + 1}</td><td class=l><span class="dot" style="background:${solid(s)}"></span><a href="${modelHref(s)}">${esc(name(s))}</a></td><td class=l>${badge(s)}</td><td class=l>${esc(harnessName(s))}</td><td><b>${fmt(s.index)}</b></td><td>${ciText(s)}</td><td>${fmt(s.pass_at_1 * 100, 0)}%</td><td>${fmt(s.pass_hat_k * 100, 0)}%</td><td>${fmt(s.safety_rate * 100, 0)}%</td><td>${money(s.cost_per_task)}</td><td>${s.type === "reference" ? "–" : mins(s.time_per_task)}</td><td>${s.tokens_per_task ? s.tokens_per_task.toLocaleString() : "–"}</td><td>${valueText(s)}</td><td>${s.type === "reference" || !s.speedup_vs_expert ? "–" : s.speedup_vs_expert + "×"}</td><td>${fmt(s.coverage * 100, 0)}%</td><td class=l>${weights}</td></tr>`;
  });
  document.getElementById("mainTable").innerHTML = h + "</tbody>";
}

function matrix() {
  const subs = visible(), cats = DATA.index.categories;
  let h = `<thead><tr><th class=l>Task</th><th class=l>Category</th>${th("Expert", "expert")}${subs.map((s) => `<th class="rot"><a href="${modelHref(s)}">${esc(short(s))}</a></th>`).join("")}</tr></thead><tbody>`;
  for (const t of DATA.tasks) {
    h += `<tr><td class=l data-tip="${esc(t.occupation)} · ${esc(t.difficulty)} · ${esc(t.horizon)}"><a href="${taskHref(t)}">${esc(t.title)}</a></td><td class=l><a href="${catHref(t.category)}">${esc(cats[t.category]?.label || t.category)}</a></td><td>${Math.round(t.expert_minutes)}m</td>`;
    for (const s of subs) {
      const r = s.tasks[t.id], v = r ? r.score * 100 : null;
      h += `<td class="heat" style="background:${seq(v)};color:${ink(v)}" data-tip="<b>${esc(s.label)}</b><br>${esc(t.title)}<br>score ${fmt(v, 0)} · solved ${r ? fmt(r.success_rate * 100, 0) + "%" : "–"} of ${r ? r.n : 0}">${fmt(v, 0)}</td>`;
    }
    h += "</tr>";
  }
  document.getElementById("matrix").innerHTML = h + "</tbody>";
}

function meta() {
  const ix = DATA.index, src = DATA.sources || {};
  const rows = [
    ["Index", `${esc(ix.name)} ${esc(ix.version)} (${esc(ix.status)})`],
    ["Tasks", `${DATA.tasks.length} tasks · ${esc((ix.splits || []).join(", "))}`],
    ["Repeats", esc(ix.repeats)],
    ["Scoring", `critical miss caps a task at ${fmt((ix.scoring.critical_cap ?? 0.25) * 100, 0)}% · unsafe attempt scores 0`],
    ["Results", esc(src.results_repo ? `${src.results_repo}@${src.results_revision || "main"}` : (src.paths || []).join(", ") || "local runs")],
    ["Errata", esc((DATA.errata_applied || []).join(", ") || "none")],
    ["Generated", `${esc(DATA.generated_at)} · owb ${esc(DATA.owb_version)}`],
  ];
  document.getElementById("meta").innerHTML = rows.map(([k, v]) => `<dt>${k}</dt><dd>${v}</dd>`).join("");
}

function notice() {
  const n = document.getElementById("notice");
  if (!hasReal) { n.hidden = false; n.innerHTML = "<b>Sample data.</b> No model results are published yet. These rows come from scripted and simulated test agents that exercise the pipeline offline."; }
  else if (DATA.note) { n.hidden = false; n.textContent = DATA.note; }
  else if (DATA.subjects.some((s) => s.simulated) && state.showTest) { n.hidden = false; n.innerHTML = "<b>Includes test agents.</b> Simulated rows come from a seeded test agent, not a real model."; }
  else n.hidden = true;
}

function syncButtons() {
  document.querySelectorAll("[data-board]").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.board === state.board)));
  document.querySelectorAll("[data-harness]").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.harness === state.harness)));
  document.getElementById("showTest").checked = state.showTest;
}
if (!hasClosed) { const seg = document.getElementById("boardToggle"); if (seg) seg.hidden = true; }
function render() { syncButtons(); notice(); headline(); CARDS.forEach(draw); tiers(); catTable(); relChart(); mainTable(); matrix(); }

// Open a chart card's tab from a shared link: #c-efficiency/time.
function fromHash() {
  const [id, key] = decodeURIComponent(location.hash.slice(1)).split("/");
  const c = CARDS.find((x) => x.id === id);
  if (!c) return;
  const i = c.views.findIndex((v) => v.key === key);
  if (i >= 0) c.active = i;
}

// Section navigation: mark the section in view.
function sidenav() {
  const links = [...document.querySelectorAll(".sidenav a")];
  const map = new Map(links.map((a) => [a.getAttribute("href").slice(1), a]));
  if (!("IntersectionObserver" in window)) return;
  const seen = new Map();
  const io = new IntersectionObserver((entries) => {
    entries.forEach((e) => seen.set(e.target.id, e.isIntersecting ? e.intersectionRatio : 0));
    let best = null, ratio = 0;
    for (const [id, r] of seen) if (r > ratio) { ratio = r; best = id; }
    links.forEach((a) => a.removeAttribute("aria-current"));
    if (best && map.get(best)) map.get(best).setAttribute("aria-current", "true");
  }, { rootMargin: "-20% 0px -55% 0px", threshold: [0, 0.01, 0.25, 0.5] });
  map.forEach((_, id) => { const s = document.getElementById(id); if (s) io.observe(s); });
}

document.querySelectorAll("[data-board]").forEach((b) => b.addEventListener("click", () => { state.board = b.dataset.board; render(); }));
document.querySelectorAll("[data-harness]").forEach((b) => b.addEventListener("click", () => { state.harness = b.dataset.harness; render(); }));
document.getElementById("showTest").addEventListener("change", (e) => { state.showTest = e.target.checked; render(); });
let rt, lastW = window.innerWidth;
window.addEventListener("resize", () => { if (window.innerWidth === lastW) return; lastW = window.innerWidth; clearTimeout(rt); rt = setTimeout(render, 120); });
window.addEventListener("hashchange", () => { fromHash(); CARDS.forEach(draw); });
fromHash(); updates(); meta(); render(); sidenav();
