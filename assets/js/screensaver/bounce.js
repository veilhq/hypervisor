/* === Screensaver Mode: Bounce === */

(function () {
  "use strict";

    // ========== MODE: Bounce ==========
    var bounceState = { x: 0, y: 0, vx: 2, vy: 1.5, hue: 0, colorIdx: 0, size: 64 };

    // Brand icon paths (viewBox 0 0 76.72 60.87)
    // Mirrors assets/hypervisor.svg — update both together when rebranding.
    var BOUNCE_VB_W = 76.72;
    var BOUNCE_VB_H = 60.87;
    var bouncePaths = [
      "M71.35,35.62h-4.49c-1.3,0-2.49-.75-3.04-1.93l-3.53-7.54c-.3-.63-1.19-.64-1.5-.01l-.8,1.65c-2.32,4.79-7.18,7.84-12.51,7.84h-14.27c-5.33,0-10.19-3.04-12.51-7.84l-.8-1.65c-.3-.63-1.2-.62-1.5.01l-3.53,7.54c-.55,1.18-1.74,1.93-3.04,1.93h-4.49c-5.49,0-7.42,7.28-2.66,10l26.46,15.14c.66.38,1.44-.26,1.2-.98l-2.98-9.18c-1.12-3.44.45-7.19,3.69-8.81h0c4.71-3.41,11.21-3.12,15.63.85,2.53,2.28,3.3,5.94,2.25,9.18l-2.59,7.97c-.23.72.54,1.35,1.2.98l26.46-15.14c4.76-2.73,2.83-10-2.66-10Z",
      "M35.66,27.34c9.72,1.84,18.08-6.52,16.24-16.24-1.03-5.43-5.41-9.81-10.84-10.84-9.72-1.84-18.08,6.52-16.24,16.24,1.03,5.43,5.41,9.81,10.84,10.84Z"
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
      var sw = bounceState.size;
      var sh = sw * (BOUNCE_VB_H / BOUNCE_VB_W);
      if (bounceState.x > ssCanvas.width - sw) bounceState.x = ssCanvas.width - sw;
      if (bounceState.y > ssCanvas.height - sh) bounceState.y = ssCanvas.height - sh;
    }

    function bounceDraw() {
      var colors = ssUsePalette() ? ssGetPalette() : null;
      ssCtx.fillStyle = "rgba(0, 0, 0, 0.08)";
      ssCtx.fillRect(0, 0, ssCanvas.width, ssCanvas.height);

      var sw = bounceState.size;
      var sh = sw * (BOUNCE_VB_H / BOUNCE_VB_W);
      // Scale factor: draw the viewBox at `sw` pixels wide, aspect preserved.
      var scale = sw / BOUNCE_VB_W;

      bounceState.x += bounceState.vx;
      bounceState.y += bounceState.vy;

      if (bounceState.x <= 0 || bounceState.x + sw >= ssCanvas.width) {
        bounceState.vx *= -1;
        bounceState.hue = (bounceState.hue + 47) % 360;
        bounceState.colorIdx = (bounceState.colorIdx + 1) % 4;
        bounceState.x = Math.max(0, Math.min(bounceState.x, ssCanvas.width - sw));
      }
      if (bounceState.y <= 0 || bounceState.y + sh >= ssCanvas.height) {
        bounceState.vy *= -1;
        bounceState.hue = (bounceState.hue + 47) % 360;
        bounceState.colorIdx = (bounceState.colorIdx + 1) % 4;
        bounceState.y = Math.max(0, Math.min(bounceState.y, ssCanvas.height - sh));
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

    ssModes.bounce = { init: bounceInit, draw: bounceDraw, resize: bounceResize, meta: { name: "Bounce", icon: "move-diagonal", desc: "A word bouncing off the walls — retro" } };
})();
