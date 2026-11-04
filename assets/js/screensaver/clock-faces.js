/* === Screensaver: Clock Faces === */

// Faces self-register into window.ssClockFaces (created by 00-engine-head.js),
// mirroring the ssModes pattern. The engine tail dispatches to the active face:
//   mount(el)        - build any sub-structure into clockEl (once, on show/switch)
//   update(el, now)  - write the current time (every tick); `now` is a Date
//   unmount(el)      - tear down sub-structure (on hide/switch), leaving el clean
//   meta: { name }   - label for the settings dropdown
//
// Text faces set el.textContent and no-op mount/unmount. Structural faces (lcd,
// flip, dot-matrix) build their sub-structure in mount, mutate it in update, and
// clear it in unmount so switching faces never leaves orphan DOM.
(function () {
  "use strict";

  var faces = window.ssClockFaces;
  if (!faces) {
    console.error("[clock-faces] window.ssClockFaces missing - engine head failed to init.");
    return;
  }

  function pad2(n) { return String(n).padStart(2, "0"); }

  // Single-box faces (digital, word) compose the shared filled chip primitive
  // rather than the former bespoke .screensaver-clock flag skin. These helpers
  // keep the class list consistent across those faces.
  var CHIP_CLASSES = ["status-chip", "status-chip-filled"];
  function addChip(el) { CHIP_CLASSES.forEach(function (c) { el.classList.add(c); }); }
  function removeChip(el) { CHIP_CLASSES.forEach(function (c) { el.classList.remove(c); }); }

  // --- Digital 24h -------------------------------------------------------
  faces["digital-24"] = {
    mount: function (el) { addChip(el); el.classList.add("clock-face-digital"); },
    unmount: function (el) { removeChip(el); el.classList.remove("clock-face-digital"); el.textContent = ""; },
    update: function (el, now) {
      el.textContent = pad2(now.getHours()) + ":" + pad2(now.getMinutes()) + ":" + pad2(now.getSeconds());
    },
    meta: { name: "Digital 24h" }
  };

  // --- Digital 12h -------------------------------------------------------
  faces["digital-12"] = {
    mount: function (el) { addChip(el); el.classList.add("clock-face-digital"); },
    unmount: function (el) { removeChip(el); el.classList.remove("clock-face-digital"); el.textContent = ""; },
    update: function (el, now) {
      var h = now.getHours();
      var suffix = h < 12 ? "AM" : "PM";
      var h12 = h % 12;
      if (h12 === 0) h12 = 12;
      el.textContent = pad2(h12) + ":" + pad2(now.getMinutes()) + ":" + pad2(now.getSeconds()) + " " + suffix;
    },
    meta: { name: "Digital 12h" }
  };

  // --- Word clock (exact-minute prose) -----------------------------------
  var HOUR_WORDS = [
    "TWELVE", "ONE", "TWO", "THREE", "FOUR", "FIVE", "SIX",
    "SEVEN", "EIGHT", "NINE", "TEN", "ELEVEN", "TWELVE"
  ];
  // Minute words 1-29 (0 and 30 handled specially; 31-59 fold to 60 - n).
  var MINUTE_WORDS = [
    "", "ONE", "TWO", "THREE", "FOUR", "FIVE", "SIX", "SEVEN", "EIGHT", "NINE",
    "TEN", "ELEVEN", "TWELVE", "THIRTEEN", "FOURTEEN", "FIFTEEN", "SIXTEEN",
    "SEVENTEEN", "EIGHTEEN", "NINETEEN", "TWENTY", "TWENTY-ONE", "TWENTY-TWO",
    "TWENTY-THREE", "TWENTY-FOUR", "TWENTY-FIVE", "TWENTY-SIX", "TWENTY-SEVEN",
    "TWENTY-EIGHT", "TWENTY-NINE"
  ];

  function wordClockText(now) {
    var h = now.getHours();
    var m = now.getMinutes();
    var hour12 = h % 12; // index into HOUR_WORDS (0 => TWELVE)
    var nextHour12 = (h + 1) % 12;

    if (m === 0) {
      return "IT IS " + HOUR_WORDS[hour12];
    }
    if (m === 15) {
      return "IT IS QUARTER PAST " + HOUR_WORDS[hour12];
    }
    if (m === 30) {
      return "IT IS HALF PAST " + HOUR_WORDS[hour12];
    }
    if (m === 45) {
      return "IT IS QUARTER TO " + HOUR_WORDS[nextHour12];
    }
    if (m < 30) {
      var unit = m === 1 ? "MINUTE" : "MINUTES";
      return "IT IS " + MINUTE_WORDS[m] + " " + unit + " PAST " + HOUR_WORDS[hour12];
    }
    // 31-59: count minutes TO the next hour.
    var rem = 60 - m;
    var unitTo = rem === 1 ? "MINUTE" : "MINUTES";
    return "IT IS " + MINUTE_WORDS[rem] + " " + unitTo + " TO " + HOUR_WORDS[nextHour12];
  }

  faces["word-clock"] = {
    mount: function (el) { addChip(el); el.classList.add("clock-face-word"); },
    unmount: function (el) { removeChip(el); el.classList.remove("clock-face-word"); el.textContent = ""; },
    update: function (el, now) { el.textContent = wordClockText(now); },
    meta: { name: "Word Clock" }
  };

  // --- LCD (seven-segment, composes HvViz.segmentDisplay) ----------------
  // HvViz sets className on its target, so render into a dedicated inner child
  // rather than clockEl itself - otherwise it would wipe the clock's own
  // screensaver-clock / clock-face-* classes and break positioning for all faces.
  faces["lcd"] = {
    mount: function (el) {
      el.classList.add("clock-face-lcd");
      el.innerHTML = '<span data-face="lcd"></span>';
    },
    unmount: function (el) { el.classList.remove("clock-face-lcd"); el.innerHTML = ""; },
    update: function (el, now) {
      if (!window.HvViz) return;
      var host = el.querySelector('[data-face="lcd"]');
      if (!host) return;
      HvViz.segmentDisplay(host, {
        value: pad2(now.getHours()) + ":" + pad2(now.getMinutes()) + ":" + pad2(now.getSeconds())
      });
    },
    meta: { name: "LCD" }
  };

  // --- Flip (split-flap, composes HvViz.flip) ----------------------------
  // Renders into a dedicated inner child (see LCD note) so HvViz.flip's
  // className assignment never clobbers clockEl's own classes.
  faces["flip"] = {
    mount: function (el) {
      el.classList.add("clock-face-flip");
      el.innerHTML = '<span data-face="flip"></span>';
    },
    unmount: function (el) { el.classList.remove("clock-face-flip"); el.innerHTML = ""; },
    update: function (el, now) {
      if (!window.HvViz) return;
      var host = el.querySelector('[data-face="flip"]');
      if (!host) return;
      HvViz.flip(host, { value: pad2(now.getHours()) + ":" + pad2(now.getMinutes()) });
    },
    meta: { name: "Flip" }
  };

  // --- Dot Matrix (composes the .viz-cell dot primitive) -----------------
  // Each digit is a 3-wide x 5-tall dot grid; lit dots use --accent, unlit are
  // the neutral .viz-cell. 3x5 glyph rows per digit (1 = lit).
  var DOT_GLYPHS = {
    '0': [[1,1,1],[1,0,1],[1,0,1],[1,0,1],[1,1,1]],
    '1': [[0,1,0],[1,1,0],[0,1,0],[0,1,0],[1,1,1]],
    '2': [[1,1,1],[0,0,1],[1,1,1],[1,0,0],[1,1,1]],
    '3': [[1,1,1],[0,0,1],[1,1,1],[0,0,1],[1,1,1]],
    '4': [[1,0,1],[1,0,1],[1,1,1],[0,0,1],[0,0,1]],
    '5': [[1,1,1],[1,0,0],[1,1,1],[0,0,1],[1,1,1]],
    '6': [[1,1,1],[1,0,0],[1,1,1],[1,0,1],[1,1,1]],
    '7': [[1,1,1],[0,0,1],[0,1,0],[0,1,0],[0,1,0]],
    '8': [[1,1,1],[1,0,1],[1,1,1],[1,0,1],[1,1,1]],
    '9': [[1,1,1],[1,0,1],[1,1,1],[0,0,1],[1,1,1]]
  };
  faces["dot-matrix"] = {
    mount: function (el) { el.classList.add("clock-face-dots"); },
    unmount: function (el) { el.classList.remove("clock-face-dots"); el.innerHTML = ""; },
    update: function (el, now) {
      var str = pad2(now.getHours()) + ":" + pad2(now.getMinutes());
      var accent = window.ssGetAccent ? window.ssGetAccent() : "#00ff41";
      var html = "";
      for (var i = 0; i < str.length; i++) {
        var ch = str.charAt(i);
        if (ch === ":") {
          html += '<span class="dots-colon"></span>';
          continue;
        }
        var g = DOT_GLYPHS[ch];
        html += '<span class="dots-digit">';
        for (var r = 0; r < 5; r++) {
          for (var c = 0; c < 3; c++) {
            var on = g && g[r][c];
            html += '<span class="viz-cell' + (on ? ' viz-cell-filled dots-on' : '') + '"></span>';
          }
        }
        html += '</span>';
      }
      el.innerHTML = html;
      // Apply the accent to lit dots (viz-cell-filled expects an inline bg).
      var lit = el.querySelectorAll(".dots-on");
      for (var k = 0; k < lit.length; k++) lit[k].style.background = accent;
    },
    meta: { name: "Dot Matrix" }
  };
})();
