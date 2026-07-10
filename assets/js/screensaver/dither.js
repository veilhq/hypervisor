/* === Screensaver Mode: Dither === */

    // ========== MODE: Dither ==========
    var ditherState = { time: 0 };

    // Bayer 8x8 ordered dither matrix (normalized 0-1)
    var bayerMatrix = [
      [ 0, 32,  8, 40,  2, 34, 10, 42],
      [48, 16, 56, 24, 50, 18, 58, 26],
      [12, 44,  4, 36, 14, 46,  6, 38],
      [60, 28, 52, 20, 62, 30, 54, 22],
      [ 3, 35, 11, 43,  1, 33,  9, 41],
      [51, 19, 59, 27, 49, 17, 57, 25],
      [15, 47,  7, 39, 13, 45,  5, 37],
      [63, 31, 55, 23, 61, 29, 53, 21]
    ];
    for (var bi = 0; bi < 8; bi++) {
      for (var bj = 0; bj < 8; bj++) {
        bayerMatrix[bi][bj] /= 64;
      }
    }

    function ditherInit() {
      ditherState.time = Math.random() * 100;
    }
    function ditherResize() {}
    function ditherDraw() {
      var accent = ssGetAccent();
      var rgb = ssHexToRgb(accent);
      var colors = ssUsePalette() ? ssGetPalette() : null;
      var paletteRgb = colors ? colors.map(ssHexToRgb) : null;
      var w = ssCanvas.width;
      var h = ssCanvas.height;
      var t = ditherState.time;
      var cell = Math.max(2, Math.floor(Math.min(w, h) / 400));

      var imgData = ssCtx.createImageData(w, h);
      var data = imgData.data;

      var cols = Math.ceil(w / cell);
      var rows = Math.ceil(h / cell);

      for (var row = 0; row < rows; row++) {
        for (var col = 0; col < cols; col++) {
          var px = col * cell;
          var py = row * cell;

          var cx = w * 0.5 + Math.sin(t * 0.4) * w * 0.3;
          var cy = h * 0.5 + Math.cos(t * 0.3) * h * 0.3;
          var dx = (px - cx) / w;
          var dy = (py - cy) / h;
          var dist = Math.sqrt(dx * dx + dy * dy);

          var g1 = 0.5 + 0.5 * Math.sin(dist * 6 - t * 0.8);
          var g2 = 0.5 + 0.5 * Math.sin((px + py) * 0.0032 + t * 0.5);
          var g3 = 0.5 + 0.5 * Math.cos((py - px) * 0.0041 - t * 0.3);
          var val = (g1 * 0.5 + g2 * 0.25 + g3 * 0.25);
          val = val * val;

          var threshold = bayerMatrix[row & 7][col & 7];
          var on = val > threshold;

          var r, g, b, a;
          if (on && paletteRgb) {
            var rawVal = (g1 * 0.5 + g2 * 0.25 + g3 * 0.25);
            var pos = rawVal * 3;
            var ci = Math.min(2, Math.floor(pos));
            var frac = pos - ci;
            var cA = paletteRgb[ci];
            var cB = paletteRgb[ci + 1];
            r = Math.round(cA.r + (cB.r - cA.r) * frac);
            g = Math.round(cA.g + (cB.g - cA.g) * frac);
            b = Math.round(cA.b + (cB.b - cA.b) * frac);
            a = 200;
          } else if (on) {
            r = rgb.r; g = rgb.g; b = rgb.b; a = 200;
          } else {
            r = 0; g = 0; b = 0; a = 0;
          }

          for (var sy = 0; sy < cell && py + sy < h; sy++) {
            for (var sx = 0; sx < cell && px + sx < w; sx++) {
              var idx = ((py + sy) * w + (px + sx)) * 4;
              data[idx] = r;
              data[idx + 1] = g;
              data[idx + 2] = b;
              data[idx + 3] = a;
            }
          }
        }
      }

      ssCtx.fillStyle = "#000000";
      ssCtx.fillRect(0, 0, w, h);
      ssCtx.putImageData(imgData, 0, 0);

      ditherState.time += 0.02;
    }

    ssModes.dither = { init: ditherInit, draw: ditherDraw, resize: ditherResize };
