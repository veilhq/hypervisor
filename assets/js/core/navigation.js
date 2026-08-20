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

  // --- Search Overlay ---
  var searchOverlay = document.getElementById("search-overlay");
  var searchModal = document.getElementById("search-modal");
  var searchTrigger = document.getElementById("search-trigger");
  var _searchNoise = null; // independent noise field for search (avoids clobbering home-anchor's HvNoiseField)

  // Lightweight standalone noise field — mirrors HvNoiseField's shader but runs independently
  function _createSearchNoise(host) {
    var canvas = document.createElement("canvas");
    canvas.className = "hv-noise-field-canvas";
    host.insertBefore(canvas, host.firstChild);
    canvas.width = host.clientWidth || 1;
    canvas.height = host.clientHeight || 1;
    var gl = canvas.getContext("webgl2", { alpha: false, antialias: false });
    if (!gl) { canvas.remove(); return null; }

    var VERT = "#version 300 es\nvoid main(){float x=float(gl_VertexID%2)*4.0-1.0;float y=float(gl_VertexID/2)*4.0-1.0;gl_Position=vec4(x,y,0,1);}";
    var FRAG = [
      "#version 300 es", "precision highp float;",
      "uniform vec2 u_resolution;", "uniform float u_time;", "uniform vec3 u_tint;", "uniform vec3 u_bg;", "uniform float u_cellDivisor;",
      "out vec4 fragColor;",
      "float bayer8(vec2 pos){ivec2 p=ivec2(mod(pos,8.0));float m[64]=float[64](0.0,32.0,8.0,40.0,2.0,34.0,10.0,42.0,48.0,16.0,56.0,24.0,50.0,18.0,58.0,26.0,12.0,44.0,4.0,36.0,14.0,46.0,6.0,38.0,60.0,28.0,52.0,20.0,62.0,30.0,54.0,22.0,3.0,35.0,11.0,43.0,1.0,33.0,9.0,41.0,51.0,19.0,59.0,27.0,49.0,17.0,57.0,25.0,15.0,47.0,7.0,39.0,13.0,45.0,5.0,37.0,63.0,31.0,55.0,23.0,61.0,29.0,53.0,21.0);return m[p.x+p.y*8]/64.0;}",
      "void main(){float t=u_time;float cellSize=max(2.0,floor(min(u_resolution.x,u_resolution.y)/u_cellDivisor));vec2 cellUv=floor(gl_FragCoord.xy/cellSize)*cellSize;vec2 cellPos=cellUv/u_resolution;float cx=0.5+sin(t*0.4)*0.3;float cy=0.5+cos(t*0.3)*0.3;vec2 d=cellPos-vec2(cx,cy);float dist=length(d);float g1=0.5+0.5*sin(dist*6.0-t*0.8);float g2=0.5+0.5*sin((cellUv.x+cellUv.y)*0.0032+t*0.5);float g3=0.5+0.5*cos((cellUv.y-cellUv.x)*0.0041-t*0.3);float val=g1*0.5+g2*0.25+g3*0.25;val=val*val;float threshold=bayer8(gl_FragCoord.xy/cellSize);if(val<threshold){fragColor=vec4(u_bg,1.0);return;}fragColor=vec4(u_tint,1.0);}"
    ].join("\n");

    var vs = gl.createShader(gl.VERTEX_SHADER);
    gl.shaderSource(vs, VERT); gl.compileShader(vs);
    var fs = gl.createShader(gl.FRAGMENT_SHADER);
    gl.shaderSource(fs, FRAG); gl.compileShader(fs);
    if (!gl.getShaderParameter(fs, gl.COMPILE_STATUS)) { canvas.remove(); return null; }
    var prog = gl.createProgram();
    gl.attachShader(prog, vs); gl.attachShader(prog, fs); gl.linkProgram(prog);
    if (!gl.getProgramParameter(prog, gl.LINK_STATUS)) { canvas.remove(); return null; }
    var vao = gl.createVertexArray();
    var t = Math.random() * 1000;
    var raf = null;

    function readTint() {
      try {
        var raw = getComputedStyle(document.documentElement).getPropertyValue("--accent").trim();
        var m = /^#?([0-9a-f]{6})$/i.exec(raw);
        if (m) { var h = m[1]; return [parseInt(h.substr(0,2),16)/255*0.15, parseInt(h.substr(2,2),16)/255*0.15, parseInt(h.substr(4,2),16)/255*0.15]; }
      } catch(e){}
      return [0.09,0.09,0.09];
    }
    function readBg() {
      try {
        var raw = getComputedStyle(document.documentElement).getPropertyValue("--bg").trim();
        var m = /^#?([0-9a-f]{6})$/i.exec(raw);
        if (m) { var h = m[1]; return [parseInt(h.substr(0,2),16)/255, parseInt(h.substr(2,2),16)/255, parseInt(h.substr(4,2),16)/255]; }
      } catch(e){}
      return [0,0,0];
    }

    function frame() {
      var w = host.clientWidth || 1, h2 = host.clientHeight || 1;
      if (canvas.width !== w || canvas.height !== h2) { canvas.width = w; canvas.height = h2; }
      gl.viewport(0, 0, w, h2);
      gl.useProgram(prog); gl.bindVertexArray(vao);
      gl.uniform2f(gl.getUniformLocation(prog, "u_resolution"), w, h2);
      gl.uniform1f(gl.getUniformLocation(prog, "u_time"), t);
      gl.uniform1f(gl.getUniformLocation(prog, "u_cellDivisor"), 300);
      var tint = readTint(); gl.uniform3f(gl.getUniformLocation(prog, "u_tint"), tint[0], tint[1], tint[2]);
      var bg = readBg(); gl.uniform3f(gl.getUniformLocation(prog, "u_bg"), bg[0], bg[1], bg[2]);
      gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);
      t += 1/60;
      raf = requestAnimationFrame(frame);
    }

    raf = requestAnimationFrame(frame);
    return { canvas: canvas, stop: function (fadeMs) {
      if (raf) { cancelAnimationFrame(raf); raf = null; }
      if (prog) gl.deleteProgram(prog);
      if (!fadeMs) { canvas.remove(); } else {
        canvas.style.transition = "opacity " + fadeMs + "ms";
        canvas.style.opacity = "0";
        setTimeout(function () { canvas.remove(); }, fadeMs);
      }
    }};
  }

  function openSearch() {
    if (!searchOverlay) return;
    searchOverlay.classList.add("visible");
    document.body.style.overflow = "hidden";
    document.documentElement.style.overflow = "hidden";
    // Mount independent noise field behind the modal
    if (!_searchNoise) {
      _searchNoise = _createSearchNoise(searchOverlay);
    }
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
    // Tear down noise field
    if (_searchNoise) {
      _searchNoise.stop(300);
      _searchNoise = null;
    }
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
        window.selectedIdx = -1;
      } else {
        _renderClientResults(matches);
      }

      // Semantic mode: trigger bridge call for question-shaped queries (>=2 words)
      if (query && _isSemanticCandidate(query) && window.isDesktopApp) {
        _scheduleSemanticSearch(query);
      } else {
        _cancelSemantic();
      }
    }

    function _isSemanticCandidate(query) {
      var words = query.trim().split(/\s+/);
      return words.length >= 2;
    }

    function _cancelSemantic() {
      if (_semanticTimer) { clearTimeout(_semanticTimer); _semanticTimer = null; }
      _lastSemanticQuery = "";
      var existing = resultsBox.querySelector(".sr-semantic-divider");
      if (existing) {
        // Remove divider and all cards after it
        while (existing.nextSibling) existing.nextSibling.remove();
        existing.remove();
      }
    }

    function _scheduleSemanticSearch(query) {
      if (query === _lastSemanticQuery) return;
      if (_semanticTimer) clearTimeout(_semanticTimer);
      _semanticTimer = setTimeout(function () {
        _lastSemanticQuery = query;
        _doSemanticSearch(query);
      }, 400);
    }

    function _doSemanticSearch(query) {
      if (!window.pywebview || !window.pywebview.api || !window.pywebview.api.semantic_search) return;
      window.pywebview.api.semantic_search(query, 5, null, null, null, null).then(function (results) {
        if (!results || !results.length) return;
        if (searchInput.value.trim() !== query) return; // stale response
        // Remove existing semantic results
        var existing = resultsBox.querySelector(".sr-semantic-divider");
        if (existing) {
          while (existing.nextSibling) existing.nextSibling.remove();
          existing.remove();
        }
        // Add divider
        var divider = document.createElement("div");
        divider.className = "sr-semantic-divider";
        divider.textContent = "related";
        resultsBox.appendChild(divider);
        // Add result cards
        results.forEach(function (r, i) {
          var href = "/" + r.path.replace(/\.md$/, "") + "/index.html";
          var pathParts = r.path.replace(/\.md$/, "").split("/");
          var category = pathParts[0] ? pathParts[0].replace(/-/g, " ").replace(/_/g, " ") : "";
          var snippet = r.content ? r.content.substring(0, 140) + (r.content.length > 140 ? "..." : "") : "";
          var card = document.createElement("a");
          card.href = href;
          card.className = "sr-card";
          card.style.animationDelay = (i * 0.04) + "s";
          card.setAttribute("data-section", r.section || "");
          card.innerHTML =
            '<span class="hv-chip hv-chip-outlined-muted sr-partial-badge">\u2248 partial</span>' +
            '<div class="sr-card-header">' +
              (category ? '<span class="sr-card-category">' + category + '</span>' : '') +
            '</div>' +
            '<div class="sr-card-title">' + r.title + (r.section ? ' \u00A7 ' + r.section : '') + '</div>' +
            (snippet ? '<div class="sr-card-snippet">' + snippet + '</div>' : '') +
            '<div class="sr-card-footer">' +
              '<span class="sr-card-path">' + r.path.replace(/\.md$/, "") + '</span>' +
            '</div>';
          resultsBox.appendChild(card);
        });
      }).catch(function () {});
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
            return '<span class="sr-tag" data-tag="' + t + '">' + t + '</span>';
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
        return '<a href="' + m.href + '" class="sr-card" style="animation-delay:' + (i * 0.04) + 's">' +
               headerHtml +
               '<div class="sr-card-title">' + m.title + '</div>' +
               snippetHtml +
               footerHtml +
               tagsHtml +
               '</a>';
      }).join("");
      window.selectedIdx = -1;
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

      // Regular result click — close overlay and navigate
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
            headings[i].style.background = "var(--accent-glow)";
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
        if (e.target === searchOverlay || e.target.classList.contains("hv-noise-field-canvas")) {
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
        openSearch();
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
        { name: "Log Viewer", icon: "terminal", href: "_utils/log-viewer/index.html" },
        { name: "Palette Generator", icon: "palette", href: "_utils/palette-generator/index.html" },
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

})();
