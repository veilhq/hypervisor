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

  // --- OKLCH color space utilities ---
  // Pipeline: sRGB [0-255] → linear RGB [0-1] → XYZ (D65) → OKLab → OKLCH
  // Reference: Björn Ottosson's OKLab, matrices from CSS Color Level 4 spec

  function multiplyMatrix3(m, v) {
    return [
      m[0] * v[0] + m[1] * v[1] + m[2] * v[2],
      m[3] * v[0] + m[4] * v[1] + m[5] * v[2],
      m[6] * v[0] + m[7] * v[1] + m[8] * v[2]
    ];
  }

  function srgbToLinear(c) {
    // c is 0-1 sRGB gamma-compressed
    return Math.abs(c) <= 0.04045
      ? c / 12.92
      : (c < 0 ? -1 : 1) * Math.pow((Math.abs(c) + 0.055) / 1.055, 2.4);
  }

  function linearToSrgb(c) {
    // c is linear, returns 0-1 sRGB gamma-compressed
    return Math.abs(c) > 0.0031308
      ? (c < 0 ? -1 : 1) * (1.055 * Math.pow(Math.abs(c), 1 / 2.4) - 0.055)
      : 12.92 * c;
  }

  // sRGB [0-1] → XYZ (D65)
  var M_SRGB_TO_XYZ = [
    0.41239079926595934, 0.357584339383878,   0.1804807884018343,
    0.21263900587151027, 0.715168678767756,   0.07219231536073371,
    0.01933081871559182, 0.11919477979462598, 0.9505321522496607
  ];

  // XYZ (D65) → sRGB linear
  var M_XYZ_TO_SRGB = [
     3.2409699419045226,  -1.537383177570094,   -0.4986107602930034,
    -0.9692436362808796,   1.8759675015077202,   0.04155505740717559,
     0.05563007969699366, -0.20397695888897652,  1.0569715142428786
  ];

  // XYZ → LMS (for OKLab)
  var M_XYZ_TO_LMS = [
    0.8190224379967030, 0.3619062600528904, -0.1288737815209879,
    0.0329836539323885, 0.9292868615863434,  0.0361446663506424,
    0.0481771893596242, 0.2642395317527308,  0.6335478284694309
  ];

  // LMS (cube root) → OKLab
  var M_LMS_TO_OKLAB = [
    0.2104542683093140,  0.7936177747023054, -0.0040720430116193,
    1.9779985324311684, -2.4285922420485799,  0.4505937096174110,
    0.0259040424655478,  0.7827717124575296, -0.8086757549230774
  ];

  // OKLab → LMS (cube root)
  var M_OKLAB_TO_LMS = [
    1,  0.3963377773761749,  0.2158037573099136,
    1, -0.1055613458156586, -0.0638541728258133,
    1, -0.0894841775298119, -1.2914855480194092
  ];

  // LMS → XYZ
  var M_LMS_TO_XYZ = [
     1.2268798758459243, -0.5578149944602171,  0.2813910456659647,
    -0.0405757452148008,  1.1122868032803170, -0.0717110580655164,
    -0.0763729366746601, -0.4214933324022432,  1.5869240198367816
  ];

  function hexToOklch(hex) {
    var rgb = hexToRgb(hex);
    // sRGB [0-255] → [0-1] → linear
    var lin = [
      srgbToLinear(rgb.r / 255),
      srgbToLinear(rgb.g / 255),
      srgbToLinear(rgb.b / 255)
    ];
    // linear RGB → XYZ → LMS → cbrt → OKLab
    var xyz = multiplyMatrix3(M_SRGB_TO_XYZ, lin);
    var lms = multiplyMatrix3(M_XYZ_TO_LMS, xyz);
    var lmsCbrt = [Math.cbrt(lms[0]), Math.cbrt(lms[1]), Math.cbrt(lms[2])];
    var lab = multiplyMatrix3(M_LMS_TO_OKLAB, lmsCbrt);
    // OKLab → OKLCH (polar)
    var L = lab[0];
    var a = lab[1];
    var b = lab[2];
    var C = Math.sqrt(a * a + b * b);
    var H = (Math.abs(a) < 0.0002 && Math.abs(b) < 0.0002)
      ? 0
      : ((Math.atan2(b, a) * 180 / Math.PI) % 360 + 360) % 360;
    return { l: L, c: C, h: H };
  }

  function oklchToSrgb(l, c, h) {
    // OKLCH → OKLab (cartesian)
    var hRad = h * Math.PI / 180;
    var a = c * Math.cos(hRad);
    var b = c * Math.sin(hRad);
    // OKLab → LMS (cube root) → LMS (cubed) → XYZ → linear RGB → sRGB
    var lmsCbrt = multiplyMatrix3(M_OKLAB_TO_LMS, [l, a, b]);
    var lms = [lmsCbrt[0] * lmsCbrt[0] * lmsCbrt[0], lmsCbrt[1] * lmsCbrt[1] * lmsCbrt[1], lmsCbrt[2] * lmsCbrt[2] * lmsCbrt[2]];
    var xyz = multiplyMatrix3(M_LMS_TO_XYZ, lms);
    var linRgb = multiplyMatrix3(M_XYZ_TO_SRGB, xyz);
    return [linearToSrgb(linRgb[0]), linearToSrgb(linRgb[1]), linearToSrgb(linRgb[2])];
  }

  function srgbInGamut(rgb) {
    return rgb[0] >= -0.001 && rgb[0] <= 1.001 &&
           rgb[1] >= -0.001 && rgb[1] <= 1.001 &&
           rgb[2] >= -0.001 && rgb[2] <= 1.001;
  }

  function oklchClampToSrgb(l, c, h) {
    // Binary search: reduce chroma until sRGB channels are in [0,1]
    var rgb = oklchToSrgb(l, c, h);
    if (srgbInGamut(rgb)) {
      return [Math.max(0, Math.min(1, rgb[0])), Math.max(0, Math.min(1, rgb[1])), Math.max(0, Math.min(1, rgb[2]))];
    }
    var lo = 0, hi = c;
    for (var i = 0; i < 20; i++) {
      var mid = (lo + hi) / 2;
      rgb = oklchToSrgb(l, mid, h);
      if (srgbInGamut(rgb)) {
        lo = mid;
      } else {
        hi = mid;
      }
    }
    rgb = oklchToSrgb(l, lo, h);
    return [Math.max(0, Math.min(1, rgb[0])), Math.max(0, Math.min(1, rgb[1])), Math.max(0, Math.min(1, rgb[2]))];
  }

  function oklchToHex(l, c, h) {
    var rgb = oklchClampToSrgb(l, c, h);
    var r = Math.round(rgb[0] * 255);
    var g = Math.round(rgb[1] * 255);
    var b = Math.round(rgb[2] * 255);
    return "#" + ((1 << 24) + (r << 16) + (g << 8) + b).toString(16).slice(1);
  }

  // --- OKLCH palette builder ---
  // Works natively in OKLCH perceptual space. Key principles:
  // - Hue rotation does the heavy lifting (perceptually uniform in OKLCH)
  // - Lightness stays in a tight band suitable for dark backgrounds (0.65–0.85)
  // - Chroma preserved near source level to maintain vibrancy
  // - No multiplicative darkening that produces muddy results
  function buildPaletteOKLCH(hex, mode) {
    var oklch = hexToOklch(hex);
    var h = oklch.h;
    // Clamp source lightness/chroma into usable ranges for UI accent colors
    // on dark backgrounds. Too dark = invisible, too light = washed out.
    // Floor at 0.55 to allow naturally dark hues (red, magenta) to stay vivid
    // without the gamut clamper desaturating them.
    var l = Math.max(Math.min(oklch.l, 0.82), 0.55);
    var c = Math.max(oklch.c, 0.08); // floor chroma so pastels stay vivid

    var warm, cool, comp;
    switch (mode) {
      case "triadic":
        // 120° intervals — classic triad with slight lightness variation
        warm = oklchToHex(Math.min(l + 0.04, 0.85), c, (h + 120) % 360);
        cool = oklchToHex(Math.max(l - 0.03, 0.55), c, (h + 240) % 360);
        comp = oklchToHex(Math.max(l - 0.06, 0.55), c * 0.9, (h + 180) % 360);
        break;
      case "analogous":
        // Tight hue cluster — harmony through proximity
        warm = oklchToHex(Math.min(l + 0.03, 0.85), c, (h + 35) % 360);
        cool = oklchToHex(Math.max(l - 0.02, 0.55), c, (h + 70) % 360);
        comp = oklchToHex(Math.max(l - 0.04, 0.55), c * 0.95, (h + 330) % 360);
        break;
      case "square":
        // 90° intervals — maximum variety
        warm = oklchToHex(Math.min(l + 0.03, 0.85), c, (h + 90) % 360);
        cool = oklchToHex(Math.max(l - 0.02, 0.55), c, (h + 180) % 360);
        comp = oklchToHex(Math.max(l - 0.05, 0.55), c * 0.9, (h + 270) % 360);
        break;
      case "complement":
        // 180° — two variations of the complement plus a muted accent
        warm = oklchToHex(Math.min(l + 0.05, 0.85), c, (h + 180) % 360);
        cool = oklchToHex(Math.max(l - 0.05, 0.55), c * 0.85, (h + 180) % 360);
        comp = oklchToHex(Math.max(l - 0.08, 0.55), c * 0.7, h);
        break;
      default: // split
        // +150° and +210° — split-complement
        warm = oklchToHex(Math.min(l + 0.04, 0.85), c, (h + 150) % 360);
        cool = oklchToHex(Math.max(l - 0.02, 0.55), c, (h + 210) % 360);
        comp = oklchToHex(Math.max(l - 0.05, 0.55), c * 0.9, (h + 180) % 360);
    }

    return { accent: hex, warm: warm, cool: cool, comp: comp };
  }

  // --- Gradient map presets (curated palettes that bypass algorithmic derivation) ---
  var GRADIENT_MAPS = {
    "frost": {
      name: "Frost",
      description: "Icy blue-white — clean and clinical",
      accent: "#d2ebfe", warm: "#c0caff", cool: "#ceb0e4", comp: "#7bc5d3",
      semantics: { success: "#7edba6", warning: "#c0caff", error: "#f78c8c", info: "#7bc5d3" }
    },
    "slate": {
      name: "Slate",
      description: "Industrial blue-grey — subdued and moody",
      accent: "#7a9bb5", warm: "#8a8fad", cool: "#6a9fa3", comp: "#a3757b",
      semantics: { success: "#7aad8a", warning: "#ad9a6a", error: "#a3757b", info: "#6a9fa3" }
    },
    "mono": {
      name: "Mono",
      description: "True monochrome — cool grey-blue only",
      accent: "#94abbe", warm: "#7b93a8", cool: "#adbfcc", comp: "#687f8f",
      semantics: { success: "#94abbe", warning: "#adbfcc", error: "#7b93a8", info: "#94abbe" }
    },
    "cyberdeck": {
      name: "Cyberdeck",
      description: "High-voltage hacker terminal",
      accent: "#00ff9f", warm: "#ffe600", cool: "#00e5ff", comp: "#ff003c",
      semantics: { success: "#00ff9f", warning: "#ffe600", error: "#ff003c", info: "#00e5ff" }
    },
    "ember": {
      name: "Ember",
      description: "Red-orange hue ladder — hot to dark",
      accent: "#ff6551", warm: "#de1d3f", cool: "#ffa565", comp: "#b21f41",
      semantics: { success: "#ffa565", warning: "#ff6551", error: "#b21f41", info: "#de1d3f" }
    },
    "spectrum": {
      name: "Spectrum",
      description: "Equal perceptual brightness at 90° intervals",
      accent: "#43b2e1", warm: "#c68bd3", cool: "#7bb76e", comp: "#e08d5d",
      semantics: { success: "#7bb76e", warning: "#e08d5d", error: "#c68bd3", info: "#43b2e1" }
    },
    "smoke": {
      name: "Smoke",
      description: "Near-achromatic — the faintest blue haze",
      accent: "#9ba6b1", warm: "#80878f", cool: "#b2bfce", comp: "#657383",
      semantics: { success: "#9ba6b1", warning: "#b2bfce", error: "#80878f", info: "#9ba6b1" }
    },
    "voltage": {
      name: "Voltage",
      description: "Complementary clash — cyan vs magenta at full chroma",
      accent: "#00d4bb", warm: "#ec6094", cool: "#50ddd5", comp: "#d43b86",
      semantics: { success: "#00d4bb", warning: "#50ddd5", error: "#d43b86", info: "#ec6094" }
    },
    "thermal": {
      name: "Thermal",
      description: "Infrared heat map — cool blue to hot yellow",
      accent: "#ffc250", warm: "#fb5a46", cool: "#5480c7", comp: "#d10054",
      semantics: { success: "#ffc250", warning: "#fb5a46", error: "#d10054", info: "#5480c7" }
    }
  };

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
    var palette = buildPaletteOKLCH(hex, paletteMode);

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

  // --- Theme mode state (custom vs preset) ---
  var THEME_MODE_KEY = "hypervisor-theme-mode";
  var GRADIENT_MAP_KEY = "hypervisor-gradient-map";
  var themeMode = "custom";
  var activeGradientMap = null;

  try { themeMode = localStorage.getItem(THEME_MODE_KEY) || "custom"; } catch (e) {}
  try { activeGradientMap = localStorage.getItem(GRADIENT_MAP_KEY) || null; } catch (e) {}

  function applySemanticDefaults() {
    // Reset semantic vars to their fixed defaults (custom mode)
    var root = document.documentElement;
    root.style.setProperty("--success", "#00ff41");
    root.style.setProperty("--warning", "#ffb000");
    root.style.setProperty("--error", "#ff3333");
    root.style.setProperty("--info", "#00cccc");
    root.style.setProperty("--highlight", "var(--accent)");
    root.style.setProperty("--surface-active", "var(--accent-glow)");
  }

  function applyGradientMap(presetKey) {
    var preset = GRADIENT_MAPS[presetKey];
    if (!preset) return false;

    var root = document.documentElement;
    var hex = preset.accent;
    var rgb = hexToRgb(hex);

    // Set palette vars directly from preset (bypass derivation)
    root.style.setProperty("--accent", hex);
    root.style.setProperty("--accent-dim", dimColor(hex, 0.8));
    root.style.setProperty("--accent-glow", "rgba(" + rgb.r + "," + rgb.g + "," + rgb.b + ",0.06)");
    root.style.setProperty("--accent-border", "rgba(" + rgb.r + "," + rgb.g + "," + rgb.b + ",0.15)");
    root.style.setProperty("--warm", preset.warm);
    root.style.setProperty("--cool", preset.cool);
    root.style.setProperty("--comp", preset.comp);

    // Set semantic vars from preset overrides
    if (preset.semantics) {
      if (preset.semantics.success) root.style.setProperty("--success", preset.semantics.success);
      if (preset.semantics.warning) root.style.setProperty("--warning", preset.semantics.warning);
      if (preset.semantics.error) root.style.setProperty("--error", preset.semantics.error);
      if (preset.semantics.info) root.style.setProperty("--info", preset.semantics.info);
    }
    root.style.setProperty("--highlight", "var(--accent)");
    root.style.setProperty("--surface-active", "var(--accent-glow)");

    // Update cursors
    var encodedColor = encodeURIComponent(hex);
    var cursorDefault = "url(\"data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' width='20' height='20' viewBox='0 0 24 24' fill='none' stroke='" + encodedColor + "' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'><path d='M4.037 4.688a.495.495 0 0 1 .651-.651l16 6.5a.5.5 0 0 1-.063.947l-6.124 1.58a2 2 0 0 0-1.438 1.435l-1.579 6.126a.5.5 0 0 1-.947.063z'/></svg>\") 2 2, auto";
    var cursorPointer = "url(\"data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' width='20' height='20' viewBox='0 0 24 24' fill='" + encodedColor + "' stroke='" + encodedColor + "' stroke-width='1.5' stroke-linecap='round' stroke-linejoin='round'><path d='M4.037 4.688a.495.495 0 0 1 .651-.651l16 6.5a.5.5 0 0 1-.063.947l-6.124 1.58a2 2 0 0 0-1.438 1.435l-1.579 6.126a.5.5 0 0 1-.947.063z'/></svg>\") 2 2, pointer";
    var cursorText = "url(\"data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' width='20' height='20' viewBox='0 0 24 24' fill='none' stroke='" + encodedColor + "' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'><path d='M17 22h-1a4 4 0 0 1-4-4V6a4 4 0 0 1 4-4h1'/><path d='M7 22h1a4 4 0 0 0 4-4V6a4 4 0 0 0-4-4H7'/></svg>\") 10 10, text";
    root.style.setProperty("--cursor-default", cursorDefault);
    root.style.setProperty("--cursor-pointer", cursorPointer);
    root.style.setProperty("--cursor-text", cursorText);

    // Update picker value to match (visual feedback even though locked)
    if (colorPicker) colorPicker.value = hex;

    // Update palette preview
    updatePalettePreview({ accent: hex, warm: preset.warm, cool: preset.cool, comp: preset.comp });

    // Persist state
    themeMode = "preset";
    activeGradientMap = presetKey;
    try {
      localStorage.setItem(THEME_MODE_KEY, "preset");
      localStorage.setItem(GRADIENT_MAP_KEY, presetKey);
      localStorage.setItem(STORAGE_KEY, hex);
    } catch (e) {}
    savePreference(THEME_MODE_KEY, "preset");
    savePreference(GRADIENT_MAP_KEY, presetKey);
    savePreference(STORAGE_KEY, hex);

    return true;
  }

  function switchToCustomMode() {
    themeMode = "custom";
    activeGradientMap = null;
    try {
      localStorage.setItem(THEME_MODE_KEY, "custom");
      localStorage.removeItem(GRADIENT_MAP_KEY);
    } catch (e) {}
    savePreference(THEME_MODE_KEY, "custom");
    savePreference(GRADIENT_MAP_KEY, "");
    applySemanticDefaults();
    var hex = colorPicker ? colorPicker.value : "#00ff41";
    applyAccent(hex);
  }

  if (colorPicker) {
    var saved = null;
    try { saved = localStorage.getItem(STORAGE_KEY); } catch (e) {}

    // On load: apply preset if active, otherwise apply saved custom accent
    if (themeMode === "preset" && activeGradientMap && GRADIENT_MAPS[activeGradientMap]) {
      applyGradientMap(activeGradientMap);
    } else if (saved) {
      colorPicker.value = saved;
      applyAccent(saved);
    }

    // Debounce disk writes — the input event fires on every drag tick of the
    // color picker, which floods the PyWebView bridge with rapid read/parse/write
    // cycles on preferences.json.  Only persist to localStorage during drag;
    // debounce the bridge call so it fires once after dragging stops.
    var accentSaveTimer = null;
    colorPicker.addEventListener("input", function () {
      // Using the picker manually switches to custom mode
      if (themeMode === "preset") {
        themeMode = "custom";
        activeGradientMap = null;
        try {
          localStorage.setItem(THEME_MODE_KEY, "custom");
          localStorage.removeItem(GRADIENT_MAP_KEY);
        } catch (e) {}
        applySemanticDefaults();
        updatePresetSelector();
      }
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

  // --- Preset selector UI (rendered dynamically) ---
  var presetChipsContainer = document.getElementById("preset-chips");
  var themeCustomRow = document.getElementById("theme-custom-row");

  function renderPresetChips() {
    if (!presetChipsContainer) return;
    var html = "";
    // "Custom" chip
    html += '<div class="preset-chip' + (themeMode === "custom" ? " active" : "") + '" data-preset="custom">';
    html += '<span class="preset-chip-swatch" style="background:var(--accent)"></span>';
    html += 'Custom</div>';
    // Preset chips
    var keys = Object.keys(GRADIENT_MAPS);
    for (var i = 0; i < keys.length; i++) {
      var key = keys[i];
      var p = GRADIENT_MAPS[key];
      var isActive = (themeMode === "preset" && activeGradientMap === key);
      html += '<div class="preset-chip' + (isActive ? " active" : "") + '" data-preset="' + key + '">';
      html += '<span class="preset-chip-swatch" style="background:' + p.accent + '"></span>';
      html += p.name + '</div>';
    }
    presetChipsContainer.innerHTML = html;

    // Wire click events
    var chips = presetChipsContainer.querySelectorAll(".preset-chip");
    chips.forEach(function (chip) {
      chip.addEventListener("click", function () {
        var preset = this.getAttribute("data-preset");
        if (preset === "custom") {
          switchToCustomMode();
        } else {
          applyGradientMap(preset);
        }
        updatePresetSelector();
        persistThemeDefaults();
      });
    });
  }

  function updatePresetSelector() {
    if (!presetChipsContainer) return;
    var chips = presetChipsContainer.querySelectorAll(".preset-chip");
    chips.forEach(function (chip) {
      var preset = chip.getAttribute("data-preset");
      if (preset === "custom") {
        chip.classList.toggle("active", themeMode === "custom");
      } else {
        chip.classList.toggle("active", themeMode === "preset" && activeGradientMap === preset);
      }
    });
    // Show/hide picker + mode toggle based on mode
    if (themeCustomRow) {
      var picker = themeCustomRow.querySelector(".settings-color-input");
      var modeBtn = themeCustomRow.querySelector(".settings-palette-mode");
      if (picker) picker.disabled = (themeMode === "preset");
      if (modeBtn) modeBtn.style.display = (themeMode === "preset") ? "none" : "";
    }
  }

  function persistThemeDefaults() {
    // Persist to theme-defaults.json via bridge if available
    if (typeof savePreference === "function") {
      var accent = colorPicker ? colorPicker.value : "#00ff41";
      var bwToggle = document.getElementById("a11y-bw-theme");
      var bwTheme = bwToggle ? bwToggle.checked : false;
      if (window.pywebview && window.pywebview.api && window.pywebview.api.save_theme_defaults) {
        window.pywebview.api.save_theme_defaults(accent, paletteMode, bwTheme, themeMode, activeGradientMap);
      }
    }
  }

  // Render on load
  renderPresetChips();
  updatePresetSelector();

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
        var palette = buildPaletteOKLCH(hex, paletteMode);
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
        var palette = buildPaletteOKLCH(hex, paletteMode);
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
