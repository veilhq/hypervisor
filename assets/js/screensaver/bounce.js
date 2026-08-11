/* === Screensaver Mode: Bounce === */

(function () {
  "use strict";

    // ========== MODE: Bounce ==========
    var bounceState = { x: 0, y: 0, vx: 2, vy: 1.5, hue: 0, colorIdx: 0, size: 64 };

    // Brand icon paths (viewBox 0 0 108.28 108.28)
    // Mirrors assets/hypervisor.svg — update both together when rebranding.
    var bouncePaths = [
      "M90.15,36.1c9.91,0,17.98-8.06,17.98-17.98S100.06.15,90.15.15s-17.98,8.06-17.98,17.98,8.06,17.98,17.98,17.98ZM90.15,33.37c-5.05,0-9.53-2.48-12.3-6.28-.35-.48,0-1.16.59-1.16h1.46c.85,0,1.68.26,2.37.75s1.51.75,2.37.75h11.28c.85,0,1.68-.26,2.37-.75s1.51-.75,2.37-.75h1.21c.59,0,.94.68.59,1.16-2.77,3.8-7.25,6.28-12.3,6.28ZM104.51,16.79h-28.72c-.43,0-.78-.38-.72-.81.2-1.37.58-2.68,1.11-3.91.11-.26.38-.43.67-.43h3.05c.85,0,1.68.26,2.37.75s1.51.75,2.37.75h11.28c.85,0,1.68-.26,2.37-.75s1.51-.75,2.37-.75h2.8c.29,0,.55.17.67.43.54,1.23.92,2.54,1.11,3.91.06.43-.29.81-.72.81ZM74.94,18.79h4.72c.87,0,1.72.26,2.42.75s1.55.75,2.42.75h11.54c.87,0,1.72-.26,2.42-.75s1.55-.75,2.42-.75h3.69c.42,0,.76.36.72.78-.13,1.36-.43,2.67-.89,3.91-.11.28-.38.46-.68.46h-27.17c-.3,0-.58-.18-.68-.46-.55-1.47-.87-3.04-.94-4.69,0,0,0,0,0,0ZM90.15,2.89c4.73,0,8.97,2.17,11.77,5.57.39.47.04,1.18-.57,1.18h-22.41c-.61,0-.95-.71-.57-1.18,2.8-3.4,7.03-5.57,11.77-5.57Z",
      "M107.94,71.76l-35.71-35.71-.04-.04h-34.8c-.63,0-1.14-.51-1.14-1.14V1.14c0-.63-.51-1.14-1.14-1.14H1.14C.51,0,0,.51,0,1.14v34.58c0,.3.12.59.33.8l33.56,33.56c.72.72.21,1.94-.8,1.94H1.14c-.63,0-1.14.51-1.14,1.14v33.98c0,.63.51,1.14,1.14,1.14h33.98c.63,0,1.14-.51,1.14-1.14v-33.73c0-.63.51-1.14,1.14-1.14h33.48c.63,0,1.14.51,1.14,1.14v33.73c0,.63.51,1.14,1.14,1.14h33.98c.63,0,1.14-.51,1.14-1.14v-34.58c0-.3-.12-.59-.33-.8Z"
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
})();
