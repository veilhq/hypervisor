// ─── Drop Import ─────────────────────────────────────────────────────────────
// Drag-and-drop .md files onto the .external/ directory index page to import them.
// Requires the PyWebView desktop app bridge for filesystem access.
// SPA-aware: activates/deactivates based on fragment sourcePath.
(function () {
  var _dropZone = null;

  function teardown() {
    // Remove the drop zone if we're navigating away from .external
    if (_dropZone && _dropZone.parentNode) {
      _dropZone.parentNode.removeChild(_dropZone);
    }
    _dropZone = null;
  }

  function init(fragment) {
    // Only activate on the .external directory index page
    if (!fragment || fragment.sourcePath !== ".external") return;

    // Need the PyWebView bridge
    var hasBridge = window.pywebview && window.pywebview.api;
    if (hasBridge) {
      initDropZone();
      initDeleteButtons();
    } else {
      // Bridge might arrive later
      window.addEventListener("pywebviewready", function onReady() {
        window.removeEventListener("pywebviewready", onReady);
        initDropZone();
        initDeleteButtons();
      });
    }
  }

  function initDropZone() {
    _dropZone = document.createElement("div");
    _dropZone.className = "dir-item drop-zone";
    _dropZone.innerHTML =
      '<i data-lucide="file-down"></i>' +
      "<span>drop files here to import</span>";

    var docList = document.querySelector(".dir-items");
    if (docList) {
      docList.insertBefore(_dropZone, docList.firstChild);
    } else {
      var contentTarget = document.getElementById("content-target");
      if (contentTarget) contentTarget.appendChild(_dropZone);
    }

    if (window.lucide) lucide.createIcons({ nodes: [_dropZone], attrs: { "stroke-width": 2 } });

    _dropZone.addEventListener("dragover", function (e) {
      e.preventDefault();
      e.dataTransfer.dropEffect = "copy";
      _dropZone.classList.add("drag-over");
    });

    _dropZone.addEventListener("dragleave", function (e) {
      e.preventDefault();
      _dropZone.classList.remove("drag-over");
    });

    // Supported non-md types mirror site_utils/external_render.SUPPORTED_EXTS.
    // Text types are read as text; images/binaries are read as base64 so their
    // bytes survive the bridge intact.
    var TEXT_EXT = /\.(md|markdown|txt|log|sql)$/i;
    var BINARY_EXT = /\.(png|jpg|jpeg|gif|webp|svg|xlsx|docx|zip)$/i;

    _dropZone.addEventListener("drop", function (e) {
      e.preventDefault();
      _dropZone.classList.remove("drag-over");

      var files = e.dataTransfer.files;
      if (!files || files.length === 0) return;

      var accepted = Array.from(files).filter(function (f) {
        return TEXT_EXT.test(f.name) || BINARY_EXT.test(f.name);
      });

      var skipped = files.length - accepted.length;
      if (skipped > 0 && window.__hypervisorToast) {
        window.__hypervisorToast({
          variant: "warn",
          message: "skipped " + skipped + " unsupported file" + (skipped > 1 ? "s" : "")
        });
      }
      if (accepted.length === 0) return;

      // Show importing state: insert skeleton rows after the drop zone
      _dropZone.classList.add("importing");
      var docList = document.querySelector(".dir-items");
      var skeletonItems = [];
      var insertRef = _dropZone.nextSibling;
      for (var i = 0; i < accepted.length; i++) {
        var skeletonLi = document.createElement("div");
        skeletonLi.className = "dir-item loading-skeleton-row doc-skeleton";
        skeletonLi.innerHTML =
          '<span class="loading-skeleton loading-skeleton-line doc-skeleton-title"></span>' +
          '<span class="loading-skeleton loading-skeleton-line loading-skeleton-sm doc-skeleton-date"></span>';
        skeletonItems.push(skeletonLi);
        if (docList) {
          docList.insertBefore(skeletonLi, insertRef);
        }
      }

      var imported = 0;
      var failed = 0;
      var total = accepted.length;

      function finish() {
        if (imported + failed !== total) return;
        if (window.__hypervisorToast) {
          var msg = "imported " + imported + " file" + (imported !== 1 ? "s" : "");
          if (failed > 0) msg += " (" + failed + " failed)";
          window.__hypervisorToast({
            variant: failed > 0 ? "warn" : "success",
            message: msg
          });
        }
        // If all failed, remove skeletons and revert drop zone
        if (failed === total) {
          skeletonItems.forEach(function (el) { if (el.parentNode) el.parentNode.removeChild(el); });
          if (_dropZone) _dropZone.classList.remove("importing");
        }
      }

      function sendImport(filename, content, encoding) {
        window.pywebview.api
          .import_external_file(filename, content, encoding)
          .then(function (result) {
            if (result && result.ok) imported++;
            else failed++;
          })
          .catch(function () { failed++; })
          .finally(finish);
      }

      accepted.forEach(function (file) {
        var reader = new FileReader();
        if (TEXT_EXT.test(file.name)) {
          reader.onload = function (ev) {
            sendImport(file.name, ev.target.result, "text");
          };
          reader.onerror = function () { failed++; finish(); };
          reader.readAsText(file);
        } else {
          // Images and binaries: readAsDataURL yields "data:...;base64,XXXX";
          // strip the prefix and send the raw base64 payload.
          reader.onload = function (ev) {
            var dataUrl = ev.target.result || "";
            var comma = dataUrl.indexOf(",");
            var b64 = comma >= 0 ? dataUrl.slice(comma + 1) : dataUrl;
            sendImport(file.name, b64, "base64");
          };
          reader.onerror = function () { failed++; finish(); };
          reader.readAsDataURL(file);
        }
      });
    });
  }

  function initDeleteButtons() {
    var items = document.querySelectorAll(".dir-item");
    items.forEach(function (li) {
      var pathSpan = li.querySelector(".doc-path");
      if (!pathSpan) return;

      var fullPath = pathSpan.textContent.trim();
      var parts = fullPath.replace(/\\/g, "/").split("/");
      var filename = parts[parts.length - 1];
      if (!filename) return;

      var btn = document.createElement("button");
      btn.className = "external-delete-btn";
      btn.setAttribute("aria-label", "Delete " + filename);
      btn.setAttribute("data-tooltip", "Delete");
      btn.innerHTML = '<i data-lucide="trash-2"></i>';
      li.appendChild(btn);

      btn.addEventListener("click", function (e) {
        e.preventDefault();
        e.stopPropagation();

        var confirmFn = window.__hypervisorConfirm || function (msg) {
          return Promise.resolve(window.confirm(msg));
        };

        confirmFn('Delete "' + filename + '" from .external?', {
          danger: true, confirmLabel: "delete", cancelLabel: "cancel"
        }).then(function (ok) {
          if (!ok) return;
          window.pywebview.api.delete_external_file(filename).then(function (result) {
            if (result && result.ok) {
              if (window.__hypervisorToast) window.__hypervisorToast({ variant: "success", message: "deleted: " + filename });
            } else {
              if (window.__hypervisorToast) window.__hypervisorToast({ variant: "error", message: "delete failed: " + (result.error || "unknown") });
            }
          });
        });
      });
    });

    if (window.lucide) lucide.createIcons({ attrs: { "stroke-width": 2 } });
  }

  // Register with router lifecycle
  if (window.__router) {
    window.__router.onNavigate(teardown, init);
  }
})();
