/* === Hypervisor: Action Registry === */

  // Central registry for page-level and global commands. Feature modules
  // register their behavior here (editor, export, explorer, pins, share key,
  // end sprint, new window) so callers -- the right-click context menu and the
  // command palette -- invoke actions directly instead of clicking hidden
  // buttons. This replaces the old bottom-right actions drawer.
  //
  // The 00- filename prefix sorts this ahead of other feature modules so the
  // namespace exists before they register into it. The self-init idiom below
  // keeps registration order-independent regardless.

  (function initActionRegistry() {
    var A = (window.__hvActions = window.__hvActions || {});

    // --- Shared helpers -------------------------------------------------

    // True when running inside the PyWebView desktop shell (bridge present).
    A.hasBridge = function () {
      return !!(window.pywebview && window.pywebview.api);
    };

    A.api = function () {
      return A.hasBridge() ? window.pywebview.api : null;
    };

    // Source path of the currently displayed document, or "" on index/home
    // pages. Populated at runtime by the router into #source-path.
    A.currentDocPath = function () {
      var el = document.getElementById("source-path");
      return el ? (el.textContent || "").trim() : "";
    };

    // Title of the current document, falling back to the file basename.
    A.currentDocTitle = function () {
      var h1 = document.querySelector("#content-target h1");
      if (h1 && h1.textContent.trim()) return h1.textContent.trim();
      var p = A.currentDocPath();
      return p ? p.split("/").pop().replace(/\.md$/, "") : "";
    };

    // --- Registration -------------------------------------------------
    // Feature modules call A.register("edit", fn) during their own init.
    // Callers use A.run("edit") which is a no-op if nothing registered.
    var _fns = {};

    A.register = function (name, fn) {
      _fns[name] = fn;
    };

    A.has = function (name) {
      return typeof _fns[name] === "function";
    };

    A.run = function (name, arg) {
      if (typeof _fns[name] === "function") return _fns[name](arg);
      return undefined;
    };
  })();
