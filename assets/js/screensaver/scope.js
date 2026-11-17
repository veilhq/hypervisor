/* === Screensaver Mode: Scope Trace === */

// The Hyperagent status sprite's scope trace across a full-screen dot matrix at the sprite's LED size: one point travels a drifting Lissajous path.
(function () {
  "use strict";

  // LED pitch and lit side in px, matching the sprite; brightness steps; share of the half-grid the path reaches.
  var PITCH = 7, LED = 5, LEVELS = 8, REACH = 0.9;
  // Head speed in cells per second, trail length in seconds, and the frame step in seconds.
  var SPEED = 96, TAIL_S = 12, FRAME_S = 1 / 60;
  // Share of the trail, from the head back, drawn as a 2x2 stroke before it thins to one LED.
  var THICK = 0.35;
  // Seconds of drift per real second; the sprite's frequency drift runs at 1.
  var DRIFT = 1;
  // Extra x-phase speed, as a share of the head's x rate, that swings the x/y phase so the whole figure reshapes like the sprite's.
  var MORPH = 0.4;
  // Soft glow around the leading point: radius in cells and peak opacity.
  var GLOW_CELLS = 2.5, GLOW_ALPHA = 0.45;
  // Phosphor: trail samples further apart than this many frames count as separate passes, and their ink adds where they cross.
  var PASS_GAP = 60;
  // Echo: a pulse that runs from the head back to the trail's end; seconds between echoes, run time, length as a share of the trail, and ink.
  var ECHO_MIN_S = 20, ECHO_MAX_S = 60, ECHO_RUN_S = 4, ECHO_LEN = 0.03, ECHO_INK = 0.6;

  var TAIL_FRAMES = Math.round(TAIL_S / FRAME_S), ECHO_FRAMES = Math.round(ECHO_RUN_S / FRAME_S);

  var scope = {
    cols: 0, rows: 0, originX: 0, originY: 0, ampX: 0, ampY: 0, rate: 0,
    time: 0, seed: 0, fx: 3, fy: 2, angleX: 0, angleY: 0, trail: null, echoWait: 0, echoAge: -1,
    cells: null, peak: null, last: null, echo: null, base: null, inks: null, live: null
  };
  function echoDelay() {
    return Math.round((ECHO_MIN_S + Math.random() * (ECHO_MAX_S - ECHO_MIN_S)) / FRAME_S);
  }

  // Resolves a token to [r, g, b] through a 1px canvas, so any CSS color syntax works.
  var swatch = null;
  function tokenRgb(token) {
    var probe = document.createElement("span");
    probe.style.color = "var(" + token + ")";
    document.body.appendChild(probe);
    var color = getComputedStyle(probe).color;
    probe.remove();
    if (!swatch) {
      var canvas = document.createElement("canvas");
      canvas.width = canvas.height = 1;
      swatch = canvas.getContext("2d", { willReadFrequently: true });
    }
    swatch.clearRect(0, 0, 1, 1);
    swatch.fillStyle = color;
    swatch.fillRect(0, 0, 1, 1);
    var pixel = swatch.getImageData(0, 0, 1, 1).data;
    return [pixel[0], pixel[1], pixel[2]];
  }
  function rgb(c, alpha) {
    return alpha === undefined ? "rgb(" + c[0] + "," + c[1] + "," + c[2] + ")" : "rgba(" + c[0] + "," + c[1] + "," + c[2] + "," + alpha + ")";
  }

  // Sizes the grid to the canvas (odd counts so one cell sits on the exact center) and paints the unlit field once.
  function scopeLayout() {
    var width = ssCanvas.width, height = ssCanvas.height;
    scope.cols = Math.max(3, Math.floor(width / PITCH));
    scope.rows = Math.max(3, Math.floor(height / PITCH));
    if (scope.cols % 2 === 0) scope.cols--;
    if (scope.rows % 2 === 0) scope.rows--;
    scope.originX = Math.floor((width - scope.cols * PITCH) / 2);
    scope.originY = Math.floor((height - scope.rows * PITCH) / 2);
    scope.ampX = (scope.cols - 1) / 2 * REACH;
    scope.ampY = (scope.rows - 1) / 2 * REACH;
    // Curve radians per second that move the head at about SPEED cells per second along the path.
    scope.rate = SPEED / Math.max(1, Math.hypot(scope.ampX * 3, scope.ampY * 2) / Math.SQRT2);
    scope.cells = new Float32Array(scope.cols * scope.rows);
    scope.peak = new Float32Array(scope.cols * scope.rows);
    scope.last = new Int32Array(scope.cols * scope.rows);
    scope.echo = new Float32Array(scope.cols * scope.rows);
    scope.trail = new Float32Array(TAIL_FRAMES * 2);

    var bg = tokenRgb("--bg"), off = tokenRgb("--border");
    scope.live = tokenRgb("--live");
    scope.inks = [];
    for (var level = 0; level < LEVELS; level++) {
      var t = level / (LEVELS - 1);
      scope.inks.push(rgb([0, 1, 2].map(function (ch) { return Math.round(off[ch] + (scope.live[ch] - off[ch]) * t); })));
    }

    scope.base = document.createElement("canvas");
    scope.base.width = width;
    scope.base.height = height;
    var baseCtx = scope.base.getContext("2d");
    baseCtx.fillStyle = rgb(bg);
    baseCtx.fillRect(0, 0, width, height);
    baseCtx.fillStyle = scope.inks[0];
    var inset = (PITCH - LED) / 2;
    for (var y = 0; y < scope.rows; y++) {
      for (var x = 0; x < scope.cols; x++) {
        baseCtx.fillRect(scope.originX + x * PITCH + inset, scope.originY + y * PITCH + inset, LED, LED);
      }
    }
    advance();
  }

  // Moves the head one frame: each axis's phase advances at its drifting frequency, and the x phase swings ahead and back so the figure morphs.
  function advance() {
    scope.time += FRAME_S * DRIFT;
    scope.fx = 3 + 0.4 * Math.sin(scope.time * 0.11 + scope.seed);
    scope.fy = 2 + 0.25 * Math.sin(scope.time * 0.07);
    scope.angleX += scope.fx * (1 + MORPH * Math.cos(scope.time * 0.11 + scope.seed)) * scope.rate * FRAME_S;
    scope.angleY += scope.fy * scope.rate * FRAME_S;
  }
  // Recomputes the whole trail back from the head with the current frequencies, so the visible path reshapes as they drift.
  function sampleTrail() {
    var trail = scope.trail, step = scope.rate * FRAME_S, midX = (scope.cols - 1) / 2, midY = (scope.rows - 1) / 2;
    for (var k = 0; k < TAIL_FRAMES; k++) {
      var u = (k - (TAIL_FRAMES - 1)) * step;
      trail[k * 2] = midX + scope.ampX * Math.sin(scope.angleX + scope.fx * u);
      trail[k * 2 + 1] = midY + scope.ampY * Math.sin(scope.angleY + scope.fy * u);
    }
  }

  function scopeInit() {
    scope.seed = Math.random() * Math.PI * 2;
    scope.time = Math.random() * 600;
    scope.angleX = scope.seed;
    scope.angleY = 0;
    scope.echoWait = echoDelay();
    scope.echoAge = -1;
    scopeLayout();
  }

  function scopeDraw() {
    var ctx = ssCtx, cols = scope.cols, cells = scope.cells, peak = scope.peak, last = scope.last, echo = scope.echo;
    var trail = scope.trail, inset = (PITCH - LED) / 2;
    ctx.globalCompositeOperation = "source-over";
    ctx.drawImage(scope.base, 0, 0);
    advance();
    sampleTrail();

    // The trail is the head's recent positions, brightest at the head and fading with age; the fresh end draws 2x2 and thins to one LED.
    // Each pass over a cell keeps its peak ink, and separate passes add, so crossings glow like scope phosphor.
    var touched = [], count = trail.length / 2;
    function light(index, ink, sample) {
      if (last[index] === 0) touched.push(index);
      else if (sample - last[index] > PASS_GAP) { cells[index] += peak[index]; peak[index] = 0; }
      last[index] = sample;
      if (ink > peak[index]) peak[index] = ink;
    }
    // Steps between frame samples at under half a cell, so a fast head leaves no gaps.
    for (var p = 0; p < count; p++) {
      var fresh = (p + 1) / count, ink = 0.25 + 0.75 * fresh * fresh;
      var x1 = trail[p * 2], y1 = trail[p * 2 + 1], x0 = p ? trail[p * 2 - 2] : x1, y0 = p ? trail[p * 2 - 1] : y1;
      var steps = Math.max(1, Math.ceil(Math.hypot(x1 - x0, y1 - y0) * 2));
      for (var s = 1; s <= steps; s++) {
        var px = x0 + (x1 - x0) * s / steps, py = y0 + (y1 - y0) * s / steps;
        if (fresh > 1 - THICK) {
          var i = Math.floor(py) * cols + Math.floor(px);
          light(i, ink, p + 1); light(i + 1, ink, p + 1); light(i + cols, ink, p + 1); light(i + cols + 1, ink, p + 1);
        } else {
          light(Math.round(py) * cols + Math.round(px), ink, p + 1);
        }
      }
    }

    // The echo: now and then a short pulse leaves the head and runs back down the trail, adding its ink on top.
    if (scope.echoAge < 0 && --scope.echoWait <= 0) scope.echoAge = 0;
    if (scope.echoAge >= 0) {
      var front = 1 - scope.echoAge / ECHO_FRAMES, from = Math.max(0, Math.floor((front - ECHO_LEN) * count));
      for (var e = from; e < Math.min(count, Math.ceil(front * count)); e++) {
        var echoInk = ECHO_INK * (1 - (front - (e + 1) / count) / ECHO_LEN);
        var ex1 = trail[e * 2], ey1 = trail[e * 2 + 1], ex0 = e ? trail[e * 2 - 2] : ex1, ey0 = e ? trail[e * 2 - 1] : ey1;
        var echoSteps = Math.max(1, Math.ceil(Math.hypot(ex1 - ex0, ey1 - ey0) * 2));
        for (var es = 1; es <= echoSteps; es++) {
          var echoCell = Math.round(ey0 + (ey1 - ey0) * es / echoSteps) * cols + Math.round(ex0 + (ex1 - ex0) * es / echoSteps);
          if (last[echoCell] === 0 && echo[echoCell] === 0) touched.push(echoCell);
          if (echoInk > echo[echoCell]) echo[echoCell] = echoInk;
        }
      }
      if (++scope.echoAge > ECHO_FRAMES) { scope.echoAge = -1; scope.echoWait = echoDelay(); }
    }

    var buckets = [];
    for (var b = 0; b < LEVELS; b++) buckets.push([]);
    for (var k = 0; k < touched.length; k++) {
      var cell = touched[k], total = Math.min(1, cells[cell] + peak[cell] + echo[cell]);
      buckets[Math.max(1, Math.round(total * (LEVELS - 1)))].push(cell);
      cells[cell] = 0; peak[cell] = 0; last[cell] = 0; echo[cell] = 0;
    }
    for (var level = 1; level < LEVELS; level++) {
      var bucket = buckets[level];
      if (!bucket.length) continue;
      ctx.fillStyle = scope.inks[level];
      for (var n = 0; n < bucket.length; n++) {
        var c = bucket[n];
        ctx.fillRect(scope.originX + (c % cols) * PITCH + inset, scope.originY + Math.floor(c / cols) * PITCH + inset, LED, LED);
      }
    }

    var headX = scope.originX + trail[trail.length - 2] * PITCH + PITCH / 2;
    var headY = scope.originY + trail[trail.length - 1] * PITCH + PITCH / 2;
    var radius = GLOW_CELLS * PITCH;
    var glow = ctx.createRadialGradient(headX, headY, 0, headX, headY, radius);
    glow.addColorStop(0, rgb(scope.live, GLOW_ALPHA));
    glow.addColorStop(1, rgb(scope.live, 0));
    ctx.globalCompositeOperation = "lighter";
    ctx.fillStyle = glow;
    ctx.fillRect(headX - radius, headY - radius, radius * 2, radius * 2);
    ctx.globalCompositeOperation = "source-over";
  }

  ssModes.scope = { init: scopeInit, draw: scopeDraw, resize: scopeLayout, meta: { name: "Scope Trace", icon: "activity", desc: "A single point tracing Hyperagent's drifting Lissajous path across a full-screen dot matrix" } };
})();
