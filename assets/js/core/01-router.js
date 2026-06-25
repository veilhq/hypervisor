/* === Hypervisor: SPA Router === */
/* Fragment-based navigation — loads content JSON and swaps <main> innerHTML */

(function () {
  "use strict";

  // --- Route → fragment path mapping ---
  // Old-style URLs:  /work/done/my-item/index.html  → fragment: /content/work/done/my-item.json
  // Directory index: /work/index.html               → fragment: /content/work.json
  // Homepage:        / or /index.html               → fragment: /content/home.json
  // Pinboard:        /_pins/index.html              → fragment: /content/_pins.json
  // Learn:           /learn/my-topic/index.html     → fragment: /content/learn/my-topic.json
  // Learn index:     /learn/index.html              → fragment: /content/learn.json
  // Utility:         /_utils/password-gen/index.html→ fragment: /content/_utils/password-gen.json
  // 404:             (fallback)                     → fragment: /content/404.json

  var contentTarget = document.getElementById("content-target");
  var tocBody = document.getElementById("toc-body");
  var tocSidebar = document.getElementById("toc-sidebar");
  var pageMain = document.getElementById("page-main");
  var sourcePath = document.getElementById("source-path");
  var breadcrumbsNav = document.querySelector(".breadcrumbs");

  // Feature lifecycle registry
  var _teardownHooks = [];
  var _initHooks = [];
  var _currentFragment = null;

  // --- Public API ---
  window.__router = {
    navigate: navigate,
    onNavigate: onNavigate,
    reload: reloadCurrent,
    getCurrentFragment: function () { return _currentFragment; },
    applyFragment: applyFragment,
    openInTab: function (url) { if (window.__tabs) window.__tabs.openInTab(url); },
  };

  /**
   * Register teardown and init functions for the content lifecycle.
   * @param {Function|null} teardown - Called before content swap (cleanup old content bindings)
   * @param {Function|null} init - Called after content swap (initialize new content bindings)
   */
  function onNavigate(teardown, init) {
    if (teardown) _teardownHooks.push(teardown);
    if (init) _initHooks.push(init);
  }

  // --- URL → fragment path resolution ---
  function resolveFragmentPath(pathname) {
    // Normalize: strip trailing slashes, handle /index.html suffix
    var path = pathname.replace(/\/index\.html$/, "").replace(/\/$/, "");

    // Homepage
    if (!path || path === "") return "/content/home.json";

    // Strip leading slash for path manipulation
    var clean = path.replace(/^\//, "");

    return "/content/" + clean + ".json";
  }

  // --- Breadcrumb rendering ---
  function renderBreadcrumbs(parts) {
    if (!breadcrumbsNav) return;

    var crumbs = ['<a href="/index.html" class="crumb crumb-link">~</a>'];
    var accumulated = "";

    for (var i = 0; i < parts.length; i++) {
      var part = parts[i];
      var label = part.replace(/-/g, " ").replace(/_/g, " ");
      accumulated = accumulated ? accumulated + "/" + part : part;

      if (i < parts.length - 1) {
        var link = "/" + accumulated + "/index.html";
        crumbs.push('<a href="' + link + '" class="crumb crumb-link">' + label + '</a>');
      } else {
        crumbs.push('<span class="crumb">' + label + '</span>');
      }
    }

    breadcrumbsNav.innerHTML = crumbs.join('<span class="crumb-sep"><i data-lucide="chevron-right"></i></span>');

    // Re-render lucide icons in breadcrumbs
    if (window.lucide) {
      lucide.createIcons({ nodes: breadcrumbsNav.querySelectorAll("[data-lucide]"), attrs: { "stroke-width": 1.5 } });
    }
  }

  // --- TOC update ---
  function updateToc(tocHtml) {
    if (!tocSidebar || !tocBody) return;

    if (tocHtml) {
      tocBody.innerHTML = tocHtml;
      tocSidebar.classList.add("visible");
      if (pageMain) pageMain.classList.add("has-toc");
    } else {
      tocBody.innerHTML = "";
      tocSidebar.classList.remove("visible");
      if (pageMain) pageMain.classList.remove("has-toc");
    }
  }

  // --- Nav rail active state ---
  function updateNavActive(breadcrumbs) {
    var navItems = document.querySelectorAll(".site-nav-item, .site-nav-child");
    navItems.forEach(function (item) { item.classList.remove("active"); });

    if (!breadcrumbs || !breadcrumbs.length) return;

    // Match the deepest category
    var category = breadcrumbs[0];
    var subCategory = breadcrumbs.length > 1 ? breadcrumbs[0] + "/" + breadcrumbs[1] : null;

    navItems.forEach(function (item) {
      var cat = item.getAttribute("data-category");
      if (cat === category || cat === subCategory) {
        item.classList.add("active");
      }
    });

    // Show children panel for active parent
    var childPanels = document.querySelectorAll(".site-nav-children");
    childPanels.forEach(function (panel) {
      var parent = panel.getAttribute("data-parent");
      panel.classList.toggle("open", parent === category);
    });
  }

  // --- Mermaid lazy loading ---
  var _mermaidLoaded = false;
  var _mermaidLoading = false;

  function loadMermaid(callback) {
    if (_mermaidLoaded) { callback(); return; }
    if (_mermaidLoading) {
      // Wait for existing load
      var check = setInterval(function () {
        if (_mermaidLoaded) { clearInterval(check); callback(); }
      }, 50);
      return;
    }
    _mermaidLoading = true;
    var script = document.createElement("script");
    script.src = "https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.min.js";
    script.onload = function () {
      mermaid.initialize({
        startOnLoad: false,
        theme: "dark",
        themeVariables: {
          darkMode: true,
          background: "#000000",
          primaryColor: "#0a2a0a",
          primaryTextColor: "#00ff41",
          primaryBorderColor: "#00ff41",
          lineColor: "#00ff41",
          secondaryColor: "#1a1a00",
          secondaryTextColor: "#ffb000",
          secondaryBorderColor: "#ffb000",
          tertiaryColor: "#001a1a",
          tertiaryTextColor: "#00cccc",
          tertiaryBorderColor: "#00cccc",
          noteBkgColor: "#0a0a0a",
          noteTextColor: "#b0b0b0",
          noteBorderColor: "#333333",
          fontFamily: "'Departure Mono', 'JetBrains Mono', 'Cascadia Code', monospace",
          fontSize: "14px"
        },
        flowchart: { curve: "linear", padding: 15 },
        er: { useMaxWidth: true },
        sequence: { useMaxWidth: true, mirrorActors: false }
      });
      _mermaidLoaded = true;
      _mermaidLoading = false;
      callback();
    };
    document.head.appendChild(script);
  }

  function renderMermaid() {
    var diagrams = contentTarget.querySelectorAll(".mermaid");
    if (!diagrams.length) return;
    loadMermaid(function () {
      mermaid.run({ nodes: diagrams });
    });
  }

  // --- Content swap with transition ---
  var _isTransitioning = false;
  var TRANSITION_OUT = 140;  // ms fade-out
  var TRANSITION_IN = 200;  // ms fade-in

  function applyFragment(fragment, pushState, targetPath) {
    // Run teardown hooks
    for (var i = 0; i < _teardownHooks.length; i++) {
      try { _teardownHooks[i](); } catch (e) {}
    }

    // Store current fragment
    _currentFragment = fragment;

    // Update document title
    document.title = (fragment.title || "Hypervisor") + " \u2014 Hypervisor";

    // Update source path in footer
    if (sourcePath) {
      sourcePath.textContent = fragment.sourcePath || "";
    }

    // Update breadcrumbs
    renderBreadcrumbs(fragment.breadcrumbs || []);

    // Update TOC
    updateToc(fragment.toc || "");

    // Update nav active state
    updateNavActive(fragment.breadcrumbs || []);

    // Push history state
    if (pushState && targetPath) {
      history.pushState({ path: targetPath }, "", targetPath);
    }

    // --- Transition: fade out → swap → fade in ---
    // Skip animation for reload (no visual flash needed) or reduced motion
    var isReload = !pushState && !targetPath;
    var reducedMotion = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    var skipTransition = isReload || reducedMotion || document.documentElement.classList.contains("a11y-reduce-motion");

    if (skipTransition || !contentTarget) {
      // Immediate swap (reload or a11y)
      doSwap(fragment);
      doPostSwap(fragment);
    } else {
      // Animated swap
      contentTarget.classList.add("rt-fade-out");
      setTimeout(function () {
        doSwap(fragment);
        contentTarget.classList.remove("rt-fade-out");
        contentTarget.classList.add("rt-fade-in");
        doPostSwap(fragment);
        setTimeout(function () {
          contentTarget.classList.remove("rt-fade-in");
        }, TRANSITION_IN);
      }, TRANSITION_OUT);
    }
  }

  function doSwap(fragment) {
    // Swap content
    if (contentTarget) {
      contentTarget.innerHTML = fragment.html || "";
    }

    // Scroll to top (unless navigating with a hash)
    if (!window.location.hash) {
      window.scrollTo(0, 0);
    }
  }

  function doPostSwap(fragment) {
    // Render lucide icons in new content
    if (window.lucide) {
      lucide.createIcons({ nodes: contentTarget.querySelectorAll("[data-lucide]"), attrs: { "stroke-width": 1.5 } });
    }

    // Execute inline scripts in injected content (innerHTML doesn't run <script> tags)
    var scripts = contentTarget.querySelectorAll("script");
    scripts.forEach(function (oldScript) {
      var newScript = document.createElement("script");
      if (oldScript.src) {
        newScript.src = oldScript.src;
      } else {
        newScript.textContent = oldScript.textContent;
      }
      Array.from(oldScript.attributes).forEach(function (attr) {
        newScript.setAttribute(attr.name, attr.value);
      });
      oldScript.parentNode.replaceChild(newScript, oldScript);
    });

    // Lazy-load mermaid if needed
    if (fragment.hasMermaid) {
      renderMermaid();
    }

    // Run init hooks
    for (var j = 0; j < _initHooks.length; j++) {
      try { _initHooks[j](fragment); } catch (e) {}
    }

    // Handle hash scrolling
    if (window.location.hash) {
      var hashTarget = document.getElementById(window.location.hash.slice(1));
      if (hashTarget) {
        setTimeout(function () { hashTarget.scrollIntoView(); }, 10);
      }
    }

    // Fire a custom event for loose-coupled modules
    window.dispatchEvent(new CustomEvent("routeChanged", { detail: fragment }));
  }

  // --- Navigation ---
  function navigate(url, pushState) {
    if (pushState === undefined) pushState = true;

    // Parse the URL
    var a = document.createElement("a");
    a.href = url;
    var pathname = a.pathname;
    var hash = a.hash;

    // Check if this is a prototype link (raw HTML, not a fragment)
    // Skip the prototypes index itself — only redirect actual prototype sub-pages
    if (pathname.indexOf("/prototypes/") === 0 && pathname !== "/prototypes/index.html") {
      window.location.href = url;
      return;
    }

    var fragmentPath = resolveFragmentPath(pathname);

    fetch(fragmentPath).then(function (res) {
      if (!res.ok) {
        // Try 404 fragment
        return fetch("/content/404.json").then(function (r) { return r.json(); });
      }
      return res.json();
    }).then(function (fragment) {
      applyFragment(fragment, pushState, pathname + (hash || ""));
    }).catch(function (err) {
      console.error("[router] Navigation failed:", err);
    });
  }

  // --- Reload current fragment (for live-reload) ---
  function reloadCurrent() {
    var pathname = window.location.pathname;
    var fragmentPath = resolveFragmentPath(pathname);

    // Cache-bust to ensure we get the freshly-built fragment
    var bustUrl = fragmentPath + "?t=" + Date.now();

    fetch(bustUrl).then(function (res) {
      if (!res.ok) return null;
      return res.json();
    }).then(function (fragment) {
      if (fragment) {
        applyFragment(fragment, false, null);
      }
    }).catch(function () {});
  }

  // --- Link click interception ---
  document.addEventListener("click", function (e) {
    // Find the closest <a> element
    var link = e.target.closest("a[href]");
    if (!link) return;

    var href = link.getAttribute("href");
    if (!href) return;

    // Skip external links, anchors-only, and non-http(s)
    if (href.startsWith("http://") || href.startsWith("https://")) return;
    if (href.startsWith("#")) {
      // Same-page anchor — scroll to it
      e.preventDefault();
      var target = document.getElementById(href.slice(1));
      if (target) target.scrollIntoView({ behavior: "smooth" });
      history.replaceState(null, "", href);
      return;
    }
    if (href.startsWith("mailto:") || href.startsWith("tel:")) return;

    // Skip links with target="_blank" or download attribute
    if (link.hasAttribute("download") || link.getAttribute("target") === "_blank") return;

    // Ctrl+click / Meta+click / Shift+click → open in new tab
    if (e.ctrlKey || e.metaKey || e.shiftKey) {
      // Handled by mousedown listener below
      e.preventDefault();
      return;
    }

    // This is an internal navigation — intercept it
    e.preventDefault();
    navigate(href, true);
  });

  // --- Popstate (back/forward) ---
  window.addEventListener("popstate", function (e) {
    navigate(window.location.pathname + window.location.hash, false);
  });

  // --- Middle-click → open in new tab ---
  document.addEventListener("auxclick", function (e) {
    if (e.button !== 1) return; // only middle-click
    var link = e.target.closest("a[href]");
    if (!link) return;
    var href = link.getAttribute("href");
    if (!href) return;
    if (href.startsWith("http://") || href.startsWith("https://") || href.startsWith("#") || href.startsWith("mailto:") || href.startsWith("tel:")) return;
    if (link.hasAttribute("download") || link.getAttribute("target") === "_blank") return;
    e.preventDefault();
    if (window.__tabs) window.__tabs.openInTab(href);
  });

  // --- Ctrl+click / middle-click via mousedown (prevents browser default) ---
  document.addEventListener("mousedown", function (e) {
    // Only handle left-click with modifier or middle-click
    var isModifiedLeft = (e.button === 0 && (e.ctrlKey || e.metaKey || e.shiftKey));
    var isMiddle = (e.button === 1);
    if (!isModifiedLeft && !isMiddle) return;

    var link = e.target.closest("a[href]");
    if (!link) return;
    var href = link.getAttribute("href");
    if (!href) return;
    if (href.startsWith("http://") || href.startsWith("https://") || href.startsWith("#") || href.startsWith("mailto:") || href.startsWith("tel:")) return;
    if (link.hasAttribute("download") || link.getAttribute("target") === "_blank") return;

    // Prevent the browser from opening a new OS/browser tab
    e.preventDefault();
    if (window.__tabs) window.__tabs.openInTab(href);
  });

  // --- Initial page load ---
  // On first load, fetch the fragment for the current URL and render it
  function initialLoad() {
    var pathname = window.location.pathname;
    var hash = window.location.hash;
    navigate(pathname + hash, false);
  }

  // Run initial load once DOM is ready
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initialLoad);
  } else {
    initialLoad();
  }

  // --- Scroll progress bar ---
  (function initScrollProgress() {
    var bar = document.createElement("div");
    bar.className = "scroll-progress";
    document.body.appendChild(bar);

    var ticking = false;
    window.addEventListener("scroll", function () {
      if (!ticking) {
        requestAnimationFrame(function () {
          var scrollTop = window.scrollY;
          var docHeight = document.documentElement.scrollHeight - window.innerHeight;
          var pct = docHeight > 0 ? (scrollTop / docHeight) * 100 : 0;
          bar.style.width = pct + "%";
          ticking = false;
        });
        ticking = true;
      }
    });
  })();

})();
