/* ===== Hypervisor: Context menu registrations =====
   Registers right-click actions for document links using the shared
   HvContextMenu primitive from Hyperkit. Bridge-dependent actions are
   only added when pywebview API is available. */

(function initContextMenuActions() {
  if (!window.HvContextMenu) return;

  function getApi() {
    return (window.pywebview && window.pywebview.api) ? window.pywebview.api : null;
  }

  // Workspace-level actions that are not tied to any specific document
  // (share key, end sprint). Appended to every menu and used as the body-level
  // fallback so they are reachable from anywhere via right-click. Returns []
  // outside the desktop app, where these bridge actions do not apply.
  function getGlobalItems(leadingSeparator) {
    var A = window.__hvActions;
    if (!A || !A.hasBridge || !A.hasBridge()) return [];
    var out = [];
    if (A.has && A.has('shareKey')) {
      out.push({ label: 'Share key', icon: 'key-round', action: function () { A.run('shareKey'); } });
    }
    if (A.has && A.has('endSprint')) {
      out.push({ label: 'End sprint', icon: 'skip-forward', action: function () { A.run('endSprint'); } });
    }
    if (out.length && leadingSeparator) out.unshift({ separator: true });
    return out;
  }

  // --- Work item metadata actions (shared by single-row and multi-select menus) ---
  var HORIZONS = ['Sprint', 'Sprint+1', 'Sprint+2', 'Sprint+3', 'Backlog'];
  // The to-do lists are work-item-only, so Status offers the work-item
  // lifecycle rather than the fuller document-status set.
  var WORK_STATUSES = ['Planned', 'In Progress', 'Complete'];

  function toast(opts) {
    if (window.__hypervisorToast) window.__hypervisorToast(opts);
  }

  function shortNameOf(path) {
    return path.replace(/\\/g, '/').split('/').pop().replace(/\.md$/, '');
  }

  // Summarize a bulk bridge result. Partial failures name the files that did
  // not change so the operator can retry them individually.
  function reportBulk(result, successLabel, countKey) {
    if (!result) { toast({ variant: 'error', message: 'update failed' }); return; }
    var results = result.results || [];
    var okCount = result[countKey] || 0;
    var failed = results.filter(function (r) { return !r.ok; });
    if (!results.length) {
      toast({ variant: 'error', message: result.error || 'update failed' });
    } else if (!failed.length) {
      toast({ variant: 'success', message: successLabel + (results.length > 1 ? ' (' + okCount + ')' : '') });
    } else {
      var detail = failed.map(function (r) { return shortNameOf(r.path) + ': ' + (r.error || 'failed'); }).join('; ');
      toast({
        variant: okCount ? 'warn' : 'error',
        message: okCount + ' of ' + results.length + ' updated - ' + detail,
        duration: 8000
      });
    }
  }

  function afterBulk() {
    if (window.__hvWorkItemSelect) window.__hvWorkItemSelect.clear();
    if (window.__router) window.__router.reload();
  }

  // Set one field across paths. Uses the bulk bridge (single rebuild, then a
  // list reload so rows regroup and re-badge). Falls back to the single-item
  // bridge when the running app predates the bulk method.
  function setField(api, paths, field, value, successLabel) {
    if (api.update_metadata_bulk) {
      return api.update_metadata_bulk(paths, field, value).then(function (result) {
        reportBulk(result, successLabel, 'updated');
        afterBulk();
      }).catch(function () { toast({ variant: 'error', message: 'update failed' }); });
    }
    if (paths.length !== 1) return;
    return api.update_metadata(paths[0], field, value).then(function (result) {
      if (result && result.ok) toast({ variant: 'success', message: successLabel });
      else toast({ variant: 'error', message: (result && result.error) || 'update failed' });
    });
  }

  function markDone(api, paths) {
    if (!window.__hypervisorConfirm) return;
    var single = paths.length === 1;
    var question = single ? 'Mark this work item as done?' : 'Mark ' + paths.length + ' work items as done?';
    window.__hypervisorConfirm(question, {
      subject: single ? shortNameOf(paths[0]) : undefined,
      confirmLabel: 'done', cancelLabel: 'cancel'
    }).then(function (confirmed) {
      if (!confirmed) return;
      if (paths.length === 1 && !api.mark_done_bulk) { api.mark_done(paths[0]); return; }
      if (!api.mark_done_bulk) return;
      api.mark_done_bulk(paths).then(function (result) {
        reportBulk(result, 'moved to done', 'moved');
        afterBulk();
      }).catch(function () { toast({ variant: 'error', message: 'mark done failed' }); });
    });
  }

  function setAssignee(api, paths) {
    if (!window.__hypervisorPrompt) return;
    var single = paths.length === 1;
    var label = single ? 'Assignee for this work item' : 'Assignee for ' + paths.length + ' work items';
    var known = api.list_assignees ? api.list_assignees().catch(function () { return []; }) : Promise.resolve([]);
    known.then(function (names) {
      return window.__hypervisorPrompt(label, {
        subject: single ? shortNameOf(paths[0]) : undefined,
        placeholder: 'pick a name or type a new one',
        hint: 'leave empty to clear',
        confirmLabel: 'set',
        cancelLabel: 'cancel',
        suggestions: names
      });
    }).then(function (value) {
      if (value === null || value === undefined) return;
      var name = String(value).trim();
      setField(api, paths, 'Assignee', name, name ? 'assignee -> ' + name : 'assignee cleared');
    });
  }

  // Horizon / Status / Assignee / Mark as done, targeting every path given.
  function workItemActions(api, paths) {
    var items = [];
    var canBulk = !!api.update_metadata_bulk;
    if (paths.length > 1 && !canBulk) return items;

    items.push({
      label: 'Horizon',
      icon: 'layers',
      children: HORIZONS.map(function (hz) {
        return {
          label: hz,
          icon: hz === 'Sprint' ? 'zap' : hz === 'Backlog' ? 'archive' : 'clock',
          action: function () { setField(api, paths, 'Horizon', hz, 'horizon -> ' + hz); }
        };
      })
    });

    items.push({
      label: 'Status',
      icon: 'circle-dot',
      children: WORK_STATUSES.map(function (st) {
        return {
          label: st,
          icon: st === 'Complete' ? 'check-circle' : st === 'In Progress' ? 'loader' : 'circle',
          action: function () {
            // Complete moves the file to done/ so status never disagrees with location.
            if (st === 'Complete') markDone(api, paths);
            else setField(api, paths, 'Status', st, 'status -> ' + st);
          }
        };
      })
    });

    items.push({ label: 'Assignee', icon: 'user', action: function () { setAssignee(api, paths); } });

    if (api.mark_done && (paths.length === 1 || api.mark_done_bulk)) {
      items.push({
        label: paths.length === 1 ? 'Mark as done' : 'Mark ' + paths.length + ' as done',
        icon: 'check-circle',
        action: function () { markDone(api, paths); }
      });
    }
    return items;
  }

  // --- Document list items (right-click on items in directory listings) ---
  // Most specific - registered first so it wins over generic a[href] or .markdown-body.
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
    // Work item rows carry their source path directly; prefer it over the
    // href-derived guess.
    var filePath = el.getAttribute('data-path') || (dirPrefix + slug + '.md');
    var shortName = slug.split('/').pop();
    var isTodo = filePath.indexOf('work/to-do/') !== -1;

    // Right-clicking a row inside an active multi-selection acts on the whole
    // selection; any other row acts on itself alone.
    var sel = window.__hvWorkItemSelect;
    if (api && isTodo && sel && sel.size() > 1 && sel.has(filePath)) {
      var selPaths = sel.paths();
      var bulkItems = [{ label: selPaths.length + ' selected', icon: 'list-checks', disabled: true }, { separator: true }];
      var actions = workItemActions(api, selPaths);
      for (var bi = 0; bi < actions.length; bi++) bulkItems.push(actions[bi]);
      bulkItems.push({ separator: true });
      bulkItems.push({ label: 'Clear selection', icon: 'x', action: function () { sel.clear(); } });
      return bulkItems;
    }
    if (sel && sel.size() && !sel.has(filePath)) sel.clear();

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

    // Work item actions (only for work/to-do items)
    if (api && isTodo) {
      var wiActions = workItemActions(api, [filePath]);
      if (wiActions.length) items.push({ separator: true });
      for (var wi = 0; wi < wiActions.length; wi++) items.push(wiActions[wi]);
    }

    // Delete
    if (api && api.delete_document) {
      if (!items[items.length - 1] || !items[items.length - 1].separator) items.push({ separator: true });
      items.push({
        label: 'Delete',
        icon: 'trash-2',
        action: function () {
          if (!window.__hypervisorConfirm) return;
          window.__hypervisorConfirm('Delete this document? This cannot be undone.', {
            subject: shortName,
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

    var gDoc = getGlobalItems(true);
    for (var gdi = 0; gdi < gDoc.length; gdi++) items.push(gDoc[gdi]);

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

    var gLink = getGlobalItems(true);
    for (var gli = 0; gli < gLink.length; gli++) items.push(gLink[gli]);

    return items;
  });

  // --- Current page context (right-click on content area) ---
  HvContextMenu.register('.markdown-body', function (el, e) {
    var sourcePathEl = document.getElementById('source-path');
    var filePath = sourcePathEl ? sourcePathEl.textContent.trim() : '';
    if (!filePath) return [];

    var api = getApi();
    var A = window.__hvActions;
    var items = [];

    // Edit (bridge-only, .md docs) - label reflects current editor mode.
    if (A && A.canEdit && A.canEdit()) {
      items.push({
        label: A.isEditing && A.isEditing() ? 'View rendered' : 'Edit',
        icon: A.isEditing && A.isEditing() ? 'eye' : 'pencil',
        action: function () { A.run('edit'); }
      });
    }

    // Export
    if (A && A.has && A.has('export')) {
      items.push({
        label: 'Export page',
        icon: 'package',
        action: function () { A.run('export'); }
      });
    }

    // Open in new window (bridge-only)
    if (api && api.open_in_new_window && A && A.has && A.has('openInNewWindow')) {
      items.push({
        label: 'Open in new window',
        icon: 'app-window',
        action: function () { A.run('openInNewWindow'); }
      });
    }

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
    if (A && A.canOpenInExplorer && A.canOpenInExplorer()) {
      items.push({
        label: 'Open in explorer',
        icon: 'folder-open',
        action: function () { A.run('openInExplorer'); }
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
          window.__hypervisorConfirm('Mark this work item as done?', {
            subject: shortName,
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
          window.__hypervisorConfirm('Delete this document? This cannot be undone.', {
            subject: shortName,
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

    // Workspace-level actions (share key, end sprint) - available everywhere.
    var g1 = getGlobalItems(true);
    for (var gi = 0; gi < g1.length; gi++) items.push(g1[gi]);

    return items;
  });

  // --- Body fallback (right-click anywhere the specific selectors miss) ---
  // Registered last so more specific menus win first. Surfaces the
  // workspace-level actions on index/home pages and empty page regions.
  HvContextMenu.register('body', function () {
    return getGlobalItems(false);
  });
})();
