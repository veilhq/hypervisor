/* === Screensaver Mode: Orbits === */

(function () {
  "use strict";

    // ========== MODE: Orbiting Great-Circle Arcs ==========
    // A sphere woven from great-circle arcs. Each arc orbits its great circle
    // continuously, drawing a fading trail behind it. The sphere never
    // dissolves — it remains intact and rotating.
    //
    // Trails are parametric (continuous angle), not sample-snapped, so motion
    // is perfectly smooth regardless of frame rate.
    //
    // 2D canvas rather than gl.LINES: ALIASED_LINE_WIDTH_RANGE is [1,1] in
    // Chromium, so WebGL cannot vary stroke weight, and depth-varying line
    // width is what reads as 3D here.
    //
    // Animation is driven by an internal step counter, not wall-clock time —
    // the engine generates card previews by calling draw() 60x in a tight loop.

    var ARC_COUNT = 34;
    var TRAIL_SEGS = 32;           // line segments drawn per trail
    var TRAIL_ARC = Math.PI * 0.7; // angular length of each trail (radians)

    var orbitState = {
      step: 0,
      arcs: null
    };

    // Deterministic PRNG
    function rand(seed) {
      var x = Math.sin(seed * 127.1 + 311.7) * 43758.5453;
      return x - Math.floor(x);
    }

    function buildArcs(seed) {
      var arcs = [];
      for (var i = 0; i < ARC_COUNT; i++) {
        var z = rand(seed + i * 3.1) * 2 - 1;
        var th = rand(seed + i * 7.7) * Math.PI * 2;
        var rxy = Math.sqrt(Math.max(0, 1 - z * z));
        var n = [rxy * Math.cos(th), rxy * Math.sin(th), z];

        var ref = Math.abs(n[0]) < 0.9 ? [1, 0, 0] : [0, 1, 0];
        var u = [
          ref[1] * n[2] - ref[2] * n[1],
          ref[2] * n[0] - ref[0] * n[2],
          ref[0] * n[1] - ref[1] * n[0]
        ];
        var ul = Math.sqrt(u[0] * u[0] + u[1] * u[1] + u[2] * u[2]) || 1;
        u = [u[0] / ul, u[1] / ul, u[2] / ul];
        var v = [
          n[1] * u[2] - n[2] * u[1],
          n[2] * u[0] - n[0] * u[2],
          n[0] * u[1] - n[1] * u[0]
        ];

        var speed = 0.012 + rand(seed + i * 5.3) * 0.010;  // radians per frame
        var phase = rand(seed + i * 11.1) * Math.PI * 2;

        arcs.push({ u: u, v: v, speed: speed, phase: phase, colorIdx: i % 4 });
      }
      return arcs;
    }

    function orbitInit() {
      orbitState.step = 0;
      orbitState.arcs = buildArcs(1);
    }

    function orbitResize() {}

    function orbitDraw() {
      var w = ssCanvas.width;
      var h = ssCanvas.height;
      var accent = ssGetAccent();
      var palette = ssUsePalette() ? ssGetPalette() : null;

      var step = orbitState.step;

      ssCtx.fillStyle = "#000000";
      ssCtx.fillRect(0, 0, w, h);

      var cx = w * 0.5;
      var cy = h * 0.5;
      var R = Math.min(w, h) * 0.34;

      // Global sphere rotation
      var ay = step * 0.0042;
      var ax = step * 0.0027;
      var cay = Math.cos(ay), say = Math.sin(ay);
      var cax = Math.cos(ax), sax = Math.sin(ax);

      ssCtx.lineCap = "round";

      for (var a = 0; a < orbitState.arcs.length; a++) {
        var arc = orbitState.arcs[a];
        var col = palette ? palette[arc.colorIdx] : accent;

        // Head angle — continuous, no snapping
        var headAngle = arc.phase + step * arc.speed;

        // Build projected trail points from head backward
        var pts = [];
        for (var i = 0; i <= TRAIL_SEGS; i++) {
          var frac = i / TRAIL_SEGS;  // 0 = head, 1 = tail
          var angle = headAngle - frac * TRAIL_ARC;
          var ct = Math.cos(angle), st = Math.sin(angle);
          var px = arc.u[0] * ct + arc.v[0] * st;
          var py = arc.u[1] * ct + arc.v[1] * st;
          var pz = arc.u[2] * ct + arc.v[2] * st;

          // Rotate Y then X
          var rx = px * cay + pz * say;
          var rz = -px * say + pz * cay;
          var ry = py * cax - rz * sax;
          var rz2 = py * sax + rz * cax;

          // Mild perspective
          var s = 1.55 / (1.55 + rz2 * 0.42);
          pts.push({ x: cx + rx * R * s, y: cy + ry * R * s, z: rz2 });
        }

        // Draw segments with per-segment alpha fade + depth
        for (var j = 0; j < TRAIL_SEGS; j++) {
          var p0 = pts[j];
          var p1 = pts[j + 1];

          var fadeT = j / TRAIL_SEGS;
          var fade = 1.0 - fadeT * fadeT;

          var avgZ = (p0.z + p1.z) * 0.5;
          var depthAlpha = avgZ >= 0 ? 0.90 : 0.22;
          var lw = avgZ >= 0 ? 1.5 : 0.7;

          var alpha = fade * depthAlpha;
          if (alpha < 0.015) continue;

          ssCtx.beginPath();
          ssCtx.moveTo(p0.x, p0.y);
          ssCtx.lineTo(p1.x, p1.y);
          ssCtx.strokeStyle = ssHexToRgba(col, alpha);
          ssCtx.lineWidth = lw;
          ssCtx.stroke();
        }
      }

      orbitState.step++;
    }

    ssModes.orbits = { init: orbitInit, draw: orbitDraw, resize: orbitResize, meta: { name: "Orbits", icon: "orbit", desc: "Great-circle arcs orbiting a rotating sphere" } };
})();
