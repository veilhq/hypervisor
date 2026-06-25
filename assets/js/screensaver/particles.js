/* === Screensaver Mode: Particles (SPH Fluid Simulation) === */

    // ========== MODE: Particles ==========
    var particleState = {
      particles: [],
      count: 1500,
      mouseX: -1,
      mouseY: -1,
      mouseRadius: 180,
      prevMouseX: -1,
      prevMouseY: -1,
      smoothingRadius: 40,
      restDensity: 1.0,
      stiffness: 200,
      viscosity: 0.3,
      gravity: 0.0,
      grid: null,
      gridCellSize: 40,
      gridCols: 0,
      gridRows: 0
    };

    function sphPoly6(distSq, h) {
      var hSq = h * h;
      if (distSq >= hSq) return 0;
      var diff = hSq - distSq;
      return diff * diff * diff;
    }

    function sphSpikyGrad(dist, h) {
      if (dist >= h || dist < 0.001) return 0;
      var diff = h - dist;
      return diff * diff;
    }

    function sphViscosityLaplacian(dist, h) {
      if (dist >= h) return 0;
      return (h - dist);
    }

    function gridClear() {
      var total = particleState.gridCols * particleState.gridRows;
      if (!particleState.grid || particleState.grid.length !== total) {
        particleState.grid = new Array(total);
      }
      for (var i = 0; i < total; i++) {
        particleState.grid[i] = null;
      }
    }

    function gridInsert(particles) {
      var cellSize = particleState.gridCellSize;
      var cols = particleState.gridCols;
      var rows = particleState.gridRows;
      var grid = particleState.grid;
      for (var i = 0; i < particles.length; i++) {
        var p = particles[i];
        var cx = Math.floor(p.x / cellSize);
        var cy = Math.floor(p.y / cellSize);
        if (cx < 0) cx = 0; if (cx >= cols) cx = cols - 1;
        if (cy < 0) cy = 0; if (cy >= rows) cy = rows - 1;
        var idx = cy * cols + cx;
        p._next = grid[idx];
        grid[idx] = p;
      }
    }

    function gridGetNeighbors(px, py, callback) {
      var cellSize = particleState.gridCellSize;
      var cols = particleState.gridCols;
      var rows = particleState.gridRows;
      var grid = particleState.grid;
      var cx = Math.floor(px / cellSize);
      var cy = Math.floor(py / cellSize);

      for (var dy = -1; dy <= 1; dy++) {
        var ny = cy + dy;
        if (ny < 0 || ny >= rows) continue;
        for (var dx = -1; dx <= 1; dx++) {
          var nx = cx + dx;
          if (nx < 0 || nx >= cols) continue;
          var node = grid[ny * cols + nx];
          while (node) {
            callback(node);
            node = node._next;
          }
        }
      }
    }

    function particleInit() {
      particleState.particles = [];
      particleState.mouseX = -1;
      particleState.mouseY = -1;
      particleState.prevMouseX = -1;
      particleState.prevMouseY = -1;

      particleState.gridCellSize = particleState.smoothingRadius;
      particleState.gridCols = Math.ceil(ssCanvas.width / particleState.gridCellSize) + 1;
      particleState.gridRows = Math.ceil(ssCanvas.height / particleState.gridCellSize) + 1;

      var count = particleState.count;
      var w = ssCanvas.width;
      var h = ssCanvas.height;
      var aspect = w / h;
      var rowCount = Math.round(Math.sqrt(count / aspect));
      var colCount = Math.round(count / rowCount);
      var spacingX = w / (colCount + 1);
      var spacingY = h / (rowCount + 1);

      for (var i = 0; i < count; i++) {
        var row = Math.floor(i / colCount);
        var col = i % colCount;
        particleState.particles.push({
          x: (col + 1) * spacingX + (Math.random() - 0.5) * spacingX * 0.5,
          y: (row + 1) * spacingY + (Math.random() - 0.5) * spacingY * 0.5,
          vx: 0,
          vy: 0,
          density: 0,
          pressure: 0,
          fx: 0,
          fy: 0,
          _next: null
        });
      }
    }

    function particleResize() {
      particleState.gridCols = Math.ceil(ssCanvas.width / particleState.gridCellSize) + 1;
      particleState.gridRows = Math.ceil(ssCanvas.height / particleState.gridCellSize) + 1;
      var w = ssCanvas.width;
      var h = ssCanvas.height;
      for (var i = 0; i < particleState.particles.length; i++) {
        var p = particleState.particles[i];
        if (p.x > w) p.x = w - 1;
        if (p.y > h) p.y = h - 1;
      }
    }

    function particleDraw() {
      var accent = ssGetAccent();
      var colors = ssUsePalette() ? ssGetPalette() : null;
      var w = ssCanvas.width;
      var h = ssCanvas.height;
      var mx = particleState.mouseX;
      var my = particleState.mouseY;
      var pmx = particleState.prevMouseX;
      var pmy = particleState.prevMouseY;
      var mr = particleState.mouseRadius;
      var particles = particleState.particles;
      var H = particleState.smoothingRadius;
      var restDensity = particleState.restDensity;
      var stiffness = particleState.stiffness;
      var viscosity = particleState.viscosity;
      var dt = 0.016;

      gridClear();
      gridInsert(particles);

      var poly6Factor = 4.0 / (Math.PI * Math.pow(H, 8));
      for (var i = 0; i < particles.length; i++) {
        var pi = particles[i];
        var density = 0;
        gridGetNeighbors(pi.x, pi.y, function (pj) {
          var dx = pi.x - pj.x;
          var dy = pi.y - pj.y;
          var distSq = dx * dx + dy * dy;
          density += sphPoly6(distSq, H);
        });
        pi.density = density * poly6Factor + 0.001;
        pi.pressure = stiffness * (pi.density - restDensity);
      }

      var spikyFactor = -30.0 / (Math.PI * Math.pow(H, 5));
      var viscFactor = 40.0 / (Math.PI * Math.pow(H, 5));
      for (var i = 0; i < particles.length; i++) {
        var pi = particles[i];
        var fx = 0, fy = 0;

        gridGetNeighbors(pi.x, pi.y, function (pj) {
          if (pj === pi) return;
          var dx = pi.x - pj.x;
          var dy = pi.y - pj.y;
          var distSq = dx * dx + dy * dy;
          if (distSq >= H * H || distSq < 0.0001) return;
          var dist = Math.sqrt(distSq);

          var pressureAvg = (pi.pressure + pj.pressure) * 0.5;
          var gradMag = spikyFactor * sphSpikyGrad(dist, H) / pj.density;
          fx += (dx / dist) * pressureAvg * gradMag;
          fy += (dy / dist) * pressureAvg * gradMag;

          var lapMag = viscFactor * sphViscosityLaplacian(dist, H) / pj.density;
          fx += viscosity * (pj.vx - pi.vx) * lapMag;
          fy += viscosity * (pj.vy - pi.vy) * lapMag;
        });

        pi.fx = fx;
        pi.fy = fy;
      }

      var mouseVx = 0, mouseVy = 0;
      if (mx >= 0 && pmx >= 0) {
        mouseVx = (mx - pmx);
        mouseVy = (my - pmy);
      }
      var mouseSpeed = Math.sqrt(mouseVx * mouseVx + mouseVy * mouseVy);

      for (var i = 0; i < particles.length; i++) {
        var p = particles[i];

        p.vx += p.fx * dt;
        p.vy += p.fy * dt;
        p.vy += particleState.gravity;

        if (mx >= 0 && my >= 0) {
          var dx = p.x - mx;
          var dy = p.y - my;
          var dist = Math.sqrt(dx * dx + dy * dy);
          if (dist < mr && dist > 0) {
            var influence = 1.0 - (dist / mr);
            influence = influence * influence;
            var radialForce = influence * 8;
            p.vx += (dx / dist) * radialForce;
            p.vy += (dy / dist) * radialForce;
            if (mouseSpeed > 1) {
              var dragForce = influence * mouseSpeed * 0.4;
              p.vx += (mouseVx / mouseSpeed) * dragForce;
              p.vy += (mouseVy / mouseSpeed) * dragForce;
            }
          }
        }

        p.vx *= 0.985;
        p.vy *= 0.985;
        p.vx += (Math.random() - 0.5) * 0.02;
        p.vy += (Math.random() - 0.5) * 0.02;

        var speed = Math.sqrt(p.vx * p.vx + p.vy * p.vy);
        if (speed > 12) {
          p.vx = (p.vx / speed) * 12;
          p.vy = (p.vy / speed) * 12;
        }

        p.x += p.vx;
        p.y += p.vy;

        var boundary = 5;
        if (p.x < boundary) { p.x = boundary; p.vx *= -0.5; }
        if (p.x > w - boundary) { p.x = w - boundary; p.vx *= -0.5; }
        if (p.y < boundary) { p.y = boundary; p.vy *= -0.5; }
        if (p.y > h - boundary) { p.y = h - boundary; p.vy *= -0.5; }
      }

      particleState.prevMouseX = mx;
      particleState.prevMouseY = my;

      // Render
      ssCtx.fillStyle = "rgba(0, 0, 0, 0.12)";
      ssCtx.fillRect(0, 0, w, h);

      for (var i = 0; i < particles.length; i++) {
        var p = particles[i];
        var speed = Math.sqrt(p.vx * p.vx + p.vy * p.vy);

        var col;
        if (colors) {
          var normSpeed = Math.min(speed / 8, 1);
          var pos = normSpeed * (colors.length - 1);
          var ci = Math.min(colors.length - 2, Math.floor(pos));
          var frac = pos - ci;
          var cA = ssHexToRgb(colors[ci]);
          var cB = ssHexToRgb(colors[ci + 1]);
          var r = Math.round(cA.r + (cB.r - cA.r) * frac);
          var g = Math.round(cA.g + (cB.g - cA.g) * frac);
          var b = Math.round(cA.b + (cB.b - cA.b) * frac);
          col = "rgb(" + r + "," + g + "," + b + ")";
        } else {
          var alpha = 0.35 + Math.min(speed / 8, 1) * 0.65;
          col = ssHexToRgba(accent, alpha);
        }

        if (speed > 0.8) {
          var len = Math.min(speed * 2.2, 16);
          var nx = p.vx / speed;
          var ny = p.vy / speed;
          ssCtx.beginPath();
          ssCtx.moveTo(p.x - nx * len * 0.5, p.y - ny * len * 0.5);
          ssCtx.lineTo(p.x + nx * len * 0.5, p.y + ny * len * 0.5);
          ssCtx.strokeStyle = col;
          ssCtx.lineWidth = 2;
          ssCtx.lineCap = "round";
          ssCtx.stroke();
        } else {
          ssCtx.beginPath();
          ssCtx.arc(p.x, p.y, 1.5, 0, Math.PI * 2);
          ssCtx.fillStyle = col;
          ssCtx.fill();
        }
      }
    }

    ssModes.particles = { init: particleInit, draw: particleDraw, resize: particleResize };

    // Expose particleState for mouse tracking in engine
    var ssParticleState = particleState;
