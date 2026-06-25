/* === Hypervisor: Navigation (search, menus, scroll) === */

  // --- Site nav: highlight current category and expand children ---
  (function () {
    var siteNav = document.getElementById("site-nav");
    if (!siteNav) return;
    // Determine current category from the page path
    var path = window.location.pathname || "";
    var segments = path.split("/").filter(function (s) { return s && s !== "index.html"; });
    var currentCategory = segments.length > 0 ? segments[0] : "";
    var currentChild = segments.length > 1 ? segments[0] + "/" + segments[1] : "";

    if (currentCategory) {
      // Highlight parent category
      var items = siteNav.querySelectorAll(".site-nav-item");
      items.forEach(function (item) {
        if (item.getAttribute("data-category") === currentCategory) {
          item.classList.add("active");
        }
      });
      // Expand and show children panel for active category
      var childPanel = siteNav.querySelector('.site-nav-children[data-parent="' + currentCategory + '"]');
      if (childPanel) {
        childPanel.classList.add("open");
      }
      // Highlight active child
      if (currentChild) {
        var childItems = siteNav.querySelectorAll(".site-nav-child");
        childItems.forEach(function (child) {
          if (child.getAttribute("data-category") === currentChild) {
            child.classList.add("active");
          }
        });
      }
    }
    // Populate pinboard count from localStorage
    var pinCount = siteNav.querySelector(".site-nav-pin-count");
    if (pinCount) {
      try {
        var pins = JSON.parse(localStorage.getItem("hypervisor-pins") || "[]");
        if (pins.length > 0) pinCount.textContent = pins.length;
      } catch (e) {}
    }
  })();

  // --- Topbar scroll shadow ---
  if (topbar) {
    var ticking = false;
    window.addEventListener("scroll", function () {
      if (!ticking) {
        requestAnimationFrame(function () {
          topbar.classList.toggle("scrolled", window.scrollY > 10);
          ticking = false;
        });
        ticking = true;
      }
    });
  }

  // --- Search ---
  if (searchInput && resultsBox) {
    // Build tag index from search data (rebuilt when index loads)
    var allTags = {};

    function rebuildTagIndex() {
      allTags = {};
      index.forEach(function (entry) {
        if (entry.tags) {
          entry.tags.forEach(function (tag) {
            var key = tag.toLowerCase();
            if (!allTags[key]) allTags[key] = { label: tag, count: 0 };
            allTags[key].count++;
          });
        }
      });
    }
    rebuildTagIndex();
    window.addEventListener("searchIndexReady", rebuildTagIndex);

    var activeTagFilter = null;

    function doSearch(query) {
      if (!query && !activeTagFilter) {
        resultsBox.classList.remove("open");
        resultsBox.innerHTML = "";
        selectedIdx = -1;
        return;
      }

      var matches = index;

      // Filter by active tag first
      if (activeTagFilter) {
        var tagLower = activeTagFilter.toLowerCase();
        matches = matches.filter(function (entry) {
          return entry.tags && entry.tags.some(function (t) {
            return t.toLowerCase() === tagLower;
          });
        });
      }

      // Then filter by text query
      if (query) {
        var q = query.toLowerCase();
        matches = matches.filter(function (entry) {
          return entry.title.toLowerCase().indexOf(q) !== -1 ||
                 entry.path.toLowerCase().indexOf(q) !== -1 ||
                 (entry.snippet && entry.snippet.toLowerCase().indexOf(q) !== -1) ||
                 (entry.tags && entry.tags.some(function (t) { return t.toLowerCase().indexOf(q) !== -1; }));
        });
      }

      matches = matches.slice(0, 15);

      if (matches.length === 0) {
        var emptyMsg = activeTagFilter
          ? 'no results for tag: ' + activeTagFilter + (query ? ' + "' + query + '"' : '')
          : 'no results';
        resultsBox.innerHTML = '<div class="sr-empty">' + emptyMsg + '</div>';
        resultsBox.classList.add("open");
        selectedIdx = -1;
        return;
      }

      resultsBox.innerHTML = matches.map(function (m, i) {
        var snippetHtml = m.snippet
          ? '<span class="sr-snippet">' + m.snippet.substring(0, 120) + (m.snippet.length > 120 ? '...' : '') + '</span>'
          : '';
        var tagsHtml = '';
        if (m.tags && m.tags.length) {
          tagsHtml = '<span class="sr-tags">' + m.tags.map(function (t) {
            return '<span class="sr-tag" data-tag="' + t + '">' + t + '</span>';
          }).join('') + '</span>';
        }
        return '<a href="' + m.href + '" style="animation-delay:' + (i * 0.03) + 's">' +
               m.title +
               '<span class="sr-path">' + m.path + '</span>' +
               snippetHtml +
               tagsHtml +
               '</a>';
      }).join("");
      resultsBox.classList.add("open");
      selectedIdx = -1;
    }

    // Tag click handler in search results
    resultsBox.addEventListener("click", function (e) {
      var tagEl = e.target.closest(".sr-tag");
      if (tagEl) {
        e.preventDefault();
        e.stopPropagation();
        var tag = tagEl.getAttribute("data-tag");
        if (activeTagFilter === tag) {
          activeTagFilter = null;
        } else {
          activeTagFilter = tag;
        }
        updateTagIndicator();
        doSearch(searchInput.value.trim());
        return;
      }
    });

    // Tag filter indicator
    function updateTagIndicator() {
      var existing = document.querySelector(".tag-filter-indicator");
      if (existing) existing.remove();
      if (activeTagFilter) {
        var indicator = document.createElement("div");
        indicator.className = "tag-filter-indicator";
        indicator.innerHTML = '<span class="tag-filter-label">tag:</span> ' +
          '<span class="tag-filter-value">' + activeTagFilter + '</span>' +
          '<button class="tag-filter-clear" aria-label="Clear tag filter">&times;</button>';
        indicator.querySelector(".tag-filter-clear").addEventListener("click", function () {
          activeTagFilter = null;
          updateTagIndicator();
          doSearch(searchInput.value.trim());
        });
        var wrap = document.querySelector(".search-wrap");
        if (wrap) wrap.appendChild(indicator);
      }
    }

    searchInput.addEventListener("input", function () {
      doSearch(this.value.trim());
    });

    searchInput.addEventListener("focus", function () {
      if (this.value.trim() || activeTagFilter) doSearch(this.value.trim());
    });

    searchInput.addEventListener("keydown", function (e) {
      var items = resultsBox.querySelectorAll("a");
      if (!items.length) return;

      if (e.key === "ArrowDown") {
        e.preventDefault();
        selectedIdx = Math.min(selectedIdx + 1, items.length - 1);
        updateSelected(items);
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        selectedIdx = Math.max(selectedIdx - 1, 0);
        updateSelected(items);
      } else if (e.key === "Enter" && selectedIdx >= 0) {
        e.preventDefault();
        items[selectedIdx].click();
      }
    });

    function updateSelected(items) {
      items.forEach(function (a, i) {
        a.classList.toggle("selected", i === selectedIdx);
      });
      if (selectedIdx >= 0 && items[selectedIdx]) {
        items[selectedIdx].scrollIntoView({ block: "nearest" });
      }
    }

    document.addEventListener("click", function (e) {
      if (!e.target.closest(".search-wrap")) {
        resultsBox.classList.remove("open");
        selectedIdx = -1;
      }
    });

    document.addEventListener("keydown", function (e) {
      if (e.key === "/" && document.activeElement !== searchInput && !document.querySelector(".shortcuts-overlay.visible")) {
        e.preventDefault();
        searchInput.focus();
      }
      if (e.key === "Escape") {
        // Close shortcuts overlay if open
        var overlay = document.querySelector(".shortcuts-overlay");
        if (overlay && overlay.classList.contains("visible")) {
          overlay.classList.remove("visible");
          return;
        }
        searchInput.value = "";
        activeTagFilter = null;
        updateTagIndicator();
        resultsBox.classList.remove("open");
        searchInput.blur();
        selectedIdx = -1;
      }
    });
  }

  // --- Reference menu dropdown ---
  (function initNavPanel() {
    var btn = document.getElementById("nav-menu-btn");
    var panel = document.getElementById("nav-panel");
    var backdrop = document.getElementById("nav-backdrop");
    var closeBtn = document.getElementById("nav-panel-close");
    if (!btn || !panel) return;

    function openDrawer() {
      panel.classList.add("open");
      btn.classList.add("active");
      if (backdrop) backdrop.classList.add("visible");
      if (window.lucide) lucide.createIcons({ attrs: { "stroke-width": 1.5 } });
    }

    function closeDrawer() {
      panel.classList.remove("open");
      btn.classList.remove("active");
      if (backdrop) backdrop.classList.remove("visible");
    }

    btn.addEventListener("click", function (e) {
      e.stopPropagation();
      if (panel.classList.contains("open")) {
        closeDrawer();
      } else {
        openDrawer();
      }
    });

    if (closeBtn) closeBtn.addEventListener("click", closeDrawer);
    if (backdrop) backdrop.addEventListener("click", closeDrawer);

    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape" && panel.classList.contains("open")) {
        closeDrawer();
      }
      if (e.key === "m" && document.activeElement !== searchInput && !document.activeElement.closest("input, textarea, [contenteditable]")) {
        e.preventDefault();
        if (panel.classList.contains("open")) {
          closeDrawer();
        } else {
          openDrawer();
        }
      }
    });

    // --- Populate reference list ---
    var refBtn = document.getElementById("nav-ref-btn");
    var refList = document.getElementById("nav-ref-list");
    if (refBtn && refList && index.length) {
      var refDocs = index.filter(function (entry) {
        return entry.path.indexOf("reference/") === 0 && entry.path !== "reference/_meta.md";
      });

      if (refDocs.length) {
        refList.innerHTML = refDocs.map(function (doc) {
          var desc = doc.snippet ? doc.snippet.substring(0, 80) + (doc.snippet.length > 80 ? '...' : '') : '';
          return '<a href="' + doc.href + '">' +
                 doc.title +
                 (desc ? '<span class="ref-item-desc">' + desc + '</span>' : '') +
                 '</a>';
        }).join('');
      } else {
        refList.innerHTML = '<div style="padding:0.4rem 0.5rem;color:var(--text-dim);font-size:0.65rem;">no reference docs yet</div>';
      }

      refBtn.addEventListener("click", function () {
        refList.classList.toggle("open");
      });
    }

    // --- Populate utilities list ---
    var utilList = document.getElementById("nav-util-list");
    if (utilList) {
      var utilities = [
        { name: "ADO Dashboard", icon: "bar-chart-3", href: "_utils/ado-dashboard/index.html" },
        { name: "Health Dashboard", icon: "activity", href: "_utils/health-dashboard/index.html" },
        { name: "Password Generator", icon: "lock-keyhole", href: "_utils/password-generator/index.html" },
        { name: "Regex Editor", icon: "regex", href: "_utils/regex-editor/index.html" },
        { name: "Screensaver", icon: "monitor", href: "_utils/screensaver/index.html" },
        { name: "Assessment", icon: "file-check", href: "_utils/assessment/index.html" }
      ];

      utilList.innerHTML = utilities.map(function (u) {
        return '<a href="/' + u.href + '" class="nav-link">' +
               '<i data-lucide="' + u.icon + '" class="nav-link-icon"></i>' +
               '<span class="nav-link-text">' + u.name + '</span>' +
               '</a>';
      }).join('');
    }
  })();

  // --- Copy button on code blocks ---
  var codeBlocks = document.querySelectorAll(".code-block");
  codeBlocks.forEach(function (block) {
    var btn = document.createElement("button");
    btn.className = "code-copy";
    btn.textContent = "copy";
    btn.setAttribute("aria-label", "Copy code to clipboard");

    btn.addEventListener("click", function () {
      var code = block.querySelector("pre code") || block.querySelector("pre");
      if (!code) return;
      var text = code.textContent || code.innerText;

      navigator.clipboard.writeText(text).then(function () {
        btn.textContent = "copied";
        btn.classList.add("copied");
        setTimeout(function () {
          btn.textContent = "copy";
          btn.classList.remove("copied");
        }, 1500);
      }).catch(function () {
        // Fallback for file:// protocol where clipboard API may not work
        btn.textContent = "err";
        setTimeout(function () { btn.textContent = "copy"; }, 1000);
      });
    });

    block.appendChild(btn);
  });

  // --- Scroll to top ---
  if (scrollBtn) {
    window.addEventListener("scroll", function () {
      scrollBtn.classList.toggle("visible", window.scrollY > 300);
    });
    scrollBtn.addEventListener("click", function () {
      window.scrollTo({ top: 0, behavior: "smooth" });
    });
  }

  // --- External link handler ---
  // Opens https:// links in the system browser instead of navigating
  // the PyWebView window away from the site. In a regular browser this
  // just opens a new tab via target="_blank".
  document.addEventListener("click", function (e) {
    var anchor = e.target.closest("a[href]");
    if (!anchor) return;
    var href = anchor.getAttribute("href");
    if (!href || !href.match(/^https?:\/\//)) return;

    e.preventDefault();
    if (window.pywebview && window.pywebview.api && window.pywebview.api.open_external_url) {
      window.pywebview.api.open_external_url(href);
    } else {
      window.open(href, "_blank");
    }
  });
