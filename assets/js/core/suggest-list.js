/* === Hypervisor: Suggest list (filterable dropdown for a free-text input) ===
   Usage: var list = window.__hypervisorSuggest(input, ["Ada", "Grace"], { onPick });
   Shows every item until the operator types, then filters; typed text that
   matches nothing exactly gets an "add" row. Arrow keys move, Enter picks the
   highlighted row, Escape closes the list. Call list.destroy() when the input goes away.
   opts.anchor: the visible box to align under when the input sits inside a padded wrapper. */

  window.__hypervisorSuggest = function (input, initialItems, opts) {
    opts = opts || {};
    var items = initialItems || [];
    var panel = null;
    var rows = [];
    var activeIdx = -1;
    var dirty = false;

    function fold(text) { return String(text).trim().toLowerCase(); }

    function close() {
      if (panel && panel.parentNode) panel.parentNode.removeChild(panel);
      panel = null;
      rows = [];
      activeIdx = -1;
    }

    function setActive(idx) {
      if (activeIdx >= 0 && rows[activeIdx]) rows[activeIdx].el.classList.remove("active");
      activeIdx = idx;
      if (idx >= 0 && rows[idx]) {
        rows[idx].el.classList.add("active");
        rows[idx].el.scrollIntoView({ block: "nearest" });
      }
    }

    function pick(value) {
      input.value = value;
      dirty = false;
      close();
      if (opts.onPick) opts.onPick(value);
    }

    function addRow(value, label, iconName) {
      var el = document.createElement("button");
      el.type = "button";
      el.className = "menu-item";
      el.setAttribute("role", "option");
      if (iconName) {
        var icon = document.createElement("i");
        icon.className = "menu-item-icon";
        icon.setAttribute("data-lucide", iconName);
        el.appendChild(icon);
      }
      var text = document.createElement("span");
      text.className = "menu-item-label";
      text.textContent = label;
      el.appendChild(text);
      // mousedown (not click) with preventDefault keeps focus in the input.
      el.addEventListener("mousedown", function (e) { e.preventDefault(); pick(value); });
      panel.appendChild(el);
      rows.push({ el: el, value: value });
    }

    function render() {
      if (!items.length && !dirty) { close(); return; }
      var typed = input.value.trim();
      var query = fold(typed);
      var exact = items.some(function (item) { return fold(item) === query; });
      var filtering = dirty && query && !exact;
      var matches = filtering
        ? items.filter(function (item) { return fold(item).indexOf(query) !== -1; })
        : items;
      var canAdd = !!typed && !exact;
      if (!matches.length && !canAdd) { close(); return; }

      close();
      panel = document.createElement("div");
      panel.className = "floating-panel suggest-panel";
      panel.setAttribute("role", "listbox");
      matches.forEach(function (item) { addRow(item, item); });
      if (canAdd) addRow(typed, opts.addLabel ? opts.addLabel(typed) : 'add "' + typed + '"', "plus");
      document.body.appendChild(panel);
      if (window.lucide) lucide.createIcons({ nodes: panel.querySelectorAll("[data-lucide]"), attrs: { "stroke-width": 2 } });

      var rect = (opts.anchor || input).getBoundingClientRect();
      panel.style.left = rect.left + "px";
      panel.style.minWidth = rect.width + "px";
      var below = window.innerHeight - rect.bottom;
      if (panel.offsetHeight > below && rect.top > below) {
        panel.classList.add("suggest-panel-above");
        panel.style.top = (rect.top - panel.offsetHeight) + "px";
      } else {
        panel.style.top = rect.bottom + "px";
      }

      setActive(filtering && matches.length ? 0 : -1);
    }

    function onInput() { dirty = true; render(); }
    function onFocus() { render(); }
    function onClick() { if (!panel) render(); }
    function onBlur() { close(); }
    function onKeyDown(e) {
      if (!panel) {
        if (e.key === "ArrowDown") { e.preventDefault(); render(); }
        return;
      }
      if (e.key === "ArrowDown" || e.key === "ArrowUp") {
        e.preventDefault();
        var step = e.key === "ArrowDown" ? 1 : -1;
        setActive((activeIdx + step + rows.length) % rows.length);
      } else if (e.key === "Enter" && activeIdx >= 0) {
        e.preventDefault();
        e.stopImmediatePropagation();
        pick(rows[activeIdx].value);
      } else if (e.key === "Escape") {
        e.preventDefault();
        e.stopImmediatePropagation();
        close();
      } else if (e.key === "Tab") {
        close();
      }
    }
    function onViewportChange(e) { if (panel && !panel.contains(e.target)) close(); }

    // Capture phase so the list sees Enter/Escape before the host dialog does.
    input.addEventListener("keydown", onKeyDown, true);
    input.addEventListener("input", onInput);
    input.addEventListener("focus", onFocus);
    input.addEventListener("click", onClick);
    input.addEventListener("blur", onBlur);
    window.addEventListener("resize", close);
    window.addEventListener("scroll", onViewportChange, true);
    if (document.activeElement === input) render();

    return {
      setItems: function (next) {
        items = next || [];
        if (panel || document.activeElement === input) render();
      },
      destroy: function () {
        close();
        input.removeEventListener("keydown", onKeyDown, true);
        input.removeEventListener("input", onInput);
        input.removeEventListener("focus", onFocus);
        input.removeEventListener("click", onClick);
        input.removeEventListener("blur", onBlur);
        window.removeEventListener("resize", close);
        window.removeEventListener("scroll", onViewportChange, true);
      }
    };
  };
