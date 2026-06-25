/* === Hypervisor: Tabbed Document Interface === */

  (function () {
    var STORAGE_KEY = "hv_tabs";
    var tabs = [];
    var activeTabId = null;
    var tabBar = null;
    var tabIdCounter = 0;

    // --- DOM Setup ---
    var highlight = null;

    function createTabBar() {
      tabBar = document.createElement("div");
      tabBar.className = "tab-bar";
      tabBar.setAttribute("role", "tablist");
      // Sliding highlight
      highlight = document.createElement("div");
      highlight.className = "tab-highlight";
      tabBar.appendChild(highlight);
      // Insert after topbar
      var topbar = document.querySelector(".topbar");
      if (topbar && topbar.nextSibling) {
        topbar.parentNode.insertBefore(tabBar, topbar.nextSibling);
      } else {
        document.body.prepend(tabBar);
      }
    }

    // --- Tab CRUD ---
    function genId() { return "tab-" + (++tabIdCounter); }

    function createTab(path, title, fragment, activate) {
      var tab = { id: genId(), path: path, title: title, fragment: fragment, scrollPos: 0, stale: false };
      tabs.push(tab);
      if (activate !== false) switchTab(tab.id);
      renderTabs();
      persist();
      return tab;
    }

    function closeTab(id) {
      if (tabs.length <= 1) return;
      var idx = tabs.findIndex(function (t) { return t.id === id; });
      if (idx === -1) return;
      tabs.splice(idx, 1);
      if (activeTabId === id) {
        var next = tabs[Math.min(idx, tabs.length - 1)];
        switchTab(next.id);
      }
      renderTabs();
      persist();
    }

    function switchTab(id) {
      // Save scroll position of current tab
      var current = getTab(activeTabId);
      if (current) current.scrollPos = window.scrollY;

      activeTabId = id;
      var tab = getTab(id);
      if (!tab) return;

      // Clear stale flag
      tab.stale = false;

      // Apply cached fragment if available — with crossfade
      if (tab.fragment && window.__router) {
        var content = document.getElementById("content-target");
        if (content) {
          content.classList.add("tab-fade-out");
          setTimeout(function () {
            window.__router.applyFragment(tab.fragment, false, null);
            content.classList.remove("tab-fade-out");
            content.classList.add("tab-fade-in");
            setTimeout(function () { content.classList.remove("tab-fade-in"); }, 120);
            // Restore scroll
            window.scrollTo(0, tab.scrollPos || 0);
          }, 80);
        } else {
          window.__router.applyFragment(tab.fragment, false, null);
          setTimeout(function () { window.scrollTo(0, tab.scrollPos || 0); }, 10);
        }
        // Push state so URL reflects the tab
        history.replaceState({ path: tab.path }, "", tab.path);
      }
      renderTabs();
    }

    function getTab(id) {
      return tabs.find(function (t) { return t.id === id; }) || null;
    }

    function getActiveTab() { return getTab(activeTabId); }

    // --- Rendering ---
    function renderTabs() {
      if (!tabBar) return;
      // Show/hide based on tab count
      tabBar.classList.toggle("visible", tabs.length > 1);

      // Remove old tab items (keep highlight)
      var old = tabBar.querySelectorAll(".tab-item");
      old.forEach(function (el) { el.remove(); });

      tabs.forEach(function (tab) {
        var el = document.createElement("div");
        el.className = "tab-item" + (tab.id === activeTabId ? " active" : "") + (tab.stale ? " tab-stale" : "");
        el.setAttribute("role", "tab");
        el.setAttribute("aria-selected", tab.id === activeTabId ? "true" : "false");
        el.setAttribute("title", tab.title || tab.path);
        el.setAttribute("data-tab-id", tab.id);

        var title = document.createElement("span");
        title.className = "tab-title";
        title.textContent = tab.title || tab.path;
        el.appendChild(title);

        var close = document.createElement("button");
        close.className = "tab-close";
        close.setAttribute("aria-label", "Close tab");
        close.textContent = "\u00d7";
        close.addEventListener("click", function (e) {
          e.stopPropagation();
          closeTab(tab.id);
        });
        el.appendChild(close);

        el.addEventListener("click", function () {
          if (tab.id !== activeTabId) switchTab(tab.id);
        });

        tabBar.appendChild(el);
      });

      positionHighlight();
    }

    function positionHighlight() {
      if (!highlight || !tabBar) return;
      var active = tabBar.querySelector(".tab-item.active");
      if (active) {
        var barRect = tabBar.getBoundingClientRect();
        var tabRect = active.getBoundingClientRect();
        highlight.style.setProperty("--tab-hl-left", (tabRect.left - barRect.left + tabBar.scrollLeft) + "px");
        highlight.style.setProperty("--tab-hl-width", tabRect.width + "px");
      } else {
        highlight.style.setProperty("--tab-hl-width", "0");
      }
    }

    // --- Persistence ---
    function persist() {
      var data = tabs.map(function (t) { return { path: t.path, title: t.title }; });
      var json = JSON.stringify({ tabs: data, activeIndex: tabs.findIndex(function (t) { return t.id === activeTabId; }) });
      try { localStorage.setItem(STORAGE_KEY, json); } catch (e) {}
      if (typeof savePreference === "function") {
        savePreference(STORAGE_KEY, json);
      }
    }

    function restore() {
      var raw = null;
      try { raw = localStorage.getItem(STORAGE_KEY); } catch (e) {}
      if (!raw) return false;
      try {
        var data = JSON.parse(raw);
        if (!data.tabs || !data.tabs.length) return false;
        data.tabs.forEach(function (t) {
          tabs.push({ id: genId(), path: t.path, title: t.title, fragment: null, scrollPos: 0, stale: false });
        });
        var activeIdx = data.activeIndex || 0;
        if (activeIdx >= tabs.length) activeIdx = 0;
        activeTabId = tabs[activeIdx].id;
        return true;
      } catch (e) { return false; }
    }

    // --- Restore fragments from server ---
    function fetchTabFragments() {
      tabs.forEach(function (tab) {
        if (tab.fragment) return; // already loaded
        var fragPath = resolveFragmentPathForTabs(tab.path);
        fetch(fragPath).then(function (res) {
          if (!res.ok) return null;
          return res.json();
        }).then(function (frag) {
          if (frag) {
            tab.fragment = frag;
            tab.title = frag.title || tab.title;
            // If this is the active tab, apply it
            if (tab.id === activeTabId) {
              window.__router.applyFragment(frag, false, null);
              history.replaceState({ path: tab.path }, "", tab.path);
            }
            renderTabs();
          }
        }).catch(function () {});
      });
    }

    function resolveFragmentPathForTabs(pathname) {
      var path = pathname.replace(/\/index\.html$/, "").replace(/\/$/, "");
      if (!path || path === "") return "/content/home.json";
      var clean = path.replace(/^\//, "");
      return "/content/" + clean + ".json";
    }

    // --- Stale tab marking (called by live-reload) ---
    function markStale(updatedPath) {
      var changed = false;
      tabs.forEach(function (tab) {
        if (tab.id !== activeTabId && tab.path === updatedPath) {
          tab.stale = true;
          tab.fragment = null; // force re-fetch on switch
          changed = true;
        }
      });
      if (changed) renderTabs();
    }

    function markAllStale() {
      tabs.forEach(function (tab) {
        if (tab.id !== activeTabId) {
          tab.stale = true;
          tab.fragment = null;
        }
      });
      renderTabs();
    }

    // --- Router integration: update active tab on navigation ---
    function onRouterNavigate(fragment) {
      var tab = getActiveTab();
      if (!tab) return;
      tab.fragment = fragment;
      tab.path = window.location.pathname;
      tab.title = fragment.title || tab.title;
      renderTabs();
      persist();
    }

    // --- Open in new tab (public API) ---
    function openInTab(url) {
      // Parse path
      var a = document.createElement("a");
      a.href = url;
      var pathname = a.pathname;

      // Don't duplicate if already open — switch to it
      var existing = tabs.find(function (t) { return t.path === pathname; });
      if (existing) {
        switchTab(existing.id);
        return;
      }

      // Fetch fragment then create tab
      var fragPath = resolveFragmentPathForTabs(pathname);
      fetch(fragPath).then(function (res) {
        if (!res.ok) return null;
        return res.json();
      }).then(function (frag) {
        if (frag) {
          createTab(pathname, frag.title || pathname, frag, true);
        }
      }).catch(function () {});
    }

    // --- Keyboard shortcut: Ctrl+F4 ---
    document.addEventListener("keydown", function (e) {
      if (e.ctrlKey && e.key === "F4") {
        e.preventDefault();
        if (tabs.length > 1) closeTab(activeTabId);
      }
    });

    // --- Init ---
    function init() {
      createTabBar();

      var restored = restore();
      if (!restored) {
        // Create initial tab from current page
        var path = window.location.pathname;
        var frag = window.__router ? window.__router.getCurrentFragment() : null;
        var title = frag ? frag.title : document.title.replace(" — Hypervisor", "");
        tabs.push({ id: genId(), path: path, title: title, fragment: frag, scrollPos: 0, stale: false });
        activeTabId = tabs[0].id;
      }

      renderTabs();

      if (restored) fetchTabFragments();

      // Listen to router navigations to keep active tab in sync
      if (window.__router) {
        window.__router.onNavigate(null, onRouterNavigate);
      }

      // Listen for routeChanged for fragment updates
      window.addEventListener("routeChanged", function (e) {
        var tab = getActiveTab();
        if (tab && e.detail) {
          tab.fragment = e.detail;
          tab.path = window.location.pathname;
          tab.title = e.detail.title || tab.title;
          persist();
          renderTabs();
        }
      });
    }

    // --- Public API ---
    window.__tabs = {
      openInTab: openInTab,
      markStale: markStale,
      markAllStale: markAllStale,
      getActiveTab: getActiveTab,
      getTabs: function () { return tabs; }
    };

    // --- Expose applyFragment publicly for tab switching ---
    // The router wraps applyFragment in its own IIFE — we need access.
    // We'll hook via a routeChanged event listener + direct navigate for tab switch.
    // Patch switchTab to use navigate for tabs without cached fragments:
    var _origSwitchTab = switchTab;
    switchTab = function (id) {
      var tab = getTab(id);
      if (tab && !tab.fragment && window.__router) {
        // No cached fragment — need to fetch
        activeTabId = id;
        var current = getTab(activeTabId);
        // save prev scroll
        var prev = tabs.find(function (t) { return t.id !== id && t.id === activeTabId; });
        window.__router.navigate(tab.path, false);
        renderTabs();
        persist();
        return;
      }
      _origSwitchTab(id);
    };

    // Boot after DOM ready
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", init);
    } else {
      init();
    }

    // Desktop app: re-check for restored tabs after preferences are loaded from disk
    // (applyLoadedPreferences seeds localStorage from preferences.json)
    window.addEventListener("pywebviewready", function () {
      if (tabs.length <= 1) {
        var raw = null;
        try { raw = localStorage.getItem(STORAGE_KEY); } catch (e) {}
        if (raw) {
          tabs.length = 0;
          tabIdCounter = 0;
          activeTabId = null;
          if (restore()) {
            renderTabs();
            fetchTabFragments();
          }
        }
      }
    });
  })();
