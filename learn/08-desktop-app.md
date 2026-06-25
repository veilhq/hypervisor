# The Desktop App

How PyWebView wraps the site into a native window with live reload and write-back.

---

## What PyWebView Does

[PyWebView](https://pywebview.flowrl.com/) creates a native OS window that renders HTML content using the system's built-in web engine (Edge WebView2 on Windows, WebKit on macOS/Linux). It's like Electron but:

- **No bundled browser** — uses what's already on your system
- **Tiny footprint** — just a Python package, not a 100MB Chromium download
- **Python-native** — your backend is Python, the bridge is Python

The result: a desktop application that looks and feels native, powered by the same HTML/CSS/JS as the browser version.

## Entry Point: `hypervisor-app.py`

```python
import webview
from build import full_build, build_single_file, OUTPUT_DIR

# 1. Run a full build on startup
build_id = full_build(quiet=True)

# 2. Create the window pointing at the generated site
window = webview.create_window(
    'Hypervisor',
    url=str(OUTPUT_DIR / 'index.html'),
    js_api=HypervisorAPI(),
    width=1400,
    height=900,
)

# 3. Start the file watcher in a background thread
start_watcher(window)

# 4. Launch the app
webview.start()
```

### The lifecycle

1. **Build** — generate the site so there's something to display
2. **Create window** — tell PyWebView what HTML to load
3. **Watch** — monitor `.md` files for changes
4. **Run** — hand control to PyWebView's event loop

## The JavaScript Bridge (`js_api`)

PyWebView lets Python expose functions that JavaScript can call. This is how the UI communicates back to Python:

```python
class HypervisorAPI:
    def toggle_checkbox(self, file_path, line_number, checked):
        """Called when a user clicks a task checkbox in the rendered HTML."""
        # Read the source .md file
        # Find the checkbox on the specified line
        # Toggle [ ] ↔ [x]
        # Write the file back
        pass

    def save_preference(self, key, value):
        """Called when the user changes a setting (accent color, width, etc.)."""
        # Write to preferences.json
        pass
```

From JavaScript:
```javascript
// Call Python from the browser
window.pywebview.api.toggle_checkbox('work/to-do/cms-bulk-upload.md', 42, true);
```

This bridge is what makes the app more than a viewer — it can **write back** to your source files.

## File Watching with Watchdog

The [`watchdog`](https://python-watchdog.readthedocs.io/) library monitors the filesystem for changes:

```python
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

class MarkdownHandler(FileSystemEventHandler):
    def on_modified(self, event):
        if event.src_path.endswith('.md'):
            build_single_file(event.src_path)
            window.evaluate_js('location.reload()')
```

### How it works

1. Watchdog registers with the OS to receive filesystem notifications
2. When a `.md` file is saved, the OS notifies watchdog
3. Watchdog calls `on_modified` with the file path
4. Hypervisor rebuilds just that file (incremental build)
5. The browser window reloads to show the update

### The ignore-path grace period

When the app writes to a file (checkbox toggle, metadata update), it would trigger the watcher, which would rebuild, which could cause a loop. The solution:

```python
ignore_until = {}  # path → timestamp

def write_to_file(path, content):
    ignore_until[path] = time.time() + 2  # Ignore events for 2 seconds
    path.write_text(content)

def on_modified(self, event):
    if ignore_until.get(event.src_path, 0) > time.time():
        return  # Skip — this was our own write
    build_single_file(event.src_path)
```

## Write-Back: Checkboxes

When you click a task checkbox in the rendered HTML:

1. JavaScript detects the click on a checkbox element
2. It reads the `data-file` and `data-line` attributes (set during post-processing)
3. It calls `window.pywebview.api.toggle_checkbox(file, line, newState)`
4. Python reads the source `.md` file
5. Finds the line and toggles `- [ ]` ↔ `- [x]`
6. Writes the file back
7. The watcher ignore-path prevents a rebuild loop

The result: clicking a checkbox in the UI permanently changes the source markdown file.

## Write-Back: Metadata

Same pattern for status changes:

```javascript
// User changes a work item's status via a dropdown
window.pywebview.api.update_metadata('work/to-do/cms-bulk-upload.md', 'Status', 'In Progress');
```

Python finds the `- Status: ...` line in the file and updates it.

## The Custom 404 Page

PyWebView serves files through a built-in Bottle web server. Hypervisor subclasses it to add a custom 404 page:

```python
class _HypervisorBottleServer(webview.http.BottleServer):
    def start_server(self, ...):
        # Set up routes like the parent
        # Add: @app.error(404) handler that serves site/404.html
        pass
```

This means broken links show a styled error page instead of a white "Not Found" screen.

## Preferences Persistence

User settings are stored in `preferences.json`:

```json
{
  "accent": "#00ff41",
  "palette_mode": "SPL",
  "reading_width": "full",
  "zoom": 100
}
```

On startup, the app injects these into the page so settings survive restarts:

```python
# After window loads, apply saved preferences
window.evaluate_js(f'applyAccent("{prefs["accent"]}")')
```

## Desktop vs Browser: Feature Matrix

| Feature | Browser (`file://`) | Desktop (PyWebView) |
|---|---|---|
| View pages | ✓ | ✓ |
| Search | ✓ | ✓ |
| Accent color | ✓ (localStorage) | ✓ (preferences.json) |
| Live reload | ✓ (polls _build.json) | ✓ (watcher triggers reload) |
| Checkbox write-back | ✗ | ✓ |
| Metadata write-back | ✗ | ✓ |
| File explorer button | ✗ | ✓ |
| Custom 404 | ✗ | ✓ |

## Coordination with the MCP Server

When Kiro is active, the MCP server (`mcp-server.py`) runs as a separate process watching the same `.hyperspace/` directory. This creates a potential conflict: two watchers, two possible build triggers, same files.

### The Ownership Rule

**The desktop app owns site builds. The MCP server owns data operations.**

The desktop app signals its presence by writing `.hypervisor/.app_running` (containing its PID) on startup and deleting it on shutdown. The MCP server checks this file before triggering any site rebuild — if the desktop app is running, it defers.

### Why This Matters

Without coordination, this sequence causes Windows file-locking errors:

1. MCP tool writes a file
2. MCP's `trigger_site_build()` starts a full build in a background thread
3. Desktop watcher detects the file change and also starts a build
4. Two builds race, both writing to `site/` → PermissionError on Windows

With coordination:
1. MCP tool writes the file and updates its in-memory index
2. MCP sees `.app_running` → skips the build
3. Desktop watcher detects the change → single clean build with debouncing

### Watcher Suppression Before File Operations

The desktop app suppresses its own watcher *before* performing file operations (not after). This prevents the watcher from triggering a build that opens the file for reading while the operation is still modifying/deleting it:

```python
def mark_done(self, file_path):
    # Suppress BEFORE the operation
    self._watcher.ignore_path(source_full, grace_seconds=3.0)
    self._watcher.ignore_path(dest_full, grace_seconds=3.0)

    # Now safe to write/move/delete
    result = _mark_done(file_path)

    # Then trigger a deliberate rebuild
    full_build(quiet=True)
```

### Shared Code: `_regenerate_index()`

The desktop app's `mark_done` operation imports `hv_mcp.index.rebuild_index` and `hv_mcp.index_file.regenerate_index_file` directly to keep `_index.md` in sync. This avoids duplicating the index regeneration logic and ensures both entry points produce identical output.

## Reference Links

- [PyWebView documentation](https://pywebview.flowrl.com/) — the full API
- [PyWebView JS API](https://pywebview.flowrl.com/guide/api.html#js-api) — exposing Python to JavaScript
- [Watchdog documentation](https://python-watchdog.readthedocs.io/) — filesystem monitoring
- [Bottle framework](https://bottlepy.org/) — the micro web framework PyWebView uses internally
- [WebView2 (Windows)](https://developer.microsoft.com/en-us/microsoft-edge/webview2/) — the rendering engine on Windows

## Next

→ [Design Decisions](../09-design-decisions/index.html) — why things are built this way
