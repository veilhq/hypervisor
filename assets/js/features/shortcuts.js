/* === Hypervisor: Keyboard Shortcuts === */

  // --- Keyboard shortcuts overlay (? to toggle) ---
  (function initShortcuts() {
    var overlay = document.createElement("div");
    overlay.className = "shortcuts-overlay";
    overlay.setAttribute("role", "dialog");
    overlay.setAttribute("aria-label", "Keyboard shortcuts");
    overlay.innerHTML =
      '<div class="shortcuts-panel">' +
        '<div class="shortcuts-header">' +
          '<span class="shortcuts-title">Keyboard Shortcuts</span>' +
          '<button class="shortcuts-close" aria-label="Close">&times;</button>' +
        '</div>' +
        '<div class="shortcuts-body">' +
          '<div class="shortcut-row"><kbd>/</kbd><span>Focus search</span></div>' +
          '<div class="shortcut-row"><kbd>Ctrl+K</kbd><span>Command palette</span></div>' +
          '<div class="shortcut-row"><kbd>Esc</kbd><span>Close search / overlay</span></div>' +
          '<div class="shortcut-row"><kbd>↑</kbd> <kbd>↓</kbd><span>Navigate search results</span></div>' +
          '<div class="shortcut-row"><kbd>Enter</kbd><span>Open selected result</span></div>' +
          '<div class="shortcut-row"><kbd>?</kbd><span>Toggle this overlay</span></div>' +
          '<div class="shortcut-row"><kbd>w</kbd><span>Toggle reading width</span></div>' +
          '<div class="shortcut-row"><kbd>+</kbd> <kbd>-</kbd><span>Zoom in / out</span></div>' +
          '<div class="shortcut-row"><kbd>0</kbd><span>Reset zoom</span></div>' +
          '<div class="shortcut-row"><kbd>s</kbd><span>Toggle screensaver</span></div>' +
          '<div class="shortcut-row"><kbd>Ctrl+F4</kbd><span>Close active tab</span></div>' +
          '<div class="shortcut-row"><kbd>e</kbd><span>Export page as standalone HTML</span></div>' +
          '<div class="shortcut-row"><kbd>p</kbd><span>Go to pinboard</span></div>' +
          '<div class="shortcut-row" id="shortcut-logs" style="display:none"><kbd>l</kbd><span>Open log viewer</span></div>' +
          '<div class="shortcut-row" id="shortcut-rebuild" style="display:none"><kbd>r</kbd><span>Rebuild site</span></div>' +
          '<div class="shortcut-row" id="shortcut-fullscreen" style="display:none"><kbd>f</kbd><span>Toggle fullscreen</span></div>' +
        '</div>' +
      '</div>';
    document.body.appendChild(overlay);

    overlay.querySelector(".shortcuts-close").addEventListener("click", function () {
      overlay.classList.remove("visible");
    });
    overlay.addEventListener("click", function (e) {
      if (e.target === overlay) overlay.classList.remove("visible");
    });

    document.addEventListener("keydown", function (e) {
      if (e.key === "?" && document.activeElement !== searchInput &&
          document.activeElement.tagName !== "INPUT" &&
          document.activeElement.tagName !== "TEXTAREA") {
        e.preventDefault();
        overlay.classList.toggle("visible");
      }
      if (e.key === "w" && document.activeElement !== searchInput &&
          document.activeElement.tagName !== "INPUT" &&
          document.activeElement.tagName !== "TEXTAREA" &&
          !overlay.classList.contains("visible")) {
        var widthBtn = document.getElementById("width-toggle");
        if (widthBtn) widthBtn.click();
      }
      if ((e.key === "+" || e.key === "=") && document.activeElement !== searchInput &&
          document.activeElement.tagName !== "INPUT" &&
          document.activeElement.tagName !== "TEXTAREA" &&
          !overlay.classList.contains("visible")) {
        var zoomInBtn = document.getElementById("zoom-in");
        if (zoomInBtn) zoomInBtn.click();
      }
      if (e.key === "-" && document.activeElement !== searchInput &&
          document.activeElement.tagName !== "INPUT" &&
          document.activeElement.tagName !== "TEXTAREA" &&
          !overlay.classList.contains("visible")) {
        var zoomOutBtn = document.getElementById("zoom-out");
        if (zoomOutBtn) zoomOutBtn.click();
      }
      if (e.key === "0" && document.activeElement !== searchInput &&
          document.activeElement.tagName !== "INPUT" &&
          document.activeElement.tagName !== "TEXTAREA" &&
          !overlay.classList.contains("visible")) {
        var zoomLabel = document.getElementById("zoom-level");
        if (zoomLabel) {
          var evt = document.createEvent("MouseEvents");
          evt.initEvent("dblclick", true, true);
          zoomLabel.dispatchEvent(evt);
        }
      }
      if (e.key === "e" && document.activeElement !== searchInput &&
          document.activeElement.tagName !== "INPUT" &&
          document.activeElement.tagName !== "TEXTAREA" &&
          !overlay.classList.contains("visible")) {
        var exportBtn = document.getElementById("export-btn");
        if (exportBtn) exportBtn.click();
      }
      if (e.key === "p" && document.activeElement !== searchInput &&
          document.activeElement.tagName !== "INPUT" &&
          document.activeElement.tagName !== "TEXTAREA" &&
          !overlay.classList.contains("visible")) {
        var pinLink = document.getElementById("nav-pinboard-link");
        if (pinLink) window.location.href = pinLink.href;
      }
      if (e.key === "r" && document.activeElement !== searchInput &&
          document.activeElement.tagName !== "INPUT" &&
          document.activeElement.tagName !== "TEXTAREA" &&
          !overlay.classList.contains("visible")) {
        if (window.pywebview && window.pywebview.api && window.pywebview.api.rebuild) {
          try { sessionStorage.removeItem("__hv_splash_seen"); } catch (ex) {}
          window.pywebview.api.rebuild();
        }
      }
      if (e.key === "l" && document.activeElement !== searchInput &&
          document.activeElement.tagName !== "INPUT" &&
          document.activeElement.tagName !== "TEXTAREA" &&
          !overlay.classList.contains("visible")) {
        if (window.pywebview && window.pywebview.api) {
          window.location.href = "/_utils/log-viewer/index.html";
        }
      }
    });

    // Show rebuild shortcut row when running in PyWebView
    if (window.pywebview && window.pywebview.api) {
      var rebuildShortcutRow = document.getElementById("shortcut-rebuild");
      if (rebuildShortcutRow) rebuildShortcutRow.style.display = "";
      var logsShortcutRow = document.getElementById("shortcut-logs");
      if (logsShortcutRow) logsShortcutRow.style.display = "";
    }
  })();
