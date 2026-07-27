/* === Hypervisor: Screensaver Engine === */

// Self-contained IIFE (WI-118 rework). All shared state promoted to window:
//   window.__ss           — mutable config/state (currentMode, ditherPattern, ...)
//   window.ssCanvas/ssCtx — stable refs to the 2D canvas + context
//   window.ssModes        — mode registry (mode files push into it)
//   window.ssMouseState   — shared mouse state
//   window.ssGetAccent, ssHexToRgba, ssHexToRgb, ssGetPalette, ssUsePalette — helpers
//   window.ssGetGLCanvas / window.ssGLCanvas — lazy WebGL canvas
//   window.ssParticleState — set by particles.js when it initializes
//
// Mode files and zz-engine-tail.js live in their own IIFEs and reference the
// above via bare identifiers (globals resolve through window) or explicit
// `window.__ss.*` where the value is a mutable primitive.
(function () {
  "use strict";

  var IDLE_KEY = "hypervisor-screensaver-idle";
  var MODE_KEY = "hypervisor-screensaver-mode";
  var CLOCK_KEY = "hypervisor-screensaver-clock";
  var PALETTE_KEY = "hypervisor-screensaver-palette";
  var DITHER_PATTERN_KEY = "hypervisor-screensaver-dither-pattern";
  var IDLE_DEFAULT = 300000; // 5 minutes

  var idleTimeout = IDLE_DEFAULT;
  var currentMode = "particles";
  var showClock = true;
  var usePalette = false;
  var ditherPattern = "trig";
  try {
    var savedIdle = localStorage.getItem(IDLE_KEY);
    if (savedIdle) idleTimeout = parseInt(savedIdle, 10) || IDLE_DEFAULT;
    var savedMode = localStorage.getItem(MODE_KEY);
    if (savedMode) currentMode = savedMode;
    var savedClock = localStorage.getItem(CLOCK_KEY);
    if (savedClock === "0") showClock = false;
    var savedPalette = localStorage.getItem(PALETTE_KEY);
    if (savedPalette === "1") usePalette = true;
    var savedDitherPattern = localStorage.getItem(DITHER_PATTERN_KEY);
    if (savedDitherPattern) ditherPattern = savedDitherPattern;
  } catch (e) {}

  // Build overlay DOM
  var overlay = document.createElement("div");
  overlay.className = "screensaver-overlay";
  overlay.setAttribute("aria-hidden", "true");

  var canvas = document.createElement("canvas");
  overlay.appendChild(canvas);

  var clockEl = document.createElement("div");
  clockEl.className = "screensaver-clock";
  overlay.appendChild(clockEl);

  var hint = document.createElement("div");
  hint.className = "screensaver-hint";
  hint.textContent = "click or press any key to dismiss";
  overlay.appendChild(hint);

  document.body.appendChild(overlay);

  var ctx = canvas.getContext("2d");

  // --- Shared helpers (mode files use ss-prefixed globals below) ---
  function getAccentColor() {
    return getComputedStyle(document.documentElement).getPropertyValue("--accent").trim() || "#00ff41";
  }
  function hexToRgba(hex, alpha) {
    var r = parseInt(hex.slice(1, 3), 16);
    var g = parseInt(hex.slice(3, 5), 16);
    var b = parseInt(hex.slice(5, 7), 16);
    return "rgba(" + r + "," + g + "," + b + "," + alpha + ")";
  }
  function hexToRgb(hex) {
    return {
      r: parseInt(hex.slice(1, 3), 16),
      g: parseInt(hex.slice(3, 5), 16),
      b: parseInt(hex.slice(5, 7), 16)
    };
  }
  function getPaletteColors() {
    var style = getComputedStyle(document.documentElement);
    var accent = style.getPropertyValue("--accent").trim() || "#00ff41";
    var warm = style.getPropertyValue("--warm").trim() || "#ff6600";
    var cool = style.getPropertyValue("--cool").trim() || "#00cccc";
    var comp = style.getPropertyValue("--comp").trim() || "#cc00cc";
    return [accent, warm, cool, comp];
  }

  var modes = {};
  var ssMouseState = { x: -1, y: -1, prevX: -1, prevY: -1 };

  // WebGL canvas (created lazily, shown only for GL modes)
  function ssGetGLCanvas() {
    if (!window.ssGLCanvas) {
      var gl = document.createElement("canvas");
      gl.style.position = "absolute";
      gl.style.top = "0";
      gl.style.left = "0";
      gl.style.width = "100%";
      gl.style.height = "100%";
      gl.style.pointerEvents = "none";
      gl.style.display = "none";
      overlay.insertBefore(gl, clockEl);
      window.ssGLCanvas = gl;
    }
    return window.ssGLCanvas;
  }

  // --- Promote shared state to window (accessible from all mode files & tail) ---
  window.ssCanvas = canvas;
  window.ssCtx = ctx;
  window.ssGLCanvas = null;
  window.ssGetGLCanvas = ssGetGLCanvas;
  window.ssGetAccent = getAccentColor;
  window.ssHexToRgba = hexToRgba;
  window.ssHexToRgb = hexToRgb;
  window.ssGetPalette = getPaletteColors;
  window.ssUsePalette = function () { return window.__ss.usePalette; };
  window.ssModes = modes;
  window.ssMouseState = ssMouseState;
  window.ssParticleState = null;

  // Mutable config namespace — tail may update; modes read.
  window.__ss = {
    IDLE_KEY: IDLE_KEY,
    MODE_KEY: MODE_KEY,
    CLOCK_KEY: CLOCK_KEY,
    PALETTE_KEY: PALETTE_KEY,
    DITHER_PATTERN_KEY: DITHER_PATTERN_KEY,
    IDLE_DEFAULT: IDLE_DEFAULT,
    idleTimeout: idleTimeout,
    currentMode: currentMode,
    showClock: showClock,
    usePalette: usePalette,
    ditherPattern: ditherPattern,
    isActive: false,
    overlay: overlay,
    clockEl: clockEl,
    // Canvas reference for tail's resize() and preview() proxying.
    canvas: canvas
  };
})();
