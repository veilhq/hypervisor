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
  // In PyWebView, localStorage is tied to an ephemeral origin that changes
  // between launches. Bridge preferences from a JSON file on disk into
  // localStorage so the accent color and palette mode survive restarts.
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

    // --- Seed localStorage from disk-backed preferences ---
    try {
      var prefs = api.load_preferences();
      if (prefs && typeof prefs.then === "function") {
        prefs.then(function (data) { applyLoadedPreferences(data); });
      } else if (prefs && typeof prefs === "object") {
        applyLoadedPreferences(prefs);
      }
    } catch (e) {}

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
        api.launch_dev();
      });
    }
    if (saveThemeBtn) {
      saveThemeBtn.addEventListener("click", function () {
        var accent = (document.getElementById("accent-color") || {}).value || "#00ff41";
        var bwToggle = document.getElementById("a11y-bw-theme");
        var bwTheme = bwToggle ? bwToggle.checked : false;
        api.save_theme_defaults(accent, paletteMode, bwTheme).then(function () {
          if (window.__hypervisorToast) window.__hypervisorToast("theme defaults saved");
        });
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

  function applyLoadedPreferences(data) {
    if (!data || typeof data !== "object") return;
    Object.keys(data).forEach(function (k) {
      // Skip pins — handled by pins.js with merge logic to avoid data loss
      if (k === "hypervisor-pins") return;
      try { localStorage.setItem(k, data[k]); } catch (e) {}
    });
    // Re-apply accent color and palette mode if they were loaded.
    // Palette mode must be set before applyAccent so the palette is built
    // with the correct mode. Always call applyAccent at the end so CSS
    // variables update even when only the palette mode changed.
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
    applyAccent(accentHex);
    // Update palette mode button label and tooltip
    if (typeof updateModeButton === "function") {
      updateModeButton();
    } else {
      var mt = document.getElementById("palette-mode");
      if (mt) mt.textContent = (PALETTE_LABELS && PALETTE_LABELS[paletteMode]) || "SPL";
    }
    // Re-apply screensaver preferences (mode, palette, clock, idle)
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
