/**
 * Kodafriq Admin - Dynamic Lesson Type Fieldset Controller & Visual Question Builder
 */
(function () {
    'use strict';

    function initLessonAuthoring() {
        var lessonTypeSelect = document.getElementById('id_lesson_type');
        if (!lessonTypeSelect) return;

        // Locate Fieldsets
        var fieldsets = {
            id: findFieldset('kf-fs-identification', ['identification', 'sequencing']),
            content: findFieldset('kf-fs-content', ['reading content', 'rich media']),
            example: findFieldset('kf-fs-example', ['floating example', 'example box']),
            terms: findFieldset('kf-fs-terms', ['terminology', 'audio hint']),
            matching: findFieldset('kf-fs-matching', ['matching', 'drag & drop']),
            quiz: findFieldset('kf-fs-quiz', ['quiz', 'knowledge check'])
        };

        // Create or locate the mode banner
        var banner = document.getElementById('kfLessonTypeBanner');
        if (!banner) {
            banner = document.createElement('div');
            banner.id = 'kfLessonTypeBanner';
            banner.className = 'kf-type-banner';
            var parentRow = lessonTypeSelect.closest('.form-row') || lessonTypeSelect.parentElement;
            parentRow.appendChild(banner);
        }

        function findFieldset(className, titleKeywords) {
            var el = document.querySelector('fieldset.' + className);
            if (el) return el;

            var allFieldsets = document.querySelectorAll('fieldset');
            for (var i = 0; i < allFieldsets.length; i++) {
                var h2 = allFieldsets[i].querySelector('h2');
                if (h2) {
                    var title = h2.textContent.toLowerCase();
                    for (var k = 0; k < titleKeywords.length; k++) {
                        if (title.indexOf(titleKeywords[k]) !== -1) {
                            return allFieldsets[i];
                        }
                    }
                }
            }
            return null;
        }

        function setVisibility(el, visible) {
            if (!el) return;
            if (visible) {
                el.classList.remove('kf-fs-hidden');
                el.style.display = '';
            } else {
                el.classList.add('kf-fs-hidden');
                el.style.display = 'none';
            }
        }

        function updateLayout() {
            var type = lessonTypeSelect.value;

            // Defaults: hide all specialized sections first
            setVisibility(fieldsets.id, true); // Always visible
            setVisibility(fieldsets.content, false);
            setVisibility(fieldsets.example, false);
            setVisibility(fieldsets.terms, false);
            setVisibility(fieldsets.matching, false);
            setVisibility(fieldsets.quiz, false);

            if (type === 'QUIZ') {
                // Focused Quiz Mode: ONLY Quiz Questions
                setVisibility(fieldsets.quiz, true);
                banner.className = 'kf-type-banner kf-type-banner-quiz';
                banner.innerHTML = '🎯 <strong>Knowledge Check / Multiple Choice Quiz Mode:</strong> Form is streamlined exclusively for setting up multiple-choice quiz questions and answer choices. Rich reading content and terminology are hidden.';
            } else if (type === 'MATCHING_QUIZ') {
                // Matching Mode: ONLY Drag & Drop Matching
                setVisibility(fieldsets.matching, true);
                banner.className = 'kf-type-banner kf-type-banner-matching';
                banner.innerHTML = '🧩 <strong>Interactive Matching (Drag & Drop) Mode:</strong> Form is streamlined exclusively for setting up prompt-to-response matching questions. Reading content and other modules are hidden.';
            } else if (type === 'TERMINOLOGY') {
                // Terminology Mode: Terms + Example Callout Box
                setVisibility(fieldsets.terms, true);
                setVisibility(fieldsets.example, true);
                banner.className = 'kf-type-banner kf-type-banner-terms';
                banner.innerHTML = '📖 <strong>Terminology &amp; Clinical Example Mode:</strong> Form displays terminology definitions with audio hints and the CareerWize floating example box.';
            } else if (type === 'CONTENT') {
                // Reading & Learning: Full access
                setVisibility(fieldsets.content, true);
                setVisibility(fieldsets.example, true);
                setVisibility(fieldsets.terms, true);
                setVisibility(fieldsets.matching, true);
                setVisibility(fieldsets.quiz, true);
                banner.className = 'kf-type-banner kf-type-banner-comp';
                banner.innerHTML = '📝 <strong>Instructional Reading / Lesson Page:</strong> Rich reading content editor active with options to include supporting example boxes, terminology, drag &amp; drop, or quiz questions.';
            } else {
                // COMPREHENSIVE or any other: Show ALL
                setVisibility(fieldsets.content, true);
                setVisibility(fieldsets.example, true);
                setVisibility(fieldsets.terms, true);
                setVisibility(fieldsets.matching, true);
                setVisibility(fieldsets.quiz, true);
                banner.className = 'kf-type-banner kf-type-banner-comp';
                banner.innerHTML = '✨ <strong>Interactive Comprehensive Lesson:</strong> All components enabled (rich reading content, floating example callout, audio terminology, matching activity, and knowledge check quizzes).';
            }

            // Trigger window resize so TinyMCE recalculates height properly if shown
            setTimeout(function () {
                window.dispatchEvent(new Event('resize'));
            }, 100);
        }

        lessonTypeSelect.addEventListener('change', updateLayout);
        updateLayout();

        // Initialize Visual Builders
        initQuizBuilder();
        initMatchingBuilder();
        initTermsBuilder();
    }

    /**
     * 1. Interactive Visual Quiz Questions Builder
     */
    function initQuizBuilder() {
        var rawTextarea = document.getElementById('id_quiz_questions_data');
        if (!rawTextarea) return;

        // Container
        var container = document.createElement('div');
        container.className = 'kf-builder-container';
        rawTextarea.parentNode.insertBefore(container, rawTextarea);

        // Header
        var header = document.createElement('div');
        header.className = 'kf-builder-header';
        header.innerHTML = '<div class="kf-builder-title"><span>🎯</span> Knowledge Check Questions Builder</div>' +
            '<div class="kf-builder-tools">' +
            '<button type="button" class="kf-btn kf-btn-outline" id="kfToggleRawQuizBtn">Toggle Raw JSON</button>' +
            '<button type="button" class="kf-btn kf-btn-outline" id="kfQuickPasteQuizBtn">📋 Quick-Paste MCQ</button>' +
            '<button type="button" class="kf-btn kf-btn-primary" id="kfAddQuizQuestionBtn">+ Add Question</button>' +
            '</div>';
        container.appendChild(header);

        var listContainer = document.createElement('div');
        listContainer.id = 'kfQuizQuestionsList';
        container.appendChild(listContainer);

        // Hide raw textarea initially
        rawTextarea.style.display = 'none';

        var questions = [];
        try {
            var rawVal = rawTextarea.value.trim();
            if (rawVal) {
                questions = JSON.parse(rawVal);
                if (!Array.isArray(questions)) questions = [];
            }
        } catch (e) {
            questions = [];
        }

        function serialize() {
            rawTextarea.value = JSON.stringify(questions, null, 2);
        }

        function render() {
            listContainer.innerHTML = '';
            if (questions.length === 0) {
                listContainer.innerHTML = '<div style="text-align:center;padding:24px;color:#94a3b8;font-size:0.9rem;border:1px dashed rgba(255,255,255,0.15);border-radius:8px;">No quiz questions added yet. Click <strong>+ Add Question</strong> or <strong>Quick-Paste MCQ</strong> to create questions.</div>';
                return;
            }

            questions.forEach(function (q, qIdx) {
                var card = document.createElement('div');
                card.className = 'kf-q-card';

                var cardHeader = document.createElement('div');
                cardHeader.className = 'kf-q-header';
                cardHeader.innerHTML = '<span class="kf-q-badge">Question ' + (qIdx + 1) + '</span>' +
                    '<button type="button" class="kf-btn kf-btn-danger" data-del-q="' + qIdx + '">Delete Question</button>';
                card.appendChild(cardHeader);

                // Prompt Input
                var promptGroup = document.createElement('div');
                promptGroup.className = 'kf-form-group';
                promptGroup.innerHTML = '<label class="kf-form-label">Question Prompt</label>' +
                    '<textarea class="kf-textarea kf-q-prompt" rows="2" placeholder="e.g. Which of the following is part of the clinical side of healthcare?">' + escapeHtml(q.prompt || '') + '</textarea>';
                card.appendChild(promptGroup);

                // Options Box
                var choicesBox = document.createElement('div');
                choicesBox.className = 'kf-choices-box';
                choicesBox.innerHTML = '<div style="font-size:0.8rem;font-weight:700;color:#94a3b8;text-transform:uppercase;margin-bottom:8px;">Answer Choices (Select the correct answer)</div>';

                var optionsList = document.createElement('div');
                var options = Array.isArray(q.options) ? q.options : [];
                if (options.length === 0) {
                    options = [
                        { text: '', is_correct: true },
                        { text: '', is_correct: false },
                        { text: '', is_correct: false },
                        { text: '', is_correct: false }
                    ];
                    q.options = options;
                }

                options.forEach(function (opt, oIdx) {
                    var letter = String.fromCharCode(65 + oIdx);
                    var row = document.createElement('div');
                    row.className = 'kf-choice-row';

                    var radioWrap = document.createElement('label');
                    radioWrap.className = 'kf-choice-radio-wrap ' + (opt.is_correct ? 'is-correct' : '');
                    radioWrap.innerHTML = '<input type="radio" name="q_correct_' + qIdx + '" value="' + oIdx + '" ' + (opt.is_correct ? 'checked' : '') + ' style="margin-right:4px;"> ' + letter + (opt.is_correct ? ' ✓ Correct' : '');

                    var optInput = document.createElement('input');
                    optInput.type = 'text';
                    optInput.className = 'kf-input kf-choice-input';
                    optInput.placeholder = 'Choice ' + letter + ' text';
                    optInput.value = opt.text || '';

                    var delBtn = document.createElement('button');
                    delBtn.type = 'button';
                    delBtn.className = 'kf-btn kf-btn-danger kf-btn-icon';
                    delBtn.innerHTML = '&times;';
                    delBtn.title = 'Remove Choice';

                    // Radio change
                    radioWrap.querySelector('input').addEventListener('change', function () {
                        options.forEach(function (o, i) { o.is_correct = (i === oIdx); });
                        serialize();
                        render();
                    });

                    // Input change
                    optInput.addEventListener('input', function () {
                        opt.text = optInput.value;
                        serialize();
                    });

                    // Delete choice
                    delBtn.addEventListener('click', function () {
                        if (options.length <= 2) {
                            alert('A question must have at least 2 choices.');
                            return;
                        }
                        options.splice(oIdx, 1);
                        if (!options.some(function (o) { return o.is_correct; })) {
                            options[0].is_correct = true;
                        }
                        serialize();
                        render();
                    });

                    row.appendChild(radioWrap);
                    row.appendChild(optInput);
                    row.appendChild(delBtn);
                    optionsList.appendChild(row);
                });

                choicesBox.appendChild(optionsList);

                var addChoiceBtn = document.createElement('button');
                addChoiceBtn.type = 'button';
                addChoiceBtn.className = 'kf-btn kf-btn-outline';
                addChoiceBtn.style.marginTop = '6px';
                addChoiceBtn.textContent = '+ Add Choice (' + String.fromCharCode(65 + options.length) + ')';
                addChoiceBtn.addEventListener('click', function () {
                    options.push({ text: '', is_correct: false });
                    serialize();
                    render();
                });
                choicesBox.appendChild(addChoiceBtn);
                card.appendChild(choicesBox);

                // Explanation
                var expGroup = document.createElement('div');
                expGroup.className = 'kf-form-group';
                expGroup.innerHTML = '<label class="kf-form-label">Clinical Explanation / Guidelines Reference (Optional)</label>' +
                    '<input type="text" class="kf-input kf-q-exp" placeholder="e.g. Diagnosing and treating patients directly involves clinical care." value="' + escapeHtml(q.explanation || '') + '">';
                card.appendChild(expGroup);

                // Event Listeners for Prompt and Explanation
                promptGroup.querySelector('textarea').addEventListener('input', function () {
                    q.prompt = this.value;
                    serialize();
                });

                expGroup.querySelector('input').addEventListener('input', function () {
                    q.explanation = this.value;
                    serialize();
                });

                // Delete Question Listener
                cardHeader.querySelector('[data-del-q]').addEventListener('click', function () {
                    if (confirm('Delete Question ' + (qIdx + 1) + '?')) {
                        questions.splice(qIdx, 1);
                        serialize();
                        render();
                    }
                });

                listContainer.appendChild(card);
            });
        }

        render();

        // Add Question Button
        document.getElementById('kfAddQuizQuestionBtn').addEventListener('click', function () {
            questions.push({
                prompt: '',
                explanation: '',
                options: [
                    { text: '', is_correct: true },
                    { text: '', is_correct: false },
                    { text: '', is_correct: false },
                    { text: '', is_correct: false }
                ]
            });
            serialize();
            render();
            // Scroll into view
            listContainer.lastElementChild && listContainer.lastElementChild.scrollIntoView({ behavior: 'smooth' });
        });

        // Toggle Raw JSON
        var isRawVisible = false;
        document.getElementById('kfToggleRawQuizBtn').addEventListener('click', function () {
            isRawVisible = !isRawVisible;
            rawTextarea.style.display = isRawVisible ? 'block' : 'none';
            this.textContent = isRawVisible ? 'Hide Raw JSON' : 'Toggle Raw JSON';
            if (!isRawVisible) {
                try {
                    questions = JSON.parse(rawTextarea.value.trim() || '[]');
                    render();
                } catch (e) {
                    alert('Invalid JSON: ' + e.message);
                }
            }
        });

        // Quick Paste MCQ
        document.getElementById('kfQuickPasteQuizBtn').addEventListener('click', function () {
            showQuickPasteModal(function (parsedQuestion) {
                if (parsedQuestion) {
                    questions.push(parsedQuestion);
                    serialize();
                    render();
                }
            });
        });

        // Ensure serialization on form submit
        var form = rawTextarea.closest('form');
        if (form) {
            form.addEventListener('submit', function () {
                serialize();
            });
        }
    }

    /**
     * Modal for Quick-Pasting MCQ text
     */
    function showQuickPasteModal(onParsed) {
        var backdrop = document.createElement('div');
        backdrop.className = 'kf-modal-backdrop';

        backdrop.innerHTML = '<div class="kf-modal">' +
            '<div class="kf-modal-title">📋 Quick-Paste MCQ from Text</div>' +
            '<div class="kf-modal-desc">Paste a question and its choices below. Mark the correct answer with an asterisk <code>*</code> or letter (e.g. <code>*B. Diagnosing patients</code>).</div>' +
            '<textarea id="kfQuickPasteInput" class="kf-textarea" rows="8" placeholder="1. Which of the following is part of the clinical side of healthcare?&#10;A. Submitting insurance claims&#10;*B. Diagnosing and treating patients&#10;C. Recording payments&#10;D. Following up on unpaid claims"></textarea>' +
            '<div style="display:flex;justify-content:flex-end;gap:10px;margin-top:16px;">' +
            '<button type="button" class="kf-btn kf-btn-outline" id="kfModalCancelBtn">Cancel</button>' +
            '<button type="button" class="kf-btn kf-btn-primary" id="kfModalInsertBtn">Parse &amp; Insert</button>' +
            '</div>' +
            '</div>';

        document.body.appendChild(backdrop);

        backdrop.querySelector('#kfModalCancelBtn').addEventListener('click', function () {
            document.body.removeChild(backdrop);
        });

        backdrop.querySelector('#kfModalInsertBtn').addEventListener('click', function () {
            var text = backdrop.querySelector('#kfQuickPasteInput').value.trim();
            if (!text) {
                document.body.removeChild(backdrop);
                return;
            }

            var lines = text.split('\n').map(function (l) { return l.trim(); }).filter(Boolean);
            var prompt = '';
            var options = [];
            var optionRegex = /^(\*?[A-Za-z][\.\)])\s*(.+)$/;

            lines.forEach(function (line) {
                var match = line.match(optionRegex);
                if (match) {
                    var prefix = match[1];
                    var isCorrect = prefix.indexOf('*') !== -1;
                    var optText = match[2].trim();
                    options.push({ text: optText, is_correct: isCorrect });
                } else if (options.length === 0) {
                    prompt = (prompt ? prompt + ' ' : '') + line.replace(/^\d+[\.\)]\s*/, '');
                }
            });

            if (options.length > 0 && !options.some(function (o) { return o.is_correct; })) {
                options[0].is_correct = true; // Default to first if none marked
            }

            if (prompt || options.length > 0) {
                onParsed({
                    prompt: prompt || 'New Question',
                    explanation: '',
                    options: options.length > 0 ? options : [
                        { text: '', is_correct: true },
                        { text: '', is_correct: false }
                    ]
                });
            }

            document.body.removeChild(backdrop);
        });
    }

    /**
     * 2. Interactive Drag & Drop Matching Builder
     */
    function initMatchingBuilder() {
        var rawTextarea = document.getElementById('id_matching_pairs');
        if (!rawTextarea) return;

        var container = document.createElement('div');
        container.className = 'kf-builder-container';
        rawTextarea.parentNode.insertBefore(container, rawTextarea);

        var header = document.createElement('div');
        header.className = 'kf-builder-header';
        header.innerHTML = '<div class="kf-builder-title"><span>🧩</span> Interactive Matching Pairs Builder</div>' +
            '<div class="kf-builder-tools">' +
            '<button type="button" class="kf-btn kf-btn-outline" id="kfToggleRawMatchingBtn">Toggle Raw JSON</button>' +
            '<button type="button" class="kf-btn kf-btn-primary" id="kfAddMatchingPairBtn">+ Add Matching Pair</button>' +
            '</div>';
        container.appendChild(header);

        var listContainer = document.createElement('div');
        listContainer.id = 'kfMatchingList';
        container.appendChild(listContainer);

        rawTextarea.style.display = 'none';

        var pairs = [];
        try {
            var raw = rawTextarea.value.trim();
            if (raw) {
                pairs = JSON.parse(raw);
                if (!Array.isArray(pairs)) pairs = [];
            }
        } catch (e) {
            pairs = [];
        }

        function serialize() {
            rawTextarea.value = JSON.stringify(pairs, null, 2);
        }

        function render() {
            listContainer.innerHTML = '';
            if (pairs.length === 0) {
                listContainer.innerHTML = '<div style="text-align:center;padding:20px;color:#94a3b8;border:1px dashed rgba(255,255,255,0.15);border-radius:8px;">No matching pairs yet. Click <strong>+ Add Matching Pair</strong>.</div>';
                return;
            }

            pairs.forEach(function (pair, idx) {
                var row = document.createElement('div');
                row.className = 'kf-pair-row';

                var qInput = document.createElement('input');
                qInput.type = 'text';
                qInput.className = 'kf-input';
                qInput.placeholder = 'Prompt / Question (e.g. Benign lesion in bone)';
                qInput.value = pair.question || pair.prompt || '';

                var aInput = document.createElement('input');
                aInput.type = 'text';
                aInput.className = 'kf-input';
                aInput.placeholder = 'Matching Answer (e.g. Osteoid osteoma)';
                aInput.value = pair.answer || pair.response || '';

                var delBtn = document.createElement('button');
                delBtn.type = 'button';
                delBtn.className = 'kf-btn kf-btn-danger kf-btn-icon';
                delBtn.innerHTML = '&times;';
                delBtn.title = 'Remove Pair';

                qInput.addEventListener('input', function () {
                    pair.question = qInput.value;
                    serialize();
                });

                aInput.addEventListener('input', function () {
                    pair.answer = aInput.value;
                    serialize();
                });

                delBtn.addEventListener('click', function () {
                    pairs.splice(idx, 1);
                    serialize();
                    render();
                });

                row.appendChild(qInput);
                row.appendChild(aInput);
                row.appendChild(delBtn);
                listContainer.appendChild(row);
            });
        }

        render();

        document.getElementById('kfAddMatchingPairBtn').addEventListener('click', function () {
            pairs.push({ question: '', answer: '' });
            serialize();
            render();
        });

        var isRaw = false;
        document.getElementById('kfToggleRawMatchingBtn').addEventListener('click', function () {
            isRaw = !isRaw;
            rawTextarea.style.display = isRaw ? 'block' : 'none';
            this.textContent = isRaw ? 'Hide Raw JSON' : 'Toggle Raw JSON';
            if (!isRaw) {
                try {
                    pairs = JSON.parse(rawTextarea.value.trim() || '[]');
                    render();
                } catch (e) { }
            }
        });
    }

    /**
     * 3. Interactive Terminology Definitions Builder
     */
    function initTermsBuilder() {
        var rawTextarea = document.getElementById('id_terms_data');
        if (!rawTextarea) return;

        var container = document.createElement('div');
        container.className = 'kf-builder-container';
        rawTextarea.parentNode.insertBefore(container, rawTextarea);

        var header = document.createElement('div');
        header.className = 'kf-builder-header';
        header.innerHTML = '<div class="kf-builder-title"><span>📖</span> Terminology &amp; Audio Hint Builder</div>' +
            '<div class="kf-builder-tools">' +
            '<button type="button" class="kf-btn kf-btn-outline" id="kfToggleRawTermsBtn">Toggle Raw JSON</button>' +
            '<button type="button" class="kf-btn kf-btn-primary" id="kfAddTermBtn">+ Add Term</button>' +
            '</div>';
        container.appendChild(header);

        var listContainer = document.createElement('div');
        listContainer.id = 'kfTermsList';
        container.appendChild(listContainer);

        rawTextarea.style.display = 'none';

        var terms = [];
        try {
            var raw = rawTextarea.value.trim();
            if (raw) {
                terms = JSON.parse(raw);
                if (!Array.isArray(terms)) terms = [];
            }
        } catch (e) {
            terms = [];
        }

        function serialize() {
            rawTextarea.value = JSON.stringify(terms, null, 2);
        }

        function render() {
            listContainer.innerHTML = '';
            if (terms.length === 0) {
                listContainer.innerHTML = '<div style="text-align:center;padding:20px;color:#94a3b8;border:1px dashed rgba(255,255,255,0.15);border-radius:8px;">No terminology items yet. Click <strong>+ Add Term</strong>.</div>';
                return;
            }

            terms.forEach(function (term, idx) {
                var row = document.createElement('div');
                row.className = 'kf-term-row kf-term-grid';

                var termInput = document.createElement('input');
                termInput.type = 'text';
                termInput.className = 'kf-input';
                termInput.placeholder = 'Term (e.g. Marfan syndrome)';
                termInput.value = term.term || '';

                var defInput = document.createElement('textarea');
                defInput.className = 'kf-textarea';
                defInput.rows = 2;
                defInput.placeholder = 'Clinical Definition';
                defInput.value = term.definition || '';

                var audioInput = document.createElement('input');
                audioInput.type = 'text';
                audioInput.className = 'kf-input';
                audioInput.placeholder = 'Audio Hint (e.g. mar-fan)';
                audioInput.value = term.audio_hint || '';

                var delBtn = document.createElement('button');
                delBtn.type = 'button';
                delBtn.className = 'kf-btn kf-btn-danger kf-btn-icon';
                delBtn.innerHTML = '&times;';
                delBtn.title = 'Remove Term';

                termInput.addEventListener('input', function () {
                    term.term = termInput.value;
                    serialize();
                });

                defInput.addEventListener('input', function () {
                    term.definition = defInput.value;
                    serialize();
                });

                audioInput.addEventListener('input', function () {
                    term.audio_hint = audioInput.value;
                    serialize();
                });

                delBtn.addEventListener('click', function () {
                    terms.splice(idx, 1);
                    serialize();
                    render();
                });

                row.appendChild(termInput);
                row.appendChild(defInput);
                row.appendChild(audioInput);
                row.appendChild(delBtn);
                listContainer.appendChild(row);
            });
        }

        render();

        document.getElementById('kfAddTermBtn').addEventListener('click', function () {
            terms.push({ term: '', definition: '', audio_hint: '' });
            serialize();
            render();
        });

        var isRaw = false;
        document.getElementById('kfToggleRawTermsBtn').addEventListener('click', function () {
            isRaw = !isRaw;
            rawTextarea.style.display = isRaw ? 'block' : 'none';
            this.textContent = isRaw ? 'Hide Raw JSON' : 'Toggle Raw JSON';
            if (!isRaw) {
                try {
                    terms = JSON.parse(rawTextarea.value.trim() || '[]');
                    render();
                } catch (e) { }
            }
        });
    }

    function escapeHtml(str) {
        return (str || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
    }

    // Run on DOM ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initLessonAuthoring);
    } else {
        initLessonAuthoring();
    }
})();
