/* === Hypervisor: Command Palette (Ctrl+K) === */

  // Unified command palette - fuzzy search across documents, actions, utilities,
  // and navigation indexes. Pure keyboard-driven with Lucide icons.

  (function initCommandPalette() {

    // --- Action Registry ---
    var ACTIONS = [
      { name: "Rebuild Site",           icon: "hammer",        fn: function () { if (window.pywebview && window.pywebview.api && window.pywebview.api.rebuild) { try { sessionStorage.removeItem("__hv_splash_seen"); } catch (e) {} window.pywebview.api.rebuild(); } } },
      { name: "Toggle Fullscreen",      icon: "maximize",      fn: function () { if (window.pywebview && window.pywebview.api && window.pywebview.api.toggle_fullscreen) window.pywebview.api.toggle_fullscreen(); } },
      { name: "Toggle Screensaver",     icon: "monitor",       fn: function () { if (window.__screensaver) window.__screensaver.toggle(); } },
      { name: "Cycle Palette Mode",     icon: "palette",       fn: function () { var b = document.getElementById("palette-mode"); if (b) b.click(); } },
      { name: "Toggle Condensed Width", icon: "columns",       fn: function () { var b = document.getElementById("width-toggle"); if (b) b.click(); } },
      { name: "Toggle Light Mode",       icon: "contrast",      fn: function () { var b = document.getElementById("a11y-bw-theme"); if (b) b.click(); } },
      { name: "Toggle Reduce Motion",   icon: "pause",         fn: function () { var b = document.getElementById("a11y-reduce-motion"); if (b) b.click(); } },
      { name: "Toggle Glitch Effect",   icon: "sparkles",      fn: function () { var b = document.getElementById("a11y-no-glitch"); if (b) b.click(); } },
      { name: "Toggle System Cursors",  icon: "mouse-pointer", fn: function () { var b = document.getElementById("a11y-system-cursors"); if (b) b.click(); } },
      { name: "Start Edit Mode",        icon: "pencil",        fn: function () { if (window.__hvActions) window.__hvActions.run("edit"); } },
      { name: "Open in File Explorer",  icon: "folder-open",   fn: function () { if (window.__hvActions) window.__hvActions.run("openInExplorer"); } },
      { name: "Export Page",            icon: "package",       fn: function () { if (window.__hvActions) window.__hvActions.run("export"); } },
      { name: "Pin / Unpin Page",       icon: "pin",           fn: function () { if (window.__hvActions) window.__hvActions.run("togglePin"); } },
      { name: "Go to Pinboard",         icon: "bookmark",      fn: function () { if (window.__router) window.__router.navigate("/_pins/index.html"); } },
      { name: "End Sprint",             icon: "skip-forward",  fn: function () { if (window.__hvActions) window.__hvActions.run("endSprint"); } },
      { name: "Set Share Key",          icon: "key-round",     fn: function () { if (window.__hvActions) window.__hvActions.run("shareKey"); } },
      { name: "Open in New Window",     icon: "app-window",    fn: function () { if (window.__hvActions) window.__hvActions.run("openInNewWindow"); } },
      { name: "Go to About",            icon: "info",          fn: function () { if (window.__router) window.__router.navigate("/_about/index.html"); } },
      { name: "Scroll to Top",          icon: "arrow-up",      fn: function () { window.scrollTo({ top: 0, behavior: "smooth" }); } },
      { name: "Launch Dev Environment", icon: "terminal",      fn: function () { if (window.pywebview && window.pywebview.api && window.pywebview.api.launch_dev) window.pywebview.api.launch_dev(); } },
      { name: "Launch HyperField",  icon: "grid-3x3",     fn: function () { if (window.pywebview && window.pywebview.api && window.pywebview.api.launch_dither_widget) window.pywebview.api.launch_dither_widget(); } }
    ];

    // --- Utility Registry ---
    // Sourced from the shared HvSearchSources loader (core/02-search-sources.js),
    // which owns the single fetch of _utils/_manifest.json. Read at search time
    // so entries are picked up once the manifest resolves - no second fetch here.
    function getUtilities() {
      return (window.HvSearchSources && window.HvSearchSources.utilities())
        || [];
    }

    // --- Navigation Indexes (top-level category pages) ---
    var NAV_INDEXES = [
      { name: "Home",       icon: "compass", href: "/index.html" },
      { name: "Work Items", icon: "compass", href: "/work/index.html" },
      { name: "To-Do",     icon: "compass", href: "/work/to-do/index.html" },
      { name: "Done",       icon: "compass", href: "/work/done/index.html" },
      { name: "Ideas",      icon: "compass", href: "/ideas/index.html" },
      { name: "Research",   icon: "compass", href: "/research/index.html" },
      { name: "Context",    icon: "compass", href: "/context/index.html" },
      { name: "Patterns",   icon: "compass", href: "/patterns/index.html" },
      { name: "Reference",  icon: "compass", href: "/reference/index.html" },
      { name: "Analysis",   icon: "compass", href: "/analysis/index.html" }
    ];

    // --- Build overlay DOM ---
    var overlay = document.createElement("div");
    overlay.className = "cmd-palette-overlay";
    overlay.setAttribute("role", "dialog");
    overlay.setAttribute("aria-label", "Command palette");
    overlay.innerHTML =
      '<div class="cmd-palette">' +
        '<div class="cmd-palette-input-wrap">' +
          '<i data-lucide="search" class="cmd-palette-icon"></i>' +
          '<input type="text" class="cmd-palette-input" placeholder="Search documents, actions..." autocomplete="off" spellcheck="false">' +
        '</div>' +
        '<div class="cmd-palette-results"></div>' +
        '<div class="cmd-palette-footer">' +
          '<span><kbd>↑↓</kbd> navigate</span>' +
          '<span><kbd>↵</kbd> select</span>' +
          '<span><kbd>esc</kbd> close</span>' +
        '</div>' +
      '</div>';
    document.body.appendChild(overlay);

    var inputEl = overlay.querySelector(".cmd-palette-input");
    var resultsEl = overlay.querySelector(".cmd-palette-results");
    var selectedIdx = -1;
    var currentItems = [];

    // --- Fuzzy match ---
    function fuzzyMatch(query, text) {
      var q = query.toLowerCase();
      var t = text.toLowerCase();
      var idx = t.indexOf(q);
      if (idx === -1) return -1;
      return idx === 0 ? 100 : Math.max(1, 50 - idx);
    }

    // --- Search all categories ---
    function doSearch(query) {
      if (!query) return [];
      var results = [];

      // 1. Documents (from search index)
      if (index && index.length) {
        index.forEach(function (entry) {
          var titleScore = fuzzyMatch(query, entry.title);
          var pathScore = fuzzyMatch(query, entry.path);
          var workIdScore = entry.work_id ? fuzzyMatch(query, entry.work_id) : -1;
          var bestScore = Math.max(titleScore, pathScore, workIdScore);
          if (bestScore > 0) {
            results.push({
              category: "doc",
              name: entry.title,
              icon: "file-text",
              hint: "doc",
              score: bestScore,
              action: function () { if (window.__router) window.__router.navigate(entry.href); }
            });
          }
        });
      }

      // 2. Actions
      ACTIONS.forEach(function (a) {
        var score = fuzzyMatch(query, a.name);
        if (score > 0) {
          results.push({
            category: "action",
            name: a.name,
            icon: a.icon,
            hint: "action",
            score: score,
            action: a.fn
          });
        }
      });

      // 3. Utilities
      getUtilities().forEach(function (u) {
        var score = fuzzyMatch(query, u.name);
        if (score > 0) {
          results.push({
            category: "utility",
            name: u.name,
            icon: (window.HvSearchSources ? window.HvSearchSources.iconForKind("utility") : "wrench"),
            hint: "utility",
            score: score,
            action: function () { if (window.__router) window.__router.navigate(u.href); }
          });
        }
      });

      // 3b. Directories (shared source - every indexed hyperspace dir)
      (window.HvSearchSources ? window.HvSearchSources.directories() : []).forEach(function (d) {
        var score = Math.max(fuzzyMatch(query, d.name), fuzzyMatch(query, d.path));
        if (score > 0) {
          results.push({
            category: "directory",
            name: d.path,
            icon: (window.HvSearchSources ? window.HvSearchSources.iconForKind("directory") : "folder"),
            hint: "directory",
            score: score,
            action: function () { if (window.__router) window.__router.navigate(d.href); }
          });
        }
      });

      // 4. Navigation indexes
      NAV_INDEXES.forEach(function (n) {
        var score = fuzzyMatch(query, n.name);
        if (score > 0) {
          results.push({
            category: "nav",
            name: n.name,
            icon: n.icon,
            hint: "nav",
            score: score,
            action: function () { if (window.__router) window.__router.navigate(n.href); }
          });
        }
      });

      // Order by category band first (directories + utilities surface ahead of
      // documents and the rest), then by score within a band. Cap at 20.
      var CATEGORY_RANK = { directory: 0, utility: 0, nav: 1, doc: 2, action: 2 };
      results.sort(function (a, b) {
        var ra = CATEGORY_RANK[a.category] != null ? CATEGORY_RANK[a.category] : 3;
        var rb = CATEGORY_RANK[b.category] != null ? CATEGORY_RANK[b.category] : 3;
        if (ra !== rb) return ra - rb;
        return b.score - a.score;
      });
      return results.slice(0, 20);
    }

    // --- Render results ---
    function render(items) {
      currentItems = items;
      selectedIdx = -1;

      if (!items.length) {
        resultsEl.innerHTML = "";
        resultsEl.classList.add("has-query");
        return;
      }

      resultsEl.classList.remove("has-query");
      resultsEl.innerHTML = items.map(function (item, i) {
        return '<div class="cmd-palette-item" data-index="' + i + '" data-category="' + item.category + '">' +
          '<i data-lucide="' + item.icon + '" class="cmd-palette-item-icon"></i>' +
          '<span class="cmd-palette-item-text">' + HvUtils.escapeHtml(item.name) + '</span>' +
          '<span class="cmd-palette-item-hint">' + item.hint + '</span>' +
          '</div>';
      }).join("");

      // Activate Lucide icons in results
      if (window.lucide) {
        lucide.createIcons({ nodes: resultsEl.querySelectorAll("[data-lucide]"), attrs: { "stroke-width": 2 } });
      }
    }

    // --- Selection management ---
    function updateSelection() {
      var items = resultsEl.querySelectorAll(".cmd-palette-item");
      items.forEach(function (el, i) {
        el.classList.toggle("selected", i === selectedIdx);
      });
      if (selectedIdx >= 0 && items[selectedIdx]) {
        items[selectedIdx].scrollIntoView({ block: "nearest" });
      }
    }

    function executeSelected() {
      if (selectedIdx >= 0 && currentItems[selectedIdx]) {
        var action = currentItems[selectedIdx].action;
        closePalette();
        action();
      }
    }

    // --- Open / Close ---
    function openPalette() {
      overlay.classList.add("open");
      inputEl.value = "";
      resultsEl.innerHTML = "";
      resultsEl.classList.remove("has-query");
      currentItems = [];
      selectedIdx = -1;
      inputEl.focus();

      // Render Lucide icon in the search input area
      if (window.lucide) {
        lucide.createIcons({ nodes: overlay.querySelectorAll(".cmd-palette-input-wrap [data-lucide]"), attrs: { "stroke-width": 2 } });
      }
    }

    function closePalette() {
      overlay.classList.remove("open");
      inputEl.value = "";
      resultsEl.innerHTML = "";
      resultsEl.classList.remove("has-query");
      currentItems = [];
      selectedIdx = -1;
    }

    function isOpen() {
      return overlay.classList.contains("open");
    }

    // --- Event handlers ---

    // Input: debounced search
    var debounceTimer = null;
    inputEl.addEventListener("input", function () {
      var q = inputEl.value.trim();
      clearTimeout(debounceTimer);
      if (!q) {
        resultsEl.innerHTML = "";
        resultsEl.classList.remove("has-query");
        currentItems = [];
        selectedIdx = -1;
        return;
      }
      debounceTimer = setTimeout(function () {
        var results = doSearch(q);
        render(results);
      }, 40);
    });

    // Keyboard navigation
    inputEl.addEventListener("keydown", function (e) {
      if (e.key === "ArrowDown") {
        e.preventDefault();
        if (currentItems.length) {
          selectedIdx = Math.min(selectedIdx + 1, currentItems.length - 1);
          updateSelection();
        }
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        if (currentItems.length) {
          selectedIdx = Math.max(selectedIdx - 1, 0);
          updateSelection();
        }
      } else if (e.key === "Enter") {
        e.preventDefault();
        executeSelected();
      } else if (e.key === "Escape") {
        e.preventDefault();
        closePalette();
      }
    });

    // Click on result
    resultsEl.addEventListener("click", function (e) {
      var item = e.target.closest(".cmd-palette-item");
      if (item) {
        var idx = parseInt(item.getAttribute("data-index"), 10);
        if (!isNaN(idx) && currentItems[idx]) {
          var action = currentItems[idx].action;
          closePalette();
          action();
        }
      }
    });

    // Click outside to close
    overlay.addEventListener("click", function (e) {
      if (e.target === overlay) closePalette();
    });

    // Global Ctrl+K shortcut
    document.addEventListener("keydown", function (e) {
      if ((e.ctrlKey || e.metaKey) && e.key === "k") {
        e.preventDefault();
        if (isOpen()) {
          closePalette();
        } else {
          openPalette();
        }
      }
    });
  })();
