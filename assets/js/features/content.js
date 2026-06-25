/* === Hypervisor: Content Interactions (filters, copy, zoom) === */

  // --- Content-bound features (reinitialized on every navigation) ---
  (function initContentLifecycle() {

    function initTodoFilters() {
      var nameInput = document.getElementById("todo-filter-name");
      var appSelect = document.getElementById("todo-filter-app");
      var typeSelect = document.getElementById("todo-filter-type");
      var statusSelect = document.getElementById("todo-filter-status");
      if (!nameInput) return;

      var shelves = document.querySelectorAll(".app-shelf");
      if (!shelves.length) return;

      // --- Collapsible shelf headers (default collapsed) ---
      shelves.forEach(function(shelf) {
        shelf.classList.add("shelf-collapsed");
        var header = shelf.querySelector(".app-shelf-header");
        if (!header) return;
        header.addEventListener("click", function() {
          shelf.classList.toggle("shelf-collapsed");
        });
      });

      function applyFilters() {
        var nameVal = nameInput.value.toLowerCase();
        var appVal = appSelect ? appSelect.value : "";
        var typeVal = typeSelect ? typeSelect.value : "";
        var statusVal = statusSelect ? statusSelect.value : "";

        shelves.forEach(function(shelf) {
          var shelfApp = shelf.getAttribute("data-app-group") || "";
          var items = shelf.querySelectorAll("li");
          var visibleCount = 0;

          items.forEach(function(li) {
            var name = li.getAttribute("data-name") || "";
            var type = li.getAttribute("data-type") || "";
            var status = li.getAttribute("data-status") || "";

            var show = true;
            if (nameVal && name.indexOf(nameVal) === -1) show = false;
            if (appVal && shelfApp !== appVal) show = false;
            if (typeVal && type !== typeVal) show = false;
            if (statusVal && status !== statusVal) show = false;

            li.classList.toggle("todo-hidden", !show);
            if (show) visibleCount++;
          });

          // Hide entire shelf if no visible items
          shelf.classList.toggle("shelf-hidden", visibleCount === 0);

          // Update shelf count
          var countEl = shelf.querySelector(".app-shelf-count");
          if (countEl) {
            var total = items.length;
            if (nameVal || appVal || typeVal || statusVal) {
              countEl.textContent = visibleCount + "/" + total;
            } else {
              countEl.textContent = total;
            }
          }
        });
      }

      nameInput.addEventListener("input", applyFilters);
      if (appSelect) appSelect.addEventListener("change", applyFilters);
      if (typeSelect) typeSelect.addEventListener("change", applyFilters);
      if (statusSelect) statusSelect.addEventListener("change", applyFilters);
    }

    function initSectionCopy() {
      var sections = document.querySelectorAll(".doc-section");
      if (!sections.length) return;

      // --- Lightweight HTML-to-Markdown converter ---
      function htmlToMd(el) {
        var out = "";
        var children = el.childNodes;
        for (var i = 0; i < children.length; i++) {
          out += nodeToMd(children[i], "");
        }
        return out.replace(/\n{3,}/g, "\n\n").trim() + "\n";
      }

      function nodeToMd(node, listPrefix) {
        if (node.nodeType === 3) return node.textContent;
        if (node.nodeType !== 1) return "";

        var tag = node.tagName.toLowerCase();
        var inner = "";

        function childrenMd(prefix) {
          var s = "";
          var kids = node.childNodes;
          for (var j = 0; j < kids.length; j++) {
            s += nodeToMd(kids[j], prefix || "");
          }
          return s;
        }

        switch (tag) {
          case "h2": return "## " + childrenMd().trim() + "\n\n";
          case "h3": return "### " + childrenMd().trim() + "\n\n";
          case "h4": return "#### " + childrenMd().trim() + "\n\n";
          case "h5": return "##### " + childrenMd().trim() + "\n\n";
          case "h6": return "###### " + childrenMd().trim() + "\n\n";
          case "p": return childrenMd().trim() + "\n\n";
          case "br": return "  \n";
          case "strong": case "b":
            inner = childrenMd().trim();
            return inner ? "**" + inner + "**" : "";
          case "em": case "i":
            inner = childrenMd().trim();
            return inner ? "*" + inner + "*" : "";
          case "code":
            if (node.parentElement && node.parentElement.tagName.toLowerCase() === "pre") return node.textContent;
            return "`" + node.textContent + "`";
          case "a":
            inner = childrenMd().trim();
            var href = node.getAttribute("href") || "";
            return "[" + inner + "](" + href + ")";
          case "ul": return listToMd(node, false) + "\n";
          case "ol": return listToMd(node, true) + "\n";
          case "li": return childrenMd(listPrefix);
          case "pre":
            var codeEl = node.querySelector("code");
            var text = codeEl ? codeEl.textContent : node.textContent;
            var lang = "";
            var parent = node.closest(".code-block");
            if (parent) {
              var langLabel = parent.querySelector(".code-lang");
              if (langLabel) lang = langLabel.textContent.trim().toLowerCase();
            }
            return "```" + lang + "\n" + text.replace(/\n$/, "") + "\n```\n\n";
          case "blockquote":
            var bqContent = childrenMd().trim();
            return bqContent.split("\n").map(function (line) { return "> " + line; }).join("\n") + "\n\n";
          case "hr": return "---\n\n";
          case "table": return tableToMd(node) + "\n";
          case "div": case "section": case "span": return childrenMd();
          case "img":
            var alt = node.getAttribute("alt") || "";
            var src = node.getAttribute("src") || "";
            return "![" + alt + "](" + src + ")";
          case "button": case "input": return "";
          default: return childrenMd();
        }
      }

      function listToMd(listEl, ordered) {
        var items = [];
        var idx = 1;
        var kids = listEl.children;
        for (var k = 0; k < kids.length; k++) {
          var li = kids[k];
          if (li.tagName.toLowerCase() !== "li") continue;
          var prefix = ordered ? (idx + ". ") : "- ";
          var taskBox = li.querySelector(".task-box");
          if (taskBox) {
            var isDone = li.classList.contains("task-done");
            prefix = "- [" + (isDone ? "x" : " ") + "] ";
          }
          var lineContent = "";
          var nestedLists = "";
          var liKids = li.childNodes;
          for (var m = 0; m < liKids.length; m++) {
            var child = liKids[m];
            if (child.nodeType === 1) {
              var childTag = child.tagName.toLowerCase();
              if (childTag === "ul" || childTag === "ol") {
                var nested = listToMd(child, childTag === "ol");
                nestedLists += nested.split("\n").map(function (line) { return line ? "  " + line : ""; }).join("\n");
              } else if (childTag === "span" && child.classList.contains("task-box")) {
                continue;
              } else {
                lineContent += nodeToMd(child, "");
              }
            } else {
              lineContent += nodeToMd(child, "");
            }
          }
          var line = prefix + lineContent.trim();
          if (nestedLists) line += "\n" + nestedLists;
          items.push(line);
          idx++;
        }
        return items.join("\n");
      }

      function tableToMd(tableEl) {
        var rows = [];
        var headerCells = tableEl.querySelectorAll("thead th, thead td");
        var bodyRows = tableEl.querySelectorAll("tbody tr");
        if (!headerCells.length) {
          var firstRow = tableEl.querySelector("tr");
          if (firstRow) headerCells = firstRow.querySelectorAll("th, td");
        }
        if (!headerCells.length) return "";
        var header = [];
        headerCells.forEach(function (cell) { header.push(cell.textContent.trim()); });
        rows.push("| " + header.join(" | ") + " |");
        rows.push("| " + header.map(function () { return "---"; }).join(" | ") + " |");
        bodyRows.forEach(function (tr) {
          var cells = [];
          tr.querySelectorAll("td, th").forEach(function (cell) { cells.push(cell.textContent.trim()); });
          if (cells.length) rows.push("| " + cells.join(" | ") + " |");
        });
        return rows.join("\n") + "\n";
      }

      // --- Add copy button to each section ---
      sections.forEach(function (section) {
        var summary = section.querySelector(".doc-section-summary");
        if (!summary) return;

        var btn = document.createElement("button");
        btn.className = "section-copy";
        btn.textContent = "copy md";
        btn.setAttribute("aria-label", "Copy section as markdown");
        btn.setAttribute("data-tooltip", "copy as markdown");

        btn.addEventListener("click", function (e) {
          e.stopPropagation();
          e.preventDefault();
          var heading = "## " + summary.textContent.trim() + "\n\n";
          var contentEl = section.querySelector(".doc-section-content");
          var md = heading + (contentEl ? htmlToMd(contentEl) : "");

          function onSuccess() {
            btn.textContent = "copied";
            btn.classList.add("copied");
            btn.setAttribute("data-tooltip", "copied!");
            setTimeout(function () {
              btn.textContent = "copy md";
              btn.classList.remove("copied");
              btn.setAttribute("data-tooltip", "copy as markdown");
            }, 1500);
          }

          function onFail() {
            btn.textContent = "err";
            setTimeout(function () { btn.textContent = "copy md"; }, 1000);
          }

          if (navigator.clipboard && navigator.clipboard.writeText) {
            navigator.clipboard.writeText(md).then(onSuccess).catch(onFail);
          } else {
            try {
              var ta = document.createElement("textarea");
              ta.value = md;
              ta.style.position = "fixed";
              ta.style.opacity = "0";
              document.body.appendChild(ta);
              ta.select();
              document.execCommand("copy");
              document.body.removeChild(ta);
              onSuccess();
            } catch (ex) { onFail(); }
          }
        });

        section.appendChild(btn);
      });
    }

    function initTableCopy() {
      var cells = document.querySelectorAll(".markdown-body table td");
      if (!cells.length) return;

      cells.forEach(function (cell) {
        cell.classList.add("cell-copyable");
        cell.setAttribute("data-tooltip", "click to copy");
        cell.addEventListener("click", function () {
          var text = (cell.textContent || "").trim();
          if (!text) return;
          navigator.clipboard.writeText(text).then(function () {
            cell.setAttribute("data-tooltip", "copied!");
            cell.classList.add("cell-copied");
            setTimeout(function () {
              cell.setAttribute("data-tooltip", "click to copy");
              cell.classList.remove("cell-copied");
            }, 1200);
          }).catch(function () {
            cell.setAttribute("data-tooltip", "copy failed");
            setTimeout(function () { cell.setAttribute("data-tooltip", "click to copy"); }, 1200);
          });
        });
      });
    }

    function initSectionCollapse() {
      var sections = document.querySelectorAll(".doc-section");
      if (!sections.length) return;

      var reducedMotion = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
      var a11yReduced = document.documentElement.classList.contains("a11y-reduce-motion");
      if (reducedMotion || a11yReduced) return;

      sections.forEach(function (section) {
        var summary = section.querySelector(".doc-section-summary");
        if (!summary) return;

        summary.addEventListener("click", function (e) {
          // Only animate the close — open animation is handled by CSS keyframes
          if (!section.hasAttribute("open")) return;

          e.preventDefault();
          var content = section.querySelector(".doc-section-content");
          if (!content) { section.removeAttribute("open"); return; }

          content.classList.add("section-collapsing");
          content.addEventListener("animationend", function handler() {
            content.removeEventListener("animationend", handler);
            content.classList.remove("section-collapsing");
            section.removeAttribute("open");
          }, { once: true });
        });
      });
    }

    // Content init function — runs on every navigation
    function contentInit() {
      initTodoFilters();
      initSectionCopy();
      initTableCopy();
      initSectionCollapse();
    }

    // Register with router lifecycle (no teardown needed — elements are replaced)
    if (window.__router) {
      window.__router.onNavigate(null, contentInit);
    }
  })();

  // --- Zoom controls (shell-level — init once) ---
  (function initZoom() {
    var inBtn = document.getElementById("zoom-in");
    var outBtn = document.getElementById("zoom-out");
    var label = document.getElementById("zoom-level");
    if (!inBtn || !outBtn || !label) return;

    var KEY = "hypervisor-zoom";
    var STEP = 10;
    var MIN = 50;
    var MAX = 200;
    var zoom = 100;
    var basePx = parseFloat(getComputedStyle(document.documentElement).fontSize) || 14;

    try {
      var saved = parseInt(localStorage.getItem(KEY), 10);
      if (saved >= MIN && saved <= MAX) zoom = saved;
    } catch (e) {}

    function apply() {
      document.documentElement.style.fontSize = (basePx * zoom / 100) + "px";
      label.textContent = zoom + "%";
      outBtn.classList.toggle("active", zoom < 100);
      inBtn.classList.toggle("active", zoom > 100);
      savePreference(KEY, String(zoom));
    }

    apply();

    inBtn.addEventListener("click", function () {
      if (zoom < MAX) { zoom += STEP; apply(); }
    });
    outBtn.addEventListener("click", function () {
      if (zoom > MIN) { zoom -= STEP; apply(); }
    });

    label.addEventListener("dblclick", function () {
      zoom = 100;
      apply();
    });
  })();

  // --- Width toggle (shell-level — init once) ---
  (function initWidthToggle() {
    var btn = document.getElementById("width-toggle");
    var page = document.getElementById("page-main");
    if (!btn || !page) return;

    var KEY = "hypervisor-condensed";
    var saved = null;
    try { saved = localStorage.getItem(KEY); } catch (e) {}

    function setCondensed(on) {
      page.classList.toggle("condensed", on);
      btn.classList.toggle("active", on);
      var iconEl = document.getElementById("width-toggle-icon");
      if (iconEl) {
        iconEl.setAttribute("data-lucide", on ? "align-center" : "columns-2");
        if (window.lucide) lucide.createIcons({ attrs: { "stroke-width": 1.5 } });
      }
      var stateEl = document.getElementById("width-toggle-state");
      if (stateEl) stateEl.textContent = on ? "Narrow" : "Full";
    }

    if (saved === "1") setCondensed(true);

    btn.addEventListener("click", function () {
      var isCondensed = page.classList.contains("condensed");
      setCondensed(!isCondensed);
      try { localStorage.setItem(KEY, !isCondensed ? "1" : "0"); } catch (e) {}
    });
  })();

  // --- Export page as standalone HTML (shell-level action, content-aware) ---
  (function initExport() {
    var btn = document.getElementById("export-btn");
    if (!btn) return;

    btn.addEventListener("click", function () {
      btn.classList.add("exporting");
      var label = btn.querySelector(".export-btn-label");
      if (label) label.textContent = "packing...";

      setTimeout(function () {
        try {
          var html = buildStandalonePage();
          var sourceRelPath = getSourceRelPath();
          var baseFilename = getExportBaseName();

          if (window.pywebview && window.pywebview.api && window.pywebview.api.save_export_zip && sourceRelPath) {
            var zipFilename = baseFilename + ".zip";
            window.pywebview.api.save_export_zip(html, zipFilename, sourceRelPath).then(function (result) {
              if (result && result.ok) {
                if (label) label.textContent = "done!";
                if (window.__hypervisorToast) window.__hypervisorToast("exported: " + zipFilename);
              } else if (result && result.error === "cancelled") {
                if (label) label.textContent = "export";
              } else {
                if (label) label.textContent = "error";
                if (window.__hypervisorToast) window.__hypervisorToast("export failed: " + (result && result.error || "unknown"));
              }
              setTimeout(function () {
                btn.classList.remove("exporting");
                if (label) label.textContent = "export";
              }, 1500);
            }).catch(function () {
              if (label) label.textContent = "error";
              setTimeout(function () { btn.classList.remove("exporting"); if (label) label.textContent = "export"; }, 2000);
            });
          } else {
            downloadFile(html, baseFilename + ".html", "text/html");
            if (label) label.textContent = "done!";
            setTimeout(function () { btn.classList.remove("exporting"); if (label) label.textContent = "export"; }, 1500);
          }
        } catch (e) {
          if (label) label.textContent = "error";
          setTimeout(function () { btn.classList.remove("exporting"); if (label) label.textContent = "export"; }, 2000);
        }
      }, 50);
    });

    function getSourceRelPath() {
      var srcEl = document.getElementById("source-path");
      if (srcEl && srcEl.textContent) return srcEl.textContent.trim();
      return null;
    }

    function getExportBaseName() {
      var srcEl = document.getElementById("source-path");
      if (srcEl && srcEl.textContent) {
        return srcEl.textContent.trim().replace(/\.md$/, "").replace(/[\/\\]/g, "-").replace(/^-+|-+$/g, "");
      }
      var title = document.title.replace(/ — Hypervisor$/, "").trim().replace(/[^a-zA-Z0-9_-]/g, "-").toLowerCase();
      return title || "hypervisor-export";
    }

    function buildStandalonePage() {
      var css = collectCSS();
      var title = document.title || "Hypervisor Export";
      var article = document.getElementById("content-target");
      var articleHtml = article ? article.innerHTML : "";
      var breadcrumbs = document.querySelector(".breadcrumbs");
      var breadcrumbsHtml = breadcrumbs ? breadcrumbs.innerHTML : "";
      var srcPath = document.getElementById("source-path");
      var srcPathText = srcPath ? srcPath.textContent : "";

      var out = '<!DOCTYPE html>\n<html lang="en">\n<head>\n';
      out += '  <meta charset="UTF-8">\n';
      out += '  <meta name="viewport" content="width=device-width, initial-scale=1.0">\n';
      out += '  <title>' + escapeHtml(title) + '</title>\n';
      out += "  <link rel=\"stylesheet\" href=\"https://db.onlinewebfonts.com/c/4571adf8e6d8270ea61a4f43a3ef31d2?family=Departure+Mono\">\n";
      out += '  <style>\n' + css + '\n  </style>\n';
      out += '</head>\n<body class="hv-export">\n';
      out += '<header class="topbar">\n  <div class="topbar-inner">\n    <div class="topbar-left">\n';
      out += '      <span class="brand"><span class="brand-text">HYPERVISOR</span></span>\n';
      out += '      <nav class="breadcrumbs" aria-label="Breadcrumb">' + breadcrumbsHtml + '</nav>\n';
      out += '    </div>\n    <div class="topbar-right"></div>\n  </div>\n</header>\n';
      out += '<main class="page">\n  <article class="markdown-body">\n' + articleHtml + '\n  </article>\n</main>\n';
      out += '<footer class="page-footer">\n  <span class="source-path">' + escapeHtml(srcPathText) + '</span>\n';
      out += '  <span class="footer-sep">|</span>\n  <span class="footer-label">hypervisor export</span>\n</footer>\n';
      out += '</body>\n</html>';
      return out;
    }

    function collectCSS() {
      var css = "";
      var sheets = document.styleSheets;
      for (var i = 0; i < sheets.length; i++) {
        try {
          var rules = sheets[i].cssRules || sheets[i].rules;
          if (!rules) continue;
          for (var j = 0; j < rules.length; j++) { css += rules[j].cssText + "\n"; }
        } catch (e) {}
      }
      var root = getComputedStyle(document.documentElement);
      var vars = ["--accent", "--accent-dim", "--accent-glow", "--accent-border", "--warm", "--cool", "--comp"];
      var overrides = ":root {\n";
      vars.forEach(function (v) { var val = root.getPropertyValue(v).trim(); if (val) overrides += "  " + v + ": " + val + ";\n"; });
      overrides += "}\n";
      overrides += "\n/* Export overrides */\n";
      overrides += "body.hv-export, body.hv-export * { cursor: auto !important; }\n";
      overrides += "body.hv-export .topbar::before { backdrop-filter: none; -webkit-backdrop-filter: none; background: #050505; }\n";
      overrides += "body.hv-export .page-footer { position: relative; backdrop-filter: none; -webkit-backdrop-filter: none; background: #050505; }\n";
      overrides += "body.hv-export .scroll-top, body.hv-export .export-btn, body.hv-export .explorer-btn { display: none !important; }\n";
      overrides += "body.hv-export .actions-drawer, body.hv-export .actions-trigger { display: none !important; }\n";
      overrides += "body.hv-export .search-wrap { display: none; }\n";
      overrides += "body.hv-export .topbar-inner { grid-template-columns: 1fr; }\n";
      overrides += "body.hv-export .code-copy { display: none; }\n";
      overrides += "body.hv-export .section-copy { display: none; }\n";
      overrides += "body.hv-export { animation: none; }\n";
      overrides += "body.hv-export, body.hv-export * { user-select: auto !important; -webkit-user-select: auto !important; }\n";
      overrides += "body.hv-export .page { animation: none; max-width: 1280px; }\n";
      overrides += "body.hv-export .toc-sidebar { display: none; }\n";
      return overrides + "\n" + css;
    }

    function escapeHtml(str) {
      return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
    }

    function downloadFile(content, filename, mimeType) {
      if (window.pywebview && window.pywebview.api && window.pywebview.api.save_export) {
        window.pywebview.api.save_export(content, filename).then(function (result) {
          if (result && result.ok) {
            if (window.__hypervisorToast) window.__hypervisorToast("exported: " + filename);
          }
        }).catch(function () {});
        return;
      }
      var blob = new Blob([content], { type: mimeType + ";charset=utf-8" });
      var url = URL.createObjectURL(blob);
      var a = document.createElement("a");
      a.href = url;
      a.download = filename;
      a.style.display = "none";
      document.body.appendChild(a);
      a.click();
      setTimeout(function () { document.body.removeChild(a); URL.revokeObjectURL(url); }, 100);
    }
  })();
