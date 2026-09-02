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
      // "2026-06-29" -> "Jun 29, 2026". Falls back to the raw string for any
      // non-date input so a stray value never renders as "undefined NaN".
      var parts = (dateStr || '').split('-');
      if (parts.length !== 3) return String(dateStr || '');
      var monthIdx = parseInt(parts[1], 10) - 1;
      var day = parseInt(parts[2], 10);
      var months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
      if (isNaN(monthIdx) || isNaN(day) || monthIdx < 0 || monthIdx > 11) {
        return String(dateStr);
      }
      return months[monthIdx] + ' ' + day + ', ' + parts[0];
    }

    // --- Parse scratch file into entries ---
    function parseEntries(content) {
      // Entries are `## HH:MM` headings (optionally suffixed with a ` (*)`
      // moved-marker) followed by content. The marker records that a note was
      // dragged out of chronological order; it is preserved across load/save.
      var lines = content.split('\n');
      var entries = [];
      var currentEntry = null;

      for (var i = 0; i < lines.length; i++) {
        var match = lines[i].match(/^## (\d{2}:\d{2})( \(\*\))?$/);
        if (match) {
          if (currentEntry) entries.push(currentEntry);
          currentEntry = { time: match[1], moved: !!match[2], lines: [] };
        } else if (currentEntry) {
          currentEntry.lines.push(lines[i]);
        }
      }
      if (currentEntry) entries.push(currentEntry);
      return entries;
    }

    // --- Rebuild content string from header + entries ---
    // Entries are written in array order (newest-first is the stored order),
    // preserving each entry's moved-marker so drag state survives a reload.
    function buildContent(dateStr, entries) {
      var out = '# Scratch \u2014 ' + dateStr + '\n\n';
      for (var i = 0; i < entries.length; i++) {
        var marker = entries[i].moved ? ' (*)' : '';
        out += '## ' + entries[i].time + marker + '\n';
        out += entries[i].lines.join('\n') + '\n\n';
      }
      return out;
    }

    // --- Recompute moved-markers after a reorder ---
    // Newest-first means timestamps should read in descending order top to
    // bottom. Any entry whose position differs from where a pure descending
    // sort would place it is flagged moved. Ties (same HH:MM) are treated as
    // interchangeable so a same-minute reorder never spuriously marks a note.
    function recomputeMoved(entries) {
      var sorted = entries.slice().sort(function(first, second) {
        return second.time.localeCompare(first.time);  // descending
      });
      for (var i = 0; i < entries.length; i++) {
        // An entry is "in place" if the entry occupying its slot in the sorted
        // order shares its timestamp — that tolerates same-minute ties.
        entries[i].moved = entries[i].time !== sorted[i].time;
      }
      return entries;
    }

    // --- Render entries as sticky-note cards ---
    // Cards go into two explicit column stacks. Array order is column-major:
    // indices 0..k fill column 1 top-to-bottom, k+1..n fill column 2. That
    // keeps visual position and array index in a fixed, deterministic
    // correspondence — CSS multi-column rebalanced the split on every change,
    // which made drop targeting unpredictable.
    //
    // `highlight` (optional) applies a one-shot animation class to a single
    // card after render: { index, kind } where kind is 'enter' | 'pulse'.
    function renderEntries(content, highlight) {
      if (!entriesContainer) return;
      var entries = parseEntries(content);
      entriesContainer.innerHTML = '';

      if (entries.length === 0) {
        entriesContainer.innerHTML = '<div class="scratch-empty">No entries yet</div>';
        return;
      }

      var colA = document.createElement('div');
      colA.className = 'scratch-col';
      colA.setAttribute('data-col', '0');
      var colB = document.createElement('div');
      colB.className = 'scratch-col';
      colB.setAttribute('data-col', '1');
      entriesContainer.appendChild(colA);
      entriesContainer.appendChild(colB);

      // Build every card into column 1 first so heights can be measured at the
      // real column width, then move the tail into column 2 at the balance
      // point. Column 1 is already 50% of the container, so widths are correct.
      var cards = [];
      for (var i = 0; i < entries.length; i++) {
        var card = buildCard(entries[i], i);
        colA.appendChild(card);
        cards.push(card);
      }
      squareUpCards();

      var splitAt = findBalancePoint(cards);
      for (var j = splitAt; j < cards.length; j++) {
        colB.appendChild(cards[j]);
      }

      if (highlight) applyHighlight(highlight);
    }

    // Choose the column-major split that most evenly divides total card height.
    // Walks the running total and stops once it would pass the halfway mark,
    // picking whichever side of that boundary leaves the smaller imbalance.
    function findBalancePoint(cards) {
      if (cards.length < 2) return cards.length;
      var heights = [];
      var total = 0;
      for (var i = 0; i < cards.length; i++) {
        var height = cards[i].offsetHeight;
        heights.push(height);
        total += height;
      }
      var half = total / 2;
      var running = 0;
      for (var k = 0; k < heights.length; k++) {
        var next = running + heights[k];
        if (next >= half) {
          // Compare imbalance with this card in column 1 vs. in column 2.
          var withIt = Math.abs((total - next) - next);
          var withoutIt = Math.abs((total - running) - running);
          var splitAt = withIt <= withoutIt ? k + 1 : k;
          // Never leave a column empty when there are 2+ cards.
          if (splitAt < 1) splitAt = 1;
          if (splitAt > cards.length - 1) splitAt = cards.length - 1;
          return splitAt;
        }
        running = next;
      }
      return cards.length - 1;
    }

    // Apply a one-shot animation class to the card at the given index, then
    // strip it on animationend so it can re-fire on a later render.
    function applyHighlight(highlight) {
      var selector = '.scratch-card[data-index="' + highlight.index + '"]';
      var card = entriesContainer.querySelector(selector);
      if (!card) return;
      var cls = highlight.kind === 'pulse' ? 'scratch-card-pulse' : 'scratch-card-entering';
      card.classList.add(cls);
      card.addEventListener('animationend', function handler() {
        card.classList.remove(cls);
        card.removeEventListener('animationend', handler);
      });
    }

    // Give each card a square minimum: min-height = its own rendered width.
    // Short notes read as squares; long notes exceed the minimum and grow.
    function squareUpCards() {
      if (!entriesContainer) return;
      var cards = entriesContainer.querySelectorAll('.scratch-card');
      for (var i = 0; i < cards.length; i++) {
        var card = cards[i];
        // Clear any prior floor before measuring so width isn't affected by it.
        card.style.minHeight = '';
        // clientWidth is the layout width — unaffected by the entrance scale()
        // transform, unlike getBoundingClientRect().
        var width = card.clientWidth;
        if (width > 0) card.style.minHeight = width + 'px';
      }
    }

    // --- Build a single sticky-note card ---
    function buildCard(entry, index) {
      var card = document.createElement('div');
      // Color cycles accent -> warm -> cool by position (comp is never used).
      var colorClass = 'scratch-card-c' + ((index % 3) + 1);
      card.className = 'scratch-card ' + colorClass;
      card.setAttribute('draggable', 'true');
      card.setAttribute('data-index', String(index));
      card.setAttribute('role', 'listitem');

      // --- Header row: drag handle + timestamp + actions ---
      var head = document.createElement('div');
      head.className = 'scratch-card-head';

      var handle = document.createElement('span');
      handle.className = 'scratch-card-handle';
      handle.textContent = '\u2237';  // grip glyph
      handle.setAttribute('aria-hidden', 'true');
      head.appendChild(handle);

      var time = document.createElement('span');
      time.className = 'scratch-card-time';
      time.textContent = entry.time;
      head.appendChild(time);

      // Moved marker is its own element so it can carry the alert color
      // independently of the timestamp's cycle color.
      if (entry.moved) {
        var marker = document.createElement('span');
        marker.className = 'scratch-card-moved';
        marker.textContent = '(*)';
        marker.title = 'Moved out of chronological order';
        head.appendChild(marker);
      }

      var actions = document.createElement('div');
      actions.className = 'scratch-card-actions';

      var editBtn = document.createElement('button');
      editBtn.className = 'scratch-card-btn scratch-card-edit';
      editBtn.textContent = 'edit';
      editBtn.setAttribute('aria-label', 'Edit note from ' + entry.time);
      editBtn.addEventListener('click', function(clickEvent) {
        clickEvent.stopPropagation();
        beginEdit(card, index);
      });
      actions.appendChild(editBtn);

      var delBtn = document.createElement('button');
      delBtn.className = 'scratch-card-btn scratch-card-delete';
      delBtn.textContent = '\u2715';  // multiplication X
      delBtn.setAttribute('aria-label', 'Delete note from ' + entry.time);
      delBtn.addEventListener('click', function(clickEvent) {
        clickEvent.stopPropagation();
        deleteEntry(index);
      });
      actions.appendChild(delBtn);

      head.appendChild(actions);
      card.appendChild(head);

      // --- Body ---
      var body = document.createElement('div');
      body.className = 'scratch-card-body';
      body.textContent = entry.lines.join('\n').trim();
      card.appendChild(body);

      // --- Drag wiring ---
      attachDragHandlers(card);

      return card;
    }

    // --- Delete a note immediately (no undo) ---
    // Plays the exit animation on the card, then splices + persists. A
    // duration-matched timeout backstops animationend so the delete still
    // completes when motion is suppressed (reduced-motion collapses the
    // animation, and animationend may not fire reliably in that case).
    function deleteEntry(index) {
      var entries = parseEntries(currentContent);
      if (index < 0 || index >= entries.length) return;
      var removedTime = entries[index].time;

      var card = entriesContainer
        ? entriesContainer.querySelector('.scratch-card[data-index="' + index + '"]')
        : null;

      function finalize() {
        var fresh = parseEntries(currentContent);
        if (index < 0 || index >= fresh.length) { renderEntries(currentContent); return; }
        fresh.splice(index, 1);
        persist(fresh);
        announce('Note from ' + removedTime + ' deleted');
      }

      if (!card) { finalize(); return; }

      var done = false;
      function once() { if (done) return; done = true; finalize(); }
      card.classList.add('scratch-card-leaving');
      card.addEventListener('animationend', once);
      // ~200ms exit (--motion-base); pad slightly for the timeout backstop.
      setTimeout(once, 260);
    }

    // --- Inline multi-line edit ---
    function beginEdit(card, index) {
      var body = card.querySelector('.scratch-card-body');
      if (!body || card.querySelector('.scratch-card-editor')) return;

      var entries = parseEntries(currentContent);
      if (index < 0 || index >= entries.length) return;

      var editor = document.createElement('textarea');
      editor.className = 'scratch-card-editor';
      editor.value = entries[index].lines.join('\n').trim();
      editor.setAttribute('spellcheck', 'false');
      editor.setAttribute('aria-label', 'Editing note from ' + entries[index].time);

      // Card is draggable, which would otherwise hijack text selection in the
      // textarea. Suspend dragging while editing.
      card.setAttribute('draggable', 'false');

      var committed = false;
      function commit() {
        if (committed) return;
        committed = true;
        var freshEntries = parseEntries(currentContent);
        if (index < 0 || index >= freshEntries.length) { renderEntries(currentContent); return; }
        var text = editor.value.trim();
        if (text) {
          freshEntries[index].lines = editor.value.split('\n');
          persist(freshEntries);
        } else {
          // Emptying a note deletes it — consistent with "no empty cards".
          freshEntries.splice(index, 1);
          persist(freshEntries);
        }
      }
      function cancel() {
        if (committed) return;
        committed = true;
        renderEntries(currentContent);
      }

      editor.addEventListener('keydown', function(keyEvent) {
        // Enter commits; Shift+Enter inserts a newline (multi-line support).
        if (keyEvent.key === 'Enter' && !keyEvent.shiftKey) {
          keyEvent.preventDefault();
          commit();
        } else if (keyEvent.key === 'Escape') {
          keyEvent.preventDefault();
          cancel();
        }
      });
      editor.addEventListener('blur', commit);

      body.replaceWith(editor);
      editor.focus();
      editor.setSelectionRange(editor.value.length, editor.value.length);
      autoResizeEl(editor);
      editor.addEventListener('input', function() { autoResizeEl(editor); });
    }

    // --- Drag-to-reorder (native HTML5 DnD) ---
    // A skeleton placeholder card marks the exact drop slot. On dragover we
    // decide before/after the hovered card from the cursor's vertical position
    // within it, and move the placeholder there — so the user drops *into a
    // gap*, not on top of a card.
    var dragSrcIndex = null;
    var placeholder = null;

    function getPlaceholder() {
      if (!placeholder) {
        placeholder = document.createElement('div');
        placeholder.className = 'scratch-card-placeholder';
        placeholder.setAttribute('aria-hidden', 'true');
      }
      return placeholder;
    }

    function removePlaceholder() {
      if (placeholder && placeholder.parentNode) {
        placeholder.parentNode.removeChild(placeholder);
      }
    }

    function attachDragHandlers(card) {
      card.addEventListener('dragstart', function(dragEvent) {
        dragSrcIndex = parseInt(card.getAttribute('data-index'), 10);
        card.classList.add('scratch-card-dragging');
        if (dragEvent.dataTransfer) {
          dragEvent.dataTransfer.effectAllowed = 'move';
          // Firefox requires data to be set for the drag to initiate.
          dragEvent.dataTransfer.setData('text/plain', String(dragSrcIndex));
        }
      });
      card.addEventListener('dragend', function() {
        card.classList.remove('scratch-card-dragging');
        removePlaceholder();
        dragSrcIndex = null;
      });
    }

    // Container-level dragover/drop — attached once. Doing this on the
    // container (not each card) means drop still fires when the cursor is
    // released over the placeholder gap or empty space, not just over a card.
    function attachContainerDragHandlers(container) {
      container.addEventListener('dragover', function(dragEvent) {
        if (dragSrcIndex === null) return;
        dragEvent.preventDefault();
        if (dragEvent.dataTransfer) dragEvent.dataTransfer.dropEffect = 'move';

        // With explicit column stacks, targeting decomposes cleanly: X picks
        // the column, Y picks the slot within it. Each column is a simple
        // top-to-bottom list, so DOM order matches what the user sees.
        var cols = container.querySelectorAll('.scratch-col');
        if (cols.length === 0) return;

        var targetCol = null;
        var bestDist = Infinity;
        for (var c = 0; c < cols.length; c++) {
          var colRect = cols[c].getBoundingClientRect();
          var colCenterX = colRect.left + colRect.width / 2;
          var dist = Math.abs(dragEvent.clientX - colCenterX);
          if (dist < bestDist) { bestDist = dist; targetCol = cols[c]; }
        }
        if (!targetCol) return;

        var ph = getPlaceholder();
        var cards = targetCol.querySelectorAll('.scratch-card');
        for (var i = 0; i < cards.length; i++) {
          // The dragged card is still in the DOM at reduced opacity; it should
          // not act as a placement anchor.
          if (cards[i].classList.contains('scratch-card-dragging')) continue;
          var rect = cards[i].getBoundingClientRect();
          if (dragEvent.clientY < rect.top + rect.height / 2) {
            if (cards[i].previousSibling !== ph) targetCol.insertBefore(ph, cards[i]);
            return;
          }
        }
        // Past every card in this column — land at the bottom of it.
        if (targetCol.lastChild !== ph) targetCol.appendChild(ph);
      });

      container.addEventListener('drop', function(dropEvent) {
        if (dragSrcIndex === null) { removePlaceholder(); return; }
        dropEvent.preventDefault();

        var targetIndex = computeDropIndex();
        removePlaceholder();

        var entries = parseEntries(currentContent);
        if (dragSrcIndex < 0 || dragSrcIndex >= entries.length) { dragSrcIndex = null; return; }
        if (targetIndex === -1) { dragSrcIndex = null; return; }

        var relocated = entries.splice(dragSrcIndex, 1)[0];
        // Splicing out the source shifts every later index down by one.
        var insertAt = targetIndex > dragSrcIndex ? targetIndex - 1 : targetIndex;
        if (insertAt === dragSrcIndex) { dragSrcIndex = null; renderEntries(currentContent); return; }
        entries.splice(insertAt, 0, relocated);
        recomputeMoved(entries);
        persist(entries, { index: insertAt, kind: 'pulse' });
        announce('Note moved to position ' + (insertAt + 1));
        dragSrcIndex = null;
      });
    }

    // Walk the columns in column-major order (all of column 1, then column 2),
    // counting real cards. The placeholder's rank in that walk is the intended
    // insertion index in the entry array — the same order renderEntries uses to
    // lay cards out, so visual position and array index agree exactly.
    function computeDropIndex() {
      if (!entriesContainer || !placeholder || !placeholder.parentNode) return -1;
      var cols = entriesContainer.querySelectorAll('.scratch-col');
      var index = 0;
      for (var c = 0; c < cols.length; c++) {
        var nodes = cols[c].childNodes;
        for (var i = 0; i < nodes.length; i++) {
          var node = nodes[i];
          if (node === placeholder) return index;
          if (node.classList && node.classList.contains('scratch-card')) index++;
        }
      }
      return index;
    }

    // --- Screen-reader live announcements ---
    var liveRegion = null;
    function announce(message) {
      if (!liveRegion) return;
      liveRegion.textContent = '';
      // Force a re-announcement even for identical consecutive messages.
      setTimeout(function() { liveRegion.textContent = message; }, 30);
    }

    // --- Save ---
    function save() {
      if (!dirty || !currentDate) return;
      dirty = false;

      var newText = textarea ? textarea.value.trim() : '';

      if (newText) {
        // Prepend the new entry so newest sits at the top of both file and
        // display. A fresh entry is chronological by definition, so it carries
        // no moved-marker.
        var entries = parseEntries(currentContent);
        entries.unshift({ time: now(), moved: false, lines: newText.split('\n') });
        currentContent = buildContent(currentDate, entries);
        textarea.value = '';
        autoResize();
        // Newest note sits at index 0 — animate its entrance.
        renderEntries(currentContent, { index: 0, kind: 'enter' });
        updateTimeLabel();
      }

      window.pywebview.api.save_scratch(currentDate, currentContent);
    }

    // --- Persist the current entry array without adding a new entry ---
    // Shared by delete, reorder, and inline-edit, which mutate `currentContent`
    // directly then call this to write through to disk and re-render.
    // `highlight` (optional) is forwarded to renderEntries for a one-shot
    // animation (e.g. the drop pulse).
    function persist(entries, highlight) {
      currentContent = buildContent(currentDate, entries);
      renderEntries(currentContent, highlight);
      if (window.pywebview && window.pywebview.api) {
        window.pywebview.api.save_scratch(currentDate, currentContent);
      }
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
      dateFlag.className = 'scratch-date-flag status-chip status-chip-outlined-accent';
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
      entriesContainer.setAttribute('role', 'list');
      entriesContainer.setAttribute('aria-label', 'Scratch notes');
      attachContainerDragHandlers(entriesContainer);
      bodyEl.appendChild(entriesContainer);

      historyContainer = document.createElement('div');
      historyContainer.className = 'scratch-history';
      historyContainer.style.display = 'none';
      bodyEl.appendChild(historyContainer);

      panel.appendChild(bodyEl);

      // Visually-hidden live region for screen-reader announcements of
      // delete/reorder actions that otherwise have no textual feedback.
      liveRegion = document.createElement('div');
      liveRegion.className = 'scratch-sr-live';
      liveRegion.setAttribute('aria-live', 'polite');
      liveRegion.setAttribute('aria-atomic', 'true');
      panel.appendChild(liveRegion);

      document.body.appendChild(panel);
    }

    function autoResize() {
      autoResizeEl(textarea);
    }

    // Grow a textarea to fit its content, capped at 128px (then it scrolls).
    function autoResizeEl(el) {
      if (!el) return;
      el.style.height = 'auto';
      el.style.height = Math.min(el.scrollHeight, 128) + 'px';
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
