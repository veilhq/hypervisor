/* === Hypervisor: Write-back (task checkboxes, status) === */

  // --- Task checkbox write-back (desktop app only) ---
  // Uses event delegation on document — survives navigation without reinit.
  (function initTaskWriteBack() {
    document.addEventListener("click", function (e) {
      var taskBox = e.target.closest(".task-box");
      if (!taskBox) return;

      var li = taskBox.closest(".task");
      if (!li) return;

      var filePath = li.getAttribute("data-src");
      var lineNum = li.getAttribute("data-line");
      if (!filePath || lineNum === null) return;

      if (!(window.pywebview && window.pywebview.api)) return;

      e.preventDefault();
      e.stopPropagation();

      var isDone = li.classList.contains("task-done");
      var lineInt = parseInt(lineNum, 10);

      if (isDone) {
        li.classList.remove("task-done");
        li.classList.add("task-open");
        taskBox.innerHTML = "&#9744;";
      } else {
        li.classList.remove("task-open");
        li.classList.add("task-done");
        taskBox.innerHTML = "&#9745;";
      }

      window.pywebview.api.toggle_checkbox(filePath, lineInt, isDone).then(function (result) {
        if (!result || !result.ok) {
          if (isDone) { li.classList.remove("task-open"); li.classList.add("task-done"); taskBox.innerHTML = "&#9745;"; }
          else { li.classList.remove("task-done"); li.classList.add("task-open"); taskBox.innerHTML = "&#9744;"; }
        }
      }).catch(function () {
        if (isDone) { li.classList.remove("task-open"); li.classList.add("task-done"); taskBox.innerHTML = "&#9745;"; }
        else { li.classList.remove("task-done"); li.classList.add("task-open"); taskBox.innerHTML = "&#9744;"; }
      });
    });
  })();

  // --- Status metadata write-back (desktop app only) ---
  // Uses event delegation on document — survives navigation without reinit.
  (function initStatusWriteBack() {
    var VALID_STATUSES = [
      "Proposed", "In Discussion", "Planned",
      "In Progress", "Implemented"
    ];

    document.addEventListener("click", function (e) {
      // New chip-strip: <span class="doc-header-chip" data-writeback-key="status">
      var chip = e.target.closest('[data-writeback-key="status"]');
      var metaVal = chip; // unified reference used by the writeback logic below
      var isLegacy = false;
      if (!metaVal) {
        // Legacy fallback: pre-chip metadata block (kept in case any old
        // fragment is still cached at load).
        metaVal = e.target.closest(".meta-val");
        if (!metaVal) return;
        var metaItem = metaVal.closest(".meta-item");
        if (!metaItem) return;
        var metaKey = metaItem.querySelector(".meta-key");
        if (!metaKey || metaKey.textContent.trim().toLowerCase() !== "status") return;
        isLegacy = true;
      }

      if (!(window.pywebview && window.pywebview.api)) return;

      e.preventDefault();

      var sourcePathEl = document.getElementById("source-path");
      if (!sourcePathEl) return;
      var filePath = sourcePathEl.textContent.trim();
      if (!filePath || !filePath.endsWith(".md")) return;

      var currentStatus = metaVal.textContent.trim();
      var currentIdx = -1;
      for (var i = 0; i < VALID_STATUSES.length; i++) {
        if (VALID_STATUSES[i].toLowerCase() === currentStatus.toLowerCase()) { currentIdx = i; break; }
      }
      var nextIdx = (currentIdx + 1) % VALID_STATUSES.length;
      var newStatus = VALID_STATUSES[nextIdx];

      metaVal.textContent = newStatus;

      // Update chip variant class (active vs idle) based on new status
      if (!isLegacy) {
        var isActive = /progress|discussion/i.test(newStatus);
        metaVal.classList.toggle("doc-header-chip-status-active", isActive);
        metaVal.classList.toggle("doc-header-chip-status-idle", !isActive);
      }

      window.pywebview.api.update_metadata(filePath, "Status", newStatus).then(function (result) {
        if (!result || !result.ok) {
          metaVal.textContent = currentStatus;
          if (!isLegacy) {
            var wasActive = /progress|discussion/i.test(currentStatus);
            metaVal.classList.toggle("doc-header-chip-status-active", wasActive);
            metaVal.classList.toggle("doc-header-chip-status-idle", !wasActive);
          }
        }
      }).catch(function () { metaVal.textContent = currentStatus; });
    });
  })();

  // --- Assignee metadata write-back (desktop app only) ---
  // Click the assignee chip → inline input → Enter/blur saves.
  (function initAssigneeWriteBack() {
    function toInitials(name) {
      return name.trim().split(/\s+/).map(function (w) { return w.charAt(0).toUpperCase(); }).join("");
    }

    document.addEventListener("click", function (e) {
      var chip = e.target.closest('[data-writeback-key="assignee"]');
      if (!chip) return;
      if (chip.querySelector(".assignee-edit-input")) return; // already editing

      if (!(window.pywebview && window.pywebview.api)) return;

      e.preventDefault();

      var sourcePathEl = document.getElementById("source-path");
      if (!sourcePathEl) return;
      var filePath = sourcePathEl.textContent.trim();
      if (!filePath || !filePath.endsWith(".md")) return;

      var originalInitials = chip.textContent.trim();
      var fullName = chip.getAttribute("data-full-value") || "";

      // Replace chip text with an inline input
      var input = document.createElement("input");
      input.type = "text";
      input.className = "assignee-edit-input form-input-inline";
      input.value = fullName;
      input.setAttribute("aria-label", "Edit assignee name");

      chip.textContent = "";
      chip.appendChild(input);
      chip.classList.add("assignee-editing");
      input.focus();
      input.select();

      function commit() {
        var val = input.value.trim();
        chip.classList.remove("assignee-editing");

        if (!val) {
          // Clear assignee
          chip.textContent = originalInitials;
          window.pywebview.api.update_metadata(filePath, "Assignee", "").then(function (result) {
            if (result && result.ok) {
              chip.parentNode.removeChild(chip);
            }
          });
          return;
        }

        var newInitials = toInitials(val);
        chip.textContent = newInitials;
        chip.setAttribute("data-full-value", val);

        window.pywebview.api.update_metadata(filePath, "Assignee", val).then(function (result) {
          if (!result || !result.ok) {
            chip.textContent = originalInitials;
            chip.setAttribute("data-full-value", fullName);
          }
        }).catch(function () {
          chip.textContent = originalInitials;
          chip.setAttribute("data-full-value", fullName);
        });
      }

      function cancel() {
        chip.classList.remove("assignee-editing");
        chip.textContent = originalInitials;
      }

      var committed = false;
      input.addEventListener("keydown", function (ev) {
        if (ev.key === "Enter") { ev.preventDefault(); committed = true; input.blur(); }
        if (ev.key === "Escape") { ev.preventDefault(); committed = false; input.blur(); }
      });
      input.addEventListener("blur", function () {
        if (committed !== false) { commit(); } else { cancel(); }
      });
      // Reset the committed flag guard — treat blur-without-keydown as commit
      committed = true;
    });
  })();

  // --- Open in File Explorer (registry action, content-aware) ---
  (function initOpenInExplorer() {
    var A = (window.__hvActions = window.__hvActions || {});

    function canOpen() {
      if (!(window.pywebview && window.pywebview.api)) return false;
      var sourcePathEl = document.getElementById("source-path");
      var filePath = sourcePathEl ? sourcePathEl.textContent.trim() : "";
      return !!(filePath && filePath.endsWith(".md"));
    }

    A.canOpenInExplorer = canOpen;
    A.register("openInExplorer", function () {
      if (!(window.pywebview && window.pywebview.api)) return;
      var sourcePathEl = document.getElementById("source-path");
      if (!sourcePathEl) return;
      var filePath = sourcePathEl.textContent.trim();
      if (!filePath || !filePath.endsWith(".md")) return;
      window.pywebview.api.open_in_explorer(filePath);
    });
  })();

  // --- Edit availability is handled by editor.js lifecycle ---

  // --- Mark Done button (desktop app only, SPA-aware) ---
  (function initMarkDone() {
    var A = (window.__hvActions = window.__hvActions || {});

    // True when the current page is a work/to-do item in the desktop app.
    A.canMarkDone = function () {
      if (!(window.pywebview && window.pywebview.api)) return false;
      var el = document.getElementById("source-path");
      var filePath = el ? (el.textContent || "").trim() : "";
      if (!filePath || !filePath.endsWith(".md")) return false;
      return filePath.replace(/\\/g, "/").indexOf("work/to-do/") !== -1;
    };

    A.register("markDone", function () {
      if (!(window.pywebview && window.pywebview.api)) return;
      if (!window.__hypervisorConfirm) return;
      var el = document.getElementById("source-path");
      var filePath = el ? (el.textContent || "").trim() : "";
      if (!filePath) return;

      window.__hypervisorConfirm("Move this work item to done?", {
        confirmLabel: "mark done", cancelLabel: "cancel"
      }).then(function (confirmed) {
        if (!confirmed) return;
        window.pywebview.api.mark_done(filePath).then(function (result) {
          if (result && result.ok) {
            if (window.__hypervisorToast) window.__hypervisorToast({ variant: "success", message: "moved to done" });
          } else {
            if (window.__hypervisorToast) window.__hypervisorToast({ variant: "error", title: "mark done failed", message: (result && result.error) || "unknown error" });
          }
        }).catch(function () {
          if (window.__hypervisorToast) window.__hypervisorToast({ variant: "error", message: "mark done failed" });
        });
      });
    });
  })();

  // --- Delete Document button (desktop app only, SPA-aware) ---
  // --- End Sprint (global action, desktop app only) ---
  (function initEndSprint() {
    var A = (window.__hvActions = window.__hvActions || {});

    A.register("endSprint", function () {
      if (!(window.pywebview && window.pywebview.api)) return;
      if (!window.__hypervisorConfirm) return;

      window.__hypervisorConfirm("End sprint? This will cascade all horizon values forward.", {
        confirmLabel: "end sprint", cancelLabel: "cancel"
      }).then(function (confirmed) {
        if (!confirmed) return;
        window.pywebview.api.end_sprint().then(function (result) {
          if (result && result.success) {
            var count = result.files_updated || 0;
            if (window.__hypervisorToast) window.__hypervisorToast({ variant: "success", message: count + " item(s) cascaded" });
          } else {
            if (window.__hypervisorToast) window.__hypervisorToast({ variant: "error", title: "end sprint failed", message: (result && result.error) || "unknown error" });
          }
        }).catch(function () {
          if (window.__hypervisorToast) window.__hypervisorToast({ variant: "error", message: "end sprint failed" });
        });
      });
    });
  })();
