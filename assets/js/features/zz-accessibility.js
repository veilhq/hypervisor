/* === Hypervisor: Accessibility === */

  // --- Accessibility panel ---
  (function initA11y() {
    var settingsBtn = document.getElementById("settings-menu-btn");
    var settingsPanel = document.getElementById("nav-panel");
    var resetBtn = document.getElementById("a11y-reset");
    if (!settingsPanel) return;

    var STORAGE_PREFIX = "hypervisor-a11y-";
    var toggles = settingsPanel.querySelectorAll("input[data-a11y]");

    // Restore saved preferences
    toggles.forEach(function (toggle) {
      var key = toggle.getAttribute("data-a11y");
      var saved = null;
      try { saved = localStorage.getItem(STORAGE_PREFIX + key); } catch (e) {}
      if (saved === "1") {
        toggle.checked = true;
        document.documentElement.classList.add("a11y-" + key);
        if (key === "system-cursors") {
          document.body.classList.remove("a11y-cursors-active");
        }
      }
    });

    // Auto-detect system preferences on first visit
    (function detectSystemPrefs() {
      var hasAnyPref = false;
      try {
        toggles.forEach(function (t) {
          if (localStorage.getItem(STORAGE_PREFIX + t.getAttribute("data-a11y")) !== null) {
            hasAnyPref = true;
          }
        });
      } catch (e) {}
      if (hasAnyPref) return; // User has made manual choices, don't override

      if (window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
        var motionToggle = document.getElementById("a11y-reduce-motion");
        if (motionToggle) {
          motionToggle.checked = true;
          document.documentElement.classList.add("a11y-reduce-motion");
        }
      }
      if (window.matchMedia && window.matchMedia("(prefers-contrast: more)").matches) {
        var contrastToggle = document.getElementById("a11y-high-contrast");
        if (contrastToggle) {
          contrastToggle.checked = true;
          document.documentElement.classList.add("a11y-high-contrast");
        }
      }
    })();

    // Update settings button indicator when any a11y toggle is active
    function updateBtnState() {
      if (!settingsBtn) return;
      var anyActive = false;
      toggles.forEach(function (t) { if (t.checked) anyActive = true; });
      settingsBtn.classList.toggle("a11y-active", anyActive);
    }
    updateBtnState();

    // Toggle handler
    toggles.forEach(function (toggle) {
      toggle.addEventListener("change", function () {
        var key = this.getAttribute("data-a11y");
        var cls = "a11y-" + key;
        if (this.checked) {
          document.documentElement.classList.add(cls);
          try { localStorage.setItem(STORAGE_PREFIX + key, "1"); } catch (e) {}
        } else {
          document.documentElement.classList.remove(cls);
          try { localStorage.setItem(STORAGE_PREFIX + key, "0"); } catch (e) {}
        }
        // Sync custom cursor body class
        if (key === "system-cursors") {
          document.body.classList.toggle("a11y-cursors-active", !this.checked);
        }
        // Re-apply accent when B&W theme toggles (forces blue override)
        if (key === "bw-theme") {
          var colorPicker = document.getElementById("accent-color");
          var hex = colorPicker ? colorPicker.value : "#00ff41";
          if (typeof applyAccent === "function") applyAccent(hex);
        }
        updateBtnState();
      });
    });

    // Reset all
    if (resetBtn) {
      resetBtn.addEventListener("click", function () {
        toggles.forEach(function (toggle) {
          var key = toggle.getAttribute("data-a11y");
          toggle.checked = false;
          document.documentElement.classList.remove("a11y-" + key);
          try { localStorage.removeItem(STORAGE_PREFIX + key); } catch (e) {}
        });
        // Restore custom cursors
        document.body.classList.add("a11y-cursors-active");
        updateBtnState();
      });
    }
  })();

})();
