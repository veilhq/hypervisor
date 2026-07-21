/* === Hypervisor: Pinboard (pin documents for quick access) === */

  // --- Pin management (localStorage-backed, with disk-preference restore) ---
  (function initPins() {
    var STORAGE_KEY = "hypervisor-pins";
    var _prefsRestored = false;
    var _currentPinBtn = null;
    var _currentDocPath = null;

    function getPins() {
      try {
        var raw = localStorage.getItem(STORAGE_KEY);
        if (raw) return JSON.parse(raw);
      } catch (e) {}
      return [];
    }

    function savePins(pins) {
      try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(pins));
      } catch (e) {}
      if (typeof savePreference === "function") {
        savePreference(STORAGE_KEY, JSON.stringify(pins));
      }
    }

    function isPinned(path) {
      return getPins().some(function (p) { return p.path === path; });
    }

    function addPin(path, title) {
      var pins = getPins();
      if (pins.some(function (p) { return p.path === path; })) return;
      pins.push({ path: path, title: title, pinned: Date.now() });
      savePins(pins);
    }

    function removePin(path) {
      var pins = getPins().filter(function (p) { return p.path !== path; });
      savePins(pins);
    }

    // --- Restore pins from preferences.json ---
    function restorePinsFromPrefs() {
      if (_prefsRestored) return;
      _prefsRestored = true;
      if (!(window.pywebview && window.pywebview.api)) return;
      try {
        var result = window.pywebview.api.load_preferences();
        var handler = function (data) {
          if (!data || typeof data !== "object") return;
          var diskRaw = data[STORAGE_KEY];
          if (!diskRaw) return;
          var diskPins;
          try { diskPins = JSON.parse(diskRaw); } catch (e) { return; }
          if (!Array.isArray(diskPins) || !diskPins.length) return;

          var localPins = getPins();
          if (localPins.length >= diskPins.length) {
            var localPaths = {};
            localPins.forEach(function (p) { localPaths[p.path] = true; });
            var merged = localPins.slice();
            diskPins.forEach(function (p) { if (!localPaths[p.path]) merged.push(p); });
            if (merged.length > localPins.length) savePins(merged);
          } else {
            var diskPaths = {};
            diskPins.forEach(function (p) { diskPaths[p.path] = true; });
            var merged = diskPins.slice();
            localPins.forEach(function (p) { if (!diskPaths[p.path]) merged.push(p); });
            savePins(merged);
          }
          // Re-render pinboard if currently on it
          var container = document.querySelector(".pinboard-content");
          if (container) renderPinboard(container);
          // Re-render homepage pins panel if currently on the home page
          var homeMount = document.querySelector("[data-pins-home-list]");
          if (homeMount) renderHomepagePins(homeMount);
          updateNavPinCount();
        };
        if (result && typeof result.then === "function") {
          result.then(handler);
        } else if (result && typeof result === "object") {
          handler(result);
        }
      } catch (e) {}
    }

    window.addEventListener("pywebviewready", restorePinsFromPrefs);

    // --- Lifecycle: teardown old pin button ---
    function teardown() {
      if (_currentPinBtn && _currentPinBtn.parentNode) {
        _currentPinBtn.parentNode.removeChild(_currentPinBtn);
      }
      _currentPinBtn = null;
      _currentDocPath = null;
    }

    // --- Lifecycle: init pin button for new page ---
    function init(fragment) {
      if (!fragment) return;

      var relPath = fragment.sourcePath || "";
      var isDocPage = relPath && (relPath.endsWith(".md") || relPath.startsWith("learn/"));
      var isPinboardPage = fragment.pageType === "pinboard";
      _currentDocPath = isDocPage ? relPath : null;

      // Add pin button on doc pages
      if (isDocPage && relPath) {
        var h1 = document.querySelector("#content-target h1");
        var pageTitle = h1 ? h1.textContent.trim() : fragment.title || "";

        var drawer = document.querySelector(".actions-drawer-inner");
        if (drawer) {
          var pinBtn = document.createElement("button");
          pinBtn.className = "action-item pin-btn";
          pinBtn.id = "pin-btn";
          pinBtn.setAttribute("aria-label", "Pin this document");

          var pinIcon = document.createElement("i");
          pinIcon.setAttribute("data-lucide", "pin");
          pinIcon.className = "action-icon";
          pinBtn.appendChild(pinIcon);

          var pinLabel = document.createElement("span");
          pinLabel.className = "action-label pin-btn-label";
          pinLabel.textContent = isPinned(relPath) ? "unpin" : "pin";
          pinBtn.appendChild(pinLabel);

          if (isPinned(relPath)) pinBtn.classList.add("pinned");

          drawer.insertBefore(pinBtn, drawer.firstChild);
          if (window.lucide) lucide.createIcons({ nodes: [pinBtn], attrs: { "stroke-width": 1.5 } });

          pinBtn.addEventListener("click", function () {
            if (isPinned(relPath)) {
              removePin(relPath);
              pinBtn.classList.remove("pinned");
              pinLabel.textContent = "pin";
              if (window.__hypervisorToast) window.__hypervisorToast("unpinned");
            } else {
              addPin(relPath, pageTitle);
              pinBtn.classList.add("pinned");
              pinLabel.textContent = "unpin";
              if (window.__hypervisorToast) window.__hypervisorToast("pinned to board");
            }
            updateNavPinCount();
          });

          _currentPinBtn = pinBtn;
        }
      }

      // Render pinboard page
      if (isPinboardPage) {
        var container = document.querySelector(".pinboard-content");
        if (container) renderPinboard(container);
      }

      // Render homepage compact pins panel
      if (fragment.pageType === "home") {
        var homeMount = document.querySelector("[data-pins-home-list]");
        if (homeMount) renderHomepagePins(homeMount);
      }

      updateNavPinCount();
    }

    function updateNavPinCount() {
      var countEl = document.querySelector(".site-nav-pin-count");
      if (countEl) {
        var count = getPins().length;
        countEl.textContent = count > 0 ? count : "";
      }
    }

    // --- Render homepage compact pins panel ---
    function renderHomepagePins(container) {
      var pins = getPins().slice();
      // Recently pinned first
      pins.sort(function (a, b) { return (b.pinned || 0) - (a.pinned || 0); });

      // Update count in the panel header
      var countEl = document.querySelector("[data-pins-home-count]");
      if (countEl) countEl.textContent = pins.length ? String(pins.length) : "";

      if (!pins.length) {
        container.innerHTML =
          '<div class="pins-home-empty">' +
          'no pins yet &mdash; pin a doc from any page, or visit the ' +
          '<a href="#_pins">pinboard</a>.' +
          '</div>';
        return;
      }

      var hrefMap = {};
      if (typeof index !== "undefined" && index && index.length) {
        index.forEach(function (entry) {
          hrefMap[entry.path] = {
            href: entry.href,
            title: entry.title,
            work_id: entry.work_id,
          };
        });
      }

      var html = "";
      pins.forEach(function (pin) {
        var entry = hrefMap[pin.path];
        var href = entry ? entry.href : "#";
        var title = entry ? entry.title : pin.title;
        var workId = entry && entry.work_id ? entry.work_id : "";
        var pathParts = pin.path.split("/");
        var category = pathParts[0] || "";
        var categoryLabel = category.replace(/-/g, " ").replace(/_/g, " ");

        html += '<a class="pin-row" href="' + href + '">';
        html += '<span class="pin-row-title">' + escapeHtml(title) + '</span>';
        html += '<span class="pin-row-meta">';
        if (categoryLabel) {
          html += '<span class="pin-row-meta-category">' + escapeHtml(categoryLabel) + '</span>';
        }
        if (workId) {
          html += '<span class="pin-row-meta-workid">' + escapeHtml(workId) + '</span>';
        }
        html += '</span>';
        html += '</a>';
      });

      container.innerHTML = html;
    }

    // --- Render pinboard page content ---
    function renderPinboard(container) {
      var pins = getPins();

      if (!pins.length) {
        container.innerHTML =
          '<div class="pinboard-empty">' +
          '<i data-lucide="pin-off" class="pinboard-empty-icon"></i>' +
          '<p>no pinned documents yet</p>' +
          '<p class="pinboard-empty-hint">pin documents from any page using the <strong>pin</strong> button in the footer</p>' +
          '</div>';
        if (window.lucide) lucide.createIcons({ attrs: { "stroke-width": 1.5 } });
        return;
      }

      var hrefMap = {};
      if (typeof index !== "undefined" && index && index.length) {
        index.forEach(function (entry) {
          hrefMap[entry.path] = { href: entry.href, title: entry.title, snippet: entry.snippet, tags: entry.tags, work_id: entry.work_id };
        });
      }

      var html = '<div class="pin-grid">';
      pins.forEach(function (pin, idx) {
        var entry = hrefMap[pin.path];
        var href = entry ? entry.href : "#";
        var title = entry ? entry.title : pin.title;
        var snippet = entry && entry.snippet ? entry.snippet.substring(0, 180) : "";
        var tags = entry && entry.tags ? entry.tags : [];
        var workId = entry && entry.work_id ? entry.work_id : "";
        var pinnedDate = pin.pinned ? new Date(pin.pinned).toLocaleDateString() : "";
        var pathParts = pin.path.split("/");
        var category = pathParts[0] || "";
        var categoryLabel = category.replace(/-/g, " ").replace(/_/g, " ");

        html += '<div class="pin-card" data-pin-idx="' + idx + '" data-href="' + href + '" style="animation-delay:' + (idx * 0.06) + 's">';
        html += '<div class="pin-card-header">';
        html += '<span class="pin-card-indicator"><i data-lucide="pin" class="pin-card-pin-icon"></i></span>';
        if (categoryLabel) html += '<span class="pin-card-category">' + escapeHtml(categoryLabel) + '</span>';
        if (workId) html += '<span class="pin-card-work-id">' + escapeHtml(workId) + '</span>';
        html += '<button class="pin-card-remove" data-path="' + escapeHtml(pin.path) + '" aria-label="Unpin" data-tooltip="unpin">';
        html += '<i data-lucide="x"></i></button></div>';
        html += '<a href="' + href + '" class="pin-card-title">' + escapeHtml(title) + '</a>';
        if (snippet) html += '<p class="pin-card-snippet">' + escapeHtml(snippet) + '</p>';
        html += '<div class="pin-card-footer">';
        html += '<span class="pin-card-path">' + escapeHtml(pin.path) + '</span>';
        html += '<span class="pin-card-date">pinned ' + pinnedDate + '</span></div>';
        if (tags.length) {
          html += '<div class="pin-card-tags">';
          tags.slice(0, 5).forEach(function (tag) { html += '<span class="pin-card-tag">' + escapeHtml(tag) + '</span>'; });
          html += '</div>';
        }
        html += '</div>';
      });
      html += '</div>';

      container.innerHTML = html;
      if (window.lucide) lucide.createIcons({ attrs: { "stroke-width": 1.5 } });

      // Wire up remove buttons
      container.querySelectorAll(".pin-card-remove").forEach(function (btn) {
        btn.addEventListener("click", function (e) {
          e.preventDefault();
          e.stopPropagation();
          var path = btn.getAttribute("data-path");
          var card = btn.closest(".pin-card");
          if (card) {
            card.classList.add("pin-card-removing");
            setTimeout(function () {
              removePin(path);
              renderPinboard(container);
              updateNavPinCount();
              if (window.__hypervisorToast) window.__hypervisorToast("unpinned");
            }, 200);
          } else {
            removePin(path);
            renderPinboard(container);
            updateNavPinCount();
          }
        });
      });
    }

    function escapeHtml(str) {
      return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
    }

    // --- Expose pin count ---
    window.__hypervisorPinCount = function () { return getPins().length; };

    // Register with router lifecycle
    if (window.__router) {
      window.__router.onNavigate(teardown, init);
    }
  })();
