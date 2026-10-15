/* === Hypervisor: Shared Search Sources === */

// Single source of truth for the non-document search categories that more than
// one surface needs - the command palette (features/command-palette.js) and
// the zen-stage search (core/navigation.js). Both previously fetched the
// utilities manifest independently; this module owns the fetch once and holds
// the parsed lists so every consumer reads the same arrays.
//
// Two categories live here:
//   - utilities: build-emitted from _utils/_manifest.json (the actual utility
//     files), each { name, href }.
//   - directories: build-emitted from _dirs/_manifest.json - every hyperspace
//     directory, top-level and nested, each { name, path, href }.
//
// Both are populated by async fetches kicked off at module load. Consumers read
// the arrays at search time (not load time), so a search that fires before a
// fetch resolves simply sees an empty list for that category and picks it up on
// the next keystroke. The arrays are mutated in place (not reassigned) so any
// closure that captured a reference sees the entries once they land.
//
// Type icons: exactly three, one per result kind - directory, file (document),
// utility. The icon is a type signal, not a per-category readout, so it maps
// off the kind alone (not the document's path/category).

(function () {
  "use strict";

  var utilities = [];
  var directories = [];

  // The three type icons. Lucide names.
  var TYPE_ICONS = {
    directory: "folder",
    file: "file-text",
    utility: "wrench",
  };

  // Normalize an href to a leading-slash absolute path for router navigation.
  function _abs(href) {
    if (!href) return href;
    return href.charAt(0) === "/" ? href : "/" + href;
  }

  fetch("/content/_utils/_manifest.json")
    .then(function (r) { return r.ok ? r.json() : []; })
    .then(function (list) {
      (list || []).forEach(function (u) {
        utilities.push({ name: u.name, href: _abs(u.href) });
      });
    })
    .catch(function () { /* manifest missing - no utilities surfaced */ });

  fetch("/content/_dirs/_manifest.json")
    .then(function (r) { return r.ok ? r.json() : []; })
    .then(function (list) {
      (list || []).forEach(function (d) {
        directories.push({ name: d.name, path: d.path, href: _abs(d.href) });
      });
    })
    .catch(function () { /* manifest missing - no directories surfaced */ });

  // Icon for a result kind - "directory", "file", or "utility". Falls back to
  // the file glyph for anything unexpected.
  function iconForKind(kind) {
    return TYPE_ICONS[kind] || TYPE_ICONS.file;
  }

  window.HvSearchSources = {
    utilities: function () { return utilities; },
    directories: function () { return directories; },
    iconForKind: iconForKind,
  };
})();
