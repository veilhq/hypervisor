/* === Hypervisor: Command Palette (Ctrl+K) === */

  // Unified command palette — fuzzy search across documents, actions, utilities,
  // tags, and navigation indexes. Pure keyboard-driven with Lucide icons.

  (function initCommandPalette() {

    // --- Action Registry ---
    var ACTIONS = [
      { name: "Rebuild Site",           icon: "hammer",        fn: function () { if (window.pywebview && window.pywebview.api && window.pywebview.api.rebuild) { try { sessionStorage.removeItem("__hv_splash_seen"); } catch (e) {} window.pywebview.api.rebuild(); } } },
      { name: "Toggle Fullscreen",      icon: "maximize",      fn: function () { if (window.pywebview && window.pywebview.api && window.pywebview.api.toggle_fullscreen) window.pywebview.api.toggle_fullscreen(); } },
      { name: "Toggle Screensaver",     icon: "monitor",       fn: function () { if (window.__screensaver) window.__screensaver.toggle(); } },
      { name: "Cycle Palette Mode",     icon: "palette",       fn: function () { var b = document.getElementById("palette-mode"); if (b) b.click(); } },
      { name: "Toggle Condensed Width", icon: "columns",       fn: function () { var b = document.getElementById("width-toggle"); if (b) b.click(); } },
      { name: "Toggle B&W Theme",       icon: "contrast",      fn: function () { var b = document.getElementById("a11y-bw-theme"); if (b) b.click(); } },
      { name: "Toggle Reduce Motion",   icon: "pause",         fn: function () { var b = document.getElementById("a11y-reduce-motion"); if (b) b.click(); } },
      { name: "Toggle Glitch Effect",   icon: "sparkles",      fn: function () { var b = document.getElementById("a11y-no-glitch"); if (b) b.click(); } },
      { name: "Toggle System Cursors",  icon: "mouse-pointer", fn: function () { var b = document.getElementById("a11y-system-cursors"); if (b) b.click(); } },
      { name: "Start Edit Mode",        icon: "pencil",        fn: function () { var b = document.getElementById("edit-btn"); if (b) b.click(); } },
      { name: "Open in File Explorer",  icon: "folder-open",   fn: function () { var b = document.getElementById("explorer-btn"); if (b) b.click(); } },
      { name: "Export Page",            icon: "package",       fn: function () { var b = document.getElementById("export-btn"); if (b) b.click(); } },
      { name: "Pin / Unpin Page",       icon: "pin",           fn: function () { var b = document.querySelector(".pin-btn"); if (b) b.click(); } },
      { name: "Go to Pinboard",         icon: "bookmark",      fn: function () { if (window.__router) window.__router.navigate("/_pins/index.html"); } },
      { name: "Scroll to Top",          icon: "arrow-up",      fn: function () { window.scrollTo({ top: 0, behavior: "smooth" }); } },
      { name: "Launch Dev Environment", icon: "terminal",      fn: function () { if (window.pywebview && window.pywebview.api && window.pywebview.api.launch_dev) window.pywebview.api.launch_dev(); } }
    ];

    // --- Utility Registry ---
    var UTILITIES = [
      { name: "ADO Dashboard",      icon: "bar-chart-3",  href: "/_utils/ado-dashboard/index.html" },
      { name: "Health Dashboard",   icon: "activity",     href: "/_utils/health-dashboard/index.html" },
      { name: "Palette Generator",  icon: "palette",      href: "/_utils/palette-generator/index.html" },
      { name: "Password Generator", icon: "lock-keyhole", href: "/_utils/password-generator/index.html" },
      { name: "Regex Editor",       icon: "regex",        href: "/_utils/regex-editor/index.html" },
      { name: "Screensaver",        icon: "monitor",      href: "/_utils/screensaver/index.html" },
      { name: "Assessment",         icon: "file-check",   href: "/_utils/assessment/index.html" }
    ];

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
          '<input type="text" class="cmd-palette-input" placeholder="Search documents, actions, tags..." autocomplete="off" spellcheck="false">' +
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

    // --- Tag index (built from search index) ---
    var tagIndex = {};
    function rebuildTagIndex() {
      tagIndex = {};
      if (!index || !index.length) return;
      index.forEach(function (entry) {
        if (entry.tags) {
          entry.tags.forEach(function (t) {
            var key = t.toLowerCase();
            if (!tagIndex[key]) tagIndex[key] = { label: t, count: 0 };
            tagIndex[key].count++;
          });
        }
      });
    }
    rebuildTagIndex();
    window.addEventListener("searchIndexReady", rebuildTagIndex);

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
      UTILITIES.forEach(function (u) {
        var score = fuzzyMatch(query, u.name);
        if (score > 0) {
          results.push({
            category: "utility",
            name: u.name,
            icon: u.icon,
            hint: "utility",
            score: score,
            action: function () { if (window.__router) window.__router.navigate(u.href); }
          });
        }
      });

      // 4. Tags
      Object.keys(tagIndex).forEach(function (key) {
        var tag = tagIndex[key];
        var score = fuzzyMatch(query, tag.label);
        if (score > 0) {
          results.push({
            category: "tag",
            name: tag.label + " (" + tag.count + ")",
            icon: "tag",
            hint: "tag",
            score: score,
            action: (function (tagLabel) {
              return function () {
                closePalette();
                if (window.__router) window.__router.navigate("/work/to-do/index.html");
                setTimeout(function () {
                  var pill = document.querySelector('.tag-pill[data-tag="' + tagLabel + '"]');
                  if (pill) pill.click();
                }, 200);
              };
            })(tag.label)
          });
        }
      });

      // 5. Navigation indexes
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

      // Sort by score descending, cap at 20 results
      results.sort(function (a, b) { return b.score - a.score; });
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
          '<span class="cmd-palette-item-text">' + escapeHtml(item.name) + '</span>' +
          '<span class="cmd-palette-item-hint">' + item.hint + '</span>' +
          '</div>';
      }).join("");

      // Activate Lucide icons in results
      if (window.lucide) {
        lucide.createIcons({ nodes: resultsEl.querySelectorAll("[data-lucide]"), attrs: { "stroke-width": 1.5 } });
      }
    }

    function escapeHtml(str) {
      return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
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
        lucide.createIcons({ nodes: overlay.querySelectorAll(".cmd-palette-input-wrap [data-lucide]"), attrs: { "stroke-width": 1.5 } });
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
