/* ===== Hypervisor: Home anchor (greeting + launcher row) =====
   Populates the rotating greeting via HvGreeting on homepage navigation.
   The dashboard background is a static CSS calibration-point grid (see
   .page-home in the layout) - no animated noise field.
   Launcher icon clicks are wired in 00-core.js (bridge-dependent). */

  (function initHomeAnchor() {
    function init(fragment) {
      if (!fragment || fragment.pageType !== 'home') return;
      // Randomized sub-greeting
      var g = document.querySelector('[data-home-greeting]');
      if (g && window.HvGreeting) window.HvGreeting.applyTo(g);
    }

    if (window.__router) {
      window.__router.onNavigate(function () {}, init);
    }
  })();
