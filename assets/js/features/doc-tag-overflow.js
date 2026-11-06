// ─── Doc Title-Row Tag Overflow ──────────────────────────────────────────────
// The topic tags sit in the top-right of the document title row. Space is
// title-first: the title keeps whatever width it needs, and the tags collapse
// to fit the remainder.
//
// Degradation ladder (widest -> narrowest):
//   [a][b][c][d]            all tags fit
//   [a][b] +2               some hidden -> trailing +N chip (title lists them)
//   4 TAGS                  nothing fits -> single count blurb (title lists all)
//
// Pure presentational JS - no bridge needed. SPA-aware via the router hook,
// and recomputes on viewport resize.
(function () {
  // How much horizontal room the tag cluster is allowed to claim before the
  // title. Title-priority: tags never push the title below this fraction of
  // the row. The title gets the rest.
  var TITLE_MIN_FRACTION = 0.5;

  function layoutOne(container) {
    var row = container.closest(".doc-title-row");
    if (!row) return;

    var raw = container.getAttribute("data-doc-tags") || "";
    var allTags = raw.split(",").map(function (s) { return s.trim(); }).filter(Boolean);
    if (!allTags.length) return;

    // Reset to the full chip set each pass so resize can re-expand, not just
    // shrink. Rebuild from data-doc-tags so prior collapses don't compound.
    container.classList.remove("doc-title-tags-blurb");
    container.innerHTML = allTags.map(function (t) {
      return '<span class="doc-title-tag">' + escapeHtml(t) + "</span>";
    }).join("");

    var chips = Array.prototype.slice.call(container.querySelectorAll(".doc-title-tag"));

    // Budget: the row width the tags may use = full row minus the title's
    // reserved minimum. Measured off the row's content box.
    var rowWidth = row.clientWidth;
    var titleEl = row.querySelector("h1");
    var titleWidth = titleEl ? titleEl.scrollWidth : 0;
    var gap = parseFloat(getComputedStyle(row).columnGap) || 0;
    var reservedForTitle = Math.max(titleWidth, rowWidth * TITLE_MIN_FRACTION);
    var budget = rowWidth - reservedForTitle - gap;

    if (budget <= 0) {
      renderBlurb(container, allTags);
      return;
    }

    // Does the full set fit? If so, done.
    if (container.scrollWidth <= budget) return;

    // Hide trailing chips until the visible set + a +N chip fits the budget.
    // Insert a reusable +N chip we grow as we hide more.
    var more = document.createElement("span");
    more.className = "doc-title-tag doc-title-tag-more";
    container.appendChild(more);

    var hidden = 0;
    for (var i = chips.length - 1; i >= 0; i--) {
      hidden++;
      chips[i].style.display = "none";
      more.textContent = "+" + hidden;
      more.setAttribute("title", allTags.slice(i).join(", "));
      if (container.scrollWidth <= budget) {
        // Does at least one real chip remain visible? If not, prefer the blurb.
        if (i === 0) break;
        return;
      }
    }

    // Nothing (or only the +N) fit -> collapse to the count blurb.
    renderBlurb(container, allTags);
  }

  function renderBlurb(container, allTags) {
    var n = allTags.length;
    container.classList.add("doc-title-tags-blurb");
    container.innerHTML =
      '<span class="doc-title-tags-count" title="' +
      escapeHtml(allTags.join(", ")) +
      '">' + (n < 10 ? "0" + n : n) + " TAG" + (n === 1 ? "" : "S") + "</span>";
  }

  function escapeHtml(s) {
    return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  }

  function layoutAll() {
    var containers = document.querySelectorAll(".doc-title-tags[data-doc-tags]");
    containers.forEach(layoutOne);
  }

  // Debounce resize so we are not relayout-thrashing on drag.
  var resizeTimer = null;
  function onResize() {
    if (resizeTimer) clearTimeout(resizeTimer);
    resizeTimer = setTimeout(layoutAll, 90);
  }

  function init() {
    layoutAll();
  }

  // Boot after DOM ready (fonts may still be settling; a second pass on load
  // catches width shifts once the mono font swaps in).
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
  window.addEventListener("load", layoutAll);
  window.addEventListener("resize", onResize);

  // Re-run on SPA navigation (new doc = new title row).
  if (window.__router) {
    window.__router.onNavigate(null, layoutAll);
  }
})();
