/* === Hypervisor: MCP Service Control ===
 *
 * Desktop-only control for the shared MCP HTTP service. The service outlives
 * the Hypervisor window on purpose (agent sessions depend on it), so it needs
 * an explicit way to inspect, bounce, and stop it.
 *
 * Bridge methods used: mcp_status, mcp_restart, mcp_stop, mcp_start.
 * Promotes nothing to window.* — fully self-contained.
 */
(function () {
  "use strict";

  var POLL_MS = 15000;
  var busy = false;
  var pollTimer = null;

  function api() {
    return (window.pywebview && window.pywebview.api) ? window.pywebview.api : null;
  }

  function el(id) { return document.getElementById(id); }

  function toast(title, message, variant) {
    if (window.HvToast && typeof window.HvToast.show === "function") {
      window.HvToast.show({ variant: variant || "info", title: title, message: message });
    }
  }

  /* Render the state chip. Uses the canonical chip vocabulary:
     filled = live/current, outlined-muted = idle/historical. */
  function renderState(s) {
    var chip = el("mcp-state");
    var stopBtn = el("mcp-stop-btn");
    var restartBtn = el("mcp-restart-btn");
    if (!chip) return;

    chip.classList.remove("status-chip-filled", "status-chip-outlined-muted", "status-chip-outlined-accent");

    if (!s || s.ok === false) {
      chip.classList.add("status-chip-outlined-muted");
      chip.textContent = "unknown";
      chip.title = (s && s.error) ? s.error : "Could not read service state";
      return;
    }

    if (s.running) {
      chip.classList.add("status-chip-filled");
      chip.textContent = "PID " + s.pid;
      chip.title = "Running on port " + s.port +
                   (s.owned ? " (started by this window)" : " (started by a previous window)");
      if (stopBtn) stopBtn.disabled = false;
      if (restartBtn) restartBtn.setAttribute("title", "Restart — picks up code changes");
    } else {
      chip.classList.add("status-chip-outlined-muted");
      chip.textContent = "stopped";
      // Port open with no lock file means a stray instance is squatting 8321.
      chip.title = s.port_open
        ? "Port " + s.port + " is in use but no service is registered — a stray instance may be running"
        : "Not running";
      if (stopBtn) stopBtn.disabled = true;
      if (restartBtn) restartBtn.setAttribute("title", "Start the service");
    }
  }

  function refresh() {
    var a = api();
    if (!a || typeof a.mcp_status !== "function") return;
    try {
      var r = a.mcp_status();
      if (r && typeof r.then === "function") {
        r.then(renderState, function () { renderState(null); });
      } else {
        renderState(r);
      }
    } catch (e) {
      renderState(null);
    }
  }

  function spin(iconId, on) {
    var icon = el(iconId);
    if (icon) icon.style.animation = on ? "spin 0.6s linear infinite" : "";
  }

  /* Run a bridge action, then refresh. Guards against double-clicks, since
     both actions terminate a process and overlapping calls would race. */
  function run(method, iconId, verb) {
    if (busy) return;
    var a = api();
    if (!a || typeof a[method] !== "function") return;

    busy = true;
    spin(iconId, true);

    function done(res) {
      busy = false;
      spin(iconId, false);
      if (res && res.ok === false) {
        toast("MCP " + verb + " failed", res.error || "Unknown error", "error");
      } else if (res && res.action === "not running") {
        toast("MCP service", "Already stopped", "info");
      } else {
        var pid = (res && res.pid) ? " (PID " + res.pid + ")" : "";
        toast("MCP service", verb + pid, "success");
        if (res && res.warning) toast("MCP service", res.warning, "info");
      }
      refresh();
    }

    try {
      var r = a[method]();
      if (r && typeof r.then === "function") {
        r.then(done, function (e) { done({ ok: false, error: String(e) }); });
      } else {
        done(r);
      }
    } catch (e) {
      done({ ok: false, error: String(e) });
    }
  }

  function startPolling() {
    if (pollTimer) return;
    pollTimer = setInterval(function () {
      // Only poll while the nav panel is actually open — no point querying
      // process state for a control nobody is looking at.
      var panel = el("nav-panel");
      if (panel && panel.classList.contains("open")) refresh();
    }, POLL_MS);
  }

  function mount() {
    var row = el("mcp-row");
    if (!row) return;
    row.style.display = "";

    var restartBtn = el("mcp-restart-btn");
    var stopBtn = el("mcp-stop-btn");

    if (restartBtn) {
      restartBtn.addEventListener("click", function () {
        // Same handler serves start and restart: mcp_restart replaces a running
        // service and launches cleanly when none is running.
        run("mcp_restart", "mcp-restart-icon", "restarted");
      });
    }
    if (stopBtn) {
      stopBtn.addEventListener("click", function () {
        run("mcp_stop", "mcp-stop-icon", "stopped");
      });
    }

    // Refresh when the menu opens so the chip is accurate on view.
    var navBtn = el("nav-menu-btn");
    if (navBtn) navBtn.addEventListener("click", function () { setTimeout(refresh, 60); });

    refresh();
    startPolling();
  }

  if (window.isDesktopApp && api()) {
    mount();
  } else {
    window.addEventListener("pywebviewready", mount);
  }
})();
