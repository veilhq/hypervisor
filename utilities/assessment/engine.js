// ===================================================================
// Assessment Engine — Generic quiz/assessment module
// ===================================================================
// Data-driven quiz engine with dynamic dataset loading.
// Reads available datasets from window.QUIZ_DATASETS (set by datasets.js).
// Loads dataset files (manifest, questions, study-guide) via dynamic
// <script> tags, then initializes the quiz UI.
//
// Supports switching between datasets at runtime — selecting a new
// dataset clears the current quiz state and loads the new data.
//
// Dataset files set these globals (cleared before each load):
//   window.QUIZ_MANIFEST    — config object
//   window.QUIZ_QUESTIONS   — question bank array
//   window.QUIZ_STUDY_GUIDE — study guide array (optional)
// ===================================================================

(function() {
  "use strict";

  var DATASETS = window.QUIZ_DATASETS || [];

  // ===== Dataset loading =====
  var loadedScripts = [];  // track injected <script> elements for cleanup

  function clearDataGlobals() {
    window.QUIZ_MANIFEST = null;
    window.QUIZ_QUESTIONS = null;
    window.QUIZ_STUDY_GUIDE = null;
  }

  function removeLoadedScripts() {
    loadedScripts.forEach(function(el) {
      if (el.parentNode) el.parentNode.removeChild(el);
    });
    loadedScripts = [];
  }

  // Load a JS file via <script> tag, returns a promise-like callback chain
  function loadScript(src, callback) {
    var script = document.createElement("script");
    script.src = src;
    script.onload = function() { callback(null); };
    script.onerror = function() { callback(new Error("Failed to load: " + src)); };
    loadedScripts.push(script);
    document.body.appendChild(script);
  }

  // Load multiple scripts in sequence (order matters: manifest → questions → guide)
  function loadScriptsInOrder(srcs, done) {
    var i = 0;
    function next(err) {
      if (err) { done(err); return; }
      if (i >= srcs.length) { done(null); return; }
      loadScript(srcs[i++], next);
    }
    next(null);
  }

  function loadDataset(datasetId, callback) {
    var dataset = null;
    for (var i = 0; i < DATASETS.length; i++) {
      if (DATASETS[i].id === datasetId) { dataset = DATASETS[i]; break; }
    }
    if (!dataset) { callback(new Error("Dataset not found: " + datasetId)); return; }

    // Clean up previous dataset
    removeLoadedScripts();
    clearDataGlobals();

    // Build script paths: datasets/{id}/{file}
    var srcs = dataset.files.map(function(f) {
      return "datasets/" + dataset.id + "/" + f;
    });

    loadScriptsInOrder(srcs, function(err) {
      if (err) { callback(err); return; }
      callback(null, dataset);
    });
  }

  // ===== Dataset selector =====
  var datasetSelect = document.getElementById("quiz-dataset-select");
  var datasetTitleEl = document.getElementById("quiz-dataset-title");

  function buildDatasetSelector() {
    if (!datasetSelect || !DATASETS.length) return;
    datasetSelect.innerHTML = "";
    DATASETS.forEach(function(ds) {
      var opt = document.createElement("option");
      opt.value = ds.id;
      opt.textContent = ds.title;
      datasetSelect.appendChild(opt);
    });
  }
  buildDatasetSelector();

  function updateDatasetTitle(title) {
    if (datasetTitleEl) {
      datasetTitleEl.textContent = title ? "(" + title + ")" : "";
    }
  }

  // ===== Engine state (module-level so it persists across dataset switches) =====
  var MANIFEST, QUESTIONS, GUIDE;
  var DOMAINS, DOMAIN_WEIGHTS, PASS_THRESHOLD, PASS_LABEL, FAIL_LABEL;
  var SCORE_NOTE, FULL_EXAM_COUNT, QUESTION_COUNTS, HAS_WEIGHTS;

  var state = {
    questions: [],
    current: 0,
    score: 0,
    answered: 0,
    answers: [],
    sessionCorrect: 0,
    sessionIncorrect: 0,
    sessionAttempted: 0
  };

  // ===== DOM refs =====
  var countSelect = document.getElementById("quiz-count");
  var weightedSetting = document.getElementById("quiz-weighted");

  var els = {
    card:            document.getElementById("quiz-card"),
    summary:         document.getElementById("quiz-summary"),
    domain:          document.getElementById("quiz-domain"),
    typeTag:         document.getElementById("quiz-type-tag"),
    multiTag:        document.getElementById("quiz-multi-tag"),
    pickCount:       document.getElementById("quiz-pick-count"),
    question:        document.getElementById("quiz-question"),
    options:         document.getElementById("quiz-options"),
    feedback:        document.getElementById("quiz-feedback"),
    check:           document.getElementById("quiz-check"),
    next:            document.getElementById("quiz-next"),
    scoreDisplay:    document.getElementById("quiz-score-display"),
    progress:        document.getElementById("quiz-progress"),
    pct:             document.getElementById("quiz-pct"),
    progressFill:    document.getElementById("quiz-progress-fill"),
    countSelect:     countSelect,
    shuffleCheck:    document.getElementById("quiz-shuffle"),
    weightedCheck:   weightedSetting,
    domainFilters:   document.getElementById("quiz-domain-filters"),
    newBtn:          document.getElementById("quiz-new"),
    restartBtn:      document.getElementById("quiz-restart"),
    reviewBtn:       document.getElementById("quiz-review"),
    summaryScore:    document.getElementById("quiz-summary-score"),
    summaryBreakdown:document.getElementById("quiz-summary-breakdown"),
    statAttempted:   document.getElementById("quiz-stat-attempted"),
    statCorrect:     document.getElementById("quiz-stat-correct"),
    statIncorrect:   document.getElementById("quiz-stat-incorrect"),
    statAccuracy:    document.getElementById("quiz-stat-accuracy")
  };

  // ===== Helpers =====
  function shuffle(arr) {
    for (var i = arr.length - 1; i > 0; i--) {
      var j = Math.floor(Math.random() * (i + 1));
      var tmp = arr[i]; arr[i] = arr[j]; arr[j] = tmp;
    }
    return arr;
  }

  function escHtml(s) {
    return s.replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;");
  }

  function isMulti(q) { return Array.isArray(q.a); }

  // ===== Read manifest into engine vars =====
  function applyManifest() {
    MANIFEST = window.QUIZ_MANIFEST || {};
    QUESTIONS = window.QUIZ_QUESTIONS || [];
    GUIDE = window.QUIZ_STUDY_GUIDE || [];

    DOMAINS = MANIFEST.domains || {};
    DOMAIN_WEIGHTS = MANIFEST.weights || {};
    PASS_THRESHOLD = MANIFEST.passThreshold || 70;
    PASS_LABEL = MANIFEST.passLabel || "PASS";
    FAIL_LABEL = MANIFEST.failLabel || "FAIL";
    SCORE_NOTE = MANIFEST.scoreNote || "";
    FULL_EXAM_COUNT = MANIFEST.fullExamCount || null;
    QUESTION_COUNTS = MANIFEST.questionCounts || [10, 20, 35, 50];
    HAS_WEIGHTS = Object.keys(DOMAIN_WEIGHTS).length > 0;
  }

  // ===== Rebuild UI controls for current manifest =====
  function rebuildControls() {
    // Question count selector
    if (countSelect) {
      countSelect.innerHTML = "";
      QUESTION_COUNTS.forEach(function(n) {
        var opt = document.createElement("option");
        opt.value = n;
        opt.textContent = n;
        if (n === (QUESTION_COUNTS[1] || QUESTION_COUNTS[0])) opt.selected = true;
        countSelect.appendChild(opt);
      });
      if (FULL_EXAM_COUNT) {
        var opt = document.createElement("option");
        opt.value = FULL_EXAM_COUNT;
        opt.textContent = FULL_EXAM_COUNT + " (full exam)";
        countSelect.appendChild(opt);
      }
    }

    // Weighted checkbox visibility
    if (weightedSetting) {
      var settingRow = weightedSetting.closest(".quiz-setting");
      if (settingRow) settingRow.style.display = HAS_WEIGHTS ? "" : "none";
      if (HAS_WEIGHTS) weightedSetting.checked = true;
    }

    // Study guide tab visibility
    var guideTab = document.querySelector('.quiz-tab[data-tab="guide"]');
    if (guideTab) guideTab.style.display = GUIDE.length ? "" : "none";

    // Domain filters
    buildDomainFilters();

    // Reset guide so it re-renders with new data
    guideRendered = false;
    if (guideNav) guideNav.innerHTML = "";
    if (guideContent) guideContent.innerHTML = "";

    // Switch to quiz tab
    var quizTab = document.querySelector('.quiz-tab[data-tab="quiz"]');
    if (quizTab) quizTab.click();
  }

  // ===== Domain filter checkboxes =====
  function buildDomainFilters() {
    var html = "";
    for (var d in DOMAINS) {
      html += '<label class="quiz-domain-label"><input type="checkbox" class="quiz-domain-cb" value="' + d + '" checked> ' + escHtml(DOMAINS[d]) + '</label>';
    }
    if (els.domainFilters) els.domainFilters.innerHTML = html;
  }

  function getSelectedDomains() {
    if (!els.domainFilters) return Object.keys(DOMAINS).map(Number);
    var cbs = els.domainFilters.querySelectorAll(".quiz-domain-cb:checked");
    var domains = [];
    cbs.forEach(function(cb) { domains.push(parseInt(cb.value)); });
    return domains;
  }

  // ===== Domain-weighted selection =====
  function selectWeighted(pool, count, domains) {
    var totalWeight = 0;
    domains.forEach(function(d) { totalWeight += (DOMAIN_WEIGHTS[d] || 0); });
    if (totalWeight === 0) { shuffle(pool); return pool.slice(0, count); }

    var targets = {};
    var allocated = 0;
    domains.forEach(function(d, i) {
      var w = (DOMAIN_WEIGHTS[d] || 0) / totalWeight;
      var n = (i === domains.length - 1) ? (count - allocated) : Math.round(count * w);
      targets[d] = n;
      allocated += n;
    });

    var byDomain = {};
    domains.forEach(function(d) { byDomain[d] = []; });
    pool.forEach(function(q) {
      if (byDomain[q.d]) byDomain[q.d].push(q);
    });

    var selected = [];
    domains.forEach(function(d) {
      shuffle(byDomain[d]);
      var take = Math.min(targets[d], byDomain[d].length);
      selected = selected.concat(byDomain[d].slice(0, take));
      byDomain[d] = byDomain[d].slice(take);
    });

    if (selected.length < count) {
      var extras = [];
      domains.forEach(function(d) { extras = extras.concat(byDomain[d]); });
      shuffle(extras);
      selected = selected.concat(extras.slice(0, count - selected.length));
    }

    shuffle(selected);
    return selected;
  }

  // ===== Quiz init =====
  function initQuiz(questionPool) {
    var count = els.countSelect ? parseInt(els.countSelect.value) : 20;
    var domains = getSelectedDomains();
    if (!domains.length) domains = Object.keys(DOMAINS).map(Number);

    var pool = (questionPool || QUESTIONS).filter(function(q) {
      return domains.indexOf(q.d) !== -1;
    });

    var useWeighted = HAS_WEIGHTS && els.weightedCheck && els.weightedCheck.checked && !questionPool;

    if (useWeighted && domains.length > 1) {
      state.questions = selectWeighted(pool, Math.min(count, pool.length), domains);
    } else {
      shuffle(pool);
      state.questions = pool.slice(0, Math.min(count, pool.length));
    }

    state.current = 0;
    state.score = 0;
    state.answered = 0;
    state.answers = [];

    if (els.summary) els.summary.style.display = "none";
    if (els.card) els.card.style.display = "";
    renderQuestion();
  }

  // ===== Render =====
  function renderQuestion() {
    var q = state.questions[state.current];
    if (!q) return;

    var multi = isMulti(q);

    if (els.domain) els.domain.textContent = DOMAINS[q.d] || "Domain " + q.d;

    if (els.typeTag) {
      if (q.t) {
        els.typeTag.textContent = q.t;
        els.typeTag.className = "quiz-type-tag quiz-type-" + q.t;
        els.typeTag.style.display = "";
      } else {
        els.typeTag.style.display = "none";
      }
    }

    if (els.multiTag) {
      if (multi) {
        els.multiTag.style.display = "";
        if (els.pickCount) els.pickCount.textContent = q.pick;
      } else {
        els.multiTag.style.display = "none";
      }
    }

    if (els.question) els.question.textContent = q.q;
    if (els.feedback) { els.feedback.textContent = ""; els.feedback.className = "quiz-feedback"; }
    if (els.check) { els.check.disabled = true; els.check.style.display = ""; }
    if (els.next) els.next.style.display = "none";

    var opts = q.o.map(function(text, idx) { return {text: text, origIdx: idx}; });
    if (els.shuffleCheck && els.shuffleCheck.checked) shuffle(opts);

    if (els.options) {
      els.options.innerHTML = opts.map(function(opt, i) {
        var inputType = multi ? "checkbox" : "radio";
        return '<button class="quiz-option" data-idx="' + opt.origIdx + '" role="' + inputType + '" aria-checked="false">' +
               '<span class="quiz-option-letter">' + String.fromCharCode(65 + i) + '</span>' +
               escHtml(opt.text) + '</button>';
      }).join("");

      var optBtns = els.options.querySelectorAll(".quiz-option");
      optBtns.forEach(function(btn) {
        btn.addEventListener("click", function() {
          if (multi) {
            btn.classList.toggle("selected");
            btn.setAttribute("aria-checked", btn.classList.contains("selected") ? "true" : "false");
            var selectedCount = els.options.querySelectorAll(".quiz-option.selected").length;
            if (els.check) els.check.disabled = selectedCount !== q.pick;
          } else {
            optBtns.forEach(function(b) {
              b.classList.remove("selected");
              b.setAttribute("aria-checked", "false");
            });
            btn.classList.add("selected");
            btn.setAttribute("aria-checked", "true");
            if (els.check) els.check.disabled = false;
          }
        });
      });
    }

    updateMeta();
  }

  function updateMeta() {
    if (els.scoreDisplay) els.scoreDisplay.textContent = state.score + " / " + state.answered;
    if (els.progress) els.progress.textContent = "Question " + (state.current + 1) + " of " + state.questions.length;
    var pct = state.questions.length ? Math.round(((state.current) / state.questions.length) * 100) : 0;
    if (els.pct) els.pct.textContent = pct + "%";
    if (els.progressFill) els.progressFill.style.width = pct + "%";
  }

  function updateSessionStats() {
    if (els.statAttempted) els.statAttempted.textContent = state.sessionAttempted;
    if (els.statCorrect) els.statCorrect.textContent = state.sessionCorrect;
    if (els.statIncorrect) els.statIncorrect.textContent = state.sessionIncorrect;
    var acc = state.sessionAttempted ? Math.round((state.sessionCorrect / state.sessionAttempted) * 100) : 0;
    if (els.statAccuracy) els.statAccuracy.textContent = state.sessionAttempted ? acc + "%" : "\u2014";
  }

  // ===== Check answer =====
  if (els.check) els.check.addEventListener("click", function() {
    var q = state.questions[state.current];
    var multi = isMulti(q);
    var optBtns = els.options.querySelectorAll(".quiz-option");
    var correct;

    if (multi) {
      var selectedIndices = [];
      els.options.querySelectorAll(".quiz-option.selected").forEach(function(btn) {
        selectedIndices.push(parseInt(btn.getAttribute("data-idx")));
      });
      selectedIndices.sort();
      var correctIndices = q.a.slice().sort();
      correct = selectedIndices.length === correctIndices.length &&
                selectedIndices.every(function(v, i) { return v === correctIndices[i]; });

      optBtns.forEach(function(btn) {
        var idx = parseInt(btn.getAttribute("data-idx"));
        btn.disabled = true;
        if (q.a.indexOf(idx) !== -1) btn.classList.add("correct");
        if (selectedIndices.indexOf(idx) !== -1 && q.a.indexOf(idx) === -1) btn.classList.add("incorrect");
      });

      state.answers.push({qIdx: state.current, selected: selectedIndices, correct: correct});
    } else {
      var selected = els.options.querySelector(".quiz-option.selected");
      if (!selected) return;
      var selIdx = parseInt(selected.getAttribute("data-idx"));
      correct = selIdx === q.a;

      optBtns.forEach(function(btn) {
        var idx = parseInt(btn.getAttribute("data-idx"));
        btn.disabled = true;
        if (idx === q.a) btn.classList.add("correct");
        if (idx === selIdx && !correct) btn.classList.add("incorrect");
      });

      state.answers.push({qIdx: state.current, selected: selIdx, correct: correct});
    }

    state.answered++;
    state.sessionAttempted++;
    if (correct) { state.score++; state.sessionCorrect++; }
    else { state.sessionIncorrect++; }

    if (els.feedback) {
      els.feedback.textContent = (correct ? "Correct. " : "Incorrect. ") + q.e;
      els.feedback.className = "quiz-feedback " + (correct ? "quiz-feedback-correct" : "quiz-feedback-incorrect");
    }

    if (els.check) els.check.style.display = "none";
    if (els.next) els.next.style.display = "";

    updateMeta();
    updateSessionStats();
  });

  // ===== Next question =====
  if (els.next) els.next.addEventListener("click", function() {
    state.current++;
    if (state.current >= state.questions.length) {
      showSummary();
    } else {
      renderQuestion();
    }
  });

  // ===== Summary =====
  function showSummary() {
    if (els.card) els.card.style.display = "none";
    if (els.summary) els.summary.style.display = "";

    var pct = state.answered ? Math.round((state.score / state.answered) * 100) : 0;
    var grade = pct >= PASS_THRESHOLD ? "pass" : "fail";
    var gradeLabel = grade === "pass" ? PASS_LABEL : FAIL_LABEL;
    var gradeClass = grade === "pass" ? "pw-str-strong" : "pw-str-weak";

    if (els.summaryScore) {
      els.summaryScore.innerHTML =
        '<span class="quiz-final-pct ' + gradeClass + '">' + pct + '%</span>' +
        '<span class="quiz-final-label">' + state.score + ' of ' + state.answered + ' correct \u2014 ' + escHtml(gradeLabel) + '</span>' +
        (SCORE_NOTE ? '<span class="quiz-final-note">' + escHtml(SCORE_NOTE) + '</span>' : '');
    }

    var domainStats = {};
    state.answers.forEach(function(ans) {
      var q = state.questions[ans.qIdx];
      if (!domainStats[q.d]) domainStats[q.d] = {correct: 0, total: 0};
      domainStats[q.d].total++;
      if (ans.correct) domainStats[q.d].correct++;
    });

    var breakdownHtml = '<div class="quiz-breakdown-title">Domain Breakdown</div>';
    for (var d in domainStats) {
      var ds = domainStats[d];
      var dp = Math.round((ds.correct / ds.total) * 100);
      breakdownHtml += '<div class="quiz-breakdown-row">' +
        '<span class="quiz-breakdown-domain">' + escHtml(DOMAINS[d] || "Domain " + d) + '</span>' +
        '<span class="quiz-breakdown-bar"><span class="quiz-breakdown-fill" style="width:' + dp + '%"></span></span>' +
        '<span class="quiz-breakdown-pct ' + (dp >= PASS_THRESHOLD ? "pw-str-strong" : "pw-str-weak") + '">' + dp + '%</span>' +
        '</div>';
    }

    var hasTypes = state.answers.some(function(ans) { return state.questions[ans.qIdx].t; });
    if (hasTypes) {
      var typeStats = {};
      state.answers.forEach(function(ans) {
        var q = state.questions[ans.qIdx];
        var t = q.t || "general";
        if (!typeStats[t]) typeStats[t] = {correct: 0, total: 0};
        typeStats[t].total++;
        if (ans.correct) typeStats[t].correct++;
      });
      breakdownHtml += '<div class="quiz-breakdown-title" style="margin-top:1rem">Question Type Breakdown</div>';
      for (var t in typeStats) {
        if (typeStats[t].total > 0) {
          var tp = Math.round((typeStats[t].correct / typeStats[t].total) * 100);
          var typeLabel = t.charAt(0).toUpperCase() + t.slice(1);
          breakdownHtml += '<div class="quiz-breakdown-row">' +
            '<span class="quiz-breakdown-domain">' + escHtml(typeLabel) + '</span>' +
            '<span class="quiz-breakdown-bar"><span class="quiz-breakdown-fill" style="width:' + tp + '%"></span></span>' +
            '<span class="quiz-breakdown-pct ' + (tp >= PASS_THRESHOLD ? "pw-str-strong" : "pw-str-weak") + '">' + tp + '%</span>' +
            '</div>';
        }
      }
    }

    if (els.summaryBreakdown) els.summaryBreakdown.innerHTML = breakdownHtml;

    if (els.pct) els.pct.textContent = "100%";
    if (els.progressFill) els.progressFill.style.width = "100%";
    if (els.progress) els.progress.textContent = "Complete";
  }

  // ===== Review missed =====
  if (els.reviewBtn) els.reviewBtn.addEventListener("click", function() {
    var missed = state.answers.filter(function(a) { return !a.correct; });
    if (!missed.length) {
      if (els.summaryScore) els.summaryScore.innerHTML += '<div class="quiz-no-missed">No missed questions \u2014 perfect score!</div>';
      return;
    }
    var missedQuestions = missed.map(function(a) { return state.questions[a.qIdx]; });
    initQuiz(missedQuestions);
  });

  // ===== Restart / New =====
  if (els.restartBtn) els.restartBtn.addEventListener("click", function() { initQuiz(); });
  if (els.newBtn) els.newBtn.addEventListener("click", function() { initQuiz(); });

  // ===== Tab switching =====
  var tabs = document.querySelectorAll(".quiz-tab");
  var panelQuiz = document.getElementById("panel-quiz");
  var panelGuide = document.getElementById("panel-guide");

  tabs.forEach(function(tab) {
    tab.addEventListener("click", function() {
      var target = this.getAttribute("data-tab");
      tabs.forEach(function(t) { t.classList.remove("active"); });
      this.classList.add("active");
      if (panelQuiz) panelQuiz.style.display = target === "quiz" ? "" : "none";
      if (panelGuide) panelGuide.style.display = target === "guide" ? "" : "none";
      if (target === "guide") renderGuide();
    });
  });

  // ===== Study Guide =====
  var guideNav = document.getElementById("guide-nav");
  var guideContent = document.getElementById("guide-content");
  var guideRendered = false;

  function renderGuide() {
    if (guideRendered || !GUIDE || !GUIDE.length) return;
    guideRendered = true;

    if (guideNav) {
      guideNav.innerHTML = GUIDE.map(function(d) {
        return '<button class="guide-nav-btn active" data-domain="' + d.domain + '">' +
               '<span class="guide-nav-num">D' + d.domain + '</span> ' + escHtml(d.title) + '</button>';
      }).join("");

      guideNav.querySelectorAll(".guide-nav-btn").forEach(function(btn) {
        btn.addEventListener("click", function() {
          btn.classList.toggle("active");
          var domId = btn.getAttribute("data-domain");
          if (guideContent) {
            var section = guideContent.querySelector('[data-guide-domain="' + domId + '"]');
            if (section) section.style.display = btn.classList.contains("active") ? "" : "none";
          }
        });
      });
    }

    if (guideContent) {
      guideContent.innerHTML = GUIDE.map(function(d) {
        var sectionsHtml = d.sections.map(function(s) {
          var pointsHtml = s.points.map(function(p) {
            var parts = p.split(/ — | \u2014 /);
            if (parts.length > 1) {
              return '<li><span class="guide-term">' + escHtml(parts[0]) + '</span> \u2014 ' + escHtml(parts.slice(1).join(" \u2014 ")) + '</li>';
            }
            return '<li>' + escHtml(p) + '</li>';
          }).join("");
          return '<div class="guide-section">' +
                 '<h4 class="guide-section-title">' + escHtml(s.heading) + '</h4>' +
                 '<ul class="guide-list">' + pointsHtml + '</ul>' +
                 '</div>';
        }).join("");

        return '<div class="guide-domain" data-guide-domain="' + d.domain + '">' +
               '<div class="guide-domain-header">' +
               '<span class="guide-domain-title">' + escHtml(d.title) + '</span>' +
               '<span class="guide-domain-weight">' + escHtml(d.weight) + '</span>' +
               '</div>' +
               sectionsHtml +
               '</div>';
      }).join("");
    }

    if (window.lucide) lucide.createIcons({ attrs: { "stroke-width": 1.5 } });
  }

  // ===== Dataset switch handler =====
  function switchDataset(datasetId) {
    loadDataset(datasetId, function(err, dataset) {
      if (err) {
        console.error("Assessment engine: " + err.message);
        return;
      }

      // Apply the loaded data
      applyManifest();
      rebuildControls();
      updateDatasetTitle(dataset.title);

      // Reset session stats on dataset switch
      state.sessionCorrect = 0;
      state.sessionIncorrect = 0;
      state.sessionAttempted = 0;
      updateSessionStats();

      // Start a fresh quiz
      initQuiz();
    });
  }

  // Dataset selector change event
  if (datasetSelect) {
    datasetSelect.addEventListener("change", function() {
      switchDataset(this.value);
    });
  }

  // ===== Initial load: load the first dataset =====
  if (DATASETS.length) {
    switchDataset(DATASETS[0].id);
  }
})();
