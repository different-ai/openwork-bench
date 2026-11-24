// Tooltips for anything with data-tip, on every page: they follow the mouse, sit under an element
// that has keyboard focus, and close on Escape.
const tip = document.getElementById("tip");
let current = null;
function place(x, y) {
  tip.style.left = Math.max(8, Math.min(window.innerWidth - tip.offsetWidth - 12, x)) + "px";
  tip.style.top = Math.max(8, Math.min(window.innerHeight - tip.offsetHeight - 12, y)) + "px";
}
function show(t, x, y) {
  if (current !== t) { tip.innerHTML = t.getAttribute("data-tip"); current = t; }
  tip.style.opacity = 1;
  place(x, y);
}
function hide() { tip.style.opacity = 0; current = null; }
if (tip) {
  document.addEventListener("mousemove", (e) => {
    const t = e.target.closest ? e.target.closest("[data-tip]") : null;
    if (t) show(t, e.clientX + 14, e.clientY + 14); else if (current && document.activeElement !== current) hide();
  });
  document.addEventListener("focusin", (e) => {
    const t = e.target.closest ? e.target.closest("[data-tip]") : null;
    if (!t) return hide();
    const r = t.getBoundingClientRect();
    show(t, r.left, r.bottom + 8);
  });
  document.addEventListener("focusout", hide);
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") hide(); });
  window.addEventListener("scroll", () => { if (current && document.activeElement !== current) hide(); }, { passive: true });
}
