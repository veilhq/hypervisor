/* === Hypervisor: Info flag (file metadata) === */

  // A second flag beside Contents. For non-work-item docs the renderer emits a
  // hidden .doc-meta-source block (tags, dates, extras); on every navigation
  // this module mounts it in the Info drawer and reveals the flag. The flag
  // markup and CSS are the Contents flag's, so the two read as one family.
  (function initMetaFlag() {
    var flagWrap = document.getElementById("meta-flag-wrap");
    var flag = document.getElementById("meta-flag");
    var flagHit = document.getElementById("meta-flag-hit");
    var drawer = document.getElementById("meta-drawer");
    var body = document.getElementById("meta-body");
    var tocFlag = document.getElementById("toc-flag");
    var tocWrap = document.getElementById("toc-flag-wrap");
    if (!flagWrap || !flag || !drawer || !body) return;

    var _open = false;
    var _timer = null;
    var _GAP = 8;

    // Sit flush against the Contents flag when it is showing, else take its slot.
    function placeSlot() {
      var offset = 0;
      var hitWidth = 0;
      if (tocWrap && tocFlag && tocWrap.classList.contains("visible")) {
        offset = tocFlag.offsetWidth + _GAP;
      }
      [flagWrap, flagHit, drawer].forEach(function (el) {
        if (el) el.style.setProperty("--flag-slot-offset", offset + "px");
      });
      if (flagHit) flagHit.style.width = flag.offsetWidth + "px";
    }

    function clearEntering() {
      flagWrap.classList.remove("entering");
      if (flagHit) flagHit.classList.remove("entering");
    }
    function show() {
      placeSlot();
      flagWrap.classList.add("visible");
      if (flagHit) flagHit.classList.add("visible");
      clearEntering();
      void flagWrap.offsetWidth;
      flagWrap.classList.add("entering");
      if (flagHit) flagHit.classList.add("entering");
      if (_timer) clearTimeout(_timer);
      _timer = setTimeout(clearEntering, 1200);
    }
    function hide() {
      flagWrap.classList.remove("visible");
      clearEntering();
      if (_timer) { clearTimeout(_timer); _timer = null; }
      if (flagHit) flagHit.classList.remove("visible");
      closeDrawer();
    }
    flagWrap.addEventListener("animationend", function (e) {
      if (e.animationName === "tocFlagRise") {
        if (_timer) { clearTimeout(_timer); _timer = null; }
        clearEntering();
      }
    });

    function openDrawer() {
      _open = true;
      drawer.classList.add("open");
      drawer.setAttribute("aria-hidden", "false");
      flag.classList.add("active");
      flag.setAttribute("aria-expanded", "true");
    }
    function closeDrawer() {
      _open = false;
      drawer.classList.remove("open");
      drawer.setAttribute("aria-hidden", "true");
      flag.classList.remove("active");
      flag.setAttribute("aria-expanded", "false");
    }
    function toggle(e) {
      e.stopPropagation();
      if (_open) closeDrawer(); else openDrawer();
    }

    flag.addEventListener("click", toggle);
    if (flagHit) {
      flagHit.addEventListener("click", toggle);
      flagHit.addEventListener("mouseenter", function () { flag.classList.add("hover"); });
      flagHit.addEventListener("mouseleave", function () { flag.classList.remove("hover"); });
    }
    document.addEventListener("click", function (e) {
      if (!_open) return;
      var t = e.target;
      var onFlag = t === flag || flag.contains(t);
      var onHit = flagHit && (t === flagHit || flagHit.contains(t));
      if (!drawer.contains(t) && !onFlag && !onHit) closeDrawer();
    }, true); // capture: clicks that stop propagation still dismiss
    document.addEventListener("keydown", function (e) {
      if (_open && e.key === "Escape") {
        closeDrawer();
        flag.focus();
      }
    });

    function teardown() {
      body.innerHTML = "";
      hide();
    }

    function init() {
      var source = document.querySelector("#content-target .doc-meta-source");
      if (!source || !source.textContent.trim()) {
        hide();
        return;
      }
      body.innerHTML = source.innerHTML;
      // The Contents flag reveals in its own init hook; place after it settles.
      show();
      if (document.fonts && document.fonts.ready) {
        document.fonts.ready.then(placeSlot);
      }
      setTimeout(placeSlot, 0);
    }

    if (window.__router) {
      window.__router.onNavigate(teardown, init);
    }
  })();
