/* === Hypervisor: Scratch Buffer / Daily Journal === */

  // Zero-friction daily scratch buffer with backtick hotkey, terminal journal
  // aesthetic, auto-save, and history browsing. Uses the PyWebView bridge
  // (open_scratch, save_scratch, list_scratch, delete_scratch) for persistence.

  (function initScratchBuffer() {
    // Bridge availability checked at call time, not init time.
    // The hotkey listener must always register.

    var panel = null;
    var isOpen = false;
    var currentDate = null;
    var currentContent = '';
    var historyMode = false;
    var saveTimer = null;
    var dirty = false;

    // --- DOM elements (created lazily) ---
    var textarea = null;
    var entriesContainer = null;
    var historyContainer = null;
    var dateFlag = null;
    var historyBtn = null;
    var inputArea = null;
    var bodyEl = null;
    var timeLabel = null;

    // --- Helpers ---
    function now() {
      var d = new Date();
      return String(d.getHours()).padStart(2, '0') + ':' + String(d.getMinutes()).padStart(2, '0');
    }

    function todayStr() {
      var d = new Date();
      return d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') + '-' + String(d.getDate()).padStart(2, '0');
    }

    function formatDateLabel(dateStr) {
      // "2026-06-29" -> "Jun 29, 2026"
      var parts = dateStr.split('-');
      var months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
      return months[parseInt(parts[1], 10) - 1] + ' ' + parseInt(parts[2], 10) + ', ' + parts[0];
    }

    // --- Parse scratch file into entries ---
    function parseEntries(content) {
      // Entries are ## HH:MM headings followed by content
      var lines = content.split('\n');
      var entries = [];
      var currentEntry = null;

      for (var i = 0; i < lines.length; i++) {
        var match = lines[i].match(/^## (\d{2}:\d{2})$/);
        if (match) {
          if (currentEntry) entries.push(currentEntry);
          currentEntry = { time: match[1], lines: [] };
        } else if (currentEntry) {
          currentEntry.lines.push(lines[i]);
        }
      }
      if (currentEntry) entries.push(currentEntry);
      return entries;
    }

    // --- Rebuild content string from header + entries + new input ---
    function buildContent(dateStr, entries) {
      var out = '# Scratch \u2014 ' + dateStr + '\n\n';
      for (var i = 0; i < entries.length; i++) {
        out += '## ' + entries[i].time + '\n';
        out += entries[i].lines.join('\n') + '\n\n';
      }
      return out;
    }

    // --- Render entries in the panel ---
    function renderEntries(content) {
      if (!entriesContainer) return;
      var entries = parseEntries(content);
      entriesContainer.innerHTML = '';

      if (entries.length === 0) {
        entriesContainer.innerHTML = '<div class="scratch-empty">No entries yet</div>';
        return;
      }

      // Render newest first
      for (var i = entries.length - 1; i >= 0; i--) {
        var entry = entries[i];
        var el = document.createElement('div');
        el.className = 'scratch-entry';
        var text = entry.lines.join('\n').trim();
        el.innerHTML = '<span class="scratch-entry-time">' + entry.time + '</span>'
          + '<span class="scratch-entry-text">' + escHtml(text) + '</span>';
        entriesContainer.appendChild(el);
      }
    }

    function escHtml(str) {
      return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    }

    // --- Save ---
    function save() {
      if (!dirty || !currentDate) return;
      dirty = false;

      // Rebuild content: keep existing entries, add new text if present
      var newText = textarea ? textarea.value.trim() : '';
      var content = currentContent;

      if (newText) {
        // Append new entry with current timestamp
        var timestamp = now();
        content += '## ' + timestamp + '\n' + newText + '\n\n';
        currentContent = content;
        textarea.value = '';
        renderEntries(content);
        updateTimeLabel();
      }

      window.pywebview.api.save_scratch(currentDate, currentContent);
    }

    function scheduleSave() {
      dirty = true;
      if (saveTimer) clearTimeout(saveTimer);
      saveTimer = setTimeout(save, 2000);
    }

    // --- Update the time label in input area ---
    function updateTimeLabel() {
      if (timeLabel) timeLabel.textContent = now();
    }

    // --- Build Panel DOM ---
    function createPanel() {
      panel = document.createElement('div');
      panel.className = 'scratch-panel';
      panel.setAttribute('aria-label', 'Scratch buffer');

      // Header
      var header = document.createElement('div');
      header.className = 'scratch-header';

      dateFlag = document.createElement('span');
      dateFlag.className = 'scratch-date-flag';
      header.appendChild(dateFlag);

      var actions = document.createElement('div');
      actions.className = 'scratch-actions';

      historyBtn = document.createElement('button');
      historyBtn.className = 'scratch-btn scratch-btn-history';
      historyBtn.textContent = 'History';
      historyBtn.addEventListener('click', toggleHistory);
      actions.appendChild(historyBtn);

      var newBtn = document.createElement('button');
      newBtn.className = 'scratch-btn scratch-btn-new';
      newBtn.textContent = '+ Entry';
      newBtn.addEventListener('click', newEntry);
      actions.appendChild(newBtn);

      var closeBtn = document.createElement('button');
      closeBtn.className = 'scratch-btn scratch-btn-close';
      closeBtn.textContent = '\u2715';
      closeBtn.addEventListener('click', closePanel);
      actions.appendChild(closeBtn);

      header.appendChild(actions);
      panel.appendChild(header);

      // Input area
      inputArea = document.createElement('div');
      inputArea.className = 'scratch-input-area';

      var inputRow = document.createElement('div');
      inputRow.className = 'scratch-input-row';

      timeLabel = document.createElement('span');
      timeLabel.className = 'scratch-input-time';
      inputRow.appendChild(timeLabel);

      var cursor = document.createElement('span');
      cursor.className = 'scratch-input-cursor';
      inputRow.appendChild(cursor);

      textarea = document.createElement('textarea');
      textarea.className = 'scratch-textarea';
      textarea.setAttribute('placeholder', 'Type a thought...');
      textarea.setAttribute('spellcheck', 'false');
      textarea.setAttribute('rows', '2');
      textarea.addEventListener('input', function() {
        dirty = true;
        autoResize();
      });
      textarea.addEventListener('keydown', function(e) {
        if (e.key === 'Enter' && !e.shiftKey) {
          e.preventDefault();
          save();
        }
        if (e.key === 'Escape') {
          closePanel();
        }
      });
      inputRow.appendChild(textarea);
      inputArea.appendChild(inputRow);
      panel.appendChild(inputArea);

      // Body (entries + history)
      bodyEl = document.createElement('div');
      bodyEl.className = 'scratch-body';

      entriesContainer = document.createElement('div');
      entriesContainer.className = 'scratch-entries';
      bodyEl.appendChild(entriesContainer);

      historyContainer = document.createElement('div');
      historyContainer.className = 'scratch-history';
      historyContainer.style.display = 'none';
      bodyEl.appendChild(historyContainer);

      panel.appendChild(bodyEl);
      document.body.appendChild(panel);
    }

    function autoResize() {
      if (!textarea) return;
      textarea.style.height = 'auto';
      textarea.style.height = Math.min(textarea.scrollHeight, 128) + 'px';
    }

    // --- Open / Close ---
    function openPanel() {
      if (!(window.pywebview && window.pywebview.api)) return;
      if (!panel) createPanel();
      isOpen = true;
      historyMode = false;
      historyBtn.classList.remove('active');
      panel.classList.add('open');

      // Load today's scratch
      window.pywebview.api.open_scratch().then(function(result) {
        if (!result.ok) return;
        currentDate = result.date;
        currentContent = result.content;
        dateFlag.textContent = formatDateLabel(currentDate);
        updateTimeLabel();
        renderEntries(currentContent);
        showJournal();
        textarea.focus();
      });
    }

    function closePanel() {
      if (!isOpen) return;
      // Save any pending input
      if (textarea && textarea.value.trim()) {
        save();
      }
      isOpen = false;
      panel.classList.remove('open');
    }

    function togglePanel() {
      if (isOpen) closePanel();
      else openPanel();
    }

    // --- New Entry ---
    function newEntry() {
      if (historyMode) {
        // Switch back to today
        historyMode = false;
        historyBtn.classList.remove('active');
        window.pywebview.api.open_scratch().then(function(result) {
          if (!result.ok) return;
          currentDate = result.date;
          currentContent = result.content;
          dateFlag.textContent = formatDateLabel(currentDate);
          renderEntries(currentContent);
          showJournal();
          textarea.focus();
        });
      } else {
        updateTimeLabel();
        textarea.focus();
      }
    }

    // --- History ---
    function toggleHistory() {
      historyMode = !historyMode;
      historyBtn.classList.toggle('active', historyMode);

      if (historyMode) {
        showHistory();
      } else {
        showJournal();
      }
    }

    function showJournal() {
      inputArea.style.display = '';
      entriesContainer.style.display = '';
      historyContainer.style.display = 'none';
    }

    function showHistory() {
      inputArea.style.display = 'none';
      entriesContainer.style.display = 'none';
      historyContainer.style.display = '';
      loadHistory();
    }

    function loadHistory() {
      window.pywebview.api.list_scratch().then(function(result) {
        if (!result.ok) return;
        historyContainer.innerHTML = '';

        if (result.files.length === 0) {
          historyContainer.innerHTML = '<div class="scratch-empty">No scratch files</div>';
          return;
        }

        for (var i = 0; i < result.files.length; i++) {
          (function(file) {
            var item = document.createElement('div');
            item.className = 'scratch-history-item' + (file.date === currentDate ? ' active' : '');

            var dateEl = document.createElement('span');
            dateEl.className = 'scratch-history-date';
            dateEl.textContent = formatDateLabel(file.date);
            item.appendChild(dateEl);

            var meta = document.createElement('span');
            meta.className = 'scratch-history-meta';

            if (file.entries > 0) {
              var badge = document.createElement('span');
              badge.className = 'scratch-history-badge';
              badge.textContent = file.entries + (file.entries === 1 ? ' entry' : ' entries');
              meta.appendChild(badge);
            }

            var delBtn = document.createElement('button');
            delBtn.className = 'scratch-history-delete';
            delBtn.textContent = '\u2715';
            delBtn.title = 'Delete this scratch file';
            delBtn.addEventListener('click', function(e) {
              e.stopPropagation();
              deleteScratch(file.date);
            });
            meta.appendChild(delBtn);

            item.appendChild(meta);

            item.addEventListener('click', function() {
              loadScratchDate(file.date);
            });

            historyContainer.appendChild(item);
          })(result.files[i]);
        }
      });
    }

    function loadScratchDate(date) {
      window.pywebview.api.open_scratch(date).then(function(result) {
        if (!result.ok) return;
        currentDate = result.date;
        currentContent = result.content;
        dateFlag.textContent = formatDateLabel(currentDate);
        renderEntries(currentContent);

        // Switch to journal view for this date
        historyMode = false;
        historyBtn.classList.remove('active');
        showJournal();
        updateTimeLabel();
        textarea.focus();
      });
    }

    function deleteScratch(date) {
      // Don't allow deleting today's active scratch
      if (date === todayStr()) return;

      window.pywebview.api.delete_scratch(date).then(function(result) {
        if (!result.ok) return;
        // Refresh history view
        loadHistory();
        // If we deleted the currently viewed date, switch back to today
        if (date === currentDate) {
          window.pywebview.api.open_scratch().then(function(r) {
            if (!r.ok) return;
            currentDate = r.date;
            currentContent = r.content;
            dateFlag.textContent = formatDateLabel(currentDate);
            renderEntries(currentContent);
          });
        }
      });
    }

    // --- Hotkey: backtick ---
    document.addEventListener('keydown', function(e) {
      // Don't trigger if typing in an input/textarea/contenteditable (unless it's our own textarea)
      var tag = (e.target.tagName || '').toLowerCase();
      var isInput = tag === 'input' || tag === 'textarea' || e.target.isContentEditable;

      if (e.key === '`' && !e.ctrlKey && !e.altKey && !e.metaKey) {
        // If panel is open and user is in our textarea, close it
        if (isOpen && e.target === textarea) {
          e.preventDefault();
          closePanel();
          return;
        }
        // If user is in another input, don't intercept
        if (isInput && e.target !== textarea) return;

        e.preventDefault();
        togglePanel();
      }
      // Esc closes the panel
      if (e.key === 'Escape' && isOpen) {
        closePanel();
      }
    });

  })();
