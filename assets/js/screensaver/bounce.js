/* === Screensaver Mode: Bounce === */

    // ========== MODE: Bounce ==========
    var bounceState = { x: 0, y: 0, vx: 2, vy: 1.5, hue: 0, colorIdx: 0, size: 64 };

    // Brand icon paths (viewBox 0 0 108.28 108.28)
    var bouncePaths = [
      "M98.58,11.9c-.13-.04-.27-.07-.43-.08-.16-.01-.33-.02-.51-.02-.36,0-.68.01-.94.03-.26.02-.49.08-.7.19-.13.1-.23.23-.31.37-.08.15-.14.29-.2.44-.13.29-.25.58-.35.87-.1.29-.22.58-.35.87-.18.33-.34.67-.47,1.01-.13.34-.26.69-.39,1.05-.34.79-.66,1.58-.98,2.36-.31.78-.64,1.57-.98,2.36-.18.42-.35.83-.49,1.23-.14.41-.32.81-.53,1.2-.05.1-.14.25-.25.44-.12.19-.28.26-.49.22-.18-.04-.31-.15-.39-.31-.08-.17-.14-.32-.2-.47-.21-.37-.38-.75-.51-1.14-.13-.38-.29-.76-.47-1.14-.52-1.12-1-2.25-1.44-3.39-.44-1.13-.92-2.26-1.44-3.39-.13-.29-.25-.58-.35-.87-.1-.29-.23-.58-.39-.87-.08-.17-.15-.33-.21-.48-.07-.16-.19-.29-.37-.39-.23-.12-.57-.19-1.01-.19h-1.25s-.13.03-.31.03c-.18.04-.34.11-.47.22-.1.15-.12.32-.04.53.08.21.14.37.2.5.18.35.34.71.49,1.06.14.35.32.71.53,1.06.05.1.1.21.14.33.04.11.08.22.14.33.16.33.31.66.45.98.14.32.29.65.45.98.52,1,1,2.01,1.42,3.03.43,1.02.9,2.03,1.42,3.03.05.1.09.19.12.27.03.07.06.16.12.27.13.29.27.6.41.92.14.32.29.63.45.92.13.23.23.46.31.7.08.24.21.44.39.61.18.19.47.29.86.3.39.01.79.02,1.21.02h.61c.2,0,.37-.03.53-.09.29-.1.47-.25.57-.45.09-.2.2-.41.33-.64.18-.33.34-.67.47-1,.13-.33.27-.67.43-1,.44-.85.84-1.72,1.19-2.59.35-.87.75-1.74,1.19-2.59.16-.27.29-.55.41-.83.12-.28.24-.56.37-.83.21-.37.38-.75.51-1.12.13-.37.3-.74.51-1.09.05-.1.09-.2.12-.3.03-.09.06-.19.12-.3.21-.35.39-.72.55-1.09.16-.37.31-.74.47-1.09.1-.19.15-.37.14-.56-.01-.19-.14-.32-.37-.41Z",
      "M90.15.15c-9.91,0-17.98,8.06-17.98,17.98s8.06,17.98,17.98,17.98,17.98-8.06,17.98-17.98S100.06.15,90.15.15ZM90.15,33.37c-8.4,0-15.24-6.84-15.24-15.24s6.84-15.24,15.24-15.24,15.24,6.84,15.24,15.24-6.84,15.24-15.24,15.24Z",
      "M72.23,36.05l-.04-.04h-34.8c-.63,0-1.14-.51-1.14-1.14V1.14c0-.63-.51-1.14-1.14-1.14H1.14C.51,0,0,.51,0,1.14v34.58c0,.3.12.59.33.8l33.56,33.56c.72.72.21,1.94-.8,1.94H1.14c-.63,0-1.14.51-1.14,1.14v33.98c0,.63.51,1.14,1.14,1.14h33.98c.63,0,1.14-.51,1.14-1.14v-33.73c0-.63.51-1.14,1.14-1.14h33.48c.63,0,1.14.51,1.14,1.14v33.73c0,.63.51,1.14,1.14,1.14h33.98c.63,0,1.14-.51,1.14-1.14v-34.58c0-.3-.12-.59-.33-.8l-35.71-35.71Z"
    ];

    // Pre-create Path2D objects for efficient drawing
    var bouncePathObjects = null;

    function bounceInit() {
      bounceState.x = ssCanvas.width * 0.3;
      bounceState.y = ssCanvas.height * 0.4;
      bounceState.hue = 0;
      bounceState.colorIdx = 0;
      // Create Path2D objects on first init
      if (!bouncePathObjects) {
        bouncePathObjects = bouncePaths.map(function(d) { return new Path2D(d); });
      }
    }

    function bounceResize() {
      var s = bounceState.size;
      if (bounceState.x > ssCanvas.width - s) bounceState.x = ssCanvas.width - s;
      if (bounceState.y > ssCanvas.height - s) bounceState.y = ssCanvas.height - s;
    }

    function bounceDraw() {
      var colors = ssUsePalette() ? ssGetPalette() : null;
      ssCtx.fillStyle = "rgba(0, 0, 0, 0.08)";
      ssCtx.fillRect(0, 0, ssCanvas.width, ssCanvas.height);

      var s = bounceState.size;
      // Scale factor: icon viewBox is 108.28, we want to draw at `s` pixels
      var scale = s / 108.28;

      bounceState.x += bounceState.vx;
      bounceState.y += bounceState.vy;

      if (bounceState.x <= 0 || bounceState.x + s >= ssCanvas.width) {
        bounceState.vx *= -1;
        bounceState.hue = (bounceState.hue + 47) % 360;
        bounceState.colorIdx = (bounceState.colorIdx + 1) % 4;
        bounceState.x = Math.max(0, Math.min(bounceState.x, ssCanvas.width - s));
      }
      if (bounceState.y <= 0 || bounceState.y + s >= ssCanvas.height) {
        bounceState.vy *= -1;
        bounceState.hue = (bounceState.hue + 47) % 360;
        bounceState.colorIdx = (bounceState.colorIdx + 1) % 4;
        bounceState.y = Math.max(0, Math.min(bounceState.y, ssCanvas.height - s));
      }

      if (colors) {
        ssCtx.fillStyle = colors[bounceState.colorIdx];
      } else {
        ssCtx.fillStyle = "hsl(" + bounceState.hue + ", 100%, 55%)";
      }

      ssCtx.save();
      ssCtx.translate(bounceState.x, bounceState.y);
      ssCtx.scale(scale, scale);
      for (var i = 0; i < bouncePathObjects.length; i++) {
        ssCtx.fill(bouncePathObjects[i]);
      }
      ssCtx.restore();
    }

    ssModes.bounce = { init: bounceInit, draw: bounceDraw, resize: bounceResize };
