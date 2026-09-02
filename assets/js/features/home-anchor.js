/* ===== Hypervisor: Home anchor (greeting + launcher row) =====
   Populates the rotating greeting via HvGreeting on homepage navigation.
   Mounts a subtle noise field across the full dashboard background.
   Launcher icon clicks are wired in 00-core.js (bridge-dependent). */

  (function initHomeAnchor() {
    function startNoise() {
      if (!window.HvNoiseField) return;
      // Mount on body so the render loop uses viewport dimensions
      window.HvNoiseField.start(document.body, { cellDivisor: 600 });
      var canvas = document.body.querySelector('canvas.noise-field-canvas');
      if (canvas) {
        canvas.style.position = 'fixed';
        canvas.style.inset = '0';
        canvas.style.zIndex = '0';
        canvas.style.pointerEvents = 'none';
        canvas.style.opacity = '0.5';
      }
    }
    function teardownNoise(immediate) {
      if (window.HvNoiseField) window.HvNoiseField.stop(immediate ? 0 : 500);
    }
    function init(fragment) {
      if (!fragment || fragment.pageType !== 'home') return;
      // Mount subtle noise field on the full page background
      startNoise();
      // Randomized sub-greeting
      var g = document.querySelector('[data-home-greeting]');
      if (g && window.HvGreeting) window.HvGreeting.applyTo(g);
    }

    if (window.__router) {
      window.__router.onNavigate(function () { teardownNoise(false); }, init);
    }
  })();
