/* === Hypervisor: Zen Mode === */

// Zen mode is a focus view for the home page. It hides the persistent chrome
// (topbar, site-nav, footer) and, instead of the full dashboard, composes an
// ambient stage: a prose-face greeting, a live search input, and a minimal
// in-progress strip - centered, quiet, keyboard-first. The `a` key swaps the
// stage for the app launcher: the stage fades out and the launcher tiles
// animate in at center; `a`, Esc, or a click on empty space brings the stage back.
//
// Composition strategy - one source of truth, no duplicated wiring:
//   - The launcher row and the search input/results are MOVED (not cloned) into
//     the launcher layer / stage. Their event listeners are bound to those exact nodes
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
  var WORK_VIEW_KEY = "hypervisor-zen-work-view";  // 'work' | 'activity' | 'hidden'
  var BODY_CLASS = "zen-mode";      // persisted preference flag
  var STAGED_CLASS = "zen-staged";  // active-on-home visual flag (stage mounted)

  // Nodes moved out of their home while zen is active, with their origin so
  // they can be returned exactly. Each: { node, parent, nextSibling }.
  var relocated = [];
  var stageEl = null;
  var launcherEl = null;

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

  // The launcher row is MOVED into the panel so its per-node click handlers
  // (wired in core) keep working; teardown returns it via restoreRelocated.
  function buildLauncher(dashboard) {
    var row = dashboard.querySelector(".launcher-row");
    if (!row) return;

    launcherEl = document.createElement("div");
    launcherEl.className = "zen-launcher";

    launcherEl.setAttribute("aria-label", "Apps");
    moveInto(row, launcherEl);
    launcherEl.style.setProperty("--launcher-n", row.children.length);
    var subtitle = document.createElement("div");
    subtitle.className = "zen-launcher-subtitle";
    subtitle.textContent = "Select an application.";
    launcherEl.appendChild(subtitle);

    // Opening fades the stage out (.launching); closing replays its entrance.
    function setOpen(open) {
      launcherEl.classList.toggle("open", open);
      if (stageEl) stageEl.classList.toggle("launching", open);
    }
    // Launching an app closes the view; the tile's own handler does the launch.
    launcherEl.addEventListener("click", function (e) {
      if (e.target.closest(".launcher-box[data-launch]")) setOpen(false);
    });
    launcherEl.__setOpen = setOpen;

    document.body.appendChild(launcherEl);
  }

  function closeLauncher() {
    if (launcherEl && launcherEl.__setOpen) launcherEl.__setOpen(false);
  }

  function toggleLauncher() {
    if (!launcherEl) return;
    launcherEl.__setOpen(!launcherEl.classList.contains("open"));
  }

  function removeLauncher() {
    if (launcherEl && launcherEl.parentNode) {
      launcherEl.parentNode.removeChild(launcherEl);
    }
    launcherEl = null;
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
      removeLauncher();
      document.body.classList.remove(STAGED_CLASS);
    }

    // Only the home page carries the dashboard the stage composes from.
    var dashboard = document.querySelector(".dashboard-wrap");
    if (!dashboard || stageEl) return;

    var page = dashboard.parentNode;
    stageEl = document.createElement("div");
    stageEl.className = "zen-stage";

    // 1. Logo - clone the Hypervisor brand mark in above the greeting (plain
    //    inline SVG, no listeners, safe to clone). Centered by the stage's
    //    align-items. Hidden on the dashboard itself via CSS; shown only here.
    var logoSrc = dashboard.querySelector("[data-zen-logo]");
    if (logoSrc) {
      var logo = logoSrc.cloneNode(true);
      logo.classList.add("zen-logo");
      stageEl.appendChild(logo);
    }

    // 2. Greeting - prose face. Zen uses a text-only greeting: the shared
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

    // Launcher - a full-viewport layer shown in place of the stage on `a`.
    // Mounted on body (not in the stage): the stage's entrance animation holds
    // a transform, which would turn position:fixed into stage-relative.
    buildLauncher(dashboard);

    // Search - move the live input row + results box in, so the existing
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

    // 4. Lower section - a pill that cycles the lower area between the
    //    active-work grid, the recent activity list, and a hidden state (no
    //    section content at all). Both grids are server-rendered in the hidden
    //    dashboard; clone each (plain anchors, safe to clone) and show one, or
    //    neither. The choice persists via savePreference, defaulting to work.
    var workGrid = dashboard.querySelector(".work-card-grid");
    var activityRows = dashboard.querySelectorAll(".home-section-recent .pulse-row-recent");
    if (workGrid || activityRows.length) {
      var section = document.createElement("div");
      section.className = "zen-section";

      // Wordless cycle button: a single --comp pill (the .pill-toggle
      // primitive) advances the section through work, activity, and hidden on
      // each click. The control carries no state - the content below (or its
      // absence) shows which view is active. Minimal, low-ink.
      var toggle = document.createElement("button");
      toggle.className = "pill-toggle zen-section-toggle";
      toggle.setAttribute("type", "button");
      toggle.setAttribute("aria-label", "Switch between work and activity");
      toggle.setAttribute("data-tooltip", "Switch work / activity");
      section.appendChild(toggle);

      // Collapsible body: holds both views and is the element that
      // height-animates. The pill stays outside it (always visible), so the
      // hidden state can smoothly shrink the content while the control that
      // cycles back out remains on screen. The gradual height change is what
      // lets the greeting/launcher/search glide into their recentered position
      // instead of teleporting when the section empties.
      var sectionBody = document.createElement("div");
      sectionBody.className = "zen-section-body";
      section.appendChild(sectionBody);

      // Work view - the cloned work-card grid.
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
      sectionBody.appendChild(workView);

      // Activity view - the cloned recent-activity rows.
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
      sectionBody.appendChild(activityView);

      // --- View selection + persistence ---
      // Three views cycled by the pill: work, activity, and hidden. For work
      // and activity, show the chosen grid and keep the body open. For hidden,
      // the body collapses via its own max-height transition (the task-panel
      // collapse pattern) - crucially the outgoing grid KEEPS its .active
      // display so it fills the body's height while max-height animates 44rem
      // -> 0. Yanking display:none off the grid in the same frame would drop
      // the content instantly and leave max-height nothing to shrink against,
      // which read as an instant exit. Keeping it mounted lets the height
      // glide, and the surrounding greeting/launcher/search glide with it.
      var lastGrid = "work";
      function selectView(view) {
        // Stage-level flag so the greeting (which lives outside the section)
        // can scale up when the stage reaches its most minimal hidden state.
        stageEl.classList.toggle("section-hidden", view === "hidden");
        if (view === "hidden") {
          sectionBody.classList.add("collapsed");
          return; // leave whichever grid is .active mounted under the clip
        }
        lastGrid = view;
        sectionBody.classList.remove("collapsed");
        workView.classList.toggle("active", view === "work");
        activityView.classList.toggle("active", view === "activity");
      }
      function setView(view) {
        selectView(view);
        if (typeof window.savePreference === "function") {
          window.savePreference(WORK_VIEW_KEY, view);
        }
      }
      // Restore persisted choice (localStorage cache; defaults to work).
      var VIEWS = ["work", "activity", "hidden"];
      var current = "work";
      try {
        var saved = localStorage.getItem(WORK_VIEW_KEY);
        if (VIEWS.indexOf(saved) !== -1) current = saved;
      } catch (ex) {}
      selectView(current);

      // Each click advances to the next view, wrapping work -> activity ->
      // hidden -> work.
      toggle.addEventListener("click", function () {
        current = VIEWS[(VIEWS.indexOf(current) + 1) % VIEWS.length];
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
    removeLauncher();
  }

  // Esc or a click on empty space (anywhere off a tile) closes the launcher.
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape") closeLauncher();
  });
  document.addEventListener("mousedown", function (e) {
    if (launcherEl && launcherEl.classList.contains("open") &&
        !e.target.closest(".launcher-box")) closeLauncher();
  });

  // --- Apply / persist -----------------------------------------------------

  // Apply the mode class and (re)build or tear down the stage. Does not
  // persist - restore paths call this so a restore never writes back.
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
    // Bare "z" only - leave Ctrl+Z / Cmd+Z (undo) and modified combos alone.
    if (e.key !== "z" || e.ctrlKey || e.metaKey || e.altKey) return;
    if (typingInField()) return;
    e.preventDefault();
    toggleZen();
  });

  // --- a-key launcher ------------------------------------------------------
  // Bare "a" swaps the stage for the launcher; only live while the stage is up.
  document.addEventListener("keydown", function (e) {
    if (e.key !== "a" || e.ctrlKey || e.metaKey || e.altKey) return;
    if (!launcherEl || typingInField()) return;
    e.preventDefault();
    toggleLauncher();
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
  //     which the router is about to replace - restoring them first keeps them
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
