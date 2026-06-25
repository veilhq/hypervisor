/* === Hypervisor: Live Reload === */

  // --- Single-tab auto-reload ---
  // Each build writes a _build.json with its unique build ID.
  // Existing tabs poll that file every 2s. When the ID changes, the tab
  // reloads the current fragment to pick up the fresh build.
  // When running inside PyWebView, skip polling — the Python process triggers
  // reloads directly via evaluate_js.
  (function () {
    var meta = document.querySelector('meta[name="build-id"]');
    if (!meta) return;
    var myBuild = meta.getAttribute("content");

    // Poll _build.json for changes
    function checkBuild() {
      // Desktop app handles reload via Python bridge — skip polling
      if (isDesktopApp) return;
      fetch("/_build.json").then(function (res) {
        if (!res.ok) return;
        return res.json();
      }).then(function (data) {
        if (data && data.buildId && data.buildId !== myBuild) {
          myBuild = data.buildId;
          // New build detected — mark inactive tabs as stale
          if (window.__tabs) window.__tabs.markAllStale();
          // Reload current fragment via router
          if (window.__router) {
            window.__router.reload();
          } else {
            window.location.reload();
          }
        }
      }).catch(function () {});
    }

    // Poll every 2 seconds
    setInterval(checkBuild, 2000);
  })();
