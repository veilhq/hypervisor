/* === Screensaver Mode: Bounce === */

    // ========== MODE: Bounce ==========
    var bounceState = { text: "HYPERVISOR", x: 0, y: 0, vx: 2, vy: 1.5, hue: 0, colorIdx: 0 };

    function bounceInit() {
      bounceState.x = ssCanvas.width * 0.3;
      bounceState.y = ssCanvas.height * 0.4;
      bounceState.hue = 0;
      bounceState.colorIdx = 0;
    }
    function bounceResize() {
      if (bounceState.x > ssCanvas.width - 200) bounceState.x = ssCanvas.width - 200;
      if (bounceState.y > ssCanvas.height - 40) bounceState.y = ssCanvas.height - 40;
    }
    function bounceDraw() {
      var colors = ssUsePalette() ? ssGetPalette() : null;
      ssCtx.fillStyle = "rgba(0, 0, 0, 0.08)";
      ssCtx.fillRect(0, 0, ssCanvas.width, ssCanvas.height);

      var text = bounceState.text;
      ssCtx.font = "bold 28px 'Departure Mono', monospace";
      var metrics = ssCtx.measureText(text);
      var tw = metrics.width;
      var th = 28;

      bounceState.x += bounceState.vx;
      bounceState.y += bounceState.vy;

      if (bounceState.x <= 0 || bounceState.x + tw >= ssCanvas.width) {
        bounceState.vx *= -1;
        bounceState.hue = (bounceState.hue + 47) % 360;
        bounceState.colorIdx = (bounceState.colorIdx + 1) % 4;
        bounceState.x = Math.max(0, Math.min(bounceState.x, ssCanvas.width - tw));
      }
      if (bounceState.y - th <= 0 || bounceState.y >= ssCanvas.height) {
        bounceState.vy *= -1;
        bounceState.hue = (bounceState.hue + 47) % 360;
        bounceState.colorIdx = (bounceState.colorIdx + 1) % 4;
        bounceState.y = Math.max(th, Math.min(bounceState.y, ssCanvas.height));
      }

      if (colors) {
        ssCtx.fillStyle = colors[bounceState.colorIdx];
      } else {
        ssCtx.fillStyle = "hsl(" + bounceState.hue + ", 100%, 55%)";
      }
      ssCtx.fillText(text, bounceState.x, bounceState.y);
    }

    ssModes.bounce = { init: bounceInit, draw: bounceDraw, resize: bounceResize };
