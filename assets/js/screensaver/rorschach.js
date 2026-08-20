/* === Screensaver Mode: Rorschach === */

// Generates symmetric ink-blot patterns behind an ASCII glyph grid.
// Two blot fields (current + target) morph between each other on a timer,
// producing an infinite parade of Rorschach-like forms. Cells inside the
// blot region cycle glyphs brightly; cells outside are dim/static.

(function () {
  "use strict";

  var SPACING = 16;
  var FONT_SIZE = 12;
  var MORPH_DURATION = 300;  // frames to transition between blots (~5s at 60fps)
  var HOLD_DURATION = 300;   // frames to hold a blot before morphing (~5s)

  var GLYPHS = '░▒▓│┤╡╢╖╕╣║╗╝╜╛┐└┴┬├─┼╞╟╚╔╩╦╠═╬╧╨╤╥╙╘╒╓╫╪┘┌█▄▌▐▀αβΓπΣσμτΦΘΩδ∞φε∩≡±≥≤⌐¬÷≈°∙·√ⁿ²■';

  var state = {
    step: 0,
    cols: 0,
    rows: 0,
    glyphs: null,
    cycling: null,
    // Blot fields: float arrays [0..1] representing ink density per cell (left half, mirrored)
    blotA: null,
    blotB: null,
    // Morph timing
    phase: 'hold',    // 'hold' or 'morph'
    phaseTimer: 0,
    // Noise seed offsets for generating distinct blots
    seedA: 0,
    seedB: 1
  };

  // Simple seeded hash for pseudo-noise (no dependency needed)
  function hash(x, y, seed) {
    var n = Math.sin(x * 127.1 + y * 311.7 + seed * 758.5) * 43758.5453;
    return n - Math.floor(n);
  }

  // Value noise with bilinear interpolation
  function noise2d(x, y, seed) {
    var ix = Math.floor(x);
    var iy = Math.floor(y);
    var fx = x - ix;
    var fy = y - iy;
    // Smoothstep
    fx = fx * fx * (3 - 2 * fx);
    fy = fy * fy * (3 - 2 * fy);
    var a = hash(ix, iy, seed);
    var b = hash(ix + 1, iy, seed);
    var c = hash(ix, iy + 1, seed);
    var d = hash(ix + 1, iy + 1, seed);
    return a + (b - a) * fx + (c - a) * fy + (a - b - c + d) * fx * fy;
  }

  // Fractal Brownian motion (3 octaves)
  function fbm(x, y, seed) {
    var val = 0;
    var amp = 0.5;
    var freq = 1.0;
    for (var i = 0; i < 3; i++) {
      val += amp * noise2d(x * freq, y * freq, seed + i * 100);
      amp *= 0.5;
      freq *= 2.0;
    }
    return val;
  }

  // Generate a blot field (half-width, will be mirrored on read)
  function generateBlot(seed, cols, rows) {
    var halfCols = Math.ceil(cols / 2);
    var field = new Float32Array(halfCols * rows);

    for (var row = 0; row < rows; row++) {
      for (var col = 0; col < halfCols; col++) {
        // col=0 is the LEFT EDGE of screen, col=halfCols-1 is the CENTER (mirror axis).
        // readBlot mirrors the right half back into this same array.
        var distFromCenter = 1.0 - (col / (halfCols - 1)); // 0 at center, 1 at edge
        var ny = ((row / rows) - 0.5) * 2.0; // -1 to 1 vertical

        // Domain warping: warp the sample coordinates with noise for organic distortion
        var wx = noise2d(distFromCenter * 5.0, ny * 5.0, seed + 200) - 0.5;
        var wy = noise2d(distFromCenter * 5.0 + 5.3, ny * 5.0 + 5.3, seed + 300) - 0.5;
        var dx = distFromCenter + wx * 0.6;
        var dy = ny + wy * 0.6;

        // Layer 1: medium-frequency structure (multiple separated lobes)
        var n1 = fbm(dx * 5.5, dy * 5.5, seed);

        // Layer 2: high-frequency detail (jagged edges, tendrils)
        var n2 = fbm(dx * 11.0 + 10, dy * 11.0 + 10, seed + 50);

        // Layer 3: very fine grain (splatter dots, broken edges)
        var n3 = noise2d(dx * 20.0 + 20, dy * 20.0 + 20, seed + 100);

        // Combine: high-freq dominates for jagged, fractured look
        var v = n1 * 0.3 + n2 * 0.4 + n3 * 0.3;

        // Angular warping — multiple harmonics for complex lobe shapes
        var angle = Math.atan2(ny, distFromCenter + 0.01);
        var angularWarp = 0.12 * Math.sin(angle * 2.0 + seed * 0.2) +
                          0.12 * Math.sin(angle * 5.0 - seed * 0.15) +
                          0.08 * Math.sin(angle * 9.0 + seed * 0.4) +
                          0.05 * Math.sin(angle * 13.0 - seed * 0.6);
        v += angularWarp;

        // Radial falloff — gentle containment, allows blot to use most of the screen
        var cy = Math.abs(ny); // 0 at vertical center, 1 at top/bottom
        var radial = 1.0 - Math.pow(distFromCenter * distFromCenter * 0.9 + cy * cy * 0.6, 0.8);
        radial = Math.max(0, radial);

        v = v * radial;

        // Higher threshold = more negative space, sparser shapes
        var threshold = 0.38;
        var softness = 0.03;
        if (v < threshold - softness) {
          v = 0;
        } else if (v < threshold + softness) {
          v = (v - (threshold - softness)) / (2 * softness);
        } else {
          v = 1;
        }

        field[row * halfCols + col] = v;
      }
    }
    return field;
  }

  // Read blot value at (col, row) with mirror symmetry
  function readBlot(field, col, row, cols, rows) {
    var halfCols = Math.ceil(cols / 2);
    // Distance from center column in grid units
    var center = (cols - 1) / 2.0;
    var dist = Math.abs(col - center);
    // Map distance back to field index: field[0]=edge, field[halfCols-1]=center
    var fieldCol = Math.round((halfCols - 1) - dist);
    if (fieldCol < 0) fieldCol = 0;
    if (fieldCol >= halfCols) fieldCol = halfCols - 1;
    if (row < 0 || row >= rows) return 0;
    return field[row * halfCols + fieldCol];
  }

  function rorschachInit() {
    var w = ssCanvas.width, h = ssCanvas.height;
    state.cols = Math.ceil(w / SPACING) + 1;
    if (state.cols % 2 === 0) state.cols++; // force odd for true center column
    state.rows = Math.ceil(h / SPACING) + 1;
    var total = state.cols * state.rows;

    state.glyphs = [];
    state.cycling = new Int16Array(total);
    for (var i = 0; i < total; i++) {
      state.glyphs.push(GLYPHS[Math.floor(Math.random() * GLYPHS.length)]);
    }

    state.seedA = Math.random() * 1000;
    state.seedB = Math.random() * 1000 + 500;
    state.blotA = generateBlot(state.seedA, state.cols, state.rows);
    state.blotB = generateBlot(state.seedB, state.cols, state.rows);
    state.phase = 'hold';
    state.phaseTimer = 0;
    state.step = 0;
  }

  function rorschachResize() {
    rorschachInit();
  }

  function rorschachDraw() {
    var w = ssCanvas.width;
    var h = ssCanvas.height;
    var accent = ssGetAccent();
    var palette = ssUsePalette() ? ssGetPalette() : null;
    var cols = state.cols;
    var rows = state.rows;
    var glyphs = state.glyphs;
    var cycling = state.cycling;

    // Phase management
    state.phaseTimer++;
    var morphT = 0; // 0 = fully blotA, 1 = fully blotB

    if (state.phase === 'hold') {
      morphT = 0;
      if (state.phaseTimer >= HOLD_DURATION) {
        state.phase = 'morph';
        state.phaseTimer = 0;
        // Generate new target
        state.seedB = Math.random() * 10000;
        state.blotB = generateBlot(state.seedB, cols, rows);
      }
    } else {
      // Morphing
      morphT = state.phaseTimer / MORPH_DURATION;
      // Ease in-out
      morphT = morphT * morphT * (3 - 2 * morphT);
      if (state.phaseTimer >= MORPH_DURATION) {
        // Swap: B becomes A, generate new B next hold cycle
        state.blotA = state.blotB;
        state.seedA = state.seedB;
        state.phase = 'hold';
        state.phaseTimer = 0;
      }
    }

    // Clear
    ssCtx.fillStyle = "#000000";
    ssCtx.fillRect(0, 0, w, h);
    ssCtx.font = FONT_SIZE + "px monospace";
    ssCtx.textAlign = "center";
    ssCtx.textBaseline = "middle";

    var step = state.step;

    // Offset grid so the center column aligns exactly with canvas center
    var centerCol = (cols - 1) / 2;
    var xOffset = (w / 2) - (centerCol * SPACING);
    var yOffset = SPACING * 0.5;

    // Pre-compute color strings for quantized alpha levels to avoid per-cell allocation.
    // 16 alpha buckets covers visible range with no perceptible banding.
    var ALPHA_STEPS = 16;
    var colorLUT;
    if (palette) {
      // Palette mode: build LUT per palette color × alpha step
      var palRgb = [];
      for (var pi = 0; pi < palette.length; pi++) {
        palRgb.push(ssHexToRgb(palette[pi]));
      }
      colorLUT = [];
      for (var ci = 0; ci < palRgb.length; ci++) {
        var arr = [];
        for (var ai = 0; ai <= ALPHA_STEPS; ai++) {
          var a = ai / ALPHA_STEPS;
          arr.push('rgba(' + palRgb[ci].r + ',' + palRgb[ci].g + ',' + palRgb[ci].b + ',' + a.toFixed(3) + ')');
        }
        colorLUT.push(arr);
      }
    } else {
      // Single accent mode: one array indexed by alpha step
      var rgb = ssHexToRgb(accent);
      colorLUT = [];
      for (var ai2 = 0; ai2 <= ALPHA_STEPS; ai2++) {
        var a2 = ai2 / ALPHA_STEPS;
        colorLUT.push('rgba(' + rgb.r + ',' + rgb.g + ',' + rgb.b + ',' + a2.toFixed(3) + ')');
      }
    }

    for (var row = 0; row < rows; row++) {
      for (var col = 0; col < cols; col++) {
        var idx = row * cols + col;

        // Get blot density (lerp between A and B)
        var valA = readBlot(state.blotA, col, row, cols, rows);
        var valB = readBlot(state.blotB, col, row, cols, rows);
        var density = valA + (valB - valA) * morphT;

        // Determine if cell is "ink"
        var isInk = density > 0.3;
        var inkStrength = Math.min(1, Math.max(0, (density - 0.3) / 0.7));

        // Activate cycling for ink cells
        if (isInk && cycling[idx] <= 0) {
          cycling[idx] = 8 + Math.floor(Math.random() * 12);
        }

        var isCycling = cycling[idx] > 0;

        // Cycle glyph
        if (isCycling && step % 3 === 0) {
          glyphs[idx] = GLYPHS[Math.floor(Math.random() * GLYPHS.length)];
          cycling[idx]--;
        }

        // Alpha: bright for ink, dim for background
        var alpha;
        if (isInk) {
          alpha = 0.4 + inkStrength * 0.55; // 0.4 to 0.95
        } else {
          alpha = 0.06 + density * 0.15; // very dim, slightly visible near edges
        }

        // Quantize alpha to LUT index
        var alphaIdx = Math.round(alpha * ALPHA_STEPS);
        if (alphaIdx > ALPHA_STEPS) alphaIdx = ALPHA_STEPS;
        if (alphaIdx < 0) alphaIdx = 0;

        // Color — lookup from pre-built strings
        if (palette) {
          var cIdx = isInk ? Math.min(2, Math.floor(inkStrength * 2.99)) : 0;
          ssCtx.fillStyle = colorLUT[cIdx][alphaIdx];
        } else {
          ssCtx.fillStyle = colorLUT[alphaIdx];
        }

        var cx = col * SPACING + xOffset;
        var cy = row * SPACING + yOffset;
        ssCtx.fillText(glyphs[idx], cx, cy);
      }
    }

    state.step++;
  }

  ssModes['rorschach'] = { init: rorschachInit, draw: rorschachDraw, resize: rorschachResize, meta: { name: "Rorschach", icon: "brain", desc: "Symmetric ink blots materialize and morph through ASCII noise" } };
})();
