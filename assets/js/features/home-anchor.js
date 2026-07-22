/* ===== Hypervisor: Home anchor (composes shared modules) =====
   Mounts the Bayer-dither noise field (HvNoiseField) into the homepage
   .home-anchor element and populates the greeting via HvGreeting.
   Both modules are defined in features/00-shared-modules.js and are ready
   for adoption by Hyperagent in WI-113. */

  (function initHomeAnchor() {
    function start(hostEl) {
      if (window.HvNoiseField) window.HvNoiseField.start(hostEl);
    }
    function teardown(immediate) {
      if (window.HvNoiseField) window.HvNoiseField.stop(immediate ? 0 : 500);
    }
    function init(fragment) {
      if (!fragment || fragment.pageType !== 'home') return;
      var el = document.querySelector('.home-anchor');
      if (el) start(el);
      // Populate a fresh random greeting on every home visit.
      // .emote class is auto-applied to kaomoji entries by HvGreeting.applyTo.
      var g = document.querySelector('[data-home-greeting]');
      if (g && window.HvGreeting) window.HvGreeting.applyTo(g);
    }

    if (window.__router) {
      window.__router.onNavigate(function () { teardown(false); }, init);
    }
  })();
