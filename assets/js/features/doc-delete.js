// ─── Doc Delete ──────────────────────────────────────────────────────────────
// Adds delete buttons to doc-list items on all directory index pages.
// Requires the PyWebView desktop app bridge for filesystem access.
// SPA-aware: re-initializes on navigation.
(function () {

  function init() {
    if (!window.pywebview || !window.pywebview.api) return;

    var items = document.querySelectorAll(".doc-list li");
    items.forEach(function (li) {
      // Skip items that already have a delete/dismiss button
      if (li.querySelector(".doc-delete-btn") || li.querySelector(".idea-dismiss-btn") || li.querySelector(".external-delete-btn")) return;
      // Skip items with .doc-path — those use a specialized delete handler (e.g. drop-import.js)
      if (li.querySelector(".doc-path")) return;
      // Skip group headers and non-doc items
      if (li.classList.contains("group-header")) return;

      var link = li.querySelector("a");
      if (!link) return;

      var href = link.getAttribute("href") || "";
      // Strip /index.html suffix and trailing slash to get the doc slug
      var slug = href.replace(/^\//, "").replace(/\/index\.html$/, "").replace(/\/$/, "");
      if (!slug) return;

      // Resolve relative hrefs against the current page's source path
      var dirPrefix = "";
      if (slug.indexOf("/") === -1 && window.__router) {
        var frag = window.__router.getCurrentFragment();
        if (frag && frag.sourcePath) dirPrefix = frag.sourcePath + "/";
      }
      var filePath = dirPrefix + slug + ".md";

      var name = slug.split("/").pop().replace(/-/g, " ");

      var btn = document.createElement("button");
      btn.className = "doc-delete-btn";
      btn.setAttribute("aria-label", "Delete " + name);
      btn.setAttribute("data-tooltip", "Delete");
      btn.innerHTML = '<i data-lucide="trash-2"></i>';
      li.appendChild(btn);

      btn.addEventListener("click", function (e) {
        e.preventDefault();
        e.stopPropagation();

        var confirmFn = window.__hypervisorConfirm || function (msg) {
          return Promise.resolve(window.confirm(msg));
        };

        confirmFn('Delete "' + name + '"?', {
          danger: true, confirmLabel: "delete", cancelLabel: "cancel"
        }).then(function (ok) {
          if (!ok) return;
          window.pywebview.api.delete_document(filePath).then(function (result) {
            if (result && result.ok) {
              if (window.__hypervisorToast) {
                window.__hypervisorToast({ variant: "success", message: "deleted: " + name });
              }
            } else {
              if (window.__hypervisorToast) {
                window.__hypervisorToast({ variant: "error", message: "delete failed: " + (result.error || "unknown") });
              }
            }
          });
        });
      });
    });

    if (window.lucide) lucide.createIcons({ attrs: { "stroke-width": 2 } });
  }

  // Run on initial load
  if (window.pywebview && window.pywebview.api) {
    init();
  } else {
    window.addEventListener("pywebviewready", init);
  }

  // Re-run on SPA navigation
  if (window.__router) {
    window.__router.onNavigate(null, init);
  }
})();
