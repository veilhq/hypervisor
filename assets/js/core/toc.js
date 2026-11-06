/* === Hypervisor: Table of Contents === */

  // --- TOC flag + slide-in drawer (SPA-aware) ---
  // A flag pops out from behind the top-left edge of the doc surface; clicking
  // it slides a drawer in from the left holding the heading list. The router
  // injects the list into #toc-body on every navigation; this module reveals
  // the flag when the doc has a TOC, owns open/close, and tracks the active
  // heading while scrolling (which must be reinitialized on every navigation).
  (function initTocLifecycle() {
    var flagWrap = document.getElementById("toc-flag-wrap");
    var flag = document.getElementById("toc-flag");
    var flagHit = document.getElementById("toc-flag-hit");
    var drawer = document.getElementById("toc-drawer");
    var tocBody = document.getElementById("toc-body");
    if (!flagWrap || !flag || !drawer || !tocBody) return;

    var _scrollHandler = null;
    var _headingElements = [];
    var _linkMap = {};
    var _currentActive = null;
    var _drawerOpen = false;

    // --- Flag show/hide ---
    var _entranceTimer = null;
    function clearEntering() {
      flagWrap.classList.remove("entering");
      if (flagHit) flagHit.classList.remove("entering");
    }
    function playEntrance() {
      // Retrigger the CSS entrance on every navigation: remove the class, force
      // a reflow so the browser drops the running animation, then re-add it.
      clearEntering();
      // Force reflow to reset the animation.
      void flagWrap.offsetWidth;
      flagWrap.classList.add("entering");
      if (flagHit) flagHit.classList.add("entering");
      // Fallback: animationend won't fire under reduced-motion (animation:none),
      // so a hidden catcher would stay unclickable. Clear after the expected
      // total (delay 0.55s + motion-slow ~0.4s, padded) regardless.
      if (_entranceTimer) clearTimeout(_entranceTimer);
      _entranceTimer = setTimeout(clearEntering, 1200);
    }
    // Once the rise finishes, drop .entering so the catcher becomes clickable
    // and the wrap returns to its plain resting state.
    flagWrap.addEventListener("animationend", function (e) {
      if (e.animationName === "tocFlagRise") {
        if (_entranceTimer) { clearTimeout(_entranceTimer); _entranceTimer = null; }
        clearEntering();
      }
    });

    function showFlag() {
      flagWrap.classList.add("visible");
      if (flagHit) flagHit.classList.add("visible");
      playEntrance();
    }
    function hideFlag() {
      flagWrap.classList.remove("visible");
      flagWrap.classList.remove("entering");
      if (_entranceTimer) { clearTimeout(_entranceTimer); _entranceTimer = null; }
      if (flagHit) {
        flagHit.classList.remove("visible");
        flagHit.classList.remove("entering");
      }
      closeDrawer();
    }

    // --- Drawer open/close ---
    function openDrawer() {
      _drawerOpen = true;
      drawer.classList.add("open");
      drawer.setAttribute("aria-hidden", "false");
      flag.classList.add("active");
      flag.setAttribute("aria-expanded", "true");
    }
    function closeDrawer() {
      _drawerOpen = false;
      drawer.classList.remove("open");
      drawer.setAttribute("aria-hidden", "true");
      flag.classList.remove("active");
      flag.setAttribute("aria-expanded", "false");
    }
    function toggleDrawer() {
      if (_drawerOpen) closeDrawer(); else openDrawer();
    }

    // Bind flag/dismiss handlers once (the elements are shell-persistent).
    flag.addEventListener("click", function (e) {
      e.stopPropagation();
      toggleDrawer();
    });
    // The flag sits behind the surface; its transparent on-top hit-catcher is
    // what actually receives pointer events. Forward its clicks to the toggle.
    if (flagHit) {
      flagHit.addEventListener("click", function (e) {
        e.stopPropagation();
        toggleDrawer();
      });
      // The visible flag is behind the surface, so :hover never fires on it via
      // the pointer (the catcher is on top). Bridge hover from the catcher to a
      // class on the flag so the lift/brighten still reads on hover.
      flagHit.addEventListener("mouseenter", function () { flag.classList.add("hover"); });
      flagHit.addEventListener("mouseleave", function () { flag.classList.remove("hover"); });
    }
    // Click outside closes the drawer (but not clicks on the flag, its
    // hit-catcher, or the drawer itself).
    document.addEventListener("click", function (e) {
      if (!_drawerOpen) return;
      var onFlag = e.target === flag || flag.contains(e.target);
      var onHit = flagHit && (e.target === flagHit || flagHit.contains(e.target));
      if (!drawer.contains(e.target) && !onFlag && !onHit) {
        closeDrawer();
      }
    }, true); // capture: clicks that stop propagation still dismiss
    // Escape closes the drawer and returns focus to the flag.
    document.addEventListener("keydown", function (e) {
      if (_drawerOpen && e.key === "Escape") {
        closeDrawer();
        flag.focus();
      }
    });
    // A TOC link click navigates within the doc; close the drawer after.
    tocBody.addEventListener("click", function (e) {
      var link = e.target.closest ? e.target.closest("a[href^='#']") : null;
      if (link) closeDrawer();
    });

    function teardown() {
      if (_scrollHandler) {
        window.removeEventListener("scroll", _scrollHandler);
        _scrollHandler = null;
      }
      _headingElements = [];
      _linkMap = {};
      _currentActive = null;
      // Hide the flag on navigation; init re-shows it when the next doc has a TOC.
      hideFlag();
    }

    function init(fragment) {
      // The router already updated the TOC body innerHTML.
      // Show the flag only when the doc actually has a TOC, then set up
      // active-heading tracking (highlights the current section in the drawer).
      var article = document.getElementById("content-target");
      if (!article) return;

      var tocLinks = tocBody.querySelectorAll("a[href]");
      if (!tocLinks.length) {
        hideFlag();
        return;
      }
      showFlag();

      // Build id → link map
      _linkMap = {};
      var headingIds = [];
      tocLinks.forEach(function (link) {
        var href = link.getAttribute("href");
        if (href && href.startsWith("#")) {
          var id = decodeURIComponent(href.slice(1));
          _linkMap[id] = link;
          headingIds.push(id);
        }
      });

      _currentActive = null;

      function setActive(id) {
        if (_currentActive === id) return;
        if (_currentActive && _linkMap[_currentActive]) {
          _linkMap[_currentActive].classList.remove("toc-active");
        }
        _currentActive = id;
        if (id && _linkMap[id]) {
          _linkMap[id].classList.add("toc-active");
        }
      }

      // Collect heading elements
      _headingElements = [];
      headingIds.forEach(function (id) {
        var el = document.getElementById(id);
        if (el) _headingElements.push({ id: id, el: el });
      });

      if (!_headingElements.length) return;

      var scrollTicking = false;
      var TOPBAR_HEIGHT = 80;

      _scrollHandler = function () {
        if (!scrollTicking) {
          requestAnimationFrame(function () {
            var active = null;
            for (var i = _headingElements.length - 1; i >= 0; i--) {
              var rect = _headingElements[i].el.getBoundingClientRect();
              if (rect.top <= TOPBAR_HEIGHT) {
                active = _headingElements[i].id;
                break;
              }
            }
            if (!active && _headingElements.length) {
              active = _headingElements[0].id;
            }
            setActive(active);
            scrollTicking = false;
          });
          scrollTicking = true;
        }
      };

      window.addEventListener("scroll", _scrollHandler);

      // Set initial active
      if (_headingElements.length) {
        var initRect = _headingElements[0].el.getBoundingClientRect();
        if (initRect.top <= TOPBAR_HEIGHT) {
          for (var i = _headingElements.length - 1; i >= 0; i--) {
            if (_headingElements[i].el.getBoundingClientRect().top <= TOPBAR_HEIGHT) {
              setActive(_headingElements[i].id);
              break;
            }
          }
        } else {
          setActive(_headingElements[0].id);
        }
      }
    }

    // Register with router lifecycle
    if (window.__router) {
      window.__router.onNavigate(teardown, init);
    }
  })();
