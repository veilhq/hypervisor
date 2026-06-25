/* === Screensaver Mode: Starfield === */

    // ========== MODE: Starfield ==========
    var starState = { stars: [], count: 400, speed: 4 };

    function starInit() {
      starState.stars = [];
      for (var i = 0; i < starState.count; i++) {
        starState.stars.push({
          x: (Math.random() - 0.5) * ssCanvas.width * 2,
          y: (Math.random() - 0.5) * ssCanvas.height * 2,
          z: Math.random() * ssCanvas.width
        });
      }
    }
    function starResize() {}
    function starDraw() {
      var accent = ssGetAccent();
      var colors = ssUsePalette() ? ssGetPalette() : null;
      var cx = ssCanvas.width / 2;
      var cy = ssCanvas.height / 2;
      var w = ssCanvas.width;

      ssCtx.fillStyle = "rgba(0, 0, 0, 0.15)";
      ssCtx.fillRect(0, 0, ssCanvas.width, ssCanvas.height);

      for (var i = 0; i < starState.stars.length; i++) {
        var s = starState.stars[i];
        s.z -= starState.speed;
        if (s.z <= 0) {
          s.x = (Math.random() - 0.5) * w * 2;
          s.y = (Math.random() - 0.5) * ssCanvas.height * 2;
          s.z = w;
        }
        var sx = (s.x / s.z) * w * 0.3 + cx;
        var sy = (s.y / s.z) * w * 0.3 + cy;
        var r = Math.max(0.3, (1 - s.z / w) * 2.5);
        var alpha = Math.max(0.1, 1 - s.z / w);

        var col = colors ? colors[i % colors.length] : accent;

        ssCtx.beginPath();
        ssCtx.arc(sx, sy, r, 0, Math.PI * 2);
        ssCtx.fillStyle = ssHexToRgba(col, alpha);
        ssCtx.fill();

        if (r > 1) {
          var prevSx = (s.x / (s.z + starState.speed * 4)) * w * 0.3 + cx;
          var prevSy = (s.y / (s.z + starState.speed * 4)) * w * 0.3 + cy;
          ssCtx.beginPath();
          ssCtx.moveTo(prevSx, prevSy);
          ssCtx.lineTo(sx, sy);
          ssCtx.strokeStyle = ssHexToRgba(col, alpha * 0.4);
          ssCtx.lineWidth = r * 0.5;
          ssCtx.stroke();
        }
      }
    }

    ssModes.starfield = { init: starInit, draw: starDraw, resize: starResize };
