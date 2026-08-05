/* === Hypervisor: Related Docs (RAG-powered inline section) === */

(function () {
  "use strict";

  // Only active in the desktop app (needs the pywebview bridge for semantic search)
  if (!window.isDesktopApp && !window.__pywebviewReady) {
    window.addEventListener("pywebviewready", initRelated);
    return;
  }
  initRelated();

  function initRelated() {
    var _abortController = null;
    var _sectionEl = null;

    function teardown() {
      if (_abortController) { _abortController.abort(); _abortController = null; }
      if (_sectionEl && _sectionEl.parentNode) {
        _sectionEl.parentNode.removeChild(_sectionEl);
      }
      _sectionEl = null;
    }

    function init(fragment) {
      if (!fragment || !fragment.sourcePath) { teardown(); return; }

      var path = fragment.sourcePath;
      if (!path.endsWith(".md")) { teardown(); return; }

      var article = document.getElementById("content-target");
      if (!article) { teardown(); return; }

      if (!window.pywebview || !window.pywebview.api || !window.pywebview.api.semantic_search) {
        teardown();
        return;
      }

      var title = fragment.title || "";
      if (!title || title.length < 5) { teardown(); return; }

      _abortController = { aborted: false, abort: function () { this.aborted = true; } };
      var controller = _abortController;

      window.pywebview.api.semantic_search(title, 5, null, null, null, null).then(function (results) {
        if (controller.aborted) return;
        if (!results || !results.length) { teardown(); return; }

        // Filter out the current page
        var currentPath = path.replace(/\\/g, "/");
        var filtered = results.filter(function (r) {
          return r.path.replace(/\\/g, "/") !== currentPath;
        });
        if (!filtered.length) { teardown(); return; }

        filtered = filtered.slice(0, 5);

        // Build list items matching backlinks-section style
        var items = filtered.map(function (r) {
          var href = "/" + r.path.replace(/\.md$/, "") + "/index.html";
          var displayPath = r.path;
          var section = r.section ? " — §" + r.section : "";
          return (
            '<li><a href="' + href + '">' +
              '<i data-lucide="sparkles" class="backlink-icon"></i> ' +
              (r.title || r.path) + section +
            '</a>' +
            '<span class="backlink-path">' + displayPath + '</span></li>'
          );
        });

        // Create section element
        var section = document.createElement("section");
        section.className = "backlinks-section related-docs-section";
        section.innerHTML =
          '<h2><i data-lucide="brain" class="section-icon"></i> Related by Content</h2>' +
          '<ul class="backlinks-list">' + items.join("\n") + '</ul>';

        // Remove old one if somehow still present
        if (_sectionEl && _sectionEl.parentNode) {
          _sectionEl.parentNode.removeChild(_sectionEl);
        }

        // Append at end of content-target (after backlinks)
        article.appendChild(section);
        _sectionEl = section;

        // Initialize Lucide icons in the new section
        if (window.lucide) try { lucide.createIcons({ nodes: [section] }); } catch (e) {}
      }).catch(function () { teardown(); });
    }

    if (window.__router) {
      window.__router.onNavigate(teardown, init);
      // Fire immediately for the current page (fixes initial-load race)
      var current = window.__router.getCurrentFragment();
      if (current) init(current);
    }
  }
})();
