/* === Hypervisor: Zen Mode === */

// Zen mode is a focus view for the home page. It hides the persistent chrome
// (topbar, site-nav, footer) and, instead of the full dashboard, composes an
// ambient stage: a prose-face greeting, a live search input, the app-tile
// launcher, and a minimal in-progress strip - centered, quiet, keyboard-first.
//
// Composition strategy — one source of truth, no duplicated wiring:
//   - The launcher row and the search input/results are MOVED (not cloned) into
//     the stage. Their event listeners are bound to those exact nodes
//     (launcher: per-node click in core; search: input listener in navigation),
//     so moving carries the behavior intact. Cloning would copy the DOM but
//     not the listeners (and would copy the __launcherWired expando, making the
//     re-wire pass skip the dead clones). On exit the nodes are moved back to
//     their original parents, leaving the home page unchanged.
//   - The in-progress work cards are CLONED. They are plain <a href> anchors
//     with no per-node listeners (navigation is native href, intercepted by the
//     SPA router via document-level delegation), so a clone keeps working.
//
// Zen is home-only: off the home page the chrome still hides but no stage is
// built, since the greeting + tiles + dashboard it composes from live only on
// the home dashboard.
//
// State persists across sessions through savePreference (localStorage cache +
// preferences.json truth). Desktop restore runs through applyAllPreferences in
// core; the localStorage fallback below covers a plain static build.

