/* === Screensaver Mode: Grid === */

    // ========== MODE: Infinite Perspective Grid ==========
    // Continuously scrolling perspective grid — lines move smoothly toward the viewer.
    var gridState = {
      zOffset: 0,
      speed: 0.015,
      numRows: 80,
      numCols: 40,
      fov: 200,
      gridSpacing: 1.2,
      mouseX: -1,
      mouseY: -1,
      tilt: 0,            // current tilt in radians
      maxTilt: 0.2,       // ~11.5 degrees max rotation
      lerpSpeed: 0.02,
      baseSpeed: 0.015,
      minSpeed: 0.002,
      maxSpeed: 0.06,
      mouseEnabled: true
    };

    // Load mouse preference
    var GRID_MOUSE_KEY = "hypervisor-screensaver-grid-mouse";
    try {
      var savedGridMouse = localStorage.getItem(GRID_MOUSE_KEY);
      if (savedGridMouse === "0") gridState.mouseEnabled = false;
    } catch (e) {}

    function gridInit() {
      gridState.zOffset = 0;
      gridState.tilt = 0;
      gridState.mouseX = -1;
      gridState.mouseY = -1;
      gridState.speed = gridState.baseSpeed;
    }

    function gridResize() {}

    function gridDraw() {
      var w = ssCanvas.width;
      var h = ssCanvas.height;
      var accent = ssGetAccent();

      // Lerp tilt angle based on mouse X
      if (gridState.mouseEnabled && gridState.mouseX >= 0) {
        var targetTilt = ((gridState.mouseX / w) - 0.5) * 2 * gridState.maxTilt;
        gridState.tilt += (targetTilt - gridState.tilt) * gridState.lerpSpeed;
      } else {
        gridState.tilt += (0 - gridState.tilt) * gridState.lerpSpeed * 0.5;
      }

      // Map mouse Y to scroll speed: top = slow, bottom = fast
      if (gridState.mouseEnabled && gridState.mouseY >= 0) {
        var yNorm = gridState.mouseY / h;
        var targetSpeed = gridState.minSpeed + yNorm * (gridState.maxSpeed - gridState.minSpeed);
        gridState.speed += (targetSpeed - gridState.speed) * 0.05;
      } else {
        gridState.speed += (gridState.baseSpeed - gridState.speed) * 0.03;
      }

      var cx = w * 0.5;
      var horizonY = h * 0.38;
      var fov = gridState.fov;
      var spacing = gridState.gridSpacing;

      // Clear (no transform — full canvas)
      ssCtx.fillStyle = "rgba(0, 0, 0, 0.4)";
      ssCtx.fillRect(0, 0, w, h);

      // Apply tilt rotation around the vanishing point
      ssCtx.save();
      ssCtx.translate(cx, horizonY);
      ssCtx.rotate(gridState.tilt);
      ssCtx.translate(-cx, -horizonY);

      // Advance Z continuously (negative = grid moves toward viewer)
      gridState.zOffset -= gridState.speed;
      if (gridState.zOffset < 0) gridState.zOffset += spacing;

      // --- Horizontal lines (rows receding into distance) ---
      var numRows = gridState.numRows;
      for (var i = 0; i < numRows; i++) {
        var z = (i * spacing) + gridState.zOffset;
        if (z <= 0.01) continue;

        var scale = fov / z;
        var sy = horizonY + scale * 0.8;

        if (sy > h + 60 || sy < horizonY - 2) continue;

        var depthNorm = Math.min(z / (numRows * spacing * 0.5), 1);
        var alpha = (1 - depthNorm) * 0.7 + 0.05;
        var lineW = (1 - depthNorm) * 1.2 + 0.3;

        var halfWidth = (w * 0.8) * scale / fov;
        var leftX = cx - halfWidth * fov * 0.6;
        var rightX = cx + halfWidth * fov * 0.6;

        ssCtx.beginPath();
        ssCtx.moveTo(leftX, sy);
        ssCtx.lineTo(rightX, sy);
        ssCtx.strokeStyle = ssHexToRgba(accent, alpha);
        ssCtx.lineWidth = lineW;
        ssCtx.stroke();
      }

      // --- Vertical lines (columns converging to vanishing point) ---
      var numCols = gridState.numCols;
      var halfCols = Math.floor(numCols / 2);
      var farZ = numRows * spacing * 0.8;
      var nearZ = 0.05;

      for (var j = -halfCols; j <= halfCols; j++) {
        var worldX = j * spacing;

        var farScale = fov / farZ;
        var farSx = cx + worldX * farScale;
        var farSy = horizonY + farScale * 0.8;

        var nearScale = fov / nearZ;
        var nearSx = cx + worldX * nearScale;
        var nearSy = horizonY + nearScale * 0.8;

        if (farSx < -10 && nearSx < -10) continue;
        if (farSx > w + 10 && nearSx > w + 10) continue;

        var edgeFactor = 1 - Math.pow(Math.abs(j) / halfCols, 1.5);
        var alpha2 = edgeFactor * 0.5;

        ssCtx.beginPath();
        ssCtx.moveTo(farSx, farSy);
        ssCtx.lineTo(nearSx, nearSy);
        ssCtx.strokeStyle = ssHexToRgba(accent, alpha2);
        ssCtx.lineWidth = 0.7;
        ssCtx.stroke();
      }

      // --- Horizon glow ---
      ssCtx.beginPath();
      ssCtx.moveTo(0, horizonY);
      ssCtx.lineTo(w, horizonY);
      ssCtx.strokeStyle = ssHexToRgba(accent, 0.5);
      ssCtx.lineWidth = 1;
      ssCtx.stroke();

      // Vanishing point glow
      var grad = ssCtx.createRadialGradient(cx, horizonY, 0, cx, horizonY, w * 0.12);
      grad.addColorStop(0, ssHexToRgba(accent, 0.15));
      grad.addColorStop(1, "rgba(0,0,0,0)");
      ssCtx.fillStyle = grad;
      ssCtx.fillRect(0, 0, w, h);

      ssCtx.restore();
    }

    ssModes.grid = { init: gridInit, draw: gridDraw, resize: gridResize };

    // Expose grid mouse toggle for settings UI
    window.__gridMouse = {
      get: function () { return gridState.mouseEnabled; },
      set: function (v) {
        gridState.mouseEnabled = !!v;
        try { localStorage.setItem(GRID_MOUSE_KEY, v ? "1" : "0"); } catch (e) {}
        if (typeof savePreference === "function") savePreference(GRID_MOUSE_KEY, v ? "1" : "0");
      }
    };

    // Track mouse for grid tilt and speed
    document.querySelector(".screensaver-overlay").addEventListener("mousemove", function (e) {
      gridState.mouseX = e.clientX;
      gridState.mouseY = e.clientY;
    });
    document.querySelector(".screensaver-overlay").addEventListener("mouseleave", function () {
      gridState.mouseX = -1;
      gridState.mouseY = -1;
    });
