#!/usr/bin/env python3
"""
Hypervisor Desktop Application — PyWebView wrapper for the Hypervisor static site.

Provides a native OS window with:
- Live file watching and auto-rebuild on .md changes
- Checkbox write-back (toggle tasks directly in the rendered view)
- Metadata write-back (update Status fields from the UI)

Usage:
    pip install -r requirements-app.txt
    python hypervisor-app.py
"""

import json
import os
import re
import subprocess
import sys
import threading
import webbrowser
from pathlib import Path

import bottle
import webview
import webview.http

from site_utils.config import HYPERSPACE_ROOT, OUTPUT_DIR, ASSETS_DIR
from site_utils.work_items import mark_done as _mark_done
from site_utils.external_files import import_external_file as _import_external, delete_external_file as _delete_external
from site_utils.ideas import delete_idea as _delete_idea
from build import full_build, build_single_file
from watcher import FileWatcher


# ---------------------------------------------------------------------------
# Custom BottleServer — adds a 404 handler that serves site/404.html
# ---------------------------------------------------------------------------

class _HypervisorBottleServer(webview.http.BottleServer):
    """BottleServer subclass that serves site/404.html for missing paths
    instead of Bottle's default white error page."""

    @classmethod
    def start_server(cls, urls, http_port, keyfile=None, certfile=None):
        from webview import _settings
        from webview.util import abspath, is_app, is_local_url

        apps = [u for u in urls if is_app(u)]
        server = cls()

        if len(apps) > 0:
            # WSGI app mode — delegate to parent unchanged
            return super().start_server(urls, http_port, keyfile, certfile)

        # --- Static file mode: replicate parent logic + add 404 handler ---
        local_urls = [u for u in urls if is_local_url(u)]
        common_path = (
            os.path.dirname(os.path.commonpath(local_urls)) if len(local_urls) > 0 else None
        )
        server.root_path = abspath(common_path) if common_path is not None else None

        app = bottle.Bottle()

        @app.post(f'/js_api/{server.uid}')
        def js_api():
            bottle.response.headers['Access-Control-Allow-Origin'] = '*'
            bottle.response.headers['Access-Control-Allow-Methods'] = (
                'PUT, GET, POST, DELETE, OPTIONS'
            )
            bottle.response.headers['Access-Control-Allow-Headers'] = (
                'Origin, Accept, Content-Type, X-Requested-With, X-CSRF-Token'
            )
            body = json.loads(bottle.request.body.read().decode('utf-8'))
            if body['uid'] in server.js_callback:
                return json.dumps(server.js_callback[body['uid']](body))

        @app.route('/')
        @app.route('/<file:path>')
        def asset(file='index.html'):
            if not server.root_path:
                return ''

            # Check if the file exists on disk
            full_path = os.path.join(server.root_path, file)
            if os.path.isfile(full_path):
                resp = bottle.static_file(file, root=server.root_path)
                resp.set_header('Cache-Control', 'no-cache, no-store, must-revalidate')
                resp.set_header('Pragma', 'no-cache')
                resp.set_header('Expires', '0')
                return resp

            # SPA fallback: for HTML page requests that don't match a real file,
            # serve index.html so the client-side router can handle the path.
            # Static assets (.js, .css, .json, .ico, etc.) should still 404.
            ext = os.path.splitext(file)[1].lower()
            static_extensions = {'.js', '.css', '.json', '.ico', '.png', '.jpg', '.svg', '.woff', '.woff2', '.ttf'}
            if ext in static_extensions:
                # Real static file not found — let Bottle return 404
                return bottle.static_file(file, root=server.root_path)

            # HTML navigation request — serve the SPA shell
            resp = bottle.static_file('index.html', root=server.root_path)
            resp.set_header('Cache-Control', 'no-cache, no-store, must-revalidate')
            resp.set_header('Pragma', 'no-cache')
            resp.set_header('Expires', '0')
            return resp

        # --- Custom 404: serve the SPA shell for missing routes ---
        @app.error(404)
        def custom_404(error):
            if server.root_path:
                shell = os.path.join(server.root_path, 'index.html')
                if os.path.isfile(shell):
                    bottle.response.content_type = 'text/html; charset=utf-8'
                    with open(shell, 'r', encoding='utf-8') as f:
                        return f.read()
            return error.body

        server.root_path = abspath(common_path) if common_path is not None else None
        server.port = http_port or webview.http._get_random_port()

        if keyfile and certfile:
            server_adapter = webview.http.SSLWSGIRefServer()
            server_adapter.port = server.port
            setattr(server_adapter, 'pywebview_keyfile', keyfile)
            setattr(server_adapter, 'pywebview_certfile', certfile)
        else:
            server_adapter = webview.http.ThreadedAdapter

        server.thread = threading.Thread(
            target=lambda: bottle.run(
                app=app, server=server_adapter, port=server.port, quiet=not _settings['debug']
            ),
            daemon=True,
        )
        server.thread.start()

        server.running = True
        protocol = 'https' if keyfile and certfile else 'http'
        server.address = f'{protocol}://127.0.0.1:{server.port}/'
        cls.common_path = common_path
        server.js_api_endpoint = f'{server.address}js_api/{server.uid}'

        return server.address, common_path, server


