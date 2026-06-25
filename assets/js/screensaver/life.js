/* === Screensaver Mode: Game of Life === */

    // ========== MODE: Game of Life ==========
    var lifeState = { grid: null, cols: 0, rows: 0, cell: 6, frame: 0, staleCount: 0, lastPop: 0 };

    var lifePatterns = {
      rpentomino: [[0,0],[1,0],[0,1],[-1,1],[0,2]],
      acorn: [[0,0],[1,0],[1,2],[3,1],[4,0],[5,0],[6,0]],
      diehard: [[0,0],[1,0],[1,1],[5,1],[6,1],[7,1],[6,-1]],
      glider: [[0,0],[1,0],[2,0],[2,-1],[1,-2]],
      lwss: [[0,0],[3,0],[4,1],[0,2],[4,2],[1,3],[2,3],[3,3],[4,3]],
      pulsar: (function () {
        var p = [];
        var offsets = [
          [2,1],[3,1],[4,1],[8,1],[9,1],[10,1],
          [1,2],[6,2],[7,2],[12,2],
          [1,3],[6,3],[7,3],[12,3],
          [1,4],[6,4],[7,4],[12,4],
          [2,5],[3,5],[4,5],[8,5],[9,5],[10,5]
        ];
        offsets.forEach(function (o) { p.push([o[0], o[1]]); p.push([o[0], 12 - o[1]]); });
        return p;
      })()
    };

    function lifeCreateGrid(cols, rows) {
      return new Uint8Array(cols * rows);
    }

    function lifeGet(grid, cols, rows, x, y) {
      x = (x + cols) % cols;
      y = (y + rows) % rows;
      return grid[y * cols + x];
    }

    function lifeSeed() {
      var cols = lifeState.cols;
      var rows = lifeState.rows;
      var grid = lifeCreateGrid(cols, rows);

      var patternKeys = ["rpentomino", "acorn", "diehard", "glider", "glider", "lwss", "pulsar"];
      for (var p = 0; p < patternKeys.length; p++) {
        var pattern = lifePatterns[patternKeys[p]];
        var ox = Math.floor(Math.random() * (cols - 20)) + 10;
        var oy = Math.floor(Math.random() * (rows - 20)) + 10;
        for (var c = 0; c < pattern.length; c++) {
          var px = (ox + pattern[c][0] + cols) % cols;
          var py = (oy + pattern[c][1] + rows) % rows;
          grid[py * cols + px] = 1;
        }
      }

      var noiseCells = Math.floor(cols * rows * 0.05);
      for (var n = 0; n < noiseCells; n++) {
        var ri = Math.floor(Math.random() * cols * rows);
        grid[ri] = 1;
      }

      lifeState.grid = grid;
      lifeState.frame = 0;
      lifeState.staleCount = 0;
      lifeState.lastPop = 0;
    }

    function lifeStep() {
      var cols = lifeState.cols;
      var rows = lifeState.rows;
      var grid = lifeState.grid;
      var next = lifeCreateGrid(cols, rows);

      for (var y = 0; y < rows; y++) {
        for (var x = 0; x < cols; x++) {
          var neighbors = 0;
          for (var dy = -1; dy <= 1; dy++) {
            for (var dx = -1; dx <= 1; dx++) {
              if (dx === 0 && dy === 0) continue;
              neighbors += lifeGet(grid, cols, rows, x + dx, y + dy);
            }
          }
          var alive = grid[y * cols + x];
          if (alive) {
            next[y * cols + x] = (neighbors === 2 || neighbors === 3) ? 1 : 0;
          } else {
            next[y * cols + x] = (neighbors === 3) ? 1 : 0;
          }
        }
      }

      lifeState.grid = next;
      lifeState.frame++;

      var pop = 0;
      for (var i = 0; i < next.length; i++) pop += next[i];
      if (pop === lifeState.lastPop) {
        lifeState.staleCount++;
      } else {
        lifeState.staleCount = 0;
      }
      lifeState.lastPop = pop;

      if (pop === 0 || lifeState.staleCount > 200) {
        lifeSeed();
      }
    }

    function lifeInit() {
      var cell = lifeState.cell;
      lifeState.cols = Math.floor(ssCanvas.width / cell);
      lifeState.rows = Math.floor(ssCanvas.height / cell);
      lifeSeed();
    }
    function lifeResize() {
      lifeInit();
    }
    function lifeDraw() {
      var accent = ssGetAccent();
      var colors = ssUsePalette() ? ssGetPalette() : null;
      var cell = lifeState.cell;
      var cols = lifeState.cols;
      var rows = lifeState.rows;
      var grid = lifeState.grid;

      if (lifeState.frame % 4 === 0 || lifeState.frame === 0) {
        lifeStep();
      } else {
        lifeState.frame++;
      }

      ssCtx.fillStyle = "#000000";
      ssCtx.fillRect(0, 0, ssCanvas.width, ssCanvas.height);

      if (colors) {
        var halfC = Math.floor(cols / 2);
        var halfR = Math.floor(rows / 2);
        for (var y = 0; y < rows; y++) {
          for (var x = 0; x < cols; x++) {
            if (grid[y * cols + x]) {
              var qi = (x < halfC ? 0 : 1) + (y < halfR ? 0 : 2);
              ssCtx.fillStyle = ssHexToRgba(colors[qi], 0.8);
              ssCtx.fillRect(x * cell + 1, y * cell + 1, cell - 2, cell - 2);
            }
          }
        }
      } else {
        ssCtx.fillStyle = ssHexToRgba(accent, 0.8);
        for (var y = 0; y < rows; y++) {
          for (var x = 0; x < cols; x++) {
            if (grid[y * cols + x]) {
              ssCtx.fillRect(x * cell + 1, y * cell + 1, cell - 2, cell - 2);
            }
          }
        }
      }

      ssCtx.strokeStyle = "rgba(255,255,255,0.02)";
      ssCtx.lineWidth = 0.5;
      for (var gx = 0; gx <= cols; gx++) {
        ssCtx.beginPath();
        ssCtx.moveTo(gx * cell, 0);
        ssCtx.lineTo(gx * cell, rows * cell);
        ssCtx.stroke();
      }
      for (var gy = 0; gy <= rows; gy++) {
        ssCtx.beginPath();
        ssCtx.moveTo(0, gy * cell);
        ssCtx.lineTo(cols * cell, gy * cell);
        ssCtx.stroke();
      }
    }

    ssModes.life = { init: lifeInit, draw: lifeDraw, resize: lifeResize };
