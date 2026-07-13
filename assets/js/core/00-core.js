/* === Hypervisor: Core (bridge, preferences, toasts) === */
/* Hypervisor — polished component-feel interactions */

(function () {
  "use strict";

  // --- PyWebView bridge detection ---
  // PyWebView injects window.pywebview asynchronously AFTER DOMContentLoaded.
  // We can't check it at parse time. Instead, use a mutable flag that gets
  // set when the "pywebviewready" event fires, and defer desktop-only init
  // to that event.
  var isDesktopApp = false;

  // --- Persistent preferences (desktop app) ---
  // Single source of truth: preferences.json on disk.
  // localStorage is an expendable cache — losing it is fine, prefs.json has the truth.
  // One load on init, direct writes via bridge after that. No queue, no coordination.

  function savePreference(key, value) {
    try { localStorage.setItem(key, value); } catch (e) {}
    if (isDesktopApp && window.pywebview && window.pywebview.api) {
      try { window.pywebview.api.save_preference(key, value); } catch (e) {}
    }
  }

  function initDesktopFeatures() {
    isDesktopApp = true;
    document.body.classList.add("hv-desktop");
    var api = window.pywebview.api;

    // --- Single load: get all prefs (flat keys + userGradientMaps) ---
    try {
      var prefs = api.load_preferences();
      if (prefs && typeof prefs.then === "function") {
        prefs.then(function (data) { applyAllPreferences(data); });
      } else if (prefs && typeof prefs === "object") {
        applyAllPreferences(prefs);
      }
    } catch (e) {
      // Bridge failed — dismiss splash after safety timeout
    }

    // --- Show and wire fullscreen toggle ---
    var fsBtn = document.getElementById("fullscreen-toggle");
    var fsRow = document.getElementById("fullscreen-row");
    if (fsRow) fsRow.style.display = "";

    var fsShortcutRow = document.getElementById("shortcut-fullscreen");
    if (fsShortcutRow) fsShortcutRow.style.display = "";

    var fsIsFullscreen = false;
    function toggleFullscreen() {
      api.toggle_fullscreen();
      fsIsFullscreen = !fsIsFullscreen;
      var icon = document.getElementById("fullscreen-toggle-icon");
      if (icon) {
        icon.setAttribute("data-lucide", fsIsFullscreen ? "minimize" : "maximize");
        if (window.lucide) lucide.createIcons({ attrs: { "stroke-width": 1.5 } });
      }
    }
    if (fsBtn) {
      fsBtn.addEventListener("click", toggleFullscreen);
    }
    document.addEventListener("keydown", function (e) {
      if (e.key === "F11" || (e.key === "f" && document.activeElement !== searchInput && !document.activeElement.closest("input, textarea, [contenteditable]"))) {
        e.preventDefault();
        toggleFullscreen();
      }
    });

    // --- Show and wire rebuild button ---
    var rebuildRow = document.getElementById("rebuild-row");
    var rebuildBtn = document.getElementById("rebuild-btn");
    if (rebuildRow) rebuildRow.style.display = "";
    if (rebuildBtn) {
      rebuildBtn.addEventListener("click", function () {
        var icon = document.getElementById("rebuild-btn-icon");
        if (icon) icon.style.animation = "spin 0.6s linear infinite";
        // Clear splash flag so it re-appears after a hard rebuild
        try { sessionStorage.removeItem("__hv_splash_seen"); } catch (e) {}
        api.rebuild().then(function () {
          if (icon) icon.style.animation = "";
        });
      });
    }

    // --- Show and wire save-theme-as-default button ---
    var saveThemeRow = document.getElementById("save-theme-row");
    var saveThemeBtn = document.getElementById("save-theme-btn");
    if (saveThemeRow) saveThemeRow.style.display = "";

    // --- Show and wire Hyperagent launch button ---
    var haBtn = document.getElementById("hyperagent-btn");
    if (haBtn) {
      haBtn.style.display = "";
      haBtn.addEventListener("click", function () {
        api.launch_hyperagent();
      });
    }
    // --- Show and wire Launch Dev button ---
    var ldBtn = document.getElementById("launch-dev-btn");
    if (ldBtn) {
      ldBtn.style.display = "";
      ldBtn.addEventListener("click", function () {
        api.launch_dev("full");
      });
    }
    if (saveThemeBtn) {
      saveThemeBtn.addEventListener("click", function () {
        // Theme state is already persisted to preferences.json on every change.
        // This button is just a reassurance UX element now.
        if (window.__hypervisorToast) window.__hypervisorToast("theme preferences are saved");
      });
    }

    // --- Show and wire new-window button ---
    var newWinBtn = document.getElementById("new-window-btn");
    if (newWinBtn) {
      newWinBtn.style.display = "";
      newWinBtn.addEventListener("click", function () {
        var path = window.location.pathname || "/index.html";
        api.open_in_new_window(path);
      });
    }
  }

  // --- Apply all preferences from the single load_preferences() payload ---
  function applyAllPreferences(data) {
    if (!data || typeof data !== "object") {
      if (window.__dismissSplash) window.__dismissSplash();
      return;
    }

    // Seed localStorage as an expendable cache (other modules may read it)
    Object.keys(data).forEach(function (k) {
      if (k === "hypervisor-pins") return;       // pins.js has merge logic
      if (k === "userGradientMaps") return;      // nested object, not a flat string
      if (typeof data[k] === "string" || typeof data[k] === "number" || typeof data[k] === "boolean") {
        try { localStorage.setItem(k, data[k]); } catch (e) {}
      }
    });

    // --- Theme: palette mode, accent, gradient map ---
    if (data["hypervisor-palette-mode"]) {
      paletteMode = data["hypervisor-palette-mode"];
    }
    var accentHex = data["hypervisor-accent"];
    var cp = document.getElementById("accent-color");
    if (accentHex) {
      if (cp) cp.value = accentHex;
    } else {
      accentHex = (cp && cp.value) || "#00ff41";
    }

    // Inject user gradient maps into theme module BEFORE applying preset
    var userMaps = data["userGradientMaps"];
    if (userMaps && typeof userMaps === "object" && typeof window.__setUserGradientMaps === "function") {
      window.__setUserGradientMaps(userMaps);
    }

    // Apply gradient map preset or custom accent
    var loadedThemeMode = data["hypervisor-theme-mode"];
    var loadedGradientMap = data["hypervisor-gradient-map"];
    if (loadedThemeMode === "preset" && loadedGradientMap && typeof applyGradientMap === "function") {
      applyGradientMap(loadedGradientMap);
    } else {
      applyAccent(accentHex);
    }

    // Update UI controls
    if (typeof populatePresetSelect === "function") populatePresetSelect();
    if (typeof updatePresetSelector === "function") updatePresetSelector();
    if (typeof updateModeButton === "function") updateModeButton();

    // --- Screensaver ---
    if (window.__screensaver) {
      if (data["hypervisor-screensaver-mode"]) {
        window.__screensaver.setMode(data["hypervisor-screensaver-mode"]);
      }
      if (data["hypervisor-screensaver-palette"] === "1") {
        window.__screensaver.setUsePalette(true);
      } else if (data["hypervisor-screensaver-palette"] === "0") {
        window.__screensaver.setUsePalette(false);
      }
      if (data["hypervisor-screensaver-clock"] === "0") {
        window.__screensaver.setShowClock(false);
      } else if (data["hypervisor-screensaver-clock"] === "1") {
        window.__screensaver.setShowClock(true);
      }
      if (data["hypervisor-screensaver-idle"]) {
        var idle = parseInt(data["hypervisor-screensaver-idle"], 10);
        if (!isNaN(idle) && idle >= 0) {
          window.__screensaver.setIdleTimeout(idle);
        }
      }
    }

    // --- Zoom ---
    if (data["hypervisor-zoom"]) {
      var z = parseInt(data["hypervisor-zoom"], 10);
      if (z >= 50 && z <= 200) {
        var zLabel = document.getElementById("zoom-level");
        var zIn = document.getElementById("zoom-in");
        var zOut = document.getElementById("zoom-out");
        var zBase = 14;
        document.documentElement.style.fontSize = (zBase * z / 100) + "px";
        if (zLabel) zLabel.textContent = z + "%";
        if (zIn) zIn.classList.toggle("active", z > 100);
        if (zOut) zOut.classList.toggle("active", z < 100);
      }
    }

    // --- Done: dismiss splash ---
    if (window.__dismissSplash) window.__dismissSplash();
  }

  // Listen for the pywebview bridge to become available
  window.addEventListener("pywebviewready", function () {
    initDesktopFeatures();
  });

  // --- Scroll position preservation ---
  // No longer needed — SPA router preserves scroll naturally.
  // Left as a no-op for any code that references __hv_scroll.

  // --- Reload helper for desktop app ---
  // The Python process calls this to reload content via the SPA router.
  window.__hypervisorReload = function () {
    // Mark inactive tabs as stale before reloading active tab
    if (window.__tabs) window.__tabs.markAllStale();
    if (window.__router) {
      window.__router.reload();
    } else {
      // Fallback: full page reload if router not ready
      window.location.reload();
    }
  };

  // --- Toast notifications (desktop app) ---
  // Shows a brief notification after a file-change rebuild.
  // The message is stashed in sessionStorage before reload and rendered after.
  (function initToasts() {
    var container = document.createElement("div");
    container.className = "hv-toast-container";
    container.setAttribute("aria-live", "polite");
    // Fixed bottom-right — append to body
    document.body.appendChild(container);

    // Check for a pending notification from before the reload
    try {
      var msg = sessionStorage.getItem("__hv_notify");
      if (msg) {
        sessionStorage.removeItem("__hv_notify");
        showToast(msg);
      }
    } catch (e) {}

    // Expose globally so Python bridge can also push toasts without reload
    window.__hypervisorToast = showToast;

    function showToast(message) {
      var toast = document.createElement("div");
      toast.className = "hv-toast";
      toast.textContent = message;
      container.appendChild(toast);

      // Trigger enter animation on next frame
      requestAnimationFrame(function () {
        toast.classList.add("hv-toast-visible");
      });

      // Auto-dismiss after 3 seconds
      setTimeout(function () {
        toast.classList.remove("hv-toast-visible");
        toast.classList.add("hv-toast-exit");
        // Remove from DOM after exit animation
        setTimeout(function () {
          if (toast.parentNode) toast.parentNode.removeChild(toast);
        }, 300);
      }, 3000);
    }
  })();

  // --- Custom confirm dialog ---
  // Replaces native window.confirm with a styled modal that matches the terminal aesthetic.
  // Usage: window.__hypervisorConfirm("message", { danger: true }).then(ok => { ... })
  (function initConfirm() {
    window.__hypervisorConfirm = function (message, opts) {
      opts = opts || {};
      return new Promise(function (resolve) {
        var overlay = document.createElement("div");
        overlay.className = "hv-confirm-overlay";

        var box = document.createElement("div");
        box.className = "hv-confirm-box";

        var msg = document.createElement("div");
        msg.className = "hv-confirm-message";
        msg.textContent = message;

        var actions = document.createElement("div");
        actions.className = "hv-confirm-actions";

        var cancelBtn = document.createElement("button");
        cancelBtn.className = "hv-confirm-btn";
        cancelBtn.textContent = opts.cancelLabel || "cancel";

        var confirmBtn = document.createElement("button");
        confirmBtn.className = "hv-confirm-btn" + (opts.danger ? " hv-confirm-btn-danger" : "");
        confirmBtn.textContent = opts.confirmLabel || "confirm";

        actions.appendChild(cancelBtn);
        actions.appendChild(confirmBtn);
        box.appendChild(msg);
        box.appendChild(actions);
        overlay.appendChild(box);
        document.body.appendChild(overlay);

        // Animate in
        requestAnimationFrame(function () {
          overlay.classList.add("visible");
        });

        function dismiss(result) {
          overlay.classList.remove("visible");
          setTimeout(function () {
            if (overlay.parentNode) overlay.parentNode.removeChild(overlay);
          }, 150);
          resolve(result);
        }

        cancelBtn.addEventListener("click", function () { dismiss(false); });
        confirmBtn.addEventListener("click", function () { dismiss(true); });
        overlay.addEventListener("click", function (e) {
          if (e.target === overlay) dismiss(false);
        });

        // Keyboard support
        function onKey(e) {
          if (e.key === "Escape") { dismiss(false); document.removeEventListener("keydown", onKey); }
          if (e.key === "Enter") { dismiss(true); document.removeEventListener("keydown", onKey); }
        }
        document.addEventListener("keydown", onKey);

        confirmBtn.focus();
      });
    };
  })();

  // --- Initialize Lucide icons ---
  if (window.lucide) {
    lucide.createIcons({
      attrs: { 'stroke-width': 1.5 }
    });
  }

  // --- Activate custom cursors (body starts as cursor:none to prevent flicker) ---
  if (!document.documentElement.classList.contains("a11y-system-cursors")) {
    document.body.classList.add("a11y-cursors-active");
  }

  // Re-check after a11y restore (the a11y init runs later and may add the class)
  // This is handled in the a11y init itself via the restore loop.

  var searchInput = document.getElementById("search");
  var resultsBox = document.getElementById("search-results");
  var scrollBtn = document.getElementById("scroll-top");
  var topbar = document.querySelector(".topbar");
  var index = [];
  var selectedIdx = -1;

  // Load search index from external JSON file
  fetch("/search-index.json").then(function (res) {
    if (!res.ok) return;
    return res.json();
  }).then(function (data) {
    if (data && Array.isArray(data)) {
      index = data;
      // Fire a custom event so other modules know the index is ready
      window.dispatchEvent(new CustomEvent("searchIndexReady"));
    }
  }).catch(function () {});