class HypervisorAPI:
    """Python <-> JavaScript bridge exposed to the PyWebView window.

    Methods on this class are callable from JavaScript via window.pywebview.api.
    """

    def __init__(self, watcher):
        self._window = None
        self._watcher = watcher
        self._prefs_lock = __import__("threading").Lock()

    def set_window(self, window):
        """Set the window reference after creation (needed for evaluate_js)."""
        self._window = window

    def _broadcast_js(self, js_code):
        """Evaluate JS in all open windows."""
        for win in webview.windows:
            try:
                win.evaluate_js(js_code)
            except Exception:
                pass

    def toggle_checkbox(self, file_path, line_number, checked):
        """Toggle a task checkbox in the source .md file.

        Args:
            file_path: Path relative to .hyperspace/ (e.g. "work/to-do/item/story.md")
            line_number: 0-indexed line number in the source file
            checked: True if the box is currently checked (will be unchecked), False if open (will be checked)
        """
        full_path = HYPERSPACE_ROOT / file_path
        if not full_path.exists():
            return {"ok": False, "error": f"File not found: {file_path}"}

        # Tell the watcher to ignore events for this file — covers both the
        # immediate write and any delayed filesystem notifications on Windows.
        self._watcher.ignore_path(str(full_path), grace_seconds=2.0)

        lines = full_path.read_text(encoding="utf-8").splitlines()

        if line_number < 0 or line_number >= len(lines):
            return {"ok": False, "error": f"Line {line_number} out of range"}

        line = lines[line_number]
        if checked:
            lines[line_number] = line.replace("- [x]", "- [ ]", 1).replace("- [X]", "- [ ]", 1)
        else:
            lines[line_number] = line.replace("- [ ]", "- [x]", 1)

        full_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

        # Rebuild the HTML on disk in the background — no page reload.
        # The JS side already did an optimistic visual toggle, so reloading
        # would just cause a content blink for no benefit.
        threading.Thread(target=build_single_file, args=(file_path,), daemon=True).start()

        return {"ok": True}

    def update_metadata(self, file_path, field, value):
        """Update a metadata field in the source .md file's header.

        Args:
            file_path: Path relative to .hyperspace/ (e.g. "work/to-do/item/idea.md")
            field: Metadata field name (e.g. "Status")
            value: New value for the field
        """
        full_path = HYPERSPACE_ROOT / file_path
        if not full_path.exists():
            return {"ok": False, "error": f"File not found: {file_path}"}

        # Tell the watcher to ignore events for this file
        self._watcher.ignore_path(str(full_path), grace_seconds=2.0)

        text = full_path.read_text(encoding="utf-8")
        lines = text.splitlines()

        # Find the metadata line matching "- Field: value" pattern
        pattern = re.compile(r'^(\s*-\s*' + re.escape(field) + r'\s*:\s*)(.+)$', re.IGNORECASE)
        found = False
        for i, line in enumerate(lines):
            m = pattern.match(line)
            if m:
                lines[i] = m.group(1) + value
                found = True
                break

        if not found:
            return {"ok": False, "error": f"Field '{field}' not found in {file_path}"}

        full_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

        # Rebuild in the background — no page reload.
        # The JS side already updated the status text optimistically.
        threading.Thread(target=build_single_file, args=(file_path,), daemon=True).start()

        return {"ok": True}

    def rebuild(self):
        """Force a full site rebuild from the UI."""
        full_build(quiet=True)
        # Reload all open windows after rebuild
        for win in webview.windows:
            try:
                win.evaluate_js(
                    "try{sessionStorage.removeItem('__hv_splash_seen')}catch(e){};"
                    "window.location.reload();"
                )
            except Exception:
                pass
        return {"ok": True}

    def launch_hyperagent(self):
        """Launch Hyperagent as a detached subprocess."""
        script = HYPERSPACE_ROOT / ".hyperagent" / "hyperagent.py"
        if not script.exists():
            return {"ok": False, "error": "hyperagent.py not found"}
        try:
            subprocess.Popen(
                ["pythonw", str(script)],
                cwd=str(script.parent),
                creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NO_WINDOW,
            )
            return {"ok": True}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def launch_dev(self, preset=None):
        """Launch the local dev environment.

        Args:
            preset: Preset name (e.g., 'full', 'cms', 'portal-only').
                    Skips the interactive menu and launches directly.
                    If None, opens the interactive launcher console.
        """
        launch_dir = HYPERSPACE_ROOT.parent / ".launch"
        launch_script = launch_dir / "launch.js"
        if not launch_script.exists():
            return {"ok": False, "error": ".launch/launch.js not found"}
        try:
            if preset:
                # Direct launch with preset — no interactive console needed
                subprocess.Popen(
                    ["node", str(launch_script), "--preset", preset],
                    cwd=str(HYPERSPACE_ROOT.parent),
                    creationflags=subprocess.CREATE_NEW_CONSOLE,
                )
            else:
                # Fallback to interactive menu
                script = HYPERSPACE_ROOT.parent / "launch.cmd"
                subprocess.Popen(
                    ["cmd", "/c", str(script)],
                    cwd=str(HYPERSPACE_ROOT.parent),
                    creationflags=subprocess.CREATE_NEW_CONSOLE,
                )
            return {"ok": True}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def import_external_file(self, filename, content):
        """Import a dropped markdown file into .external/ directory.

        Args:
            filename: Original filename (e.g., "meeting-notes.md")
            content: Plain text content of the markdown file

        Returns:
            dict with ok/error status and path of imported file
        """
        try:
            result = _import_external(filename, content)
            if result["ok"]:
                full_build(quiet=True)
                self._broadcast_js("window.__hypervisorReload()")
            return result
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def delete_external_file(self, filename):
        """Delete a file from the .external/ directory.

        Args:
            filename: Filename relative to .external/ (e.g., "meeting-notes.md")

        Returns:
            dict with ok/error status
        """
        try:
            result = _delete_external(filename)
            if result["ok"]:
                full_build(quiet=True)
                self._broadcast_js("window.__hypervisorReload()")
            return result
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def delete_idea(self, filename):
        """Delete an idea file from the ideas/ directory.

        Used when an idea has been implemented or is no longer relevant.

        Args:
            filename: Filename relative to ideas/ (e.g., "my-cool-idea.md")

        Returns:
            dict with ok/error status
        """
        try:
            source_full = str(HYPERSPACE_ROOT / "ideas" / filename)
            self._watcher.ignore_path(source_full, grace_seconds=3.0)

            result = _delete_idea(filename)
            if result["ok"]:
                full_build(quiet=True)
                self._broadcast_js("window.__hypervisorReload()")
            return result
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def read_file(self, file_path):
        """Read raw markdown content from a hyperspace document.

        Args:
            file_path: Path relative to .hyperspace/ (e.g. "work/to-do/my-item.md")

        Returns:
            dict with ok status and content string, or error.
        """
        full_path = HYPERSPACE_ROOT / file_path
        if not full_path.exists():
            return {"ok": False, "error": f"File not found: {file_path}"}
        try:
            content = full_path.read_text(encoding="utf-8")
            return {"ok": True, "content": content}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def write_file(self, file_path, content):
        """Write content to a hyperspace document.

        Persists the content to disk and triggers a single-file rebuild.
        The watcher is suppressed to avoid duplicate rebuilds.

        Args:
            file_path: Path relative to .hyperspace/ (e.g. "work/to-do/my-item.md")
            content: Full file content to write (UTF-8 string)

        Returns:
            dict with ok status, or error.
        """
        full_path = HYPERSPACE_ROOT / file_path
        if not full_path.exists():
            return {"ok": False, "error": f"File not found: {file_path}"}

        # Suppress watcher to avoid duplicate rebuild
        self._watcher.ignore_path(str(full_path), grace_seconds=2.0)

        try:
            full_path.write_text(content, encoding="utf-8")
        except Exception as e:
            return {"ok": False, "error": str(e)}

        # Rebuild in background
        threading.Thread(target=build_single_file, args=(file_path,), daemon=True).start()

        return {"ok": True}

    def save_theme_defaults(self, accent, palette_mode, bw_theme, mode=None, gradient_map=None, palette=None):
        """DEPRECATED: Theme state now lives entirely in preferences.json.
        Kept as a no-op for backward compat with any JS that still calls it.
        """
        return {"ok": True}

    def get_status(self):
        """Return current application status for diagnostics."""
        return {
            "ok": True,
            "hyperspace_root": str(HYPERSPACE_ROOT),
            "output_dir": str(OUTPUT_DIR),
            "site_exists": OUTPUT_DIR.exists(),
        }

    def toggle_fullscreen(self):
        """Toggle the window between fullscreen and windowed mode."""
        win = webview.active_window()
        if win:
            win.toggle_fullscreen()
        return {"ok": True}

    def save_preference(self, key, value):
        """Persist a user preference to disk so it survives app restarts.

        Preferences are stored in .hypervisor/preferences.json.
        Uses a lock + atomic write (temp file → rename) to prevent concurrent
        bridge calls from reading a half-written file and nuking existing data.
        """
        prefs_path = OUTPUT_DIR.parent / "preferences.json"
        with self._prefs_lock:
            prefs = {}
            if prefs_path.exists():
                try:
                    prefs = json.loads(prefs_path.read_text(encoding="utf-8"))
                except (json.JSONDecodeError, OSError):
                    # File is corrupt or unreadable — DON'T overwrite blindly.
                    # Try once more after a brief pause (write may be in-flight).
                    import time
                    time.sleep(0.05)
                    try:
                        prefs = json.loads(prefs_path.read_text(encoding="utf-8"))
                    except (json.JSONDecodeError, OSError):
                        prefs = {}
            prefs[key] = value
            # Atomic write: write to temp file then replace
            tmp_path = prefs_path.with_suffix(".tmp")
            tmp_path.write_text(json.dumps(prefs, indent=2), encoding="utf-8")
            tmp_path.replace(prefs_path)
        return {"ok": True}

    def load_preferences(self):
        """Load all saved preferences from disk."""
        prefs_path = OUTPUT_DIR.parent / "preferences.json"
        if not prefs_path.exists():
            return {}
        try:
            return json.loads(prefs_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}

    def save_preferences_batch(self, updates):
        """Merge multiple preference keys into preferences.json in one write.

        Args:
            updates: Dict of {key: value} pairs to merge into the file.
                     Preserves all existing keys not in updates (e.g. userGradientMaps).
        """
        prefs_path = OUTPUT_DIR.parent / "preferences.json"
        with self._prefs_lock:
            prefs = {}
            if prefs_path.exists():
                try:
                    prefs = json.loads(prefs_path.read_text(encoding="utf-8"))
                except (json.JSONDecodeError, OSError):
                    import time
                    time.sleep(0.05)
                    try:
                        prefs = json.loads(prefs_path.read_text(encoding="utf-8"))
                    except (json.JSONDecodeError, OSError):
                        prefs = {}
            # Merge flat keys only — skip nested objects passed from JS
            for k, v in updates.items():
                if isinstance(v, str) or isinstance(v, (int, float, bool)):
                    prefs[k] = v
            tmp_path = prefs_path.with_suffix(".tmp")
            tmp_path.write_text(json.dumps(prefs, indent=2), encoding="utf-8")
            tmp_path.replace(prefs_path)
        return {"ok": True}

    def get_user_gradient_maps(self):
        """DEPRECATED: User maps are now returned as part of load_preferences().
        Kept for backward compat with palette-generator.html.
        """
        prefs_path = OUTPUT_DIR.parent / "preferences.json"
        if not prefs_path.exists():
            return {}
        try:
            prefs = json.loads(prefs_path.read_text(encoding="utf-8"))
            return prefs.get("userGradientMaps", {})
        except (json.JSONDecodeError, OSError):
            return {}

    def save_user_gradient_map(self, key, data):
        """Save a user-created gradient map preset.

        Args:
            key: Unique key for the preset (kebab-case, e.g. 'my-sunset')
            data: Dict with name, description, accent, warm, cool, comp, and
                  optional semantics {success, warning, error, info}
        """
        prefs_path = OUTPUT_DIR.parent / "preferences.json"
        with self._prefs_lock:
            prefs = {}
            if prefs_path.exists():
                try:
                    prefs = json.loads(prefs_path.read_text(encoding="utf-8"))
                except (json.JSONDecodeError, OSError):
                    prefs = {}
            if "userGradientMaps" not in prefs:
                prefs["userGradientMaps"] = {}
            prefs["userGradientMaps"][key] = data
            tmp_path = prefs_path.with_suffix(".tmp")
            tmp_path.write_text(json.dumps(prefs, indent=2), encoding="utf-8")
            tmp_path.replace(prefs_path)
        return {"ok": True, "key": key}

    def delete_user_gradient_map(self, key):
        """Delete a user-created gradient map preset by key.

        Args:
            key: The preset key to remove.
        """
        prefs_path = OUTPUT_DIR.parent / "preferences.json"
        with self._prefs_lock:
            if not prefs_path.exists():
                return {"ok": False, "error": "No preferences file"}
            try:
                prefs = json.loads(prefs_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                return {"ok": False, "error": "Failed to read preferences"}
            maps = prefs.get("userGradientMaps", {})
            if key not in maps:
                return {"ok": False, "error": f"Preset '{key}' not found"}
            del maps[key]
            prefs["userGradientMaps"] = maps
            tmp_path = prefs_path.with_suffix(".tmp")
            tmp_path.write_text(json.dumps(prefs, indent=2), encoding="utf-8")
            tmp_path.replace(prefs_path)
        return {"ok": True}

    def mark_done(self, file_path):
        """Move a work item from work/to-do/ to work/done/ and update index.

        Delegates file operations to site_utils.work_items, then handles
        watcher suppression, rebuild, and UI navigation.

        Args:
            file_path: Path relative to .hyperspace/ (e.g. "work/to-do/my-item.md")
        """
        try:
            # Suppress watcher BEFORE the file operation to prevent race conditions.
            # The watcher seeing the source modification could trigger a build that
            # locks the file, blocking the rename/delete on Windows.
            source_full = str(HYPERSPACE_ROOT / file_path)
            filename = Path(file_path).name
            dest_full = str(HYPERSPACE_ROOT / "work" / "done" / filename)
            self._watcher.ignore_path(source_full, grace_seconds=3.0)
            self._watcher.ignore_path(dest_full, grace_seconds=3.0)

            result = _mark_done(file_path)
            if not result["ok"]:
                return result

            # Full rebuild + navigate to work/to-do index via SPA router
            full_build(quiet=True)
            win = webview.active_window()
            if win:
                win.evaluate_js(
                    "if(window.__router){"
                    "  window.__router.navigate('/work/to-do/index.html');"
                    "  if(window.__hypervisorToast)window.__hypervisorToast('moved to done');"
                    "}else{window.location.href='/work/to-do/index.html';}"
                )

            return {"ok": True, "new_path": result["new_path"]}

        except Exception as e:
            return {"ok": False, "error": str(e)}

    def open_in_explorer(self, file_path):
        """Open Windows File Explorer with the source file selected.

        Args:
            file_path: Path relative to .hyperspace/ (e.g. "work/to-do/item/idea.md")
        """
        import subprocess
        full_path = HYPERSPACE_ROOT / file_path
        if not full_path.exists():
            return {"ok": False, "error": f"File not found: {file_path}"}
        # Resolve to absolute path and normalize for Windows
        abs_path = str(full_path.resolve())
        try:
            subprocess.Popen(["explorer", "/select,", abs_path])
        except Exception as e:
            return {"ok": False, "error": str(e)}
        return {"ok": True}

    def open_in_new_window(self, path="/index.html"):
        """Open a document in a separate OS window.

        Args:
            path: URL path to open (e.g. "/work/to-do/my-item/index.html")
        """
        try:
            # Derive the server base URL from the main window's current URL
            current_url = self._window.get_current_url() or ""
            # Extract scheme + host + port (e.g. "http://127.0.0.1:54321")
            from urllib.parse import urlparse
            parsed = urlparse(current_url)
            base = f"{parsed.scheme}://{parsed.netloc}"
            url = base + path
            webview.create_window(
                "Hypervisor",
                url,
                js_api=self,
                width=1200,
                height=800,
                min_size=(800, 600),
            )
            return {"ok": True}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def open_external_url(self, url):
        """Open an external URL in the system's default browser.

        Args:
            url: Full URL string (must start with http:// or https://)
        """
        if not url or not url.startswith(("http://", "https://")):
            return {"ok": False, "error": "Invalid URL"}
        try:
            webbrowser.open(url)
        except Exception as e:
            return {"ok": False, "error": str(e)}
        return {"ok": True}

    def save_export(self, html_content, suggested_filename):
        """Save exported HTML content via a native Save As dialog.

        Args:
            html_content: The full HTML string to save
            suggested_filename: Suggested filename for the save dialog
        """
        if not self._window:
            return {"ok": False, "error": "No window available"}

        try:
            result = self._window.create_file_dialog(
                webview.SAVE_DIALOG,
                save_filename=suggested_filename,
                file_types=("HTML Files (*.html)",),
            )
            if result:
                # result is a string path on save dialog
                save_path = result if isinstance(result, str) else str(result)
                Path(save_path).write_text(html_content, encoding="utf-8")
                return {"ok": True, "path": save_path}
            else:
                return {"ok": False, "error": "cancelled"}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def save_export_zip(self, html_content, suggested_filename, source_rel_path):
        """Save exported page as a zip containing both HTML and source markdown.

        Args:
            html_content: The full standalone HTML string
            suggested_filename: Suggested zip filename for the save dialog
            source_rel_path: Relative path to the source .md file within .hyperspace/
        """
        import zipfile
        import io

        if not self._window:
            return {"ok": False, "error": "No window available"}

        # Read the source markdown from disk
        md_path = HYPERSPACE_ROOT / source_rel_path
        if not md_path.exists():
            return {"ok": False, "error": f"Source file not found: {source_rel_path}"}

        try:
            md_content = md_path.read_text(encoding="utf-8")
        except Exception as e:
            return {"ok": False, "error": f"Failed to read source: {e}"}

        try:
            result = self._window.create_file_dialog(
                webview.SAVE_DIALOG,
                save_filename=suggested_filename,
                file_types=("ZIP Archives (*.zip)",),
            )
            if not result:
                return {"ok": False, "error": "cancelled"}

            save_path = result if isinstance(result, str) else str(result)

            # Derive filenames for zip contents from the base name
            base_name = Path(suggested_filename).stem
            html_name = base_name + ".html"
            md_name = Path(source_rel_path).name

            # Build the zip in memory, then write to disk
            buf = io.BytesIO()
            with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
                zf.writestr(html_name, html_content)
                zf.writestr(md_name, md_content)

            Path(save_path).write_bytes(buf.getvalue())
            return {"ok": True, "path": save_path}

        except Exception as e:
            return {"ok": False, "error": str(e)}

    # --- Scratch Buffer / Daily Journal ---

    def open_scratch(self, date=None):
        """Load a scratch file by date, or today's file (creating if absent).

        Args:
            date: Optional date string "YYYY-MM-DD". Defaults to today.

        Returns:
            dict with ok, date, content, and whether the file was just created.
        """
        from datetime import datetime as _dt

        scratch_dir = HYPERSPACE_ROOT / ".scratch"
        scratch_dir.mkdir(exist_ok=True)

        target_date = date or _dt.now().strftime("%Y-%m-%d")
        file_path = scratch_dir / f"{target_date}.md"

        created = False
        if not file_path.exists():
            # Initialize with a header
            file_path.write_text(f"# Scratch \u2014 {target_date}\n\n", encoding="utf-8")
            created = True

        content = file_path.read_text(encoding="utf-8")
        return {"ok": True, "date": target_date, "content": content, "created": created}

    def save_scratch(self, date, content):
        """Save scratch content for a given date.

        Args:
            date: Date string "YYYY-MM-DD"
            content: Full file content to write

        Returns:
            dict with ok status.
        """
        scratch_dir = HYPERSPACE_ROOT / ".scratch"
        scratch_dir.mkdir(exist_ok=True)

        file_path = scratch_dir / f"{date}.md"
        try:
            file_path.write_text(content, encoding="utf-8")
            return {"ok": True}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def list_scratch(self):
        """List all scratch files with dates and entry counts.

        Returns:
            dict with ok and files list [{date, entries, size}], newest first.
        """
        scratch_dir = HYPERSPACE_ROOT / ".scratch"
        if not scratch_dir.exists():
            return {"ok": True, "files": []}

        files = []
        for f in sorted(scratch_dir.glob("*.md"), reverse=True):
            # Date is the filename stem (YYYY-MM-DD)
            date = f.stem
            content = f.read_text(encoding="utf-8")
            # Count entries by counting ## HH:MM headings
            entries = content.count("\n## ")
            files.append({"date": date, "entries": entries, "size": len(content)})

        return {"ok": True, "files": files}

    def delete_scratch(self, date):
        """Delete a scratch file by date.

        Args:
            date: Date string "YYYY-MM-DD"

        Returns:
            dict with ok status.
        """
        scratch_dir = HYPERSPACE_ROOT / ".scratch"
        file_path = scratch_dir / f"{date}.md"

        if not file_path.exists():
            return {"ok": False, "error": f"Scratch file not found: {date}"}

        try:
            file_path.unlink()
            return {"ok": True}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def refresh_health_dashboard(self):
        """Fetch live hyperspace health analytics for the dashboard.

        Calls the hv_mcp analytics functions directly to return fresh data
        including health report, stale documents, and tag analytics.

        Returns:
            dict with health, stale, tags data and timestamp.
        """
        try:
            from datetime import datetime as _dt
            from hv_mcp.index import rebuild_index
            from hv_mcp.analytics import health_report, stale_documents, tag_analytics

            rebuild_index()

            return {
                "ok": True,
                "health": health_report(),
                "stale": stale_documents(days=30),
                "tags": tag_analytics(),
                "timestamp": _dt.now().strftime("%Y-%m-%d %H:%M"),
            }
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def fix_violations(self, dry_run=True):
        """Run schema migration to auto-fix metadata violations.

        Handles fixable issues: Date→Created rename, bold→dash-prefixed,
        missing Created/Updated, date format normalization, metadata reordering.

        Does NOT fix: unknown tags, tag count issues, missing titles, unknown projects.

        Args:
            dry_run: If True, preview changes without writing. If False, apply fixes.

        Returns:
            dict with migration results including what was (or would be) fixed,
            plus remaining_violations that require manual intervention.
        """
        try:
            from hv_mcp.migration import migrate_document
            from hv_mcp.validation import validate_all

            result = migrate_document(path="all", dry_run=dry_run)
            result["ok"] = True

            # Include remaining violations that migration can't fix
            validation = validate_all()
            result["remaining_violations"] = validation.get("top_issues", [])
            result["total_violations"] = validation.get("violations", 0)

            return result
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def refresh_ado_dashboard(self):
        """Fetch fresh ADO sprint data and return it as JSON for the dashboard.

        Uses the ado_collector module to pull current iteration, work items,
        and pull requests from Azure DevOps. Response shaping is delegated
        to tools.ado_dashboard.

        Returns:
            dict with sprint data or error information.
        """
        try:
            tools_dir = Path(__file__).parent / "tools"
            sys.path.insert(0, str(tools_dir))
            from ado_collector import load_config, ADOClient, extract_top_level_items, ADOConfigError
            from ado_dashboard import build_dashboard_payload
            sys.path.pop(0)
        except ImportError as e:
            return {"ok": False, "error": f"Failed to import ado modules: {e}"}

        try:
            config = load_config()
        except ADOConfigError as e:
            return {"ok": False, "error": str(e)}

        try:
            client = ADOClient(config["org"], pat=config.get("pat"), use_entra=config.get("use_entra", False))

            # Get current iteration
            iteration = client.get_current_iteration(config["project"], config["team"])
            if not iteration:
                return {"ok": False, "error": "No current iteration found."}

            # Get work items for the iteration
            iter_data = client.get_iteration_work_items(
                config["project"], config["team"], iteration["id"]
            )
            top_level_ids = extract_top_level_items(iter_data)

            # Get work item details
            fields = [
                "System.Id", "System.Title", "System.State",
                "System.WorkItemType", "System.AssignedTo", "System.Tags",
                "Microsoft.VSTS.Scheduling.StoryPoints",
            ]
            work_items = client.get_work_items(config["project"], top_level_ids, fields=fields)

            # Get active PRs
            pull_requests = client.get_pull_requests(config["project"])

            # Get outstanding work requests
            wiql = (
                "SELECT [System.Id], [System.Title], [System.State], "
                "[System.AssignedTo], [System.CreatedDate] "
                "FROM WorkItems "
                "WHERE [System.TeamProject] = @project "
                "AND [System.WorkItemType] = 'Work Request' "
                "AND [System.State] <> 'Done' "
                "AND [System.State] <> 'Closed' "
                "AND [System.State] <> 'Removed' "
                "ORDER BY [System.CreatedDate] DESC"
            )
            work_requests = client.query_work_items_wiql(config["project"], wiql, top=50)

            # Get historical burndown from Analytics OData
            iter_path = iteration.get("path", "")
            start_date = iteration.get("attributes", {}).get("startDate", "")[:10]
            finish_date = iteration.get("attributes", {}).get("finishDate", "")[:10]
            burndown_history = []
            if iter_path and start_date and finish_date:
                try:
                    burndown_history = client.get_burndown_history(
                        config["org"], config["project"], iter_path, start_date, finish_date
                    )
                except Exception:
                    pass  # Non-fatal — dashboard still works without history

            # Build and return the dashboard payload
            return build_dashboard_payload(iteration, work_items, pull_requests, work_requests, config, burndown_history)

        except Exception as e:
            return {"ok": False, "error": str(e)}


def on_file_changed(rel_path):
    """Callback from the file watcher when a .md file changes.

    Args:
        rel_path: Relative path to the changed file, or None for deletions/full rebuild.
    """
    global _window, _api

    if rel_path:
        print(f"  File changed: {rel_path}")
        build_single_file(rel_path)
    else:
        print("  File deleted or moved — full rebuild")
        full_build(quiet=True)

    if _window:
        try:
            # With the SPA router, __hypervisorReload re-fetches the current fragment.
            # Show a toast notification after reload completes.
            if rel_path:
                safe_path = rel_path.replace("\\", "/").replace("'", "\\'")
                js_code = (
                    "window.__hypervisorReload();"
                    "if(window.__hypervisorToast)window.__hypervisorToast('updated: " + safe_path + "');"
                )
            else:
                js_code = (
                    "window.__hypervisorReload();"
                    "if(window.__hypervisorToast)window.__hypervisorToast('full rebuild complete');"
                )
            for win in webview.windows:
                try:
                    win.evaluate_js(js_code)
                except Exception:
                    pass
        except Exception:
            pass  # Window may be closing


def start_watcher_thread(watcher):
    """Background thread that runs the file watcher."""
    watcher.start()


# Module-level references for the callback
_window = None
_api = None


def _apply_window_chrome(title: str, icon_path: str):
    """Force dark title bar and custom icon via Windows DWM API."""
    import ctypes
    hwnd = ctypes.windll.user32.FindWindowW(None, title)
    if not hwnd:
        return
    # Dark title bar
    DWMWA_USE_IMMERSIVE_DARK_MODE = 20
    val = ctypes.c_int(1)
    ctypes.windll.dwmapi.DwmSetWindowAttribute(
        hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE, ctypes.byref(val), ctypes.sizeof(val)
    )
    # Custom icon
    IMAGE_ICON = 1
    LR_LOADFROMFILE = 0x0010
    WM_SETICON = 0x0080
    ICON_BIG = 1
    ICON_SMALL = 0
    hicon = ctypes.windll.user32.LoadImageW(
        0, icon_path, IMAGE_ICON, 0, 0, LR_LOADFROMFILE
    )
    if hicon:
        ctypes.windll.user32.SendMessageW(hwnd, WM_SETICON, ICON_BIG, hicon)
        ctypes.windll.user32.SendMessageW(hwnd, WM_SETICON, ICON_SMALL, hicon)


def main():
    global _window, _api

    print("Hypervisor Desktop: starting ...")

    # Signal that the desktop app is running — MCP tools check this to avoid
    # triggering duplicate site builds (the desktop watcher handles rebuilds).
    app_lock = OUTPUT_DIR.parent / ".app_running"
    app_lock.write_text(str(os.getpid()), encoding="utf-8")

    # Initial full build
    build_id = full_build()
    print(f"  Build complete (id: {build_id})")

    # Set up file watcher
    watcher = FileWatcher(on_file_changed, debounce_seconds=0.3)

    # Set up the JS bridge API
    api = HypervisorAPI(watcher)
    _api = api

    # Create the native window — pass the file path so pywebview treats it
    # as a local URL and starts its HTTP server (needed for the js_api bridge).
    index_path = str((OUTPUT_DIR / "index.html").resolve())
    window = webview.create_window(
        "Hypervisor",
        index_path,
        js_api=api,
        width=1400,
        height=900,
        min_size=(800, 600),
        background_color='#000000',
    )
    _window = window
    api.set_window(window)

    def on_loaded():
        """Called when the webview finishes loading a page."""
        # The SPA shell defines __hypervisorReload in app.js (uses the router).
        # No need to inject a reload helper — just ensure the bridge is ready.
        pass

    window.events.loaded += on_loaded

    # Start the watcher on a background thread
    def background():
        import time
        time.sleep(1)
        _apply_window_chrome("Hypervisor", str((ASSETS_DIR / "hv-box.ico").resolve()))
        start_watcher_thread(watcher)

    # Start PyWebView — pass our custom server class so the internal HTTP
    # server uses our 404 handler instead of Bottle's default white page.
    # private_mode=False + storage_path pins localStorage to a fixed location
    # on disk so it persists across app restarts (regardless of port changes).
    icon_path = str((ASSETS_DIR / "hv-box.ico").resolve())
    storage_dir = str((OUTPUT_DIR.parent / ".webview_data").resolve())
    webview.start(background, debug=False, icon=icon_path,
                  private_mode=False, storage_path=storage_dir,
                  server=_HypervisorBottleServer)

    # Cleanup
    print("  Window closed — shutting down")
    watcher.stop()
    try:
        app_lock.unlink()
    except OSError:
        pass
    print("  Done")


if __name__ == "__main__":
    main()
