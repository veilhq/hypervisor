/* === Splash Screen — initial load only === */

(function initSplash() {
  var splash = document.getElementById("hv-splash");
  if (!splash) return;

  // Only show on first visit this session
  var seen = false;
  try { seen = sessionStorage.getItem("__hv_splash_seen") === "1"; } catch (e) {}

  if (seen) {
    // Already seen — remove immediately without animation
    splash.parentNode.removeChild(splash);
    document.documentElement.classList.remove("hv-splash-active");
    return;
  }

  // Lock scrollbars while splash is visible
  document.documentElement.classList.add("hv-splash-active");

  // Mark as seen for this session
  try { sessionStorage.setItem("__hv_splash_seen", "1"); } catch (e) {}

  // Fade out after 2 seconds, then remove from DOM
  setTimeout(function () {
    splash.classList.add("hv-splash-hidden");
    setTimeout(function () {
      if (splash.parentNode) splash.parentNode.removeChild(splash);
      document.documentElement.classList.remove("hv-splash-active");
    }, 700);
  }, 2000);
})();
