/* === Hypervisor: Rebuild Queue ===
 *
 * File changes are queued by the desktop watcher and built together after a
 * quiet period. While changes are waiting, a sticky toast shows the pending
 * count with a "Rebuild now" action that flushes the queue immediately.
 *
 * Python calls window.__hvRebuildQueue(count, full) as the queue changes;
 * count 0 clears the toast. Bridge method used: flush_rebuild_queue.
 */
(function () {
  "use strict";

  var KEY = "rebuild-queue";
  var UPDATE_MS = 800;
  var shown = null;
  var shownCount = 0;
  var updateTimer = null;

  function flush() {
    var a = window.pywebview && window.pywebview.api;
    if (!a || typeof a.flush_rebuild_queue !== "function") return;
    try { a.flush_rebuild_queue(); } catch (e) {}
  }

  function label(count, full) {
    var n = count + (count === 1 ? " change" : " changes");
    return n + " queued" + (full ? " (full rebuild)" : "");
  }

  function show(count, full) {
    if (!window.HvToast) return;
    shown = window.HvToast.show({
      variant: "info",
      message: label(count, full),
      duration: "sticky",
      dedupeKey: KEY,
      action: { label: "Rebuild now", onClick: flush }
    });
    shownCount = count;
  }

  function clear() {
    if (updateTimer) { clearTimeout(updateTimer); updateTimer = null; }
    if (shown) { shown.dismiss(); shown = null; }
    shownCount = 0;
  }

  /* The first change shows the toast at once; later counts are applied at
     most once per UPDATE_MS so a burst of writes does not flicker it. */
  window.__hvRebuildQueue = function (count, full) {
    if (!count) { clear(); return; }
    if (!shown) { show(count, full); return; }
    if (count === shownCount) return;
    if (updateTimer) clearTimeout(updateTimer);
    updateTimer = setTimeout(function () {
      updateTimer = null;
      show(count, full);
    }, UPDATE_MS);
  };
})();
