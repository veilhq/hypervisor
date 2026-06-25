/* === Screensaver Mode: Worm === */

    // ========== MODE: Worm ==========
    var wormState = { worms: [] };

    function wormInit() {
      wormState.worms = [];
      var count = 5 + Math.floor(Math.random() * 3);
      for (var i = 0; i < count; i++) {
        wormState.worms.push({
          x: Math.random() * ssCanvas.width,
          y: Math.random() * ssCanvas.height,
          angle: Math.random() * Math.PI * 2,
          speed: 1.2 + Math.random() * 1.5,
          turnRate: 0.04 + Math.random() * 0.06,
          trail: [],
          maxTrail: 120 + Math.floor(Math.random() * 80),
          hueOffset: i * 50
        });
      }
    }
    function wormResize() {}
    function wormDraw() {
      var accent = ssGetAccent();
      var colors = ssUsePalette() ? ssGetPalette() : null;
      var rgb = ssHexToRgb(accent);

      ssCtx.fillStyle = "rgba(0, 0, 0, 0.06)";
      ssCtx.fillRect(0, 0, ssCanvas.width, ssCanvas.height);

      for (var i = 0; i < wormState.worms.length; i++) {
        var w = wormState.worms[i];

        w.angle += (Math.random() - 0.5) * w.turnRate * 2;
        w.x += Math.cos(w.angle) * w.speed;
        w.y += Math.sin(w.angle) * w.speed;

        if (w.x < 0) w.x += ssCanvas.width;
        if (w.x > ssCanvas.width) w.x -= ssCanvas.width;
        if (w.y < 0) w.y += ssCanvas.height;
        if (w.y > ssCanvas.height) w.y -= ssCanvas.height;

        w.trail.push({ x: w.x, y: w.y });
        if (w.trail.length > w.maxTrail) w.trail.shift();

        var wormRgb;
        if (colors) {
          wormRgb = ssHexToRgb(colors[i % colors.length]);
        } else {
          wormRgb = {
            r: Math.min(255, rgb.r + w.hueOffset * 0.3),
            g: Math.min(255, rgb.g + w.hueOffset * 0.1),
            b: Math.min(255, rgb.b + w.hueOffset * 0.5)
          };
        }

        for (var t = 1; t < w.trail.length; t++) {
          var alpha = (t / w.trail.length) * 0.7;
          var prev = w.trail[t - 1];
          var curr = w.trail[t];

          var dx = Math.abs(curr.x - prev.x);
          var dy = Math.abs(curr.y - prev.y);
          if (dx > ssCanvas.width * 0.5 || dy > ssCanvas.height * 0.5) continue;

          ssCtx.beginPath();
          ssCtx.moveTo(prev.x, prev.y);
          ssCtx.lineTo(curr.x, curr.y);
          ssCtx.strokeStyle = "rgba(" + Math.floor(wormRgb.r) + "," + Math.floor(wormRgb.g) + "," + Math.floor(wormRgb.b) + "," + alpha + ")";
          ssCtx.lineWidth = 2;
          ssCtx.stroke();
        }

        var headCol = colors ? colors[i % colors.length] : accent;
        ssCtx.beginPath();
        ssCtx.arc(w.x, w.y, 3, 0, Math.PI * 2);
        ssCtx.fillStyle = ssHexToRgba(headCol, 0.9);
        ssCtx.fill();
      }
    }

    ssModes.worm = { init: wormInit, draw: wormDraw, resize: wormResize };
