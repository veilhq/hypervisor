/* === Screensaver Engine: Registry, Activation & Event Handling === */

    // ========== Public API & Lifecycle ==========

    // Expose for the utility page
    window.__screensaver = {
      getMode: function () { return currentMode; },
      setMode: function (m) {
        if (ssModes[m]) {
          currentMode = m;
          try { localStorage.setItem(MODE_KEY, m); } catch (e) {}
          savePreference(MODE_KEY, m);
        }
      },
      getIdleTimeout: function () { return idleTimeout; },
      setIdleTimeout: function (ms) {
        idleTimeout = ms;
        try { localStorage.setItem(IDLE_KEY, String(ms)); } catch (e) {}
        savePreference(IDLE_KEY, String(ms));
        resetIdleTimer();
      },
      getShowClock: function () { return showClock; },
      setShowClock: function (v) {
        showClock = !!v;
        try { localStorage.setItem(CLOCK_KEY, showClock ? "1" : "0"); } catch (e) {}
        savePreference(CLOCK_KEY, showClock ? "1" : "0");
      },
      getUsePalette: function () { return usePalette; },
      setUsePalette: function (v) {
        usePalette = !!v;
        try { localStorage.setItem(PALETTE_KEY, usePalette ? "1" : "0"); } catch (e) {}
        savePreference(PALETTE_KEY, usePalette ? "1" : "0");
      },
      getDitherPattern: function () { return ditherPattern; },
      setDitherPattern: function (p) {
        ditherPattern = p;
        try { localStorage.setItem(DITHER_PATTERN_KEY, p); } catch (e) {}
        savePreference(DITHER_PATTERN_KEY, p);
      },
      activate: function (mode) {
        if (mode && ssModes[mode]) currentMode = mode;
        activate();
      },
      dismiss: dismiss,
      isActive: function () { return isActive; },
      modes: Object.keys(ssModes),
      preview: function (modeKey, extCtx, w, h) {
        if (!ssModes[modeKey]) return;
        // WebGL modes provide their own preview method
        if (ssModes[modeKey].gl && ssModes[modeKey].preview) {
          ssModes[modeKey].preview(extCtx, w, h);
          return;
        }
        // Fallback for GL modes without a preview method
        if (ssModes[modeKey].gl) {
          extCtx.fillStyle = "#000000";
          extCtx.fillRect(0, 0, w, h);
          extCtx.fillStyle = getAccentColor();
          extCtx.font = "10px monospace";
          extCtx.textAlign = "center";
          extCtx.fillText("WebGL", w / 2, h / 2);
          return;
        }
        var origCtx = ssCtx;
        var origCanvas = ssCanvas;
        var proxyCanvas = { width: w, height: h };
        ssCtx = extCtx;
        ssCanvas = proxyCanvas;
        ssModes[modeKey].init();
        var frames = modeKey === "worm" ? 150 : modeKey === "dither" ? 30 : modeKey === "life" ? 80 : modeKey === "ferrofluid" ? 100 : 60;
        for (var i = 0; i < frames; i++) {
          ssModes[modeKey].draw();
        }
        ssCtx = origCtx;
        ssCanvas = origCanvas;
      }
    };

    function resize() {
      canvas.width = window.innerWidth;
      canvas.height = window.innerHeight;
      // Update shared refs (mode files use ssCanvas/ssCtx)
      ssCanvas = canvas;
      ssCtx = canvas.getContext("2d");
      if (ssModes[currentMode] && ssModes[currentMode].resize) {
        ssModes[currentMode].resize();
      }
    }

    function drawFrame() {
      if (ssModes[currentMode]) ssModes[currentMode].draw();
      animFrame = requestAnimationFrame(drawFrame);
    }

    function updateClock() {
      var now = new Date();
      var h = String(now.getHours()).padStart(2, "0");
      var m = String(now.getMinutes()).padStart(2, "0");
      var s = String(now.getSeconds()).padStart(2, "0");
      clockEl.textContent = h + ":" + m + ":" + s;
    }

    function activate() {
      if (isActive) return;
      var tag = document.activeElement ? document.activeElement.tagName : "";
      if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return;

      if (!ssModes[currentMode]) currentMode = "particles";

      isActive = true;
      resize();

      // Toggle canvas visibility based on mode type
      var mode = ssModes[currentMode];
      if (mode && mode.gl) {
        canvas.style.display = "none";
        ssGetGLCanvas().style.display = "";
      } else {
        canvas.style.display = "";
        if (ssGLCanvas) ssGLCanvas.style.display = "none";
      }

      ssCtx.fillStyle = "#000000";
      ssCtx.fillRect(0, 0, ssCanvas.width, ssCanvas.height);
      if (mode) mode.init();
      overlay.classList.add("active");
      clockEl.style.display = showClock ? "" : "none";
      if (showClock) {
        updateClock();
        clockInterval = setInterval(updateClock, 1000);
      }
      animFrame = requestAnimationFrame(drawFrame);
    }

    function dismiss() {
      if (!isActive) return;
      isActive = false;
      // Call cleanup on active mode if it has one
      if (ssModes[currentMode] && ssModes[currentMode].cleanup) {
        ssModes[currentMode].cleanup();
      }
      overlay.classList.remove("active");
      if (animFrame) { cancelAnimationFrame(animFrame); animFrame = null; }
      if (clockInterval) { clearInterval(clockInterval); clockInterval = null; }
      // Hide GL canvas on dismiss
      if (ssGLCanvas) ssGLCanvas.style.display = "none";
      canvas.style.display = "";
      resetIdleTimer();
    }

    function resetIdleTimer() {
      if (idleTimer) clearTimeout(idleTimer);
      if (idleTimeout > 0) {
        idleTimer = setTimeout(activate, idleTimeout);
      }
    }

    // Dismiss on click or keypress
    var justDismissed = false;
    var dismissEvents = ["mousedown", "keydown", "touchstart"];
    dismissEvents.forEach(function (evt) {
      document.addEventListener(evt, function (e) {
        if (isActive) {
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
    overlay.addEventListener("mousemove", function (e) {
      ssMouseState.prevX = ssMouseState.x;
      ssMouseState.prevY = ssMouseState.y;
      ssMouseState.x = e.clientX;
      ssMouseState.y = e.clientY;
      // Backwards compat: update particles state if it exists
      if (typeof ssParticleState !== "undefined") {
        ssParticleState.mouseX = e.clientX;
        ssParticleState.mouseY = e.clientY;
      }
    });
    overlay.addEventListener("mouseleave", function () {
      ssMouseState.prevX = ssMouseState.x;
      ssMouseState.prevY = ssMouseState.y;
      ssMouseState.x = -1;
      ssMouseState.y = -1;
      if (typeof ssParticleState !== "undefined") {
        ssParticleState.mouseX = -1;
        ssParticleState.mouseY = -1;
      }
    });

    // Reset idle timer on movement/scroll
    ["mousemove", "scroll"].forEach(function (evt) {
      document.addEventListener(evt, function () {
        if (!isActive) resetIdleTimer();
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
      if (isActive) resize();
    });

    if (document.documentElement.classList.contains("a11y-reduce-motion")) {
      idleTimeout = 0;
    }

    resetIdleTimer();
  })();
