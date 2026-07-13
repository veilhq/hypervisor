/* === Splash Screen — 5s minimum, dismiss after prefs applied === */

(function initSplash() {
  var splash = document.getElementById("hv-splash");
  if (!splash) return;

  // Only show on first visit this session
  var seen = false;
  try { seen = sessionStorage.getItem("__hv_splash_seen") === "1"; } catch (e) {}

  if (seen) {
    splash.parentNode.removeChild(splash);
    document.documentElement.classList.remove("hv-splash-active");
    return;
  }

  // Lock scrollbars while splash is visible
  document.documentElement.classList.add("hv-splash-active");
  try { sessionStorage.setItem("__hv_splash_seen", "1"); } catch (e) {}

  // Two conditions must be met before dismiss:
  // 1. Minimum 5 seconds have elapsed
  // 2. Preferences have been applied (applyAllPreferences called __dismissSplash)
  var minElapsed = false;
  var prefsReady = false;
  var dismissed = false;

  function tryDismiss() {
    if (dismissed || !minElapsed || !prefsReady) return;
    dismissed = true;
    splash.classList.add("hv-splash-hidden");
    setTimeout(function () {
      if (splash.parentNode) splash.parentNode.removeChild(splash);
      document.documentElement.classList.remove("hv-splash-active");
    }, 700);
  }

  // Condition 1: 2s minimum
  setTimeout(function () {
    minElapsed = true;
    tryDismiss();
  }, 2000);

  // Condition 2: prefs applied (called by applyAllPreferences in 00-core.js)
  window.__dismissSplash = function () {
    prefsReady = true;
    tryDismiss();
  };

  // Safety net: dismiss after 4s max regardless (e.g. bridge failure)
  setTimeout(function () {
    if (!dismissed) {
      dismissed = true;
      splash.classList.add("hv-splash-hidden");
      setTimeout(function () {
        if (splash.parentNode) splash.parentNode.removeChild(splash);
        document.documentElement.classList.remove("hv-splash-active");
      }, 700);
    }
  }, 4000);
})();
