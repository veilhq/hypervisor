/* === Hypervisor: LAN Share Key === */

  // Desktop-app-only control in the actions drawer. Lets the operator set or
  // clear the access key that gates LAN sharing of the site. The server reads
  // the key per-request from preferences.json, so changes take effect without
  // an app restart. When no key is set, LAN access is denied entirely.

  (function initShareKey() {
    var isDesktop = !!(window.pywebview && window.pywebview.api);
    var btn = document.getElementById("share-key-btn");

    function setup() {
      btn = document.getElementById("share-key-btn");
      if (!btn) return;
      var hasBridge = !!(window.pywebview && window.pywebview.api);
      if (hasBridge) btn.style.display = "";
      btn.addEventListener("click", handleClick);
    }

    function handleClick() {
      if (!(window.pywebview && window.pywebview.api)) return;

      // Prefill with the current key so the operator can view/edit it.
      window.pywebview.api.get_lan_key().then(function (res) {
        var current = (res && res.key) || "";
        var url = (res && res.url) || "";
        var hint = current
          ? "Coworkers open:  " + url
          : "Set a key to enable sharing. Coworkers will open:  " + (url || "http://<your-ip>:8420/") + "?key=<key>";
        window.__hypervisorPrompt("LAN sharing access key", {
          value: current,
          placeholder: "leave blank to disable sharing",
          confirmLabel: "save",
          cancelLabel: "cancel",
          hint: hint
        }).then(function (next) {
          // Cancelled — leave the key unchanged.
          if (next === null) return;

          window.pywebview.api.set_lan_key(next).then(function (r) {
            var k = (r && r.key) || "";
            var newUrl = (r && r.url) || "";
            if (window.__hypervisorToast) {
              if (k) {
                window.__hypervisorToast({ variant: "success", title: "LAN sharing enabled", message: newUrl });
              } else {
                window.__hypervisorToast({ variant: "success", message: "LAN sharing disabled" });
              }
            }
            if (window.__closeActionsDrawer) window.__closeActionsDrawer();
          }).catch(function () {
            if (window.__hypervisorToast) window.__hypervisorToast({ variant: "error", message: "failed to set key" });
          });
        });
      });
    }

    if (isDesktop) {
      setup();
    } else {
      window.addEventListener("pywebviewready", function onReady() {
        window.removeEventListener("pywebviewready", onReady);
        setup();
      });
    }

    // Re-attach after SPA navigation (drawer re-renders from page template).
    if (window.__router) {
      window.__router.onNavigate(null, function () {
        setup();
      });
    }
  })();
