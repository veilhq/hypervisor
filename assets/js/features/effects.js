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
      var now = new Date();
      var h = String(now.getHours()).padStart(2, "0");
      var m = String(now.getMinutes()).padStart(2, "0");
      var s = String(now.getSeconds()).padStart(2, "0");
      el.textContent = h + ":" + m + ":" + s;
    }
    tick();
    setInterval(tick, 1000);
  })();

  // --- Cursor companion box ---
  (function initCursorBox() {
    var box = document.createElement("div");
    box.className = "cursor-box";
    document.body.appendChild(box);

    var OFFSET_X = 14;
    var OFFSET_Y = -4;
    var hovering = false;
    var CLICKABLE = "a, button, [role='button'], input[type='color'], .card, .pin-card, .swatch, .palette-mode-btn, .code-copy, .sr-tag, .ref-menu-btn, .util-menu-btn, .width-toggle, .settings-menu-btn, .a11y-toggle, .a11y-reset, .cell-copyable, .section-copy, .quiz-option, .quiz-btn, .quiz-tab, .guide-nav-btn";

    document.addEventListener("mousemove", function (e) {
      box.style.left = (e.clientX + OFFSET_X) + "px";
      box.style.top = (e.clientY + OFFSET_Y) + "px";

      var over = document.elementFromPoint(e.clientX, e.clientY);
      var isClickable = over && over.closest(CLICKABLE);
      if (isClickable && !hovering) {
        hovering = true;
        box.classList.add("visible");
      } else if (!isClickable && hovering) {
        hovering = false;
        box.classList.remove("visible", "blink");
      }
    });

    document.addEventListener("mousedown", function (e) {
      var over = document.elementFromPoint(e.clientX, e.clientY);
      if (!over || !over.closest(CLICKABLE)) return;
      box.classList.remove("blink");
      void box.offsetWidth;
      box.classList.add("blink");
      setTimeout(function () { box.classList.remove("blink"); }, 350);
    });
  })();
