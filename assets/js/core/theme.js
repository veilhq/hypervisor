/* === Hypervisor: Theme (accent color, palette) === */

  // --- Accent color picker with complementary palette ---
  var colorPicker = document.getElementById("accent-color");
  var STORAGE_KEY = "hypervisor-accent";

  function hexToRgb(hex) {
    var r = parseInt(hex.slice(1, 3), 16);
    var g = parseInt(hex.slice(3, 5), 16);
    var b = parseInt(hex.slice(5, 7), 16);
    return { r: r, g: g, b: b };
  }

  function rgbToHsl(r, g, b) {
    r /= 255; g /= 255; b /= 255;
    var max = Math.max(r, g, b), min = Math.min(r, g, b);
    var h, s, l = (max + min) / 2;
    if (max === min) { h = s = 0; }
    else {
      var d = max - min;
      s = l > 0.5 ? d / (2 - max - min) : d / (max + min);
      if (max === r) h = ((g - b) / d + (g < b ? 6 : 0)) / 6;
      else if (max === g) h = ((b - r) / d + 2) / 6;
      else h = ((r - g) / d + 4) / 6;
    }
    return { h: h * 360, s: s, l: l };
  }

  function hslToHex(h, s, l) {
    h = ((h % 360) + 360) % 360;
    var c = (1 - Math.abs(2 * l - 1)) * s;
    var x = c * (1 - Math.abs((h / 60) % 2 - 1));
    var m = l - c / 2;
    var r, g, b;
    if (h < 60)       { r = c; g = x; b = 0; }
    else if (h < 120) { r = x; g = c; b = 0; }
    else if (h < 180) { r = 0; g = c; b = x; }
    else if (h < 240) { r = 0; g = x; b = c; }
    else if (h < 300) { r = x; g = 0; b = c; }
    else               { r = c; g = 0; b = x; }
    r = Math.round((r + m) * 255);
    g = Math.round((g + m) * 255);
    b = Math.round((b + m) * 255);
    return "#" + ((1 << 24) + (r << 16) + (g << 8) + b).toString(16).slice(1);
  }

  function dimColor(hex, factor) {
    var rgb = hexToRgb(hex);
    return "rgb(" + Math.round(rgb.r * factor) + "," +
           Math.round(rgb.g * factor) + "," +
           Math.round(rgb.b * factor) + ")";
  }

  var PALETTE_MODES = ["split", "triadic", "analogous", "square", "complement"];
  var PALETTE_LABELS = { split: "SPL", triadic: "TRI", analogous: "ANA", square: "SQR", complement: "CMP" };
  var PALETTE_TITLES = {
    split:      "Split-complementary",
    triadic:    "Triadic",
    analogous:  "Analogous",
    square:     "Tetradic (square)",
    complement: "Complementary"
  };

  function buildPalette(hex, mode) {
    var rgb = hexToRgb(hex);
    var hsl = rgbToHsl(rgb.r, rgb.g, rgb.b);
    var warm, cool, comp;

    switch (mode) {
      case "triadic":
        // 120° intervals
        warm = hslToHex(hsl.h + 120, Math.min(hsl.s * 1.1, 1), Math.min(hsl.l * 1.15, 0.75));
        cool = hslToHex(hsl.h + 240, Math.min(hsl.s * 0.9, 1), Math.min(hsl.l * 0.95, 0.65));
        comp = hslToHex(hsl.h + 180, hsl.s * 0.7, Math.min(hsl.l * 0.85, 0.55));
        break;
      case "analogous":
        // Tight cluster: +30°, +60°, -30°
        warm = hslToHex(hsl.h + 30, Math.min(hsl.s * 1.05, 1), Math.min(hsl.l * 1.1, 0.75));
        cool = hslToHex(hsl.h + 60, Math.min(hsl.s * 0.9, 1), Math.min(hsl.l * 0.95, 0.65));
        comp = hslToHex(hsl.h - 30, hsl.s * 0.85, Math.min(hsl.l * 0.9, 0.6));
        break;
      case "square":
        // 90° intervals
        warm = hslToHex(hsl.h + 90, Math.min(hsl.s * 1.1, 1), Math.min(hsl.l * 1.1, 0.75));
        cool = hslToHex(hsl.h + 180, Math.min(hsl.s * 0.9, 1), Math.min(hsl.l * 0.95, 0.65));
        comp = hslToHex(hsl.h + 270, hsl.s * 0.8, Math.min(hsl.l * 0.85, 0.55));
        break;
      case "complement":
        // 180° complement + saturation/lightness shifts for variety
        warm = hslToHex(hsl.h + 180, Math.min(hsl.s * 1.1, 1), Math.min(hsl.l * 1.2, 0.75));
        cool = hslToHex(hsl.h + 180, Math.min(hsl.s * 0.7, 1), Math.min(hsl.l * 0.7, 0.5));
        comp = hslToHex(hsl.h, hsl.s * 0.5, Math.min(hsl.l * 0.6, 0.4));
        break;
      default: // split
        // +150° and +210°
        warm = hslToHex(hsl.h + 150, Math.min(hsl.s * 1.1, 1), Math.min(hsl.l * 1.15, 0.75));
        cool = hslToHex(hsl.h + 210, Math.min(hsl.s * 0.9, 1), Math.min(hsl.l * 0.95, 0.65));
        comp = hslToHex(hsl.h + 180, hsl.s * 0.7, Math.min(hsl.l * 0.85, 0.55));
    }

    return { accent: hex, warm: warm, cool: cool, comp: comp };
  }

  // Current palette mode
  var PALETTE_MODE_KEY = "hypervisor-palette-mode";
  var paletteMode = "split";
  try { paletteMode = localStorage.getItem(PALETTE_MODE_KEY) || "split"; } catch (e) {}
  // Validate stored mode against known modes
  if (PALETTE_MODES.indexOf(paletteMode) === -1) paletteMode = "split";

  function applyAccent(hex) {
    var root = document.documentElement;
    var isBW = root.classList.contains("a11y-bw-theme");

    // In B&W mode, force pure blue for all accent colors
    if (isBW) {
      root.style.setProperty("--accent", "#0000ff");
      root.style.setProperty("--accent-dim", "#0000cc");
      root.style.setProperty("--accent-glow", "rgba(0,0,255,0.15)");
      root.style.setProperty("--accent-border", "#0000ff");
      root.style.setProperty("--warm", "#0000ff");
      root.style.setProperty("--cool", "#0000ff");
      root.style.setProperty("--comp", "#0000ff");

      var encodedColor = encodeURIComponent("#0000ff");
      var cursorDefault = "url(\"data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' width='20' height='20' viewBox='0 0 24 24' fill='none' stroke='" + encodedColor + "' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'><path d='M4.037 4.688a.495.495 0 0 1 .651-.651l16 6.5a.5.5 0 0 1-.063.947l-6.124 1.58a2 2 0 0 0-1.438 1.435l-1.579 6.126a.5.5 0 0 1-.947.063z'/></svg>\") 2 2, auto";
      var cursorPointer = "url(\"data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' width='20' height='20' viewBox='0 0 24 24' fill='" + encodedColor + "' stroke='" + encodedColor + "' stroke-width='1.5' stroke-linecap='round' stroke-linejoin='round'><path d='M4.037 4.688a.495.495 0 0 1 .651-.651l16 6.5a.5.5 0 0 1-.063.947l-6.124 1.58a2 2 0 0 0-1.438 1.435l-1.579 6.126a.5.5 0 0 1-.947.063z'/></svg>\") 2 2, pointer";
      var cursorText = "url(\"data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' width='20' height='20' viewBox='0 0 24 24' fill='none' stroke='" + encodedColor + "' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'><path d='M17 22h-1a4 4 0 0 1-4-4V6a4 4 0 0 1 4-4h1'/><path d='M7 22h1a4 4 0 0 0 4-4V6a4 4 0 0 0-4-4H7'/></svg>\") 10 10, text";
      root.style.setProperty("--cursor-default", cursorDefault);
      root.style.setProperty("--cursor-pointer", cursorPointer);
      root.style.setProperty("--cursor-text", cursorText);

      updatePalettePreview({ accent: "#0000ff", warm: "#0000ff", cool: "#0000ff", comp: "#0000ff" });
      return;
    }

    var rgb = hexToRgb(hex);
    var palette = buildPalette(hex, paletteMode);

    // Primary accent
    root.style.setProperty("--accent", hex);
    root.style.setProperty("--accent-dim", dimColor(hex, 0.8));
    root.style.setProperty("--accent-glow", "rgba(" + rgb.r + "," + rgb.g + "," + rgb.b + ",0.06)");
    root.style.setProperty("--accent-border", "rgba(" + rgb.r + "," + rgb.g + "," + rgb.b + ",0.15)");

    // Complementary palette
    root.style.setProperty("--warm", palette.warm);
    root.style.setProperty("--cool", palette.cool);
    root.style.setProperty("--comp", palette.comp);

    // Update custom cursor color
    var encodedColor = encodeURIComponent(hex);
    var cursorDefault = "url(\"data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' width='20' height='20' viewBox='0 0 24 24' fill='none' stroke='" + encodedColor + "' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'><path d='M4.037 4.688a.495.495 0 0 1 .651-.651l16 6.5a.5.5 0 0 1-.063.947l-6.124 1.58a2 2 0 0 0-1.438 1.435l-1.579 6.126a.5.5 0 0 1-.947.063z'/></svg>\") 2 2, auto";
    var cursorPointer = "url(\"data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' width='20' height='20' viewBox='0 0 24 24' fill='" + encodedColor + "' stroke='" + encodedColor + "' stroke-width='1.5' stroke-linecap='round' stroke-linejoin='round'><path d='M4.037 4.688a.495.495 0 0 1 .651-.651l16 6.5a.5.5 0 0 1-.063.947l-6.124 1.58a2 2 0 0 0-1.438 1.435l-1.579 6.126a.5.5 0 0 1-.947.063z'/></svg>\") 2 2, pointer";
    root.style.setProperty("--cursor-default", cursorDefault);
    root.style.setProperty("--cursor-pointer", cursorPointer);

    // Update custom text cursor color
    var cursorText = "url(\"data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' width='20' height='20' viewBox='0 0 24 24' fill='none' stroke='" + encodedColor + "' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'><path d='M17 22h-1a4 4 0 0 1-4-4V6a4 4 0 0 1 4-4h1'/><path d='M7 22h1a4 4 0 0 0 4-4V6a4 4 0 0 0-4-4H7'/></svg>\") 10 10, text";
    root.style.setProperty("--cursor-text", cursorText);

    // Update palette preview if it exists
    updatePalettePreview(palette);
  }

  function updatePalettePreview(palette) {
    var preview = document.getElementById("palette-preview");
    if (!preview) return;
    var swatches = preview.querySelectorAll(".swatch");
    var colors = [palette.accent, palette.warm, palette.cool, palette.comp];
    var labels = ["accent", "warm", "cool", "comp"];
    swatches.forEach(function (sw, i) {
      if (i < colors.length) {
        sw.style.background = colors[i];
        sw.setAttribute("data-tooltip", labels[i] + ": " + colors[i]);
      }
    });
  }

  if (colorPicker) {
    var saved = null;
    try { saved = localStorage.getItem(STORAGE_KEY); } catch (e) {}
    if (saved) {
      colorPicker.value = saved;
      applyAccent(saved);
    }

    // Debounce disk writes — the input event fires on every drag tick of the
    // color picker, which floods the PyWebView bridge with rapid read/parse/write
    // cycles on preferences.json.  Only persist to localStorage during drag;
    // debounce the bridge call so it fires once after dragging stops.
    var accentSaveTimer = null;
    colorPicker.addEventListener("input", function () {
      var hex = this.value;
      applyAccent(hex);
      try { localStorage.setItem(STORAGE_KEY, hex); } catch (e) {}
      clearTimeout(accentSaveTimer);
      accentSaveTimer = setTimeout(function () {
        savePreference(STORAGE_KEY, hex);
      }, 300);
    });

    // change fires once on final selection — guaranteed single bridge call
    colorPicker.addEventListener("change", function () {
      clearTimeout(accentSaveTimer);
      savePreference(STORAGE_KEY, this.value);
    });
  }

  // --- Palette mode toggle ---
  var modeToggle = document.getElementById("palette-mode");

  function updateModeButton() {
    if (!modeToggle) return;
    modeToggle.textContent = PALETTE_LABELS[paletteMode] || "SPL";
    var nextIdx = (PALETTE_MODES.indexOf(paletteMode) + 1) % PALETTE_MODES.length;
    modeToggle.setAttribute("data-tooltip", PALETTE_TITLES[paletteMode] + " — click for " + PALETTE_TITLES[PALETTE_MODES[nextIdx]].toLowerCase());
  }

  if (modeToggle) {
    updateModeButton();

    modeToggle.addEventListener("click", function () {
      var idx = PALETTE_MODES.indexOf(paletteMode);
      paletteMode = PALETTE_MODES[(idx + 1) % PALETTE_MODES.length];
      updateModeButton();
      savePreference(PALETTE_MODE_KEY, paletteMode);
      applyAccent(colorPicker ? colorPicker.value : "#00ff41");
    });
  }

  // --- Home title icon: cycle palette colors on hover ---
  var titleIcon = document.querySelector(".home-title-icon");
  if (titleIcon) {
    var cycleTimer = null;
    var cycleIdx = 0;
    var titleTarget = titleIcon;

    titleTarget.addEventListener("mouseenter", function () {
      cycleIdx = 0;
      function tick() {
        var hex = colorPicker ? colorPicker.value : "#00ff41";
        var palette = buildPalette(hex, paletteMode);
        var colors = [palette.accent, palette.warm, palette.cool, palette.comp];
        titleIcon.style.color = colors[cycleIdx % colors.length];
        cycleIdx++;
        cycleTimer = setTimeout(tick, 50);
      }
      tick();
    });

    titleTarget.addEventListener("mouseleave", function () {
      clearTimeout(cycleTimer);
      cycleTimer = null;
      titleIcon.style.color = "";
    });
  }

  // --- Brand (header icon + text): cycle palette colors on hover ---
  var brand = document.querySelector(".brand");
  if (brand) {
    var brandIcon = brand.querySelector(".brand-icon");
    var brandText = brand.querySelector(".brand-text");
    var brandTimer = null;
    var brandIdx = 0;

    brand.addEventListener("mouseenter", function () {
      brandIdx = 0;
      function tick() {
        var hex = colorPicker ? colorPicker.value : "#00ff41";
        var palette = buildPalette(hex, paletteMode);
        var colors = [palette.accent, palette.warm, palette.cool, palette.comp];
        var c = colors[brandIdx % colors.length];
        if (brandIcon) {
          brandIcon.style.color = c;
        }
        if (brandText) {
          brandText.style.color = c;
        }
        brandIdx++;
        brandTimer = setTimeout(tick, 50);
      }
      tick();
    });

    brand.addEventListener("mouseleave", function () {
      clearTimeout(brandTimer);
      brandTimer = null;
      if (brandIcon) {
        brandIcon.style.color = "";
      }
      if (brandText) {
        brandText.style.color = "";
      }
    });
  }
