/* === Hypervisor: LAN Mode — rendering switch for LAN visitors === */

  // The server decides local-vs-LAN by request origin and reports it at
  // /lan-mode. This module turns that into a single reusable rendering flag:
  //
  //   body.lan-mode   — set when the viewer is a LAN visitor (not the operator's
  //                     local webview). Any LAN-specific rendering difference
  //                     should key off this class in CSS, so new tweaks don't
  //                     each need their own JS.
  //
  // Two things happen when LAN mode is active:
  //   1. body gets the `lan-mode` class (CSS contract for all visual diffs).
  //   2. the full-workspace nav rail is REMOVED from the DOM — not just hidden,
  //      because CSS-hiding would still leak the category names in page source.
  //      LAN visitors navigate the shared surface via the Project Context
  //      dashboard instead.

  (function initLanMode() {
    // Fast path: the operator's local webview is always loopback. Skip the
    // probe entirely so nothing runs locally — LAN detection only matters for
    // remote viewers.
    var host = window.location.hostname;
    if (host === "127.0.0.1" || host === "localhost" || host === "::1" || host === "") {
      return;
    }

    function applyLanMode() {
      document.body.classList.add("lan-mode");
      // Hard-remove the nav rail (security: must not be present in source).
      var nav = document.getElementById("site-nav");
      if (nav && nav.parentNode) nav.parentNode.removeChild(nav);
    }

    fetch("/lan-mode", { cache: "no-store" })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (!(data && data.lan)) return;   // local viewer — full site, no change
        applyLanMode();
        // Re-apply after SPA navigation re-renders shell chrome (nav can return).
        if (window.__router && window.__router.onNavigate) {
          window.__router.onNavigate(null, applyLanMode);
        }
      })
      .catch(function () { /* probe failed — leave the site as-is */ });
  })();
