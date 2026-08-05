/* === Screensaver Engine: Registry, Activation & Event Handling === */

// Self-contained IIFE (WI-118 rework). Reads shared state from window.__ss
// (mutable primitives) and window.ss* (stable refs). No dependency on head's
// closure — all cross-file state flows through window.
(function () {
  "use strict";

  var $ = window.__ss;
  if (!$) {
    console.error("[screensaver] window.__ss missing — engine head failed to init.");
    return;
  }

  var animFrame = null;
  var clockInterval = null;
  var idleTimer = null;

  // ========== Public API ==========
  window.__screensaver = {
    getMode: function () { return $.currentMode; },
    setMode: function (m) {
      if (window.ssModes[m]) {
        $.currentMode = m;
        try { localStorage.setItem($.MODE_KEY, m); } catch (e) {}
        if (window.savePreference) window.savePreference($.MODE_KEY, m);
      }
    },
    getIdleTimeout: function () { return $.idleTimeout; },
    setIdleTimeout: function (ms) {
      $.idleTimeout = ms;
      try { localStorage.setItem($.IDLE_KEY, String(ms)); } catch (e) {}
      if (window.savePreference) window.savePreference($.IDLE_KEY, String(ms));
      resetIdleTimer();
    },
    getShowClock: function () { return $.showClock; },
    setShowClock: function (v) {
      $.showClock = !!v;
      try { localStorage.setItem($.CLOCK_KEY, $.showClock ? "1" : "0"); } catch (e) {}
      if (window.savePreference) window.savePreference($.CLOCK_KEY, $.showClock ? "1" : "0");
    },
    getUsePalette: function () { return $.usePalette; },
    setUsePalette: function (v) {
      $.usePalette = !!v;
      try { localStorage.setItem($.PALETTE_KEY, $.usePalette ? "1" : "0"); } catch (e) {}
      if (window.savePreference) window.savePreference($.PALETTE_KEY, $.usePalette ? "1" : "0");
    },
    getDitherPattern: function () { return $.ditherPattern; },
    setDitherPattern: function (p) {
      $.ditherPattern = p;
      try { localStorage.setItem($.DITHER_PATTERN_KEY, p); } catch (e) {}
      if (window.savePreference) window.savePreference($.DITHER_PATTERN_KEY, p);
    },
    activate: function (mode) {
      if (mode && window.ssModes[mode]) $.currentMode = mode;
      activate();
    },
    dismiss: dismiss,
    isActive: function () { return $.isActive; },
    modes: Object.keys(window.ssModes),
    preview: function (modeKey, extCtx, w, h) {
      var modes = window.ssModes;
      if (!modes[modeKey]) return;
      if (modes[modeKey].gl && modes[modeKey].preview) {
        modes[modeKey].preview(extCtx, w, h);
        return;
      }
      if (modes[modeKey].gl) {
        extCtx.fillStyle = "#000000";
        extCtx.fillRect(0, 0, w, h);
        extCtx.fillStyle = window.ssGetAccent();
        extCtx.font = "10px monospace";
        extCtx.textAlign = "center";
        extCtx.fillText("WebGL", w / 2, h / 2);
        return;
      }
      var origCtx = window.ssCtx;
      var origCanvas = window.ssCanvas;
      var proxyCanvas = { width: w, height: h };
      window.ssCtx = extCtx;
      window.ssCanvas = proxyCanvas;
      modes[modeKey].init();
      var frames = modeKey === "worm" ? 150 : modeKey === "dither" ? 30 : modeKey === "life" ? 80 : modeKey === "ferrofluid" ? 100 : 60;
      for (var i = 0; i < frames; i++) {
        modes[modeKey].draw();
      }
      window.ssCtx = origCtx;
      window.ssCanvas = origCanvas;
    }
  };

  function resize() {
    var c = $.canvas;
    c.width = window.innerWidth;
    c.height = window.innerHeight;
    // Update shared refs (mode files use ssCanvas/ssCtx)
    window.ssCanvas = c;
    window.ssCtx = c.getContext("2d");
    var m = window.ssModes[$.currentMode];
    if (m && m.resize) m.resize();
  }

  function drawFrame() {
    var m = window.ssModes[$.currentMode];
    if (m) m.draw();
    animFrame = requestAnimationFrame(drawFrame);
  }

  function updateClock() {
    var now = new Date();
    var h = String(now.getHours()).padStart(2, "0");
    var mm = String(now.getMinutes()).padStart(2, "0");
    var s = String(now.getSeconds()).padStart(2, "0");
    $.clockEl.textContent = h + ":" + mm + ":" + s;
  }

  function activate() {
    if ($.isActive) return;
    var tag = document.activeElement ? document.activeElement.tagName : "";
    if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return;

    if (!window.ssModes[$.currentMode]) $.currentMode = "particles";

    $.isActive = true;
    resize();

    var mode = window.ssModes[$.currentMode];
    if (mode && mode.gl) {
      $.canvas.style.display = "none";
      window.ssGetGLCanvas().style.display = "";
    } else {
      $.canvas.style.display = "";
      if (window.ssGLCanvas) window.ssGLCanvas.style.display = "none";
    }

    window.ssCtx.fillStyle = "#000000";
    window.ssCtx.fillRect(0, 0, window.ssCanvas.width, window.ssCanvas.height);
    if (mode) mode.init();
    $.overlay.classList.add("active");
    document.body.style.overflow = "hidden";
    document.documentElement.style.overflow = "hidden";
    $.clockEl.style.display = $.showClock ? "" : "none";
    if ($.showClock) {
      updateClock();
      clockInterval = setInterval(updateClock, 1000);
    }
    animFrame = requestAnimationFrame(drawFrame);
  }

  function dismiss() {
    if (!$.isActive) return;
    $.isActive = false;
    var m = window.ssModes[$.currentMode];
    if (m && m.cleanup) m.cleanup();
    $.overlay.classList.remove("active");
    document.body.style.overflow = "";
    document.documentElement.style.overflow = "";
    if (animFrame) { cancelAnimationFrame(animFrame); animFrame = null; }
    if (clockInterval) { clearInterval(clockInterval); clockInterval = null; }
    if (window.ssGLCanvas) window.ssGLCanvas.style.display = "none";
    $.canvas.style.display = "";
    resetIdleTimer();
  }

  function resetIdleTimer() {
    if (idleTimer) clearTimeout(idleTimer);
    if ($.idleTimeout > 0) {
      idleTimer = setTimeout(activate, $.idleTimeout);
    }
  }

  // Dismiss on click or keypress
  var justDismissed = false;
  var dismissEvents = ["mousedown", "keydown", "touchstart"];
  dismissEvents.forEach(function (evt) {
    document.addEventListener(evt, function (e) {
      if ($.isActive) {
        e.preventDefault();
        justDismissed = true;
        dismiss();
        setTimeout(function () { justDismissed = false; }, 0);
        return;
      }
      resetIdleTimer();
    }, true);
  });

  // Track mouse position for interactive modes (shared state)
  $.overlay.addEventListener("mousemove", function (e) {
    var ms = window.ssMouseState;
    ms.prevX = ms.x; ms.prevY = ms.y;
    ms.x = e.clientX; ms.y = e.clientY;
    if (window.ssParticleState) {
      window.ssParticleState.mouseX = e.clientX;
      window.ssParticleState.mouseY = e.clientY;
    }
  });
  $.overlay.addEventListener("mouseleave", function () {
    var ms = window.ssMouseState;
    ms.prevX = ms.x; ms.prevY = ms.y;
    ms.x = -1; ms.y = -1;
    if (window.ssParticleState) {
      window.ssParticleState.mouseX = -1;
      window.ssParticleState.mouseY = -1;
    }
  });

  // Reset idle timer on movement/scroll
  ["mousemove", "scroll"].forEach(function (evt) {
    document.addEventListener(evt, function () {
      if (!$.isActive) resetIdleTimer();
    }, true);
  });

  // Keyboard shortcut: s to launch
  document.addEventListener("keydown", function (e) {
    if (justDismissed) return;
    if (e.key === "s" &&
        document.activeElement.tagName !== "INPUT" &&
        document.activeElement.tagName !== "TEXTAREA") {
      activate();
    }
  });

  window.addEventListener("resize", function () {
    if ($.isActive) resize();
  });

  if (document.documentElement.classList.contains("a11y-reduce-motion")) {
    $.idleTimeout = 0;
  }

  resetIdleTimer();
})();
