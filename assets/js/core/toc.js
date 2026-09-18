/* === Hypervisor: Table of Contents === */

  // --- Floating TOC sidebar (SPA-aware) ---
  // The TOC content is injected by the router; this module handles
  // active heading tracking which must be reinitialized on every navigation.
  (function initTocLifecycle() {
    var tocSidebar = document.getElementById("toc-sidebar");
    var tocBody = document.getElementById("toc-body");
    var tocHead = document.getElementById("toc-head");
    if (!tocSidebar || !tocBody) return;

    var _scrollHandler = null;
    var _headingElements = [];
    var _linkMap = {};
    var _currentActive = null;

    // --- Compact card show/hide + collapse ---
    function showCard() {
      tocSidebar.classList.add("visible");
      // Default to condensed each time a doc's TOC appears — expand on click.
      tocSidebar.classList.add("collapsed");
      tocSidebar.setAttribute("aria-hidden", "false");
    }
    function hideCard() {
      tocSidebar.classList.remove("visible");
      tocSidebar.setAttribute("aria-hidden", "true");
    }
    // Header click collapses/expands the body (chevron rotates via CSS).
    // Uses the shared HvCollapsible primitive; the header + panel markup is
    // owned here, the primitive attaches only the toggle behavior.
    if (tocHead && window.HvCollapsible) {
      window.HvCollapsible.register({ header: tocHead, panel: tocSidebar, collapsed: true });
    } else if (tocHead) {
      // Fallback if the primitive is unavailable (defensive; should not happen).
      tocHead.addEventListener("click", function () {
        tocSidebar.classList.toggle("collapsed");
      });
    }

    function teardown() {
      if (_scrollHandler) {
        window.removeEventListener("scroll", _scrollHandler);
        _scrollHandler = null;
      }
      _headingElements = [];
      _linkMap = {};
      _currentActive = null;
      // Hide the card on navigation; init re-shows it when the next doc has a TOC.
      hideCard();
    }

    function init(fragment) {
      // The router already updated the TOC body innerHTML.
      // Show the card only when the doc actually has a TOC, then set up
      // active-heading tracking (highlights the current section in the card).
      var article = document.getElementById("content-target");
      if (!article) return;

      var tocLinks = tocBody.querySelectorAll("a[href]");
      if (!tocLinks.length) {
        hideCard();
        return;
      }
      showCard();

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
