/* === Screensaver Mode: Compass (ASCII Dot Matrix) === */

    // A grid of random glyphs. Mouse interaction makes nearby cells cycle
    // through characters. Idle cells hold still. Sparse idle pattern slowly
    // activates distant cells to cycle on their own.

    (function () {
      var SPACING = 16;
      var FONT_SIZE = 12;
      var MOUSE_RADIUS = 60;

      var GLYPHS = '░▒▓│┤╡╢╖╕╣║╗╝╜╛┐└┴┬├─┼╞╟╚╔╩╦╠═╬╧╨╤╥╙╘╒╓╫╪┘┌█▄▌▐▀αβΓπΣσμτΦΘΩδ∞φε∩≡±≥≤⌐¬÷≈°∙·√ⁿ²■';

      var compassState = {
        step: 0,
        glyphs: null,
        cycling: null,   // per-cell: frames remaining to cycle
        cols: 0,
        rows: 0
      };

      function compassInit() {
        compassState.step = 0;
        var w = ssCanvas.width, h = ssCanvas.height;
        compassState.cols = Math.ceil(w / SPACING) + 1;
        compassState.rows = Math.ceil(h / SPACING) + 1;
        var total = compassState.cols * compassState.rows;
        compassState.glyphs = [];
        compassState.cycling = new Int16Array(total);
        for (var i = 0; i < total; i++) {
          compassState.glyphs.push(GLYPHS[Math.floor(Math.random() * GLYPHS.length)]);
        }
      }

      function compassResize() {
        compassInit();
      }

      function compassDraw() {
        var w = ssCanvas.width;
        var h = ssCanvas.height;
        var accent = ssGetAccent();
        var palette = ssUsePalette() ? ssGetPalette() : null;
        var step = compassState.step;
        var cols = compassState.cols;
        var rows = compassState.rows;
        var glyphs = compassState.glyphs;
        var cycling = compassState.cycling;

        var mx = ssMouseState.x, my = ssMouseState.y;
        var hasMouse = mx >= 0;

        ssCtx.fillStyle = "#000000";
        ssCtx.fillRect(0, 0, w, h);

        ssCtx.font = FONT_SIZE + "px monospace";
        ssCtx.textAlign = "center";
        ssCtx.textBaseline = "middle";

        var t = step * 0.015;

        // Idle: inverted voronoi — cells near region boundaries activate
        if (step % 8 === 0) {
          var total = cols * rows;
          var NUM_SEEDS = 8;
          var seeds = [];
          for (var s = 0; s < NUM_SEEDS; s++) {
            seeds.push({
              x: (0.5 + 0.4 * Math.sin(t * 0.12 * (s + 1) + s * 2.1)) * w,
              y: (0.5 + 0.4 * Math.cos(t * 0.1 * (s + 1) + s * 1.7)) * h
            });
          }
          for (var k = 0; k < total; k++) {
            if (cycling[k] <= 0) {
              var col3 = k % cols;
              var row3 = Math.floor(k / cols);
              var px = col3 * SPACING + SPACING * 0.5;
              var py = row3 * SPACING + SPACING * 0.5;
              var d1 = Infinity, d2 = Infinity;
              for (var s2 = 0; s2 < NUM_SEEDS; s2++) {
                var dd = Math.abs(px - seeds[s2].x) + Math.abs(py - seeds[s2].y);
                if (dd < d1) { d2 = d1; d1 = dd; }
                else if (dd < d2) { d2 = dd; }
              }
              var edge = d2 - d1;
              if (edge < 18) {
                cycling[k] = 12 + Math.floor(Math.random() * 15);
              }
            }
          }
        }

        for (var row = 0; row < rows; row++) {
          for (var col = 0; col < cols; col++) {
            var idx = row * cols + col;
            var cx = col * SPACING + SPACING * 0.5;
            var cy = row * SPACING + SPACING * 0.5;

            // Mouse activates cycling on the cell directly under the cursor
            if (hasMouse) {
              var dx = Math.abs(cx - mx);
              var dy = Math.abs(cy - my);
              if (dx < SPACING * 0.6 && dy < SPACING * 0.6) {
                cycling[idx] = Math.max(cycling[idx], 10);
              }
            }

            var isCycling = cycling[idx] > 0;

            // Cycle glyph every 3 frames if active
            if (isCycling && step % 3 === 0) {
              glyphs[idx] = GLYPHS[Math.floor(Math.random() * GLYPHS.length)];
              cycling[idx]--;
            }

            // Dim static cells, bright cycling cells
            var alpha = isCycling ? 0.85 : 0.15;

            // Color
            if (palette) {
              if (isCycling && hasMouse) {
                var dx2 = Math.abs(cx - mx);
                var dy2 = Math.abs(cy - my);
                if (dx2 < SPACING * 0.6 && dy2 < SPACING * 0.6) {
                  var cA = ssHexToRgb(palette[3]);
                  ssCtx.fillStyle = 'rgba(' + cA.r + ',' + cA.g + ',' + cA.b + ',' + alpha + ')';
                } else {
                  var cB = ssHexToRgb(palette[0]);
                  ssCtx.fillStyle = 'rgba(' + cB.r + ',' + cB.g + ',' + cB.b + ',' + alpha + ')';
                }
              } else {
                var cC = ssHexToRgb(palette[isCycling ? 1 : 0]);
                ssCtx.fillStyle = 'rgba(' + cC.r + ',' + cC.g + ',' + cC.b + ',' + alpha + ')';
              }
            } else {
              ssCtx.fillStyle = ssHexToRgba(accent, alpha);
            }

            ssCtx.fillText(glyphs[idx], cx, cy);
          }
        }

        compassState.step++;
      }

      ssModes['dot-matrix'] = { init: compassInit, draw: compassDraw, resize: compassResize, meta: { name: "Dot Matrix", icon: "grip", desc: "Flickering dot grid — mouse sends ripples through the field" } };
    })();
