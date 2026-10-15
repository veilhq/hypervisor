/* === Hypervisor: Inline Document Editor === */

  // Provides a toggle-to-edit experience for markdown documents inside the
  // Hypervisor desktop app. Uses the PyWebView bridge (read_file / write_file)
  // for file I/O. No external dependencies. SPA-aware via router lifecycle.

  (function initInlineEditor() {
    var A = (window.__hvActions = window.__hvActions || {});

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
      editorWrap.className = "inline-editor-wrap";
      editorWrap.style.display = "none";

      // Save indicator
      saveIndicator = document.createElement("span");
      saveIndicator.className = "inline-editor-indicator";
      saveIndicator.textContent = "";
      editorWrap.appendChild(saveIndicator);

      // Textarea
      textarea = document.createElement("textarea");
      textarea.className = "inline-editor-textarea";
      textarea.setAttribute("spellcheck", "false");
      textarea.setAttribute("autocomplete", "off");
      textarea.setAttribute("autocorrect", "off");
      textarea.setAttribute("autocapitalize", "off");
      textarea.setAttribute("aria-label", "Markdown editor");
      editorWrap.appendChild(textarea);

      // Action bar (save / cancel)
      var actionBar = document.createElement("div");
      actionBar.className = "inline-editor-actions";

      var saveBtn = document.createElement("button");
      saveBtn.className = "inline-editor-save";
      saveBtn.textContent = "save";
      saveBtn.setAttribute("aria-label", "Save changes");
      saveBtn.addEventListener("click", function () { save(); });

      var cancelBtn = document.createElement("button");
      cancelBtn.className = "inline-editor-cancel";
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
        if (related && related.closest && related.closest(".inline-editor-actions")) return;
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

      // Reload fragment to show rebuilt content
      if (window.__router) {
        window.__router.reload();
      }
    }

    // --- Toggle handler (invoked from context menu / command palette) ---
    function toggleEdit() {
      if (!(window.pywebview && window.pywebview.api)) return;
      if (!filePath) return;
      if (isEditing) {
        exitEditMode();
      } else {
        enterEditMode();
      }
    }

    // Register with the action registry so callers invoke edit directly.
    A.register("edit", toggleEdit);
    // Whether edit is available for the current page (desktop + .md doc).
    A.canEdit = function () {
      return !!(window.pywebview && window.pywebview.api) && !!filePath;
    };
    // Current editor mode, so callers can label the action edit vs. view.
    A.isEditing = function () { return isEditing; };

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
    }

    // --- Lifecycle: init on navigation ---
    function init(fragment) {
      if (!fragment) return;
      var srcPath = fragment.sourcePath || "";
      if (!srcPath || !srcPath.endsWith(".md")) {
        filePath = null;
        return;
      }
      filePath = srcPath;
    }

    // Register with router
    if (window.__router) {
      window.__router.onNavigate(teardown, init);
    }
  })();
