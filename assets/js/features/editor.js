/* === Hypervisor: Inline Document Editor === */

  // Provides a toggle-to-edit experience for markdown documents inside the
  // Hypervisor desktop app. Uses the PyWebView bridge (read_file / write_file)
  // for file I/O. No external dependencies. SPA-aware via router lifecycle.

  (function initInlineEditor() {
    var editBtn = document.getElementById("edit-btn");
    if (!editBtn) return;

    var isEditing = false;
    var editorWrap = null;
    var textarea = null;
    var saveIndicator = null;
    var dirty = false;
    var filePath = null;

    // --- Build editor UI (lazily, on first activation) ---
    function createEditor() {
      var article = document.getElementById("content-target");
      if (!article) return;

      editorWrap = document.createElement("div");
      editorWrap.className = "hv-editor-wrap";
      editorWrap.style.display = "none";

      // Save indicator
      saveIndicator = document.createElement("span");
      saveIndicator.className = "hv-editor-indicator";
      saveIndicator.textContent = "";
      editorWrap.appendChild(saveIndicator);

      // Textarea
      textarea = document.createElement("textarea");
      textarea.className = "hv-editor-textarea";
      textarea.setAttribute("spellcheck", "false");
      textarea.setAttribute("autocomplete", "off");
      textarea.setAttribute("autocorrect", "off");
      textarea.setAttribute("autocapitalize", "off");
      textarea.setAttribute("aria-label", "Markdown editor");
      editorWrap.appendChild(textarea);

      // Action bar (save / cancel)
      var actionBar = document.createElement("div");
      actionBar.className = "hv-editor-actions";

      var saveBtn = document.createElement("button");
      saveBtn.className = "hv-editor-save";
      saveBtn.textContent = "save";
      saveBtn.setAttribute("aria-label", "Save changes");
      saveBtn.addEventListener("click", function () { save(); });

      var cancelBtn = document.createElement("button");
      cancelBtn.className = "hv-editor-cancel";
      cancelBtn.textContent = "cancel";
      cancelBtn.setAttribute("aria-label", "Discard changes");
      cancelBtn.addEventListener("click", function () { cancelEdit(); });

      actionBar.appendChild(cancelBtn);
      actionBar.appendChild(saveBtn);
      editorWrap.appendChild(actionBar);

      // Insert before article
      article.parentNode.insertBefore(editorWrap, article);

      // --- Tab key inserts spaces ---
      textarea.addEventListener("keydown", function (e) {
        if (e.key === "Tab") {
          e.preventDefault();
          var start = textarea.selectionStart;
          var end = textarea.selectionEnd;
          var value = textarea.value;
          textarea.value = value.substring(0, start) + "  " + value.substring(end);
          textarea.selectionStart = textarea.selectionEnd = start + 2;
          dirty = true;
        }
      });

      // --- Ctrl+S save ---
      textarea.addEventListener("keydown", function (e) {
        if ((e.ctrlKey || e.metaKey) && e.key === "s") {
          e.preventDefault();
          save();
        }
      });

      // --- Track dirty state ---
      textarea.addEventListener("input", function () {
        dirty = true;
      });

      // --- Blur auto-save ---
      textarea.addEventListener("blur", function (e) {
        var related = e.relatedTarget;
        if (related && related.closest && related.closest(".hv-editor-actions")) return;
        if (dirty) save();
      });
    }

    // --- Save content via bridge ---
    function save() {
      if (!textarea || !dirty || !filePath) return;
      if (!(window.pywebview && window.pywebview.api)) return;

      dirty = false;
      showIndicator("saving...");

      window.pywebview.api.write_file(filePath, textarea.value).then(function (result) {
        if (result && result.ok) {
          showIndicator("saved");
          savedDuringSession = true;
        } else {
          showIndicator("error: " + (result && result.error || "unknown"));
          dirty = true;
        }
      }).catch(function () {
        showIndicator("save failed");
        dirty = true;
      });
    }

    // --- Cancel edit (discard changes, return to rendered view) ---
    var savedDuringSession = false;

    function cancelEdit() {
      dirty = false;
      if (editorWrap) editorWrap.style.display = "none";
      var article = document.getElementById("content-target");
      if (article) article.style.display = "";
      isEditing = false;

      editBtn.setAttribute("data-tooltip", "Edit markdown");
      var label = editBtn.querySelector(".edit-btn-label");
      if (label) label.textContent = "edit";
      var icon = editBtn.querySelector("[data-lucide]");
      if (icon) {
        icon.setAttribute("data-lucide", "pencil");
        if (window.lucide) lucide.createIcons({ attrs: { "stroke-width": 1.5 } });
      }

      // If a save happened, reload the fragment to show updated content
      if (savedDuringSession && window.__router) {
        savedDuringSession = false;
        window.__router.reload();
      }
    }

    function showIndicator(msg) {
      if (!saveIndicator) return;
      saveIndicator.textContent = msg;
      saveIndicator.classList.add("visible");
      if (msg === "saved") {
        setTimeout(function () { saveIndicator.classList.remove("visible"); }, 2000);
      }
    }

    // --- Enter edit mode ---
    function enterEditMode() {
      if (!(window.pywebview && window.pywebview.api)) return;
      if (!filePath) return;

      if (!editorWrap) createEditor();

      showIndicator("loading...");
      window.pywebview.api.read_file(filePath).then(function (result) {
        if (result && result.ok) {
          textarea.value = result.content;
          dirty = false;
          editorWrap.style.display = "";
          var article = document.getElementById("content-target");
          if (article) article.style.display = "none";
          isEditing = true;

          editBtn.setAttribute("data-tooltip", "View rendered");
          var label = editBtn.querySelector(".edit-btn-label");
          if (label) label.textContent = "view";
          var icon = editBtn.querySelector("[data-lucide]");
          if (icon) {
            icon.setAttribute("data-lucide", "eye");
            if (window.lucide) lucide.createIcons({ attrs: { "stroke-width": 1.5 } });
          }

          showIndicator("");
          saveIndicator.classList.remove("visible");
          textarea.focus();
        } else {
          showIndicator("load failed: " + (result && result.error || ""));
        }
      }).catch(function () {
        showIndicator("load failed");
      });
    }

    // --- Exit edit mode ---
    function exitEditMode() {
      if (dirty) save();

      if (editorWrap) editorWrap.style.display = "none";
      var article = document.getElementById("content-target");
      if (article) article.style.display = "";
      isEditing = false;

      editBtn.setAttribute("data-tooltip", "Edit markdown");
      var label = editBtn.querySelector(".edit-btn-label");
      if (label) label.textContent = "edit";
      var icon = editBtn.querySelector("[data-lucide]");
      if (icon) {
        icon.setAttribute("data-lucide", "pencil");
        if (window.lucide) lucide.createIcons({ attrs: { "stroke-width": 1.5 } });
      }

      // Reload fragment to show rebuilt content
      if (window.__router) {
        window.__router.reload();
      }
    }

    // --- Button click handler ---
    editBtn.addEventListener("click", function () {
      if (!(window.pywebview && window.pywebview.api)) return;
      if (!filePath) return;
      if (isEditing) {
        exitEditMode();
      } else {
        enterEditMode();
      }
    });

    // --- Lifecycle: teardown on navigation ---
    function teardown() {
      // If editing, save and close before navigating away
      if (isEditing) {
        if (dirty) save();
        if (editorWrap) editorWrap.style.display = "none";
        var article = document.getElementById("content-target");
        if (article) article.style.display = "";
        isEditing = false;
      }
      // Remove editor DOM if it exists (content-target gets replaced)
      if (editorWrap && editorWrap.parentNode) {
        editorWrap.parentNode.removeChild(editorWrap);
      }
      editorWrap = null;
      textarea = null;
      saveIndicator = null;
      dirty = false;
      savedDuringSession = false;
      filePath = null;

      // Reset button state
      editBtn.style.display = "none";
      var label = editBtn.querySelector(".edit-btn-label");
      if (label) label.textContent = "edit";
      var icon = editBtn.querySelector("[data-lucide]");
      if (icon) {
        icon.setAttribute("data-lucide", "pencil");
        if (window.lucide) lucide.createIcons({ attrs: { "stroke-width": 1.5 } });
      }
    }

    // --- Lifecycle: init on navigation ---
    function init(fragment) {
      if (!fragment) return;
      var srcPath = fragment.sourcePath || "";
      if (!srcPath || !srcPath.endsWith(".md")) {
        filePath = null;
        editBtn.style.display = "none";
        return;
      }

      filePath = srcPath;

      // Show edit button only if desktop bridge is available
      if (isDesktopApp) {
        editBtn.style.display = "";
      }
    }

    // Register with router
    if (window.__router) {
      window.__router.onNavigate(teardown, init);
    }
  })();
