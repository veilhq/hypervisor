/* === Hypervisor: Navigation (search, menus, scroll) === */

(function () {
  "use strict";

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
        if (pins.length > 0) pinCount.textContent = HvUtils.pad2(pins.length);
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

  // --- Search Overlay ---
  var searchOverlay = document.getElementById("search-overlay");
  var searchModal = document.getElementById("search-modal");
  var searchTrigger = document.getElementById("search-trigger");

  function openSearch() {
    if (!searchOverlay) return;
    searchOverlay.classList.add("visible");
    document.body.style.overflow = "hidden";
    document.documentElement.style.overflow = "hidden";
    setTimeout(function () {
      if (searchInput) searchInput.focus();
    }, 50);
  }

  function closeSearch() {
    if (!searchOverlay) return;
    searchOverlay.classList.remove("visible");
    document.body.style.overflow = "";
    document.documentElement.style.overflow = "";
    if (searchInput) {
      searchInput.value = "";
    }
    if (resultsBox) {
      resultsBox.innerHTML = "";
    }
    activeTagFilter = null;
    updateTagIndicator();
    window.selectedIdx = -1;
    _cancelSemantic();
  }

  // Trigger button in topbar
  if (searchTrigger) {
    searchTrigger.addEventListener("click", function (e) {
      e.preventDefault();
      openSearch();
    });
  }

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
    var _semanticTimer = null;
    var _lastSemanticQuery = "";

    function doSearch(query) {
      if (!query && !activeTagFilter) {
        resultsBox.innerHTML = "";
        window.selectedIdx = -1;
        _cancelSemantic();
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

        // WI-id fast-path: a query shaped like "wi-282" / "WI282" / "282" (when
        // prefixed) resolves straight to the work item by its exact work_id,
        // surfaced ahead of the fuzzy text matches. Works in a plain static
        // build too, since work_id already lives on the client search index.
        var widMatch = /^wi-?(\d+)$/i.exec(query.trim());
        var exactWorkItems = [];
        if (widMatch) {
          var targetId = "wi-" + widMatch[1];
          exactWorkItems = matches.filter(function (entry) {
            return entry.work_id && entry.work_id.toLowerCase() === targetId;
          });
        }

        matches = matches.filter(function (entry) {
          return entry.title.toLowerCase().indexOf(q) !== -1 ||
                 entry.path.toLowerCase().indexOf(q) !== -1 ||
                 (entry.snippet && entry.snippet.toLowerCase().indexOf(q) !== -1) ||
                 (entry.tags && entry.tags.some(function (t) { return t.toLowerCase().indexOf(q) !== -1; })) ||
                 (entry.work_id && entry.work_id.toLowerCase().indexOf(q) !== -1);
        });

        // Hoist the exact WI-id hit(s) to the front, de-duplicated against the
        // text matches so a single item never renders twice.
        if (exactWorkItems.length) {
          var exactPaths = {};
          exactWorkItems.forEach(function (entry) { exactPaths[entry.path] = true; });
          matches = exactWorkItems.concat(matches.filter(function (entry) {
            return !exactPaths[entry.path];
          }));
        }
      }

      matches = matches.slice(0, 15);

      // Utility + directory matches from the shared source. Only text queries
      // produce these (a bare tag filter is a document concept); they render as
      // a labelled group ABOVE the document cards, mirroring the command
      // palette ordering so directories/utilities surface first.
      var utilDirMatches = query ? _matchUtilDir(query) : [];

      if (matches.length === 0 && utilDirMatches.length === 0) {
        var emptyMsg = activeTagFilter
          ? 'no results for tag: ' + activeTagFilter + (query ? ' + "' + query + '"' : '')
          : 'no results';
        resultsBox.innerHTML = '<div class="sr-empty">' + emptyMsg + '</div>';
        window.selectedIdx = -1;
      } else {
        // Docs render first (they own the innerHTML wipe), then the util/dir
        // group is prepended above them so it lands at the top of the list.
        _renderClientResults(matches);
        _prependUtilDirResults(utilDirMatches, matches.length > 0);
      }

      // Semantic mode: trigger bridge call for question-shaped queries (>=2 words)
      if (query && _isSemanticCandidate(query) && window.isDesktopApp) {
        _scheduleSemanticSearch(query);
      } else {
        _cancelSemantic();
      }
    }

    // Fuzzy-ish name/path match for the non-document categories. Mirrors the
    // substring semantics the document filter uses (indexOf), scoring an
    // earlier match higher so exact prefixes float up.
    function _udScore(query, text) {
      if (!text) return -1;
      var idx = text.toLowerCase().indexOf(query.toLowerCase());
      if (idx === -1) return -1;
      return idx === 0 ? 100 : Math.max(1, 50 - idx);
    }

    function _matchUtilDir(query) {
      var out = [];
      var utils = (window.HvSearchSources && window.HvSearchSources.utilities()) || [];
      var dirs = (window.HvSearchSources && window.HvSearchSources.directories()) || [];
      utils.forEach(function (u) {
        var s = _udScore(query, u.name);
        if (s > 0) out.push({ kind: "utility", label: u.name, href: u.href, score: s });
      });
      dirs.forEach(function (d) {
        var s = Math.max(_udScore(query, d.name), _udScore(query, d.path));
        if (s > 0) out.push({ kind: "directory", label: d.path, href: d.href, score: s });
      });
      out.sort(function (a, b) { return b.score - a.score; });
      return out.slice(0, 8);
    }

    // Prepend utility/directory cards ABOVE the document results. No section
    // header - each card's leading type glyph (folder for a directory, the
    // utility's own icon for a utility) is the kind readout, matching the
    // document cards' icon treatment so the whole list reads as one surface.
    // Reuses the .sr-card vocabulary so keyboard nav (which selects .sr-card
    // nodes) and the delegated click handler cover these for free.
    function _prependUtilDirResults(items, hasFilesBelow) {
      if (!items || !items.length) return;
      var frag = document.createDocumentFragment();
      items.forEach(function (item, i) {
        var card = document.createElement("a");
        card.href = item.href;
        card.className = "sr-card sr-card-compact";
        card.style.animationDelay = (i * 0.04) + "s";
        var tIcon = (window.HvSearchSources && window.HvSearchSources.iconForKind(item.kind)) || "folder";
        card.innerHTML =
          '<i data-lucide="' + tIcon + '" class="sr-card-icon"></i>' +
          '<div class="sr-card-title">' + HvUtils.escapeHtml(item.label) + '</div>' +
          '<span class="sr-card-kind">' + item.kind + '</span>';
        frag.appendChild(card);
      });
      // Hairline rule between the non-file group above and the file results
      // below. Only when both sides exist - a trailing divider with nothing
      // under it would dangle.
      if (hasFilesBelow) {
        var rule = document.createElement("div");
        rule.className = "sr-group-divider";
        frag.appendChild(rule);
      }
      resultsBox.insertBefore(frag, resultsBox.firstChild);
      _renderResultIcons();
    }

    function _isSemanticCandidate(query) {
      var words = query.trim().split(/\s+/);
      return words.length >= 2;
    }

    function _cancelSemantic() {
      if (_semanticTimer) { clearTimeout(_semanticTimer); _semanticTimer = null; }
      _lastSemanticQuery = "";
      var existing = resultsBox.querySelector(".sr-related-divider");
      if (existing) {
        // Remove divider and all cards after it
        while (existing.nextSibling) existing.nextSibling.remove();
        existing.remove();
      }
      // Also remove any skeleton placeholders
      var skel = resultsBox.querySelector(".sr-semantic-skeleton");
      if (skel) skel.remove();
    }

    function _showSemanticSkeleton() {
      // Remove any existing skeleton
      var existing = resultsBox.querySelector(".sr-semantic-skeleton");
      if (existing) existing.remove();
      // Add skeleton placeholder rows below client results
      var wrap = document.createElement("div");
      wrap.className = "sr-semantic-skeleton";
      wrap.innerHTML =
        '<div class="sr-semantic-divider" style="opacity:0.5">related</div>' +
        '<li class="loading-skeleton loading-skeleton-row"></li>' +
        '<li class="loading-skeleton loading-skeleton-row"></li>' +
        '<li class="loading-skeleton loading-skeleton-row"></li>';
      resultsBox.appendChild(wrap);
    }

    function _scheduleSemanticSearch(query) {
      if (query === _lastSemanticQuery) return;
      if (_semanticTimer) clearTimeout(_semanticTimer);
      // Show skeleton placeholders immediately while waiting for debounce + bridge call
      _showSemanticSkeleton();
      _semanticTimer = setTimeout(function () {
        _lastSemanticQuery = query;
        _doSemanticSearch(query);
      }, 400);
    }

    // Query words worth highlighting: 3+ characters, de-duplicated, lower-cased.
    function _queryTerms(query) {
      var seen = {};
      return (query.toLowerCase().match(/[a-z0-9][a-z0-9_-]{2,}/g) || []).filter(function (t) {
        if (seen[t]) return false;
        seen[t] = true;
        return true;
      });
    }

    // Escaped ~140-char snippet centered on the first matched term, with every
    // matched term wrapped in <mark class="sr-hit">.
    function _highlightSnippet(content, terms) {
      if (!content) return "";
      var text = content.replace(/\s+/g, " ").trim();
      var lower = text.toLowerCase();
      var first = -1;
      terms.forEach(function (t) {
        var idx = lower.indexOf(t);
        if (idx !== -1 && (first === -1 || idx < first)) first = idx;
      });
      var start = first > 40 ? first - 40 : 0;
      var slice = text.substring(start, start + 140);
      var html = HvUtils.escapeHtml(slice);
      if (terms.length) {
        var pattern = terms.map(function (t) {
          return HvUtils.escapeHtml(t).replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
        }).join("|");
        html = html.replace(new RegExp("(" + pattern + ")", "gi"), '<mark class="sr-hit">$1</mark>');
      }
      return (start > 0 ? "..." : "") + html + (start + 140 < text.length ? "..." : "");
    }

    function _doSemanticSearch(query) {
      if (!window.pywebview || !window.pywebview.api || !window.pywebview.api.semantic_search) return;
      window.pywebview.api.semantic_search(query, 5, null, null, null, null).then(function (results) {
        // Remove skeleton placeholders
        var skel = resultsBox.querySelector(".sr-semantic-skeleton");
        if (skel) skel.remove();
        if (!results || !results.length) return;
        if (searchInput.value.trim() !== query) return; // stale response
        // Remove existing semantic results
        var existing = resultsBox.querySelector(".sr-related-divider");
        if (existing) {
          while (existing.nextSibling) existing.nextSibling.remove();
          existing.remove();
        }
        // Add divider; says so when nothing cleared the confidence floor
        var esc = HvUtils.escapeHtml;
        var anyConfident = results.some(function (r) { return r.confidence !== "low"; });
        var divider = document.createElement("div");
        divider.className = "sr-semantic-divider sr-related-divider";
        divider.textContent = anyConfident ? "related" : "related - no strong match";
        resultsBox.appendChild(divider);
        var terms = _queryTerms(query);
        // Add result cards
        results.forEach(function (r, i) {
          var href = "/" + r.path.replace(/\.md$/, "") + "/index.html";
          var pathParts = r.path.replace(/\.md$/, "").split("/");
          var category = pathParts[0] ? pathParts[0].replace(/-/g, " ").replace(/_/g, " ") : "";
          var low = r.confidence === "low";
          var card = document.createElement("a");
          card.href = href;
          card.className = "sr-card" + (low ? " sr-card-low" : "");
          card.style.animationDelay = (i * 0.04) + "s";
          card.setAttribute("data-section", r.section || "");
          var sIcon = (window.HvSearchSources && window.HvSearchSources.iconForKind("file")) || "file-text";
          // Confidence is an icon (solid check = strong, dashed circle = weak)
          // with the word on hover; then the item status, and "exact id" only
          // when the query was a work item ID.
          var confidence = low
            ? '<span class="sr-card-confidence sr-conf-weak" title="weak match" aria-label="weak match"><i data-lucide="circle-dashed"></i></span>'
            : '<span class="sr-card-confidence sr-conf-strong" title="strong match" aria-label="strong match"><i data-lucide="circle-check"></i></span>';
          var badges = '';
          if (r.matched_by === "id") badges += '<span class="label-badge label-badge-muted">exact id</span>';
          if (r.status) badges += '<span class="label-badge label-badge-muted">' + esc(r.status) + '</span>';
          var snippet = _highlightSnippet(r.content, terms);
          var dateStr = r.updated ? esc(String(r.updated).substring(0, 10)) : "";
          card.innerHTML =
            '<i data-lucide="' + sIcon + '" class="sr-card-icon"></i>' +
            '<div class="sr-card-body">' +
              '<div class="sr-card-header">' +
                (category ? '<span class="sr-card-category">' + esc(category) + '</span>' : '') +
                badges +
                confidence +
              '</div>' +
              '<div class="sr-card-title">' + esc(r.title || r.path) + '</div>' +
              (snippet ? '<div class="sr-card-snippet">' + snippet + '</div>' : '') +
              '<div class="sr-card-footer">' +
                '<span class="sr-card-path">' + esc(r.path.replace(/\.md$/, "")) +
                  (r.section ? '<span class="sr-card-path-sep">/</span>' + esc(r.section) : '') + '</span>' +
                (dateStr ? '<span class="sr-card-date">' + dateStr + '</span>' : '') +
              '</div>' +
            '</div>';
          resultsBox.appendChild(card);
        });
        _renderResultIcons();
      }).catch(function () {
        var skel = resultsBox.querySelector(".sr-semantic-skeleton");
        if (skel) skel.remove();
      });
    }

    function _formatPath(path) {
      // Convert "context/cms-architecture" to breadcrumb-style
      var parts = path.replace(/\.md$/, "").replace(/\/index$/, "").split("/");
      return parts.map(function (p) {
        return '<span>' + p + '</span>';
      }).join('<span class="sr-card-path-sep">/</span>');
    }

    function _renderClientResults(matches) {
      resultsBox.innerHTML = matches.map(function (m, i) {
        var snippetHtml = m.snippet
          ? '<div class="sr-card-snippet">' + m.snippet.substring(0, 140) + (m.snippet.length > 140 ? '...' : '') + '</div>'
          : '';
        var tagsHtml = '';
        if (m.tags && m.tags.length) {
          tagsHtml = '<div class="sr-card-tags">' + m.tags.map(function (t) {
            return '<span class="label-badge sr-tag" data-tag="' + t + '">' + t + '</span>';
          }).join('') + '</div>';
        }
        // Header: category from first path segment + optional work ID
        var pathParts = m.path.replace(/\.md$/, "").split("/");
        var category = pathParts[0] ? pathParts[0].replace(/-/g, " ").replace(/_/g, " ") : "";
        var headerHtml = '<div class="sr-card-header">';
        if (category) headerHtml += '<span class="sr-card-category">' + category + '</span>';
        if (m.work_id) headerHtml += '<span class="sr-card-work-id">' + m.work_id + '</span>';
        headerHtml += '</div>';
        // Footer: path + date
        var dateStr = m.date ? m.date.substring(0, 10) : "";
        var footerHtml = '<div class="sr-card-footer">';
        footerHtml += '<span class="sr-card-path">' + m.path.replace(/\.md$/, "") + '</span>';
        if (dateStr) footerHtml += '<span class="sr-card-date">' + dateStr + '</span>';
        footerHtml += '</div>';
        // Leading type glyph - all documents use the single file icon.
        var icon = (window.HvSearchSources && window.HvSearchSources.iconForKind("file")) || "file-text";
        var iconHtml = '<i data-lucide="' + icon + '" class="sr-card-icon"></i>';
        return '<a href="' + m.href + '" class="sr-card" style="animation-delay:' + (i * 0.04) + 's">' +
               iconHtml +
               '<div class="sr-card-body">' +
                 headerHtml +
                 '<div class="sr-card-title">' + m.title + '</div>' +
                 snippetHtml +
                 footerHtml +
                 tagsHtml +
               '</div>' +
               '</a>';
      }).join("");
      _renderResultIcons();
      window.selectedIdx = -1;
    }

    // Activate Lucide glyphs in the results box. Cards carry data-lucide
    // placeholders; this swaps them for SVGs. Safe to call repeatedly - already
    // rendered icons are skipped by Lucide.
    function _renderResultIcons() {
      if (window.lucide) {
        try { window.lucide.createIcons({ nodes: resultsBox.querySelectorAll(".sr-card-icon[data-lucide], .sr-card-confidence [data-lucide]"), attrs: { "stroke-width": 2 } }); } catch (ex) {}
      }
    }

    // Tag click handler in search results
    resultsBox.addEventListener("click", function (e) {
      // Section-anchor scroll for semantic results
      var semanticLink = e.target.closest(".sr-card[data-section]");
      if (semanticLink && semanticLink.getAttribute("data-section")) {
        e.preventDefault();
        var href = semanticLink.getAttribute("href");
        var section = semanticLink.getAttribute("data-section");
        closeSearch();
        if (window.__hypervisorNavigate) {
          window.__hypervisorNavigate(href, function () {
            _scrollToSection(section);
          });
        } else {
          window.location.href = href + "#" + _slugify(section);
        }
        return;
      }

      // Regular result click - close overlay and navigate
      var resultCard = e.target.closest(".sr-card");
      if (resultCard && !e.target.closest(".sr-tag")) {
        e.preventDefault();
        var cardHref = resultCard.getAttribute("href");
        closeSearch();
        if (window.__hypervisorNavigate) {
          window.__hypervisorNavigate(cardHref);
        } else {
          window.location.href = cardHref;
        }
        return;
      }

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

    // Tag filter indicator (inside modal)
    function updateTagIndicator() {
      var existing = searchModal ? searchModal.querySelector(".search-tag-filter") : null;
      if (existing) existing.remove();
      if (activeTagFilter && searchModal) {
        var indicator = document.createElement("div");
        indicator.className = "search-tag-filter";
        indicator.innerHTML = '<span class="search-tag-filter-label">tag:</span> ' +
          '<span class="search-tag-filter-value">' + activeTagFilter + '</span>' +
          '<button class="search-tag-filter-clear" aria-label="Clear tag filter">&times;</button>';
        indicator.querySelector(".search-tag-filter-clear").addEventListener("click", function () {
          activeTagFilter = null;
          updateTagIndicator();
          doSearch(searchInput.value.trim());
        });
        // Insert after input row, before results
        var inputRow = searchModal.querySelector(".search-input-row");
        if (inputRow && inputRow.nextSibling) {
          searchModal.insertBefore(indicator, inputRow.nextSibling);
        } else {
          searchModal.appendChild(indicator);
        }
      }
    }

    function _slugify(text) {
      return text.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
    }

    function _scrollToSection(sectionTitle) {
      setTimeout(function () {
        var headings = document.querySelectorAll(".markdown-body h2, .markdown-body h3");
        for (var i = 0; i < headings.length; i++) {
          if (headings[i].textContent.trim() === sectionTitle) {
            headings[i].scrollIntoView({ behavior: "smooth", block: "start" });
            headings[i].style.transition = "background 0.3s";
            headings[i].style.background = "var(--selected-wash)";
            setTimeout(function () { headings[i].style.background = ""; }, 1500);
            return;
          }
        }
        var slug = _slugify(sectionTitle);
        var target = document.getElementById(slug);
        if (target) target.scrollIntoView({ behavior: "smooth", block: "start" });
      }, 200);
    }

    searchInput.addEventListener("input", function () {
      doSearch(this.value.trim());
    });

    searchInput.addEventListener("keydown", function (e) {
      var items = resultsBox.querySelectorAll(".sr-card");
      if (e.key === "ArrowDown" && items.length) {
        e.preventDefault();
        window.selectedIdx = Math.min(selectedIdx + 1, items.length - 1);
        updateSelected(items);
      } else if (e.key === "ArrowUp" && items.length) {
        e.preventDefault();
        window.selectedIdx = Math.max(selectedIdx - 1, 0);
        updateSelected(items);
      } else if (e.key === "Enter" && selectedIdx >= 0 && items.length) {
        e.preventDefault();
        items[selectedIdx].click();
      } else if (e.key === "Enter" && items.length && selectedIdx < 0) {
        // Auto-select first result on Enter with no selection
        e.preventDefault();
        items[0].click();
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

    // Close on backdrop click (but not on modal click)
    if (searchOverlay) {
      searchOverlay.addEventListener("click", function (e) {
        if (e.target === searchOverlay) {
          closeSearch();
        }
      });
    }

    // Global keyboard handler
    document.addEventListener("keydown", function (e) {
      var isOverlayOpen = searchOverlay && searchOverlay.classList.contains("visible");

      // '/' opens search (when not in an input and overlay is closed)
      if (e.key === "/" && !isOverlayOpen &&
          document.activeElement !== searchInput &&
          !document.activeElement.closest("input, textarea, [contenteditable]") &&
          !document.querySelector(".shortcuts-overlay.visible")) {
        e.preventDefault();
        // In zen mode the search input is inline in the stage, not in the
        // overlay - focus it directly rather than opening the (now shell-only)
        // overlay. Gated on zen-staged (stage actually mounted), since that is
        // when the input lives inline; off-home the overlay path is correct.
        if (document.body.classList.contains("zen-staged") && searchInput) {
          searchInput.focus();
        } else {
          openSearch();
        }
        return;
      }

      // Escape closes search overlay
      if (e.key === "Escape" && isOverlayOpen) {
        e.preventDefault();
        closeSearch();
        return;
      }
    });
  }

  // --- Reference menu dropdown ---
  (function initNavPanel() {
    var btn = document.getElementById("nav-menu-btn");
    var panel = document.getElementById("nav-panel");
    var backdrop = document.getElementById("nav-backdrop");
    if (!btn || !panel) return;

    function openDrawer() {
      panel.classList.add("open");
      btn.classList.add("active");
      if (backdrop) backdrop.classList.add("visible");
      if (window.lucide) lucide.createIcons({ attrs: { "stroke-width": 2 } });
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

    // --- Nav panel tabs ---
    (function initNavTabs() {
      var tabs = panel.querySelectorAll(".nav-tab-bar .nav-tab");
      var panels = panel.querySelectorAll(".nav-tab-content");
      if (!tabs.length || !panels.length) return;

      var STORAGE_KEY = "hypervisor-nav-tab";
      var stored = localStorage.getItem(STORAGE_KEY);

      function activate(id) {
        tabs.forEach(function (t) {
          var active = t.getAttribute("aria-controls") === id;
          t.classList.toggle("active", active);
          t.setAttribute("aria-selected", active ? "true" : "false");
        });
        panels.forEach(function (p) {
          p.classList.toggle("active", p.id === id);
        });
        localStorage.setItem(STORAGE_KEY, id);
      }

      // Restore persisted tab
      if (stored && panel.querySelector("#" + stored)) {
        activate(stored);
      }

      tabs.forEach(function (tab) {
        tab.addEventListener("click", function () {
          activate(tab.getAttribute("aria-controls"));
        });
      });
    })();

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
        refList.innerHTML = '<div style="padding:0.4rem 0.5rem;color:var(--text-dim);font-size: var(--fs-mono);">no reference docs yet</div>';
      }

      refBtn.addEventListener("click", function () {
        refList.classList.toggle("open");
      });
    }

    // --- Populate utilities list ---
    var utilList = document.getElementById("nav-util-list");
    if (utilList) {
      // Utilities list is data-driven: the build emits _utils/_manifest.json
      // from the actual utility files, so this never needs manual editing.
      fetch('/content/_utils/_manifest.json')
        .then(function (r) { return r.ok ? r.json() : []; })
        .then(function (utilities) {
          utilList.innerHTML = (utilities || []).map(function (u) {
            return '<a href="/' + u.href + '" class="nav-link">' +
                   '<i data-lucide="' + u.icon + '" class="nav-link-icon"></i>' +
                   '<span class="nav-link-text">' + u.name + '</span>' +
                   '</a>';
          }).join('');
          if (window.lucide && window.lucide.createIcons) window.lucide.createIcons();
        })
        .catch(function () { /* manifest missing - leave nav utils empty */ });
    }
  })();

  // --- Copy button on code blocks ---
  // Re-runs on every content swap: code blocks arrive with each navigated
  // fragment, so a one-time pass at load only decorates the first page's
  // blocks and leaves navigated-to pages without copy buttons.
  function initCodeCopy() {
    var codeBlocks = document.querySelectorAll(".code-block");
    codeBlocks.forEach(function (block) {
      // Guard against decorating a block twice if the hook fires again over
      // content that survived a swap.
      if (block.querySelector(".code-copy")) return;

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
  }

  // Decorate the initial page, then re-decorate after every fragment swap.
  initCodeCopy();
  if (window.__router && window.__router.onNavigate) {
    window.__router.onNavigate(null, initCodeCopy);
  }

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

})();
