/* === Hypervisor: Effects (glitch, clock, cursor) === */

  // --- Terminal glitch effect ---
  // Periodically scrambles random text on the page for a split second
  (function initGlitch() {
    // Unicode glitch characters: box-drawing, block elements, misc symbols
    var glyphPool = "░▒▓█▄▀▐▌╔╗╚╝║═╠╣╦╩╬┃━┏┓┗┛┣┫┳┻╋▲▼◆◇○●◎■□▪▫≡≈∞∴∵⌐¬¡¿«»¦§¶†‡";

    function randInt(min, max) {
      return Math.floor(Math.random() * (max - min + 1)) + min;
    }

    function randomGlyph() {
      return glyphPool[randInt(0, glyphPool.length - 1)];
    }

    // Collect all visible text nodes inside the page content
    function getGlitchTargets() {
      var targets = [];
      var walker = document.createTreeWalker(
        document.querySelector(".page") || document.body,
        NodeFilter.SHOW_TEXT,
        {
          acceptNode: function (node) {
            // Skip empty, whitespace-only, script/style, and very short nodes
            var text = node.textContent.trim();
            if (text.length < 4) return NodeFilter.FILTER_REJECT;
            var parent = node.parentElement;
            if (!parent) return NodeFilter.FILTER_REJECT;
            var tag = parent.tagName.toLowerCase();
            if (tag === "script" || tag === "style" || tag === "input" || tag === "textarea" || tag === "code" || tag === "pre")
              return NodeFilter.FILTER_REJECT;
            return NodeFilter.FILTER_ACCEPT;
          }
        }
      );
      while (walker.nextNode()) targets.push(walker.currentNode);
      return targets;
    }

    function glitchOnce() {
      // Respect accessibility toggle
      if (document.documentElement.classList.contains("a11y-no-glitch")) return;
      var targets = getGlitchTargets();
      if (!targets.length) return;

      // Pick 1-3 random text nodes to glitch simultaneously
      var count = randInt(1, Math.min(3, targets.length));
      var chosen = [];
      for (var i = 0; i < count; i++) {
        chosen.push(targets[randInt(0, targets.length - 1)]);
      }

      var originals = [];
      chosen.forEach(function (node) {
        originals.push({ node: node, text: node.textContent });
      });

      // Cycle through 5 different glyph scrambles before restoring
      var cyclesLeft = 6;
      var cycleInterval = 70;
      function glitchCycle() {
        if (cyclesLeft <= 0) {
          originals.forEach(function (o) {
            o.node.textContent = o.text;
          });
          return;
        }
        chosen.forEach(function (node, idx) {
          var chars = originals[idx].text.split("");
          var scrambleCount = randInt(
            Math.ceil(chars.length * 0.15),
            Math.ceil(chars.length * 0.4)
          );
          for (var j = 0; j < scrambleCount; j++) {
            var pos = randInt(0, chars.length - 1);
            if (chars[pos] !== " " && chars[pos] !== "\n") {
              chars[pos] = randomGlyph();
            }
          }
          node.textContent = chars.join("");
        });
        cyclesLeft--;
        setTimeout(glitchCycle, cycleInterval);
      }
      glitchCycle();
    }

    function scheduleNext() {
      var delay = randInt(8000, 25000);
      setTimeout(function () {
        glitchOnce();
        scheduleNext();
      }, delay);
    }

    // Start after a short initial delay
    setTimeout(scheduleNext, 3000);
  })();

  // --- Footer clock ---
  (function initClock() {
    var el = document.getElementById("footer-clock");
    if (!el) return;
    function tick() {
      // Skip the DOM write while hidden — nothing is on screen to read it.
      if (document.hidden) return;
      var now = new Date();
      var h = String(now.getHours()).padStart(2, "0");
      var m = String(now.getMinutes()).padStart(2, "0");
      var s = String(now.getSeconds()).padStart(2, "0");
      el.textContent = h + ":" + m + ":" + s;
    }
    tick();
    setInterval(tick, 1000);
    // Repaint immediately on return so the clock isn't visibly stale.
    document.addEventListener("visibilitychange", function () {
      if (!document.hidden) tick();
    });
  })();

  // --- Cursor companion box ---
  // Relocated to Hyperkit (WI-142 follow-up) — window.HvCursorBox is loaded
  // before this file. Edit the module in .hyperkit/js/cursor-box.js, not here.
  (function initCursorBox() {
    if (!window.HvCursorBox) return;
    HvCursorBox.start(document.body);
  })();


  // --- WebGL cursor trail (WI-119) ---
  // Sits directly below the .cursor-box companion (z-index 549 vs 550) and
  // stamps the sitewide pointer SVG along the motion segment each frame.
  // Idempotent, idle-suspending, and a11y-gated internally — no coordination
  // needed with the cursor-box above.
  (function initCursorTrail() {
    if (!window.HvCursorTrail) return;
    HvCursorTrail.start(document.body);
  })();
