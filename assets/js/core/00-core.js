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
        if (window.__hypervisorToast) window.__hypervisorToast({ variant: "success", message: "theme preferences are saved" });
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

  // --- Toast notifications (WI-115 variant-aware primitive) ---
  // Shared cross-app IIFE — byte-identical to `.hyperagent/assets/js/00-core.js`
  // modulo this header comment. See `.hyperspace/work/to-do/hyper-ecosystem-toast-rework.md`.
  //
  //   HvToast.show("plain message")                    → info variant, 3s
  //   HvToast.show({ variant, title, message, icon,
  //                  duration, action, dedupeKey })    → full options
  //
  //   variant:   'success' | 'info' | 'warn' | 'error'   (default: 'info')
  //   duration:  ms number | 'sticky'                    (variant defaults apply)
  //   action:    { label: string, onClick: () => void }  (adds inline button)
  //   dedupeKey: string — replaces prior toast with same key (rebuild spam guard)
  //
  // Also exposed as `window.__hypervisorToast` for the Python bridge and legacy
  // call sites. Both signatures (string or options) flow through the same code path.
  (function initToasts() {
    if (window.HvToast) return; // idempotent

    var container = document.createElement("div");
    container.className = "hv-toast-container";
    container.setAttribute("aria-live", "polite");
    container.setAttribute("aria-atomic", "false");
    function attach() { document.body.appendChild(container); }
    if (document.body) attach();
    else document.addEventListener("DOMContentLoaded", attach);

    var VARIANTS = {
      success: { icon: "check-circle",   duration: 3000,     assertive: false },
      info:    { icon: "info",           duration: 3000,     assertive: false },
      warn:    { icon: "alert-triangle", duration: 5000,     assertive: true  },
      error:   { icon: "circle-x",       duration: "sticky", assertive: true  }
    };
    var MAX_VISIBLE = 5;
    var EXIT_MS = 300;
    var visible = [];       // ordered oldest → newest
    var dedupeMap = {};     // key → toast element

    function normalize(input) {
      if (typeof input === "string") return { variant: "info", message: input };
      if (!input || typeof input !== "object") return { variant: "info", message: String(input) };
      return input;
    }

    function dismiss(toast) {
      if (!toast || toast.__dismissed) return;
      toast.__dismissed = true;
      if (toast.__timer) clearTimeout(toast.__timer);
      toast.classList.remove("hv-toast-visible");
      toast.classList.add("hv-toast-exit");
      var idx = visible.indexOf(toast);
      if (idx >= 0) visible.splice(idx, 1);
      if (toast.__dedupeKey && dedupeMap[toast.__dedupeKey] === toast) {
        delete dedupeMap[toast.__dedupeKey];
      }
      setTimeout(function () {
        if (toast.parentNode) toast.parentNode.removeChild(toast);
      }, EXIT_MS);
    }

    function show(input) {
      var opts = normalize(input);
      var variant = VARIANTS[opts.variant] ? opts.variant : "info";
      var defaults = VARIANTS[variant];
      var icon = opts.icon || defaults.icon;
      var duration = opts.duration != null ? opts.duration : defaults.duration;
      var sticky = duration === "sticky";
      var message = opts.message == null ? "" : String(opts.message);
      var title = opts.title ? String(opts.title) : "";
      var action = opts.action && opts.action.label && typeof opts.action.onClick === "function" ? opts.action : null;
      var dedupeKey = opts.dedupeKey || null;

      if (dedupeKey && dedupeMap[dedupeKey]) dismiss(dedupeMap[dedupeKey]);

      var toast = document.createElement("div");
      toast.className = "hv-toast hv-toast-" + variant;
      if (defaults.assertive) toast.setAttribute("role", "alert");
      toast.__dedupeKey = dedupeKey;

      var iconEl = document.createElement("i");
      iconEl.className = "hv-toast-icon";
      iconEl.setAttribute("data-lucide", icon);
      toast.appendChild(iconEl);

      var body = document.createElement("div");
      body.className = "hv-toast-body";
      if (title) {
        var titleEl = document.createElement("div");
        titleEl.className = "hv-toast-title";
        titleEl.textContent = title;
        body.appendChild(titleEl);
      }
      var msgEl = document.createElement("div");
      msgEl.className = "hv-toast-message";
      msgEl.textContent = message;
      body.appendChild(msgEl);
      if (action) {
        var actionBtn = document.createElement("button");
        actionBtn.className = "hv-button hv-button-ghost hv-toast-action";
        actionBtn.type = "button";
        actionBtn.textContent = action.label;
        actionBtn.addEventListener("click", function () {
          try { action.onClick(); } catch (e) {}
          dismiss(toast);
        });
        body.appendChild(actionBtn);
      }
      toast.appendChild(body);

      if (sticky || action) {
        var closeBtn = document.createElement("button");
        closeBtn.className = "hv-toast-close";
        closeBtn.type = "button";
        closeBtn.setAttribute("aria-label", "Dismiss notification");
        closeBtn.textContent = "\u00d7";
        closeBtn.addEventListener("click", function () { dismiss(toast); });
        toast.appendChild(closeBtn);
      }

      container.appendChild(toast);
      visible.push(toast);
      if (dedupeKey) dedupeMap[dedupeKey] = toast;

      while (visible.length > MAX_VISIBLE) dismiss(visible[0]);

      if (window.lucide && typeof window.lucide.createIcons === "function") {
        try { window.lucide.createIcons(); } catch (e) {}
      }

      requestAnimationFrame(function () { toast.classList.add("hv-toast-visible"); });

      if (!sticky) {
        toast.__timer = setTimeout(function () { dismiss(toast); }, duration);
      }

      return { dismiss: function () { dismiss(toast); } };
    }

    // Recover pending notification from a live-reload (Hypervisor-only path;
    // no-op in Hyperagent where nothing writes this key).
    try {
      var pending = sessionStorage.getItem("__hv_notify");
      if (pending) {
        sessionStorage.removeItem("__hv_notify");
        show(pending);
      }
    } catch (e) {}

    window.HvToast = { show: show, dismiss: dismiss };
    window.__hypervisorToast = show;  // legacy alias — accepts string or options
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
