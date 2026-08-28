/* ===== Hypervisor: Context menu registrations =====
   Registers right-click actions for document links using the shared
   HvContextMenu primitive from Hyperkit. Bridge-dependent actions are
   only added when pywebview API is available. */

(function initContextMenuActions() {
  if (!window.HvContextMenu) return;

  function getApi() {
    return (window.pywebview && window.pywebview.api) ? window.pywebview.api : null;
  }

  // --- Document list items (right-click on items in directory listings) ---
  // Most specific — registered first so it wins over generic a[href] or .markdown-body.
  HvContextMenu.register('.doc-list li', function (el, e) {
    var api = getApi();
    var link = el.querySelector('a');
    if (!link) return [];

    var href = link.getAttribute('href') || '';
    if (!href || href.startsWith('http')) return [];

    // Resolve file path from href
    var slug = href.replace(/^\//, '').replace(/\/index\.html$/, '').replace(/\/$/, '').replace(/\.html$/, '');
    if (!slug) return [];

    // For relative hrefs, prepend the current directory context
    var dirPrefix = '';
    if (slug.indexOf('/') === -1 && window.__router) {
      var frag = window.__router.getCurrentFragment();
      if (frag && frag.sourcePath) dirPrefix = frag.sourcePath + '/';
    }
    var filePath = dirPrefix + slug + '.md';
    var shortName = slug.split('/').pop();

    var items = [];

    // Open in new window
    if (api && api.open_in_new_window) {
      items.push({
        label: 'Open in new window',
        icon: 'app-window',
        action: function () { api.open_in_new_window(href); }
      });
    }

    // Copy path
    items.push({
      label: 'Copy path',
      icon: 'clipboard',
      action: function () {
        navigator.clipboard.writeText(filePath).then(function () {
          if (window.__hypervisorToast) window.__hypervisorToast({ variant: 'success', message: 'path copied' });
        });
      }
    });

    // Open in explorer
    if (api && api.open_in_explorer) {
      items.push({
        label: 'Open in explorer',
        icon: 'folder-open',
        action: function () { api.open_in_explorer(filePath); }
      });
    }

    // Mark as done (only for work/to-do items)
    if (api && api.mark_done && filePath.indexOf('work/to-do/') !== -1) {
      items.push({ separator: true });
      items.push({
        label: 'Mark as done',
        icon: 'check-circle',
        action: function () {
          if (!window.__hypervisorConfirm) return;
          window.__hypervisorConfirm('Mark ' + shortName + ' as done?', {
            confirmLabel: 'done', cancelLabel: 'cancel'
          }).then(function (confirmed) {
            if (!confirmed) return;
            api.mark_done(filePath);
          });
        }
      });

      // Set Horizon submenu
      var horizonChildren = [];
      var horizons = ['Sprint', 'Sprint+1', 'Sprint+2', 'Sprint+3', 'Backlog'];
      for (var h = 0; h < horizons.length; h++) {
        (function (hz) {
          horizonChildren.push({
            label: hz,
            icon: hz === 'Sprint' ? 'zap' : hz === 'Backlog' ? 'archive' : 'clock',
            action: function () {
              api.update_metadata(filePath, 'Horizon', hz).then(function (result) {
                if (result && result.ok) {
                  if (window.__hypervisorToast) window.__hypervisorToast({ variant: 'success', message: 'horizon → ' + hz });
                } else {
                  if (window.__hypervisorToast) window.__hypervisorToast({ variant: 'error', message: (result && result.error) || 'update failed' });
                }
              });
            }
          });
        })(horizons[h]);
      }
      items.push({ label: 'Horizon', icon: 'layers', children: horizonChildren });
    }

    // Delete
    if (api && api.delete_document) {
      if (!items[items.length - 1] || !items[items.length - 1].separator) items.push({ separator: true });
      items.push({
        label: 'Delete',
        icon: 'trash-2',
        action: function () {
          if (!window.__hypervisorConfirm) return;
          window.__hypervisorConfirm('Delete ' + shortName + '? This cannot be undone.', {
            confirmLabel: 'delete', cancelLabel: 'cancel'
          }).then(function (confirmed) {
            if (!confirmed) return;
            api.delete_document(filePath).then(function (result) {
              if (!result || !result.ok) {
                if (window.__hypervisorToast) window.__hypervisorToast({ variant: 'error', title: 'delete failed', message: (result && result.error) || 'unknown error' });
              }
            }).catch(function () {
              if (window.__hypervisorToast) window.__hypervisorToast({ variant: 'error', message: 'delete failed' });
            });
          });
        }
      });
    }

    return items;
  });

  // --- Document links (any anchor with internal hrefs, outside doc-lists) ---
  HvContextMenu.register('a[href]', function (el) {
    var href = el.getAttribute('href') || '';
    // Only internal doc links (not external URLs)
    if (href.startsWith('http://') || href.startsWith('https://')) return [];
    // Skip anchor-only links
    if (href.startsWith('#')) return [];

    var api = getApi();
    var items = [];

    // Open in new window (bridge-only)
    if (api && api.open_in_new_window) {
      items.push({
        label: 'Open in new window',
        icon: 'app-window',
        action: function () { api.open_in_new_window(href); }
      });
    }

    // Copy path
    items.push({
      label: 'Copy path',
      icon: 'clipboard',
      action: function () {
        var path = href.replace(/^\//, '').replace(/\.html$/, '.md');
        navigator.clipboard.writeText(path).then(function () {
          if (window.__hypervisorToast) window.__hypervisorToast({ variant: 'success', message: 'path copied' });
        });
      }
    });

    // Open in file explorer (bridge-only)
    if (api && api.open_in_explorer) {
      items.push({
        label: 'Open in explorer',
        icon: 'folder-open',
        action: function () {
          var path = href.replace(/^\//, '').replace(/\.html$/, '.md');
          api.open_in_explorer(path);
        }
      });
    }

    return items;
  });

  // --- Current page context (right-click on content area) ---
  HvContextMenu.register('.markdown-body', function (el, e) {
    var sourcePathEl = document.getElementById('source-path');
    var filePath = sourcePathEl ? sourcePathEl.textContent.trim() : '';
    if (!filePath) return [];

    var api = getApi();
    var items = [];

    // Edit (bridge-only)
    if (api && api.open_in_editor) {
      items.push({
        label: 'Edit',
        icon: 'pencil',
        action: function () {
          var editBtn = document.getElementById('edit-btn');
          if (editBtn) editBtn.click();
        }
      });
    }

    // Export
    items.push({
      label: 'Export page',
      icon: 'package',
      action: function () {
        var exportBtn = document.getElementById('export-btn');
        if (exportBtn) exportBtn.click();
      }
    });

    // Copy page path
    items.push({
      label: 'Copy path',
      icon: 'clipboard',
      action: function () {
        navigator.clipboard.writeText(filePath).then(function () {
          if (window.__hypervisorToast) window.__hypervisorToast({ variant: 'success', message: 'path copied' });
        });
      }
    });

    // Open in explorer (bridge-only)
    if (api && api.open_in_explorer && filePath.endsWith('.md')) {
      items.push({
        label: 'Open in explorer',
        icon: 'folder-open',
        action: function () { api.open_in_explorer(filePath); }
      });
    }

    // --- Pin / Unpin ---
    var pageTitle = document.querySelector('#content-target h1');
    var titleText = pageTitle ? pageTitle.textContent.trim() : filePath.split('/').pop().replace('.md', '');
    if (filePath && window.HvPins) {
      items.push({ separator: true });
      var pinned = window.HvPins.isPinned(filePath);
      items.push({
        label: pinned ? 'Unpin' : 'Pin',
        icon: pinned ? 'pin-off' : 'pin',
        action: function () {
          if (pinned) {
            window.HvPins.remove(filePath);
            if (window.__hypervisorToast) window.__hypervisorToast({ variant: 'success', message: 'unpinned' });
          } else {
            window.HvPins.add(filePath, titleText);
            if (window.__hypervisorToast) window.__hypervisorToast({ variant: 'success', message: 'pinned' });
          }
        }
      });
    }

    // --- Mark as Done (work/to-do items only, bridge-only) ---
    if (api && api.mark_done && filePath.indexOf('work/to-do/') !== -1) {
      items.push({
        label: 'Mark as done',
        icon: 'check-circle',
        action: function () {
          if (!window.__hypervisorConfirm) return;
          var shortName = filePath.replace(/\\/g, '/').split('/').pop();
          window.__hypervisorConfirm('Mark ' + shortName + ' as done?', {
            confirmLabel: 'done', cancelLabel: 'cancel'
          }).then(function (confirmed) {
            if (!confirmed) return;
            api.mark_done(filePath);
          });
        }
      });

      // Set Horizon submenu
      var horizonChildren = [];
      var horizons = ['Sprint', 'Sprint+1', 'Sprint+2', 'Sprint+3', 'Backlog'];
      for (var h = 0; h < horizons.length; h++) {
        (function (hz) {
          horizonChildren.push({
            label: hz,
            icon: hz === 'Sprint' ? 'zap' : hz === 'Backlog' ? 'archive' : 'clock',
            action: function () {
              api.update_metadata(filePath, 'Horizon', hz).then(function (result) {
                if (result && result.ok) {
                  if (window.__hypervisorToast) window.__hypervisorToast({ variant: 'success', message: 'horizon → ' + hz });
                } else {
                  if (window.__hypervisorToast) window.__hypervisorToast({ variant: 'error', message: (result && result.error) || 'update failed' });
                }
              });
            }
          });
        })(horizons[h]);
      }
      items.push({ label: 'Horizon', icon: 'layers', children: horizonChildren });
    }

    // Delete (bridge-only, .md files only)
    if (api && api.delete_document && filePath.endsWith('.md')) {
      if (!items.length || !items[items.length - 1].separator) items.push({ separator: true });
      items.push({
        label: 'Delete',
        icon: 'trash-2',
        action: function () {
          if (!window.__hypervisorConfirm) return;
          var shortName = filePath.replace(/\\/g, '/').split('/').pop();
          window.__hypervisorConfirm('Delete ' + shortName + '? This cannot be undone.', {
            confirmLabel: 'delete', cancelLabel: 'cancel'
          }).then(function (confirmed) {
            if (!confirmed) return;
            api.delete_document(filePath).then(function (result) {
              if (!result || !result.ok) {
                if (window.__hypervisorToast) window.__hypervisorToast({ variant: 'error', title: 'delete failed', message: (result && result.error) || 'unknown error' });
              }
            }).catch(function () {
              if (window.__hypervisorToast) window.__hypervisorToast({ variant: 'error', message: 'delete failed' });
            });
          });
        }
      });
    }

    return items;
  });
})();
