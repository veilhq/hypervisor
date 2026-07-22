// ─── Ideas Dismiss ───────────────────────────────────────────────────────────
// Adds "dismiss" (delete) buttons to idea list items on the ideas/ directory page.
// Requires the PyWebView desktop app bridge for filesystem access.
(function () {
  function isIdeasPage() {
    var sp = document.getElementById("source-path");
    return sp && sp.textContent.trim() === "ideas";
  }

  function initDismissButtons() {
    if (!isIdeasPage()) return;
    if (!window.pywebview || !window.pywebview.api) return;

    var items = document.querySelectorAll(".doc-list li");
    items.forEach(function (li) {
      if (li.querySelector(".idea-dismiss-btn")) return;

      var link = li.querySelector("a");
      if (!link) return;

      var href = link.getAttribute("href") || "";
      var slug = href.replace("/index.html", "").replace(/\/$/, "");
      if (!slug) return;

      var filename = slug + ".md";
      if (filename === "_conventions.md") return;

      var btn = document.createElement("button");
      btn.className = "idea-dismiss-btn";
      btn.setAttribute("aria-label", "Remove " + slug);
      btn.title = "Implemented \u2014 remove";
      btn.innerHTML = '<i data-lucide="check-circle-2"></i>';
      li.appendChild(btn);

      btn.addEventListener("click", function (e) {
        e.preventDefault();
        e.stopPropagation();

        var confirmFn = window.__hypervisorConfirm || function (msg) {
          return Promise.resolve(window.confirm(msg));
        };

        confirmFn('Remove "' + slug.replace(/-/g, " ") + '" from ideas?', {
          danger: true,
          confirmLabel: "remove",
          cancelLabel: "keep"
        }).then(function (ok) {
          if (!ok) return;

          window.pywebview.api
            .delete_idea(filename)
            .then(function (result) {
              if (result && result.ok) {
                if (window.__hypervisorToast) {
                  window.__hypervisorToast({
                    variant: "success",
                    message: "removed: " + slug.replace(/-/g, " ")
                  });
                }
              } else {
                if (window.__hypervisorToast) {
                  window.__hypervisorToast({
                    variant: "error",
                    message: "remove failed: " + (result.error || "unknown")
                  });
                }
              }
            });
        });
      });
    });

    if (window.lucide) lucide.createIcons({ attrs: { "stroke-width": 1.5 } });
  }

  // Run on initial load
  if (window.pywebview && window.pywebview.api) {
    initDismissButtons();
  } else {
    window.addEventListener("pywebviewready", initDismissButtons);
  }

  // Re-run on SPA navigation
  if (window.__router) {
    window.__router.onNavigate(null, initDismissButtons);
  }
})();
