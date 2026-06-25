/* === Hypervisor: Actions Drawer === */

  // Provides the pop-up actions drawer triggered from the footer.
  // Slides up from the bottom-right, dismissed by clicking outside or pressing Escape.

  (function initActionsDrawer() {
    var trigger = document.getElementById("actions-trigger");
    var drawer = document.getElementById("actions-drawer");
    if (!trigger || !drawer) return;

    var isOpen = false;

    function open() {
      isOpen = true;
      drawer.classList.add("open");
      drawer.setAttribute("aria-hidden", "false");
      trigger.classList.add("active");
    }

    function close() {
      isOpen = false;
      drawer.classList.remove("open");
      drawer.setAttribute("aria-hidden", "true");
      trigger.classList.remove("active");
    }

    function toggle() {
      if (isOpen) close(); else open();
    }

    // Trigger button
    trigger.addEventListener("click", function (e) {
      e.stopPropagation();
      toggle();
    });

    // Click outside to close
    document.addEventListener("click", function (e) {
      if (!isOpen) return;
      if (!drawer.contains(e.target) && e.target !== trigger && !trigger.contains(e.target)) {
        close();
      }
    });

    // Escape to close
    document.addEventListener("keydown", function (e) {
      if (isOpen && e.key === "Escape") {
        close();
        trigger.focus();
      }
    });

    // Close after an action is performed (optional: actions can call this)
    window.__closeActionsDrawer = close;
  })();
