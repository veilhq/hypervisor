/* === Hypervisor: Screensaver Engine === */

  // --- Screensaver (multi-mode + clock) ---
  // Modes are registered as objects with init/draw/resize/cleanup methods.
  // The active mode key is persisted to localStorage.
  // Mode implementations live in separate 09x-ss-*.js files.
  (function initScreensaver() {
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
    var animFrame = null;
    var clockInterval = null;
    var isActive = false;
    var idleTimer = null;

    // --- Shared helpers (available to all mode files via closure) ---
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

    // Expose shared state for mode files (all in same IIFE scope after concatenation)
    // Mode files access: ssCanvas, ssCtx, ssGetAccent, ssHexToRgba, ssHexToRgb, ssGetPalette, ssUsePalette, ssModes
    var ssCanvas = canvas;
    var ssCtx = ctx;
    var ssGetAccent = getAccentColor;
    var ssHexToRgba = hexToRgba;
    var ssHexToRgb = hexToRgb;
    var ssGetPalette = getPaletteColors;
    var ssUsePalette = function () { return usePalette; };

    // Mode registry — mode files push into this
    var modes = {};
    var ssModes = modes;

    // Shared mouse state — all modes (2D and WebGL) read from this
    var ssMouseState = { x: -1, y: -1, prevX: -1, prevY: -1 };

    // WebGL canvas (created lazily, shown only for GL modes)
    var ssGLCanvas = null;
    function ssGetGLCanvas() {
      if (!ssGLCanvas) {
        ssGLCanvas = document.createElement("canvas");
        ssGLCanvas.style.position = "absolute";
        ssGLCanvas.style.top = "0";
        ssGLCanvas.style.left = "0";
        ssGLCanvas.style.width = "100%";
        ssGLCanvas.style.height = "100%";
        ssGLCanvas.style.pointerEvents = "none";
        ssGLCanvas.style.display = "none";
        overlay.insertBefore(ssGLCanvas, clockEl);
      }
      return ssGLCanvas;
    }