(function () {
  "use strict";

  var ZEN_KEY = "hypervisor-zen-mode";
  var WORK_VIEW_KEY = "hypervisor-zen-work-view";  // 'work' | 'activity'
  var BODY_CLASS = "zen-mode";      // persisted preference flag
  var STAGED_CLASS = "zen-staged";  // active-on-home visual flag (stage mounted)

  // Nodes moved out of their home while zen is active, with their origin so
  // they can be returned exactly. Each: { node, parent, nextSibling }.
  var relocated = [];
  var stageEl = null;

  function isZen() {
    return document.body.classList.contains(BODY_CLASS);
  }

  // --- Composition ---------------------------------------------------------

  // Record a node's current position, then move it into target. The recorded
  // position is what teardown restores, so order of relocation does not matter.
  function moveInto(node, target) {
    if (!node) return;
    relocated.push({ node: node, parent: node.parentNode, nextSibling: node.nextSibling });
    target.appendChild(node);
  }

  function buildStage() {
    // A content swap (e.g. the 'r' rebuild-reload) replaces #content-target's
    // innerHTML, which silently detaches a mounted stage without running our
    // teardown. If stageEl is set but no longer in the document, it is such an
    // orphan. Recover before rebuilding: the search input-row and results live
    // in #search-modal (OUTSIDE #content-target), so they were moved into the
    // stage and are now stranded in the detached fragment - restore them to
    // their recorded origins so the rebuild below can find and re-move them.
    // (The launcher/work nodes lived inside #content-target and are already
    // gone with the swap; their restore is a harmless no-op.) Then drop the
    // orphan and the staged flag so the guard does not wrongly bail.
    if (stageEl && !document.body.contains(stageEl)) {
      restoreRelocated();
      if (stageEl && stageEl.parentNode) stageEl.parentNode.removeChild(stageEl);
      stageEl = null;
      document.body.classList.remove(STAGED_CLASS);
    }

    // Only the home page carries the dashboard the stage composes from.
    var dashboard = document.querySelector(".dashboard-wrap");
    if (!dashboard || stageEl) return;

    var page = dashboard.parentNode;
    stageEl = document.createElement("div");
    stageEl.className = "zen-stage";

    // 1. Greeting — prose face. Zen uses a text-only greeting: the shared
    //    picker also returns kaomoji emotes (sanctioned character elsewhere),
    //    but the zen stage reads better with a plain prose line. Pick until a
    //    non-emote comes up (bounded so a degenerate picker can't loop), then
    //    set the text directly so no .emote glow class is applied.
    var greeting = document.createElement("div");
    greeting.className = "zen-greeting";
    if (window.HvGreeting && typeof window.HvGreeting.pick === "function") {
      var picked = window.HvGreeting.pick();
      for (var attempt = 0; attempt < 12 && picked.isEmote; attempt++) {
        picked = window.HvGreeting.pick();
      }
      greeting.textContent = picked.isEmote ? "Workspace online." : picked.text;
    } else {
      greeting.textContent = "Workspace online.";
    }
    stageEl.appendChild(greeting);

    // 2. Launcher — move the live tile row in (per-node click handlers intact).
    var launcher = dashboard.querySelector(".launcher-row");
    if (launcher) moveInto(launcher, stageEl);

    // 3. Search — move the live input row + results box in, so the existing
    //    input listener (text + WI-id fast-path + semantic) drives them inline.
    //    The results box floats (absolute) so a full result list overlays
    //    downward instead of pushing the launcher/work siblings off the page.
    var searchWrap = document.createElement("div");
    searchWrap.className = "zen-search";
    var inputRow = document.querySelector("#search-modal .search-input-row");
    var resultsBox = document.getElementById("search-results");
    if (inputRow) moveInto(inputRow, searchWrap);
    if (resultsBox) moveInto(resultsBox, searchWrap);
    stageEl.appendChild(searchWrap);

    // 4. Lower section — a toggle between the active-work grid and the recent
    //    activity list. Both are server-rendered in the hidden dashboard; clone
    //    each (plain anchors, safe to clone) and show one at a time. The choice
    //    persists via savePreference, defaulting to the work view.
    var workGrid = dashboard.querySelector(".work-card-grid");
    var activityRows = dashboard.querySelectorAll(".home-section-recent .pulse-row-recent");
    if (workGrid || activityRows.length) {
      var section = document.createElement("div");
      section.className = "zen-section";

      // Wordless cycle button: a single --comp pill (the .pill-toggle
      // primitive) advances the section between work and activity on each
      // click. The control carries no state - the content below shows which
      // view is active. Minimal, low-ink.
      var toggle = document.createElement("button");
      toggle.className = "pill-toggle zen-section-toggle";
      toggle.setAttribute("type", "button");
      toggle.setAttribute("aria-label", "Switch between work and activity");
      toggle.setAttribute("data-tooltip", "Switch work / activity");
      section.appendChild(toggle);

      // Work view — the cloned work-card grid.
      var workView = document.createElement("div");
      workView.className = "zen-work zen-section-view";
      workView.setAttribute("data-view", "work");
      if (workGrid) {
        var workClone = workGrid.cloneNode(true);
        workClone.classList.add("zen-work-grid");
        workView.appendChild(workClone);
      } else {
        workView.innerHTML = '<div class="zen-section-empty">no items in progress</div>';
      }
      section.appendChild(workView);

      // Activity view — the cloned recent-activity rows.
      var activityView = document.createElement("div");
      activityView.className = "zen-activity zen-section-view";
      activityView.setAttribute("data-view", "activity");
      if (activityRows.length) {
        activityRows.forEach(function (row) {
          activityView.appendChild(row.cloneNode(true));
        });
      } else {
        activityView.innerHTML = '<div class="zen-section-empty">no recent activity</div>';
      }
      section.appendChild(activityView);

      // --- View selection + persistence ---
      // Only two views; the pill cycles between them. selectView just shows the
      // chosen view (the pill itself carries no state).
      function selectView(view) {
        var isActivity = view === "activity";
        workView.classList.toggle("active", !isActivity);
        activityView.classList.toggle("active", isActivity);
      }
      function setView(view) {
        selectView(view);
        if (typeof window.savePreference === "function") {
          window.savePreference(WORK_VIEW_KEY, view);
        }
      }
      // Restore persisted choice (localStorage cache; defaults to work).
      var current = "work";
      try { current = localStorage.getItem(WORK_VIEW_KEY) === "activity" ? "activity" : "work"; } catch (ex) {}
      selectView(current);

      // Each click advances to the next (and only other) view.
      toggle.addEventListener("click", function () {
        current = current === "work" ? "activity" : "work";
        setView(current);
      });

      stageEl.appendChild(section);
    }

    page.insertBefore(stageEl, dashboard);

    // Flag the staged state at body level. All zen VISUAL css (chrome hide,
    // nav-offset zero, dashboard hide, gradient) is scoped to .zen-staged, not
    // .zen-mode, so those effects apply only while a stage is actually mounted
    // (home + zen on). .zen-mode stays the persisted preference flag; this is
    // the active-on-home visual flag. Keeping them in lockstep means navigating
    // to a doc tears the stage down and restores the chrome, instead of
    // stranding the page with no nav.
    document.body.classList.add(STAGED_CLASS);

    // Re-render any Lucide icons that rode along in the moved/cloned nodes.
    if (window.lucide) {
      try { window.lucide.createIcons({ attrs: { "stroke-width": 2 } }); } catch (ex) {}
    }
  }

  // Return every moved node to its recorded origin, in reverse so earlier
  // insertion points are still valid when later ones restore. Guards on the
  // origin parent still being connected to the document: a parent wiped by a
  // content swap (the launcher/work parents, which lived in #content-target)
  // would otherwise re-attach the node into a detached tree. Skipping those
  // lets them stay gone (correct - the swap already replaced them), while the
  // survivors (search nodes, whose #search-modal parent persists) go home.
  function restoreRelocated() {
    for (var i = relocated.length - 1; i >= 0; i--) {
      var rec = relocated[i];
      if (!document.body.contains(rec.parent)) continue;
      if (rec.nextSibling && rec.nextSibling.parentNode === rec.parent) {
        rec.parent.insertBefore(rec.node, rec.nextSibling);
      } else {
        rec.parent.appendChild(rec.node);
      }
    }
    relocated = [];
  }

  function teardownStage() {
    document.body.classList.remove(STAGED_CLASS);
    restoreRelocated();
    if (stageEl && stageEl.parentNode) stageEl.parentNode.removeChild(stageEl);
    stageEl = null;
  }

  // --- Apply / persist -----------------------------------------------------

  // Apply the mode class and (re)build or tear down the stage. Does not
  // persist — restore paths call this so a restore never writes back.
  function applyZen(on) {
    document.body.classList.toggle(BODY_CLASS, !!on);
    if (on) buildStage();
    else teardownStage();
  }

  function setZen(on) {
    applyZen(on);
    if (typeof window.savePreference === "function") {
      window.savePreference(ZEN_KEY, on ? "1" : "0");
    }
  }

  function toggleZen() {
    setZen(!isZen());
  }

  window.__zenMode = {
    toggle: toggleZen,
    set: setZen,
    apply: applyZen,
    isActive: isZen
  };

  // --- Input-focus guard ---------------------------------------------------
  // Mirrors the other single-key shortcuts: never fire while typing in the
  // search field, any input/textarea, or a contenteditable surface.
  function typingInField() {
    var active = document.activeElement;
    if (!active) return false;
    if (active === window.searchInput) return true;
    var tag = active.tagName;
    if (tag === "INPUT" || tag === "TEXTAREA") return true;
    if (active.isContentEditable) return true;
    return false;
  }

  // --- z-key toggle --------------------------------------------------------
  document.addEventListener("keydown", function (e) {
    // Bare "z" only — leave Ctrl+Z / Cmd+Z (undo) and modified combos alone.
    if (e.key !== "z" || e.ctrlKey || e.metaKey || e.altKey) return;
    if (typingInField()) return;
    e.preventDefault();
    toggleZen();
  });

  // --- Static-build restore fallback ---------------------------------------
  // Desktop restore runs via applyAllPreferences; a plain static build has no
  // bridge payload, so read the localStorage cache directly once DOM is ready
  // (buildStage needs the dashboard present).
  function restoreFromCache() {
    try {
      if (localStorage.getItem(ZEN_KEY) === "1") applyZen(true);
    } catch (ex) {}
  }
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", restoreFromCache);
  } else {
    restoreFromCache();
  }

  // --- SPA router integration ----------------------------------------------
  // The home dashboard is a router-loaded fragment, not static initial HTML, so
  // a zen restore on launch can fire before the fragment exists. Hook the
  // navigation lifecycle:
  //   - teardown (before content swap): return any relocated nodes to the
  //     dashboard first. The launcher and work-grid live inside #content-target,
  //     which the router is about to replace — restoring them first keeps them
  //     from being discarded with the old fragment.
  //   - init (after content swap): if zen is active and the new page is the
  //     home fragment, rebuild the stage against the freshly rendered dashboard.
  if (window.__router && typeof window.__router.onNavigate === "function") {
    window.__router.onNavigate(
      function zenTeardown() {
        if (stageEl) teardownStage();
      },
      function zenInit(fragment) {
        if (isZen() && fragment && fragment.pageType === "home") {
          buildStage();
        }
      }
    );
  }
})();
