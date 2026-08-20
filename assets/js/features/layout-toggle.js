/* === Layout Toggle (Cyberdeck ↔ Refined) === */
/* Reads preference from localStorage on load, applies html class,
   wires the settings panel toggle button. Ecosystem-wide — the
   same key drives both Hypervisor and Hyperagent. */

(function initLayoutToggle() {
  "use strict";

  var KEY = "hypervisor-layout";
  var btn = document.getElementById("layout-toggle");
  var stateEl = document.getElementById("layout-toggle-state");

  // --- Apply on load (before paint) ---
  var saved = null;
  try { saved = localStorage.getItem(KEY); } catch (e) {}
  if (saved === "refined") {
    document.documentElement.classList.add("layout-refined");
  }

  function setLayout(mode) {
    var isRefined = mode === "refined";
    document.documentElement.classList.toggle("layout-refined", isRefined);
    if (stateEl) stateEl.textContent = isRefined ? "Refined" : "Cyberdeck";
    if (btn) btn.classList.toggle("active", isRefined);
    var iconEl = document.getElementById("layout-toggle-icon");
    if (iconEl) {
      iconEl.setAttribute("data-lucide", isRefined ? "sparkles" : "terminal");
      if (window.lucide) lucide.createIcons({ attrs: { "stroke-width": 1.5 } });
    }
    window.savePreference(KEY, mode);
  }

  // Init UI state
  if (saved === "refined") {
    if (stateEl) stateEl.textContent = "Refined";
    if (btn) btn.classList.add("active");
    var iconEl = document.getElementById("layout-toggle-icon");
    if (iconEl) iconEl.setAttribute("data-lucide", "sparkles");
  }

  // Wire click
  if (btn) {
    btn.addEventListener("click", function () {
      var isRefined = document.documentElement.classList.contains("layout-refined");
      setLayout(isRefined ? "cyberdeck" : "refined");
    });
  }

  // Expose for command palette / keyboard shortcut
  window.__toggleLayout = function () {
    if (btn) btn.click();
  };
})();
