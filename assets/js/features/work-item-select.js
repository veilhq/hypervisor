/* ===== Hypervisor: Work item multi-select =====
   Transient selection over to-do list rows so context-menu actions can apply
   to many work items at once.

     Ctrl/Cmd+click   toggle one row
     Shift+click      select the contiguous visible range from the anchor row
     Space            toggle the focused row (focus is on the row's link)
     Shift+Space      extend the range to the focused row
     Escape / plain click elsewhere / filter change / navigation  clear

   Only rows whose data-path is under work/to-do/ are selectable. Rows hidden
   by the list filters or inside a collapsed shelf are never range-selected,
   so a selection cannot act on rows the operator cannot see. Selectable rows
   carry data-selectable, which the router reads to suppress its own
   modified-click "open in tab" behavior on them.

   Public API: window.__hvWorkItemSelect
     paths()        selected paths in list (DOM) order
     has(path)      whether a path is selected
     size()         selection count
     clear()        drop the selection */

(function initWorkItemSelect() {
  var SELECTED_CLASS = "work-item-selected";
  var ROW_SELECTOR = ".todo-list li[data-selectable]";

  var selected = Object.create(null);
  var anchorPath = null;
  var liveRegion = null;

  function rowPath(row) {
    return row ? row.getAttribute("data-path") || "" : "";
  }

  function allRows() {
    return Array.prototype.slice.call(document.querySelectorAll(ROW_SELECTOR));
  }

  function isVisible(row) {
    if (row.classList.contains("todo-hidden")) return false;
    var shelf = row.closest(".app-shelf");
    if (shelf && (shelf.classList.contains("shelf-collapsed") || shelf.classList.contains("shelf-hidden"))) return false;
    return true;
  }

  function count() {
    return Object.keys(selected).length;
  }

  function announce() {
    if (!liveRegion) return;
    var n = count();
    liveRegion.textContent = n ? n + " work item" + (n === 1 ? "" : "s") + " selected" : "selection cleared";
  }

  function setRow(row, on) {
    var path = rowPath(row);
    if (!path) return;
    if (on) selected[path] = true;
    else delete selected[path];
    row.classList.toggle(SELECTED_CLASS, on);
  }

  function clear(silent) {
    var hadSelection = count() > 0;
    selected = Object.create(null);
    anchorPath = null;
    var marked = document.querySelectorAll("." + SELECTED_CLASS);
    for (var i = 0; i < marked.length; i++) marked[i].classList.remove(SELECTED_CLASS);
    if (hadSelection && !silent) announce();
  }

  function toggle(row) {
    var path = rowPath(row);
    setRow(row, !selected[path]);
    anchorPath = path;
    announce();
  }

  function selectRange(row) {
    var rows = allRows().filter(isVisible);
    var target = rows.indexOf(row);
    var anchor = -1;
    for (var i = 0; i < rows.length; i++) {
      if (rowPath(rows[i]) === anchorPath) { anchor = i; break; }
    }
    // No usable anchor (none set, or it scrolled out via a filter): start here.
    if (anchor === -1 || target === -1) {
      toggle(row);
      return;
    }
    var lo = Math.min(anchor, target);
    var hi = Math.max(anchor, target);
    for (var j = lo; j <= hi; j++) setRow(rows[j], true);
    announce();
  }

  // Mark eligible rows after each content swap. Rows are rebuilt on every
  // navigation and reload, so the in-memory selection is dropped with them.
  function init() {
    clear(true);
    var rows = document.querySelectorAll(".todo-list li[data-path]");
    for (var i = 0; i < rows.length; i++) {
      if (rowPath(rows[i]).indexOf("work/to-do/") === 0) rows[i].setAttribute("data-selectable", "");
    }
    if (!liveRegion) {
      liveRegion = document.createElement("div");
      liveRegion.className = "work-item-select-live";
      liveRegion.setAttribute("role", "status");
      liveRegion.setAttribute("aria-live", "polite");
      document.body.appendChild(liveRegion);
    }
  }

  function inTransientUi(target) {
    return !!(target.closest && target.closest(".context-menu, .confirm-dialog-overlay"));
  }

  document.addEventListener("click", function (e) {
    if (e.button !== 0) return;
    if (inTransientUi(e.target)) return;
    var row = e.target.closest(ROW_SELECTOR);
    var additive = e.ctrlKey || e.metaKey;
    if (row && (additive || e.shiftKey)) {
      e.preventDefault();
      if (e.shiftKey) selectRange(row);
      else toggle(row);
      return;
    }
    // Plain click anywhere (including on a row) drops the selection; a click
    // on a row link then navigates as usual.
    if (count()) clear();
  });

  // Shift+mousedown would otherwise start a native text-range selection.
  document.addEventListener("mousedown", function (e) {
    if (e.button === 0 && e.shiftKey && e.target.closest(ROW_SELECTOR)) e.preventDefault();
  });

  // Capture phase so Escape is seen before the context menu's own handler
  // closes it: Escape with a menu open only closes the menu.
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape") {
      if (document.querySelector(".context-menu.visible, .confirm-dialog-overlay")) return;
      if (count()) clear();
      return;
    }
    if (e.key !== " " && e.key !== "Spacebar") return;
    var row = document.activeElement && document.activeElement.closest
      ? document.activeElement.closest(ROW_SELECTOR) : null;
    if (!row) return;
    e.preventDefault();
    if (e.shiftKey) selectRange(row);
    else toggle(row);
  }, true);

  // Changing a filter can hide selected rows; drop the selection rather than
  // keep acting on rows that are no longer visible.
  function onFilterChange(e) {
    if (e.target.closest && e.target.closest("#todo-filters") && count()) clear();
  }
  document.addEventListener("input", onFilterChange);
  document.addEventListener("change", onFilterChange);

  window.__hvWorkItemSelect = {
    paths: function () {
      return allRows().map(rowPath).filter(function (path) { return selected[path]; });
    },
    has: function (path) { return !!selected[path]; },
    size: count,
    clear: function () { clear(); }
  };

  if (window.__router && window.__router.onNavigate) {
    window.__router.onNavigate(function () { clear(true); }, init);
  }
})();
