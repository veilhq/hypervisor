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
      var metaVal = e.target.closest(".meta-val");
      if (!metaVal) return;

      var metaItem = metaVal.closest(".meta-item");
      if (!metaItem) return;

      var metaKey = metaItem.querySelector(".meta-key");
      if (!metaKey || metaKey.textContent.trim().toLowerCase() !== "status") return;

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

      window.pywebview.api.update_metadata(filePath, "Status", newStatus).then(function (result) {
        if (!result || !result.ok) metaVal.textContent = currentStatus;
      }).catch(function () { metaVal.textContent = currentStatus; });
    });
  })();

  // --- Open in File Explorer (shell-level button, content-aware) ---
  (function initOpenInExplorer() {
    var btn = document.getElementById("explorer-btn");
    if (!btn) return;

    function updateVisibility() {
      var sourcePathEl = document.getElementById("source-path");
      var filePath = sourcePathEl ? sourcePathEl.textContent.trim() : "";
      var show = filePath && filePath.endsWith(".md") && isDesktopApp;
      btn.style.display = show ? "" : "none";
    }

    // Update on navigation
    if (window.__router) {
      window.__router.onNavigate(null, updateVisibility);
    }

    // Show on pywebview ready
    window.addEventListener("pywebviewready", updateVisibility);

    btn.addEventListener("click", function () {
      if (!(window.pywebview && window.pywebview.api)) return;
      var sourcePathEl = document.getElementById("source-path");
      if (!sourcePathEl) return;
      var filePath = sourcePathEl.textContent.trim();
      if (!filePath || !filePath.endsWith(".md")) return;
      window.pywebview.api.open_in_explorer(filePath);
    });
  })();

  // --- Edit button visibility is handled by editor.js lifecycle ---

  // --- Mark Done button (desktop app only, SPA-aware) ---
  (function initMarkDone() {
    var _markDoneBtn = null;

    function teardown() {
      if (_markDoneBtn && _markDoneBtn.parentNode) {
        _markDoneBtn.parentNode.removeChild(_markDoneBtn);
      }
      _markDoneBtn = null;
    }

    function init(fragment) {
      if (!fragment) return;
      var filePath = fragment.sourcePath || "";
      if (!filePath || !filePath.endsWith(".md")) return;

      var normalized = filePath.replace(/\\/g, "/");
      if (normalized.indexOf("work/to-do/") === -1) return;

      var btn = document.createElement("button");
      btn.className = "action-item mark-done-btn";
      btn.id = "mark-done-btn";
      btn.setAttribute("aria-label", "Mark work item as done");
      btn.innerHTML = '<i data-lucide="check-circle" class="action-icon"></i><span class="action-label mark-done-label">done</span>';

      // Only show if desktop bridge available
      if (!isDesktopApp) btn.style.display = "none";

      var drawer = document.querySelector(".actions-drawer-inner");
      if (!drawer) return;
      drawer.appendChild(btn);
      _markDoneBtn = btn;

      if (window.lucide) lucide.createIcons({ nodes: [btn], attrs: { "stroke-width": 1.5 } });

      // Show when bridge becomes available
      if (!isDesktopApp) {
        window.addEventListener("pywebviewready", function onReady() {
          btn.style.display = "";
          window.removeEventListener("pywebviewready", onReady);
        });
      }

      btn.addEventListener("click", function () {
        if (!(window.pywebview && window.pywebview.api)) return;
        if (!window.__hypervisorConfirm) return;

        window.__hypervisorConfirm("Move this work item to done?", {
          confirmLabel: "mark done", cancelLabel: "cancel"
        }).then(function (confirmed) {
          if (!confirmed) return;
          btn.disabled = true;
          btn.classList.add("mark-done-pending");

          window.pywebview.api.mark_done(filePath).then(function (result) {
            if (result && result.ok) {
              if (window.__hypervisorToast) window.__hypervisorToast("moved to done");
            } else {
              btn.disabled = false;
              btn.classList.remove("mark-done-pending");
              if (window.__hypervisorToast) window.__hypervisorToast("failed: " + (result.error || "unknown error"));
            }
          }).catch(function () {
            btn.disabled = false;
            btn.classList.remove("mark-done-pending");
            if (window.__hypervisorToast) window.__hypervisorToast("mark done failed");
          });
        });
      });
    }

    if (window.__router) {
      window.__router.onNavigate(teardown, init);
    }
  })();
